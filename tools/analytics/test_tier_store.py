"""#1239 — the D1 tier store against its written contract (docs/TIER_STORE_CONTRACT.md).

The two D1 folds, locked: the PROVENANCE trio rides every row (source_file basename ·
one ingest_ts per batch · schema_version, NULL-honest), and the §4 µs INVARIANT holds
on a deliberately sub-millisecond fixture — the exact shape where ms-floored absolute
timestamps diverge from float-seconds truncation (D0's real-data catch, now a
permanent regression net).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tier_store import (
    COLUMNS,
    build_partition,
    hours_per_band_duckdb,
    hours_per_band_truth,
    tagged_day_rows,
)

_DAY = date(2026, 7, 18)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts: str, sensor: str, raw: int, level: str = "OK", q: str = "OK") -> str:
    return f"plants.soil,{ts},x,sess1,dev1,{sensor},{raw},{q},level={level};gpio=35\n"


def _files(tmp_path: Path) -> list[str]:
    """Two source files (per-row lineage must distinguish them). File A is schema v4;
    file B carries no schema line (schema_version NULL-honest). The s1 timestamps are
    SUB-MILLISECOND on purpose: gap a->b = 999_200 µs exactly — ms-floored absolute
    epochs would call it 1_000_000 and float-seconds truncation 999_000."""
    a = tmp_path / "dev1_20260718_a.csv"
    a.write_text(
        "# schema_version=4  fw=0.8.0  git=t  device_id=dev1  session_id=sess1\n"
        + _COLS
        + _row("2026-07-18T12:00:00.000900Z", "s1", 1500)
        + _row("2026-07-18T12:00:01.000100Z", "s1", 1510)  # +999_200 µs
        + _row("2026-07-18T12:00:31.000100Z", "s1", 1905, level="needs water")
        + _row("2026-07-18T12:20:31.000100Z", "s1", 1910, level="needs water"),  # >cap
        encoding="utf-8",
    )
    b = tmp_path / "dev1_20260718_b.csv"
    b.write_text(
        "# fw=0.8.0  git=t  device_id=dev1  session_id=sess2\n"
        + _COLS
        + _row("2026-07-18T13:00:00.000000Z", "s2", 2000)
        + _row("2026-07-18T13:00:30.000000Z", "s2", 2005, q="NO_SIGNAL")
        + _row("2026-07-19T01:00:00.000000Z", "s2", 2050),  # next UTC day — excluded
        encoding="utf-8",
    )
    return [str(a), str(b)]


# #1331: identity is resolved on INTERVALS now — (device, port, plant, start, end).
# Null bounds = grandfathered start / still-open end, which is this fixture's case.
_MAP = [
    ("dev1", "s1", "p01", None, None),
    ("dev1", "s2", "p02", None, None),
]


def test_day_slice_is_by_parsed_timestamp_with_lineage(tmp_path: Path) -> None:
    tagged = tagged_day_rows(_files(tmp_path), "dev1", _DAY)
    assert len(tagged) == 6  # the 07-19 row excluded by the PARSED date
    srcs = {src for _r, src in tagged}
    assert srcs == {"dev1_20260718_a.csv", "dev1_20260718_b.csv"}


def test_contract_columns_and_the_provenance_trio(tmp_path: Path) -> None:
    import duckdb

    tagged = tagged_day_rows(_files(tmp_path), "dev1", _DAY)
    parquet, stats = build_partition(tagged, "dev1", _DAY, tmp_path / "tier")
    assert parquet == (
        tmp_path / "tier" / "date=2026-07-18" / "device=dev1" / "part.parquet"
    )
    assert stats["rows"] == 6 and stats["sensors"] == 2  # the §6 fidelity gate
    con = duckdb.connect()
    cols = [
        d[0]
        for d in con.execute(
            "DESCRIBE SELECT * FROM read_parquet("
            f"'{parquet.as_posix()}', hive_partitioning = false)"
        ).fetchall()
    ]
    assert tuple(cols) == COLUMNS  # the contract's §3 schema, exactly
    # source_file: each row carries ITS OWN origin basename
    per_src = dict(
        con.execute(
            "SELECT source_file, COUNT(*) FROM read_parquet(?) GROUP BY source_file",
            [parquet.as_posix()],
        ).fetchall()
    )
    assert per_src == {"dev1_20260718_a.csv": 4, "dev1_20260718_b.csv": 2}
    # ingest_ts: ONE instant per build batch; schema_version: v4 rows 4, NULL-honest 2
    n_ingest, v4, nulls = con.execute(
        "SELECT COUNT(DISTINCT ingest_ts),"
        " COUNT(*) FILTER (schema_version = 4),"
        " COUNT(*) FILTER (schema_version IS NULL) "
        "FROM read_parquet(?)",
        [parquet.as_posix()],
    ).fetchone()
    con.close()
    assert (n_ingest, v4, nulls) == (1, 4, 2)


def test_the_us_invariant_on_the_sub_ms_fixture(tmp_path: Path) -> None:
    # §4 doctrine: the store answer equals the pure recompute EXACTLY on timestamps
    # where ms-floored epochs (1_000_000) and float-seconds truncation (999_000) both
    # get it wrong. The true first-gap dwell is 999_200 µs.
    tagged = tagged_day_rows(_files(tmp_path), "dev1", _DAY)
    parquet, _ = build_partition(tagged, "dev1", _DAY, tmp_path / "tier")
    sql = hours_per_band_duckdb(parquet, _MAP)
    truth = hours_per_band_truth(tagged, _MAP)
    assert sql == truth  # equal BY CONSTRUCTION — the invariant
    # s1/p01: OK = 999_200 (sub-ms gap) + 30_000_000 (to the band change);
    # needs water = CAP (the 20-min gap capped) + 0 (last row)
    assert truth[("p01", "OK")] == 999_200 + 30_000_000
    assert truth[("p01", "needs water")] == 120_000_000
    # s2/p02: the NO_SIGNAL row's dwell never tallies; first row's 30 s does
    assert truth[("p02", "OK")] == 30_000_000
