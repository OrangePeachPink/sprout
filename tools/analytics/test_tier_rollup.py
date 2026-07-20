"""#1242 D4 — the rollup tiers: exact-µs bucket floors, config_id never blended,
quality carried never averaged, events at exact timestamps, labeled reads."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tier_rollup import (
    build_events,
    build_rollups,
    pick_tier,
    read_envelope,
    read_events,
    trajectory_series,
)


def _fixture_raw(root: Path, rows: list[tuple]) -> None:
    """(device, sensor, ts, raw, band, flag, session, config) into the raw layout."""
    con = duckdb.connect()
    by_part: dict = {}
    for dev, sensor, ts, raw, band, flag, sess, cfg in rows:
        day = ts.split(" ")[0]
        by_part.setdefault((day, dev), []).append(
            (ts, dev, sensor, raw, band, flag, sess, cfg)
        )
    for (day, dev), part in by_part.items():
        d = root / f"date={day}" / f"device={dev}"
        d.mkdir(parents=True)
        con.execute(
            "CREATE OR REPLACE TABLE t (timestamp_utc TIMESTAMP, device_id VARCHAR,"
            " sensor_id VARCHAR, raw_value INTEGER, band VARCHAR,"
            " quality_flag VARCHAR, session_id VARCHAR, config_id VARCHAR)"
        )
        con.executemany("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?, ?)", part)
        con.execute(f"COPY t TO '{(d / 'part.parquet').as_posix()}' (FORMAT PARQUET)")


def _r(ts, raw, band="Moist", flag="OK", sess="s-1", cfg="cfg-a", dev="devA", sen="s1"):
    return (dev, sen, ts, raw, band, flag, sess, cfg)


def test_bucket_floor_envelope_and_labeling(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _fixture_raw(
        raw,
        [
            _r("2026-07-01 00:00:00.000000", 1000),
            _r("2026-07-01 00:00:30.000000", 1010),
            _r("2026-07-01 00:00:59.999999", 1004),  # still the :00 minute bucket
            _r("2026-07-01 00:01:00.000000", 1100),  # exact floor -> next bucket
        ],
    )
    out = tmp_path / "rollup"
    stats = build_rollups(raw, out)
    assert stats["t1"] == 2 and stats["t3"] == 1
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 2, tzinfo=timezone.utc)
    b0, b1 = read_envelope("devA", "s1", t0, t1, tier="t1", root=out)
    assert (b0["n"], b0["min"], b0["max"], b0["spread"]) == (3, 1000, 1010, 10)
    assert b0["mean"] == (1000 + 1010 + 1004) / 3
    assert (b1["n"], b1["min"]) == (1, 1100)
    assert b0["tier"] == "t1" and b0["bucket_seconds"] == 60  # labeled, never raw
    assert b1["bucket_us"] - b0["bucket_us"] == 60_000_000  # exact integer µs floors


def test_config_id_is_carried_and_never_blended(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _fixture_raw(
        raw,
        [
            _r("2026-07-01 00:00:00", 1000, cfg="cfg-a"),
            _r("2026-07-01 00:00:30", 2000, cfg="cfg-b"),  # same minute, new config
        ],
    )
    out = tmp_path / "rollup"
    build_rollups(raw, out)
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 2, tzinfo=timezone.utc)
    buckets = read_envelope("devA", "s1", t0, t1, tier="t1", root=out)
    assert len(buckets) == 2  # split by config_id inside one time bucket
    assert {b["config_id"] for b in buckets} == {"cfg-a", "cfg-b"}
    assert all(b["n"] == 1 for b in buckets)  # a gain shift never blends raws


def test_quality_is_carried_never_averaged_away(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _fixture_raw(
        raw,
        [
            _r("2026-07-01 00:00:00", 1000),
            _r("2026-07-01 00:00:10", 1002, flag="SUSPECT"),
            _r("2026-07-01 00:00:20", 1004, flag="SENSOR_FAULT"),
            _r("2026-07-01 00:00:30", 1006),
        ],
    )
    out = tmp_path / "rollup"
    build_rollups(raw, out)
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 2, tzinfo=timezone.utc)
    (b,) = read_envelope("devA", "s1", t0, t1, tier="t1", root=out)
    assert b["n"] == 4 and b["n_flagged"] == 2
    assert b["flags"] == "SENSOR_FAULT+SUSPECT"  # the tokens ride the bucket


def test_events_survive_at_exact_timestamps(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _fixture_raw(
        raw,
        [
            _r("2026-07-01 00:00:00.123456", 1000, band="Moist"),
            _r("2026-07-01 00:00:30.654321", 1300, band="Drying"),  # band transition
            _r("2026-07-01 00:01:00", 1302, band="Drying", flag="rate_spike"),
            _r("2026-07-01 00:01:30", 1304, band="Drying", flag="rate_spike"),
            _r("2026-07-01 00:02:00", 1306, band="Drying", sess="s-2"),
            _r("2026-07-01 00:02:30", 1308, band="Drying", sess="s-2", cfg="cfg-b"),
        ],
    )
    n = build_events(raw, tmp_path / "events")
    assert n == 4
    ev = read_events(root=tmp_path / "events")
    kinds = [(e["kind"], e["detail"]) for e in ev]
    assert ("band", "Moist->Drying") in kinds
    assert kinds.count(("quality", "rate_spike")) == 1  # run START only
    assert ("session", "s-1->s-2") in kinds
    assert ("config", "cfg-a->cfg-b") in kinds
    band_ev = next(e for e in ev if e["kind"] == "band")
    assert band_ev["timestamp_utc"].microsecond == 654321  # exact, never bucketed


def test_rebuild_is_idempotent_and_pick_tier_maps_ranges(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    _fixture_raw(
        raw, [_r("2026-07-01 00:00:00", 1000), _r("2026-07-01 12:00:00", 1500)]
    )
    out = tmp_path / "rollup"
    first = build_rollups(raw, out)
    second = build_rollups(raw, out)  # full rebuild converges (delete-and-rebuild)
    assert first == second
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 2, tzinfo=timezone.utc)
    assert [
        b["n"] for b in read_envelope("devA", "s1", t0, t1, tier="t3", root=out)
    ] == [1, 1]
    assert pick_tier(24) == "raw"  # #827's cache path
    assert pick_tier(7 * 24) == "t1"
    assert pick_tier(14 * 24) == "t2"
    assert pick_tier(365 * 24) == "t3"


def test_trajectory_carries_the_envelope_and_never_smooths(tmp_path: Path) -> None:
    # #978: a long-range read must keep min/max + n per point — a mean-only line
    # would erase the spike the operator is looking for.
    raw = tmp_path / "raw"
    rows = []
    for i in range(120):  # 2 h at 1-min spacing -> hourly buckets
        v = 1500 + i
        if i == 30:
            v = 2600  # a spike inside bucket 0
        rows.append(_r(f"2026-07-01 {i // 60:02d}:{i % 60:02d}:00", v))
    _fixture_raw(raw, rows)
    out = tmp_path / "rollup"
    build_rollups(raw, out)
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 7, 2, tzinfo=timezone.utc)
    tj = trajectory_series("devA", "s1", t0, t1, tier="t3", root=out)
    assert tj["tier"] == "t3" and tj["bucket_seconds"] == 3600
    assert tj["n_readings"] == 120  # every reading accounted for
    assert tj["n_points"] == 2  # ...in 2 points: sub-linear by construction
    first = tj["points"][0]
    assert first["max"] == 2600  # the spike SURVIVES the rollup
    assert first["min"] == 1500 and first["n"] == 60
    assert first["mean"] < first["max"]  # a mean alone would have hidden it


def test_trajectory_breaks_across_a_gap_never_draws_through_it(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    early = [_r(f"2026-07-01 0{h}:00:00", 1500 + h) for h in range(3)]
    late = [_r(f"2026-07-01 1{h}:00:00", 1600 + h) for h in range(3)]  # 7 h outage
    _fixture_raw(raw, early + late)
    out = tmp_path / "rollup"
    build_rollups(raw, out)
    tj = trajectory_series(
        "devA",
        "s1",
        datetime(2026, 7, 1, tzinfo=timezone.utc),
        datetime(2026, 7, 2, tzinfo=timezone.utc),
        tier="t3",
        root=out,
    )
    breaks = [p for p in tj["points"] if p["mean"] is None]
    assert len(breaks) == 1  # the outage is surfaced as an explicit break
    xs = [p["x"] for p in tj["points"]]
    assert xs == sorted(xs)  # the break sits between the two runs, in order


def test_trajectory_refuses_the_raw_range(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError):
        trajectory_series(
            "devA",
            "s1",
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 1, 6, tzinfo=timezone.utc),  # 6 h -> "raw"
            root=tmp_path,
        )
