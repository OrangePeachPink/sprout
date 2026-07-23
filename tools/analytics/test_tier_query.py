"""Tests for the #1249 tier query ergonomics (`just store-query`).

Runs under `just test-analytics` (pytest tools/analytics/). Builds a synthetic partition
in the ratified `date=/device=` layout and exercises `tier_query.run`; the store is a
DuckDB view over the glob, so date/device come from the path (hive-partitioning)."""

from pathlib import Path

import duckdb

from tools.analytics import tier_query


def _mk_store(tmp_path: Path) -> str:
    part = tmp_path / "date=2026-07-18" / "device=dev1"
    part.mkdir(parents=True)
    pq = part / "part.parquet"
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT 'Thirsty' AS band, 1 AS n UNION ALL SELECT 'Happy', 2) "
        f"TO '{pq.as_posix()}' (FORMAT PARQUET)"
    )
    con.close()
    return (tmp_path / "**" / "*.parquet").as_posix()


def test_query_runs_over_the_store(tmp_path: Path) -> None:
    assert tier_query.run("SELECT COUNT(*) FROM store", _mk_store(tmp_path)) == 0


def test_hive_partition_columns_are_exposed(tmp_path: Path) -> None:
    # date + device come from the path, not the row data — the ratified layout
    assert (
        tier_query.run("SELECT device, date, band FROM store", _mk_store(tmp_path)) == 0
    )


def test_missing_store_is_a_clean_one(tmp_path: Path) -> None:
    glob = (tmp_path / "empty" / "**" / "*.parquet").as_posix()
    assert tier_query.run("SELECT 1 FROM store", glob) == 1


def test_empty_sql_is_usage_two() -> None:
    assert tier_query.main([]) == 2
    assert tier_query.main(["   "]) == 2
