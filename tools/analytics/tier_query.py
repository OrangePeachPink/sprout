#!/usr/bin/env python3
"""#1249 (DX ergonomics) — the ad-hoc query entrypoint for the DuckDB/Parquet tier.

Registers the gitignored tier store (the ratified #1239 layout ``reports/tier/raw/…``,
consumed from ``tier_store._TIER_ROOT`` — never a second copy) as a DuckDB view named
``store``, with hive-partitioning so ``date`` and ``device`` are columns, then runs the
SQL you pass and prints the result. Read-only convenience; the store is *built* by
``just store-rebuild`` (tier_backfill) and *verified* by ``just store-verify``
(tier_store). The contract is ``docs/TIER_STORE_CONTRACT.md``.

    just store-query "SELECT band, COUNT(*) FROM store GROUP BY band"
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# _TIER_ROOT = the ratified store layout (§1); consume it, don't copy it.
from tier_store import _TIER_ROOT  # noqa: E402

_STORE_GLOB = (_TIER_ROOT / "**" / "*.parquet").as_posix()


def run(sql: str, glob: str = _STORE_GLOB) -> int:
    import duckdb

    con = duckdb.connect()
    try:
        con.execute(
            f"CREATE VIEW store AS "
            f"SELECT * FROM read_parquet('{glob}', hive_partitioning = true)"
        )
    except duckdb.IOException:
        print(
            f"no store under {Path(glob).parent} - run `just store-rebuild` first.",
            file=sys.stderr,
        )
        return 1
    print(con.sql(sql))
    con.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or not argv[0].strip():
        print('usage: just store-query "<SQL over the `store` view>"', file=sys.stderr)
        return 2
    return run(argv[0])


if __name__ == "__main__":
    sys.exit(main())
