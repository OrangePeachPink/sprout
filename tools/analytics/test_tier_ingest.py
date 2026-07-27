"""#1241 D3 — live ingest + compaction: store-derived watermark, append visibility,
gate-checked compaction that heals duplicates, shrink recovery, freshness."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb

from tools.analytics.tier_ingest import compact, freshness, ingest_once

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_HDR = "# schema_version=4  fw=0.8.0  git=t  device_id=dev1  session_id=sess1\n"


def _row(ts, dev, sensor, raw):
    return f"plants.soil,{ts},x,sess1,{dev},{sensor},{raw},OK,level=OK;gpio=35\n"


def _count(root: Path) -> int:
    con = duckdb.connect()
    n = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{root.as_posix()}/*/*/*.parquet')"
    ).fetchone()[0]
    con.close()
    return n


def _mk_csv(tmp_path: Path, rows: list[str]) -> Path:
    f = tmp_path / "dev1_20260718_a.csv"
    f.write_text(_HDR + _COLS + "".join(rows), encoding="utf-8")
    return f


R1 = _row("2026-07-18T10:00:00.000000Z", "dev1", "s1", 1500)
R2 = _row("2026-07-18T10:00:30.000000Z", "dev1", "s1", 1502)
R3 = _row("2026-07-18T10:01:00.000000Z", "dev1", "s2", 2000)
R4 = _row("2026-07-19T00:00:10.000000Z", "dev1", "s1", 1504)  # next UTC day


def test_ingest_grows_with_the_file_and_readers_see_appends(tmp_path: Path) -> None:
    root = tmp_path / "tier"
    f = _mk_csv(tmp_path, [R1, R2])
    s = ingest_once([str(f)], root)
    assert (s["appended_rows"], s["append_files"], s["failures"]) == (2, 1, [])
    assert _count(root) == 2  # visible via the §8 *.parquet reader glob
    assert ingest_once([str(f)], root)["appended_rows"] == 0  # idempotent cycle
    # the file grows: +1 same-day row and +1 next-UTC-day row -> two partitions
    f.write_text(_HDR + _COLS + R1 + R2 + R3 + R4, encoding="utf-8")
    s = ingest_once([str(f)], root)
    assert (s["appended_rows"], s["append_files"]) == (2, 2)
    assert _count(root) == 4
    assert (root / "date=2026-07-19" / "device=dev1").is_dir()  # parsed-ts routing


def test_compact_rebuilds_whole_and_heals_duplicate_appends(tmp_path: Path) -> None:
    root = tmp_path / "tier"
    f = _mk_csv(tmp_path, [R1, R2, R3])
    ingest_once([str(f)], root)
    part_dir = root / "date=2026-07-18" / "device=dev1"
    appends = sorted(part_dir.glob("append-*.parquet"))
    assert len(appends) == 1 and not (part_dir / "part.parquet").is_file()
    # simulate an ingest crash: the same append landed twice -> duplicates
    (part_dir / "append-19990101T000000000000.parquet").write_bytes(
        appends[0].read_bytes()
    )
    assert _count(root) == 6  # honest: readers see the duplicates until compaction
    s = compact([str(f)], root, include_today=True)
    assert s["compacted"] == ["2026-07-18 dev1"] and s["failures"] == []
    assert (part_dir / "part.parquet").is_file()
    assert list(part_dir.glob("append-*.parquet")) == []
    assert _count(root) == 3  # healed back to source truth
    assert compact([str(f)], root, include_today=True)["compacted"] == []  # no-op


def test_closed_day_default_skips_the_open_day(tmp_path: Path) -> None:
    root = tmp_path / "tier"
    today = datetime.now(timezone.utc).date().isoformat()
    live = _row(f"{today}T00:00:05.000000Z", "dev1", "s1", 1600)
    f = _mk_csv(tmp_path, [live])
    ingest_once([str(f)], root)
    s = compact([str(f)], root)  # default: closed days only
    assert s["compacted"] == [] and s["skipped_open"] == 1
    assert list(root.glob(f"date={today}/device=dev1/append-*.parquet"))


def test_shrunken_source_heals_by_whole_rebuild(tmp_path: Path) -> None:
    root = tmp_path / "tier"
    f = _mk_csv(tmp_path, [R1, R2, R3])
    ingest_once([str(f)], root)
    assert _count(root) == 3
    f.write_text(_HDR + _COLS + R1 + R2, encoding="utf-8")  # the segment SHRANK
    s = ingest_once([str(f)], root)
    assert s["rebuilt"] == ["2026-07-18 dev1"] and s["failures"] == []
    part_dir = root / "date=2026-07-18" / "device=dev1"
    assert (part_dir / "part.parquet").is_file()
    assert list(part_dir.glob("append-*.parquet")) == []
    assert _count(root) == 2  # exactly the new source truth, no stale rows


def test_freshness_reports_pending_rows_and_append_debt(tmp_path: Path) -> None:
    root = tmp_path / "tier"
    f = _mk_csv(tmp_path, [R1, R2])
    ingest_once([str(f)], root)
    now = datetime(2026, 7, 18, 10, 2, 0, tzinfo=timezone.utc)
    fr = freshness([str(f)], root, now=now)
    assert fr["pending_rows"] == 0 and fr["append_files"] == 1
    f.write_text(_HDR + _COLS + R1 + R2 + R3, encoding="utf-8")  # a row not ingested
    fr = freshness([str(f)], root, now=now)
    assert fr["pending_by_file"] == {f.name: 1}
    assert fr["oldest_pending_s"] == 60.0  # R3 @10:01:00 vs now @10:02:00
