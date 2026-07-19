"""#1240 — D2 backfill: every historical segment → the store, idempotent + checked.

A two-device, two-day fixture whose rotation file spans midnight (rows route by the
PARSED timestamp), plus the resume path (--skip-existing) and the idempotence claim
(a re-run converges — identical partitions except the truthful ingest_ts).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tier_backfill import backfill, bucket_files

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts, dev, sensor, raw):
    return f"plants.soil,{ts},x,sess1,{dev},{sensor},{raw},OK,level=OK;gpio=35\n"


def _fixture(tmp_path: Path) -> list[str]:
    """dev1: one file straddling the 07-18/07-19 UTC midnight (rotation names lie);
    dev2: one clean 07-18 file. -> three (device, day) partitions."""
    a = tmp_path / "dev1_20260718_evening.csv"
    a.write_text(
        "# schema_version=4  fw=0.8.0  git=t  device_id=dev1  session_id=sess1\n"
        + _COLS
        + _row("2026-07-18T23:59:30.000000Z", "dev1", "s1", 1500)
        + _row("2026-07-19T00:00:00.500000Z", "dev1", "s1", 1502)  # next UTC day
        + _row("2026-07-19T00:00:30.500000Z", "dev1", "s1", 1504),
        encoding="utf-8",
    )
    b = tmp_path / "dev2_20260718_day.csv"
    b.write_text(
        "# schema_version=4  fw=0.8.0  git=t  device_id=dev2  session_id=sess9\n"
        + _COLS
        + _row("2026-07-18T12:00:00.000000Z", "dev2", "s1", 2000)
        + _row("2026-07-18T12:00:30.000000Z", "dev2", "s2", 2100),
        encoding="utf-8",
    )
    return [str(a), str(b)]


def test_buckets_route_by_parsed_day_across_rotation(tmp_path: Path) -> None:
    buckets = bucket_files(_fixture(tmp_path))
    keys = {(d, day.isoformat()) for d, day in buckets}
    assert keys == {
        ("dev1", "2026-07-18"),
        ("dev1", "2026-07-19"),  # the midnight-straddling rows split correctly
        ("dev2", "2026-07-18"),
    }
    assert len(buckets[("dev1", __import__("datetime").date(2026, 7, 19))]) == 2


def test_backfill_writes_all_partitions_with_fidelity(tmp_path: Path) -> None:
    out = tmp_path / "tier"
    stats = backfill(_fixture(tmp_path), out)
    assert stats["partitions"] == 3 and stats["rows"] == 5
    assert stats["failures"] == [] and stats["skipped"] == 0
    assert (out / "date=2026-07-19" / "device=dev1" / "part.parquet").is_file()


def test_rerun_is_idempotent_and_skip_existing_resumes(tmp_path: Path) -> None:
    import duckdb

    files = _fixture(tmp_path)
    out = tmp_path / "tier"
    backfill(files, out)
    p = out / "date=2026-07-18" / "device=dev2" / "part.parquet"
    con = duckdb.connect()

    def snapshot():
        # everything except the truthful ingest_ts must be identical across runs
        return con.execute(
            "SELECT timestamp_utc, device_id, sensor_id, raw_value, band,"
            " quality_flag, session_id, config_id, source_file, schema_version "
            f"FROM read_parquet('{p.as_posix()}') ORDER BY sensor_id, timestamp_utc"
        ).fetchall()

    first = snapshot()
    stats2 = backfill(files, out)  # full re-run: rebuilds, converges
    assert stats2["partitions"] == 3 and stats2["failures"] == []
    assert snapshot() == first  # idempotent (ingest_ts excluded — it truthfully moves)
    stats3 = backfill(files, out, skip_existing=True)  # the cheap resume
    con.close()
    assert stats3 == {"partitions": 0, "rows": 0, "skipped": 3, "failures": []}
