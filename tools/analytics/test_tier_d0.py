"""#1238 — the D0 tracer: CSV device-day → Parquet → DuckDB, fidelity-asserted.

Synthetic device-day with the tricky shapes the dwell rule must survive: a band change,
a >cap logging gap, a NO_SIGNAL row mid-sequence, an unmapped sensor, another device,
an off-day row. The DuckDB answer must equal the pure-Python CSV-truth calc EXACTLY
(exact integer microseconds — same rule, two independent paths, one number).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.parse_v1 import Reading
from tools.analytics.tier_d0 import (
    _COLUMNS,
    CAP_US,
    build_parquet,
    day_rows,
    hours_per_band_duckdb,
    hours_per_band_truth,
)

_DAY = date(2026, 7, 18)
_T0 = datetime(2026, 7, 18, 12, 0, 0, tzinfo=timezone.utc)


def _r(sec, level, raw, sid="s1", dev="dev1", quality="OK", extra=None, day_off=0):
    payload = {"level": level, **(extra or {})}
    return Reading(
        "plants.soil",
        _T0 + timedelta(seconds=sec, days=day_off),
        None,
        None,
        "sess",
        dev,
        "0.8.0",
        "x",
        None,
        "UMLIFE_v2_TLC555",
        sid,
        "",
        sid,
        raw,
        None,
        "",
        quality,
        payload,
    )


def _fixture():
    return [
        # s1 (mapped -> p01): OK, OK, band change, a >cap gap, NO_SIGNAL, OK-last
        _r(0, "OK", 1500, extra={"config_id": "abcd1234"}),
        _r(30, "OK", 1510),
        _r(60, "needs water", 1900),
        _r(660, "needs water", 1910),  # 10-min gap before this -> capped at CAP_US
        _r(690, "needs water", 1905, quality="NO_SIGNAL"),  # dwell never tallied
        _r(720, "OK", 1520),  # the day's last s1 reading -> owns 0
        # s2 (unmapped): band-bearing but no plant -> never in the answer
        _r(0, "OK", 2000, sid="s2"),
        _r(30, "OK", 2005, sid="s2"),
        # another device entirely -> excluded by day_rows(device)
        _r(0, "OK", 1000, dev="dev2"),
        # right device, wrong UTC day -> excluded by day_rows(date)
        _r(0, "OK", 1400, day_off=1),
    ]


_MAP = {("dev1", "s1"): "p01"}

# hand-computed truth for s1/p01 (exact int us):
#   OK: 30 s (t0) + 30 s (t1) + 0 (last)           = 60_000_000
#   needs water: CAP_US (capped 10-min gap) + 30 s = 150_000_000; NO_SIGNAL dropped
_EXPECT = {
    ("p01", "OK"): 60_000_000,
    ("p01", "needs water"): CAP_US + 30_000_000,
}


def test_day_rows_filters_device_date_and_type() -> None:
    rows = day_rows(_fixture(), "dev1", _DAY)
    assert len(rows) == 8  # 6 s1 + 2 s2; dev2 + the off-day row excluded
    assert {r.device_id for r in rows} == {"dev1"}
    assert {r.timestamp_utc.date() for r in rows} == {_DAY}


def test_parquet_carries_the_candidate_layout_and_fidelity_trio(tmp_path: Path) -> None:
    import duckdb

    rows = day_rows(_fixture(), "dev1", _DAY)
    parquet, stats = build_parquet(rows, "dev1", _DAY, tmp_path)
    # the candidate layout: hive-style date= / device= partitions, one file
    assert parquet == tmp_path / "date=2026-07-18" / "device=dev1" / "part.parquet"
    # fidelity trio, computed FROM the parquet: rows, raw checksum, sensor count
    assert stats["rows"] == len(rows)
    assert stats["raw_sum"] == sum(r.raw_value for r in rows)
    assert stats["sensors"] == 2
    # the FILE carries wire-truth columns only — incl. config_id (ADR-0025), never
    # the legacy value % — while the PATH carries the partition keys: a default
    # hive read surfaces date/device as queryable dimensions on top.
    con = duckdb.connect()
    cols = [
        d[0]
        for d in con.execute(
            "DESCRIBE SELECT * FROM read_parquet("
            f"'{parquet.as_posix()}', hive_partitioning = false)"
        ).fetchall()
    ]
    assert tuple(cols) == _COLUMNS
    hive_cols = [
        d[0]
        for d in con.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet.as_posix()}')"
        ).fetchall()
    ]
    assert set(hive_cols) == set(_COLUMNS) | {"date", "device"}
    got = con.execute(
        "SELECT config_id FROM read_parquet(?) WHERE config_id IS NOT NULL",
        [parquet.as_posix()],
    ).fetchall()
    con.close()
    assert got == [("abcd1234",)]  # the fingerprint rides as a column, never blended


def test_duckdb_answer_equals_the_csv_truth_exactly(tmp_path: Path) -> None:
    rows = day_rows(_fixture(), "dev1", _DAY)
    parquet, _ = build_parquet(rows, "dev1", _DAY, tmp_path)
    sql = hours_per_band_duckdb(parquet, _MAP)
    truth = hours_per_band_truth(rows, _MAP)
    assert sql == truth  # two independent paths, one exact integer answer
    assert sql == _EXPECT  # and it is the hand-computed number


def test_the_dwell_rule_caps_gaps_and_drops_no_signal() -> None:
    truth = hours_per_band_truth(day_rows(_fixture(), "dev1", _DAY), _MAP)
    # the 10-minute gap contributed CAP_US, not 600 s
    assert truth[("p01", "needs water")] == CAP_US + 30_000_000
    # the NO_SIGNAL row's dwell is gone entirely (never attributed to any band)
    assert sum(truth.values()) == 60_000_000 + CAP_US + 30_000_000
    # the unmapped sensor never appears
    assert all(plant == "p01" for plant, _ in truth)
