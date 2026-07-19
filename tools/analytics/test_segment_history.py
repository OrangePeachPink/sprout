"""#1246 C2 — full-history classification over the tier: exact-µs metrics, the
unmapped bucket, first-class sensorless absence, and the fleet pass wiring."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from segment_history import full_history, summarize
from tier_store import CAP_US

T0 = "2026-07-01 00:00:00"


def _fixture_tier(root: Path, rows: list[tuple]) -> None:
    """Write (date_dir, device_id, sensor_id, ts, raw, flag) rows into the hive
    layout the store contract fixes: date=<UTC>/device=<id>/part.parquet."""
    con = duckdb.connect()
    by_part: dict[tuple[str, str], list[tuple]] = {}
    for date_dir, dev, sensor, ts, raw, flag in rows:
        by_part.setdefault((date_dir, dev), []).append((dev, sensor, ts, raw, flag))
    for (date_dir, dev), part in by_part.items():
        d = root / f"date={date_dir}" / f"device={dev}"
        d.mkdir(parents=True)
        con.execute(
            "CREATE OR REPLACE TABLE t (device_id VARCHAR, sensor_id VARCHAR,"
            " timestamp_utc TIMESTAMP, raw_value DOUBLE, quality_flag VARCHAR)"
        )
        con.executemany("INSERT INTO t VALUES (?, ?, ?, ?, ?)", part)
        con.execute(f"COPY t TO '{(d / 'part.parquet').as_posix()}' (FORMAT PARQUET)")


def _registry() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32dev",
                label="A",
                channels={"s1": {"plant_id": "pA", "plant_name": "a"}, "s2": {}},
            ),
            Device(
                device_id="devB",
                board="esp32c5",
                label="B",
                channels={"s1": {"plant_id": "pB", "plant_name": "b"}},
            ),
        ],
        sensorless=[{"plant_id": "pS", "plant_name": "windowsill cactus"}],
    )


def test_metrics_exact_us_cap_flagged_unmapped_sensorless(tmp_path: Path) -> None:
    # devA/s1 → pA: 5 steady @30 s, a 999,200 µs sub-ms gap, a 1 h outage (caps at
    # CAP_US), a flagged row whose 30 s forward gap must land in `flagged`.
    rows = [
        ("2026-07-01", "devA", "s1", "2026-07-01 00:00:00", 2000.0, "OK"),
        ("2026-07-01", "devA", "s1", "2026-07-01 00:00:30", 2001.0, "OK"),
        ("2026-07-01", "devA", "s1", "2026-07-01 00:01:00", 2002.0, "OK"),
        ("2026-07-01", "devA", "s1", "2026-07-01 00:01:30", 2003.0, "OK"),
        ("2026-07-01", "devA", "s1", "2026-07-01 00:02:00", 2004.0, "OK"),
        ("2026-07-01", "devA", "s1", "2026-07-01 00:02:00.999200", 2004.0, "OK"),
        ("2026-07-01", "devA", "s1", "2026-07-01 01:02:00.999200", 2010.0, "OK"),
        (
            "2026-07-01",
            "devA",
            "s1",
            "2026-07-01 01:02:30.999200",
            2011.0,
            "rate_spike",
        ),
        ("2026-07-01", "devA", "s1", "2026-07-01 01:03:00.999200", 2012.0, "OK"),
        # devA/s2 carries no plant_id → the unmapped bucket, never dropped
        ("2026-07-01", "devA", "s2", "2026-07-01 00:00:00", 1500.0, "OK"),
        ("2026-07-01", "devA", "s2", "2026-07-01 00:00:30", 1501.0, "OK"),
    ]
    _fixture_tier(tmp_path, rows)
    report = full_history(tmp_path, registry=_registry())
    m = report["plants"]["pA"]
    steady_us = 4 * 30_000_000 + 999_200 + CAP_US + 30_000_000
    flagged_us = 30_000_000
    assert m["n_obs"] == 9
    assert m["kind_us"]["steady-drying"] == steady_us  # exact µs — no ms-floor
    assert m["kind_us"]["flagged"] == flagged_us
    assert m["observed_us"] == steady_us + flagged_us
    assert m["span_us"] == 3_780_999_200
    assert m["pct_valid"] == steady_us / (steady_us + flagged_us)
    assert m["segment_counts"] == {
        "steady-drying": 2,
        "watering-transient": 0,
        "rebound": 0,
        "flagged": 1,
    }
    assert report["unmapped"] == {"devA/s2": 2}
    s = report["plants"]["pS"]  # sensorless: first-class absence, honest zeros
    assert s["source"] == "sensorless" and s["n_obs"] == 0 and s["coverage"] is None


def test_fleet_pass_clusters_soil_onsets_and_glugs(tmp_path: Path) -> None:
    def series(date_dir, dev, hh):  # pre-drop pair, -300 drop, rebound tail
        base = [
            (
                f"2026-07-0{date_dir}",
                dev,
                "s1",
                f"2026-07-0{date_dir} {hh}:{mm:02d}:00",
                v,
                "OK",
            )
            for mm, v in [
                (0, 2000.0),
                (1, 2000.0),
                (2, 1700.0),
                (12, 1740.0),
                (22, 1780.0),
                (32, 1800.0),
                (42, 1801.0),
                (52, 1802.0),
            ]
        ]
        return base

    _fixture_tier(tmp_path, series(1, "devA", "01") + series(2, "devB", "01"))
    # devB rides its own partition day; its onset 01:01 on 07-02 is ~24 h from devA's
    # — two passes without a journal. A glug 5 min after devA's onset joins ITS pass.
    journal = tmp_path / "journal.jsonl"
    journal.write_text(
        '{"plant_id": "pB", "source": "manual", "ts": "2026-07-01T01:06:00Z"}\n'
        "not-json — skipped honestly\n",
        encoding="utf-8",
    )
    report = full_history(tmp_path, registry=_registry(), journal=journal)
    for pid in ("pA", "pB"):
        c = report["plants"][pid]["segment_counts"]
        assert c["watering-transient"] == 1 and c["rebound"] >= 1
    assert len(report["passes"]) == 2
    first, second = report["passes"]
    assert first["sources"] == ["glug", "soil"] and first["plants"] == ["pA", "pB"]
    assert second["sources"] == ["soil"] and second["plants"] == ["pB"]
    assert first["n_events"] == 2 and second["n_events"] == 1


def test_summarize_empty_is_absent_safe() -> None:
    m = summarize([])
    assert m["n_obs"] == 0 and m["pct_valid"] is None and m["coverage"] is None
