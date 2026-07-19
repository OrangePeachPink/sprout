#!/usr/bin/env python3
"""#1241 — D3: live ingest + compaction. New collector rows land in the tier
continuously as small ``append-*.parquet`` siblings; daily compaction rebuilds each
closed partition whole from source and removes the appends (contract §8).

- **The store is its own watermark.** How much of a source segment is already
  ingested = COUNT of its rows in the store, grouped by the ``source_file`` lineage
  column — no side-car state file to lose or to drift. A crash between an append
  landing and anything else simply converges next cycle (at-least-once appends;
  the canonical part is exactly-once via the gate-checked rebuild).
- **Append-only source assumption** (contract §8): a segment only ever grows; the
  first N parsed rows are the N already stored. A file that SHRANK (rotation,
  recovery, rewrite) is detected (stored > parsed) and healed by rebuilding every
  partition it feeds, whole, from source — delete-and-rebuild, never patch (§1).
- **Compaction = the D2 path.** Feeder files come FROM the partition's own lineage
  column; the partition is rebuilt whole via ``build_partition`` (fidelity-gated,
  §6) and only then are its appends deleted. Duplicates from an ingest crash heal
  here. Default compacts CLOSED (pre-today UTC) days; ``--include-today`` for all.
- **Freshness** (contract §8): with an ingest cycle of I, open-day store lag ≤ I;
  ``status`` reports per-file pending rows + the oldest pending row's age, live.

Inputs (CSVs) are read-only, always. Every write goes through ``build_partition``
(the one schema path); every parse through ``parse_v1`` (the one parse boundary).
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from parse_v1 import parse_file  # noqa: E402  (the ONE parse boundary, ADR-0021)
from tier_store import _TIER_ROOT, build_partition  # noqa: E402


def _soil_rows(path: str) -> list:
    return [
        r
        for r in parse_file(path).readings
        if r.record_type == "plants.soil"
        and r.device_id
        and r.timestamp_utc is not None
    ]


def _store_counts(root: Path) -> dict[str, int]:
    """{source_file basename: rows already stored} — the watermark, derived live."""
    import duckdb

    if not any(root.glob("date=*/device=*/*.parquet")):
        return {}
    con = duckdb.connect()
    rows = con.execute(
        "SELECT source_file, COUNT(*) FROM "
        f"read_parquet('{root.as_posix()}/*/*/*.parquet', hive_partitioning=false) "
        "GROUP BY source_file"
    ).fetchall()
    con.close()
    return dict(rows)


def _partitions_fed_by(root: Path, base: str) -> list[tuple[str, object]]:
    """(device_id, day) partitions holding rows from ``base`` — from lineage."""
    import duckdb

    con = duckdb.connect()
    out = con.execute(
        "SELECT DISTINCT device_id, CAST(timestamp_utc AS DATE) FROM "
        f"read_parquet('{root.as_posix()}/*/*/*.parquet', hive_partitioning=false) "
        "WHERE source_file = ?",
        [base],
    ).fetchall()
    con.close()
    return out


def _delete_appends(part_dir: Path) -> int:
    n = 0
    for p in part_dir.glob("append-*.parquet"):
        p.unlink()
        n += 1
    return n


def _rebuild_partition(files_by_base: dict, device: str, day, root: Path) -> bool:
    """Rebuild one (device, day) whole from its feeder files (delete-and-rebuild,
    §1): gate-checked part.parquet first, appends removed only on a passing gate."""
    tagged = []
    for base, path in sorted(files_by_base.items()):
        for r in _soil_rows(path):
            if r.device_id == device and r.timestamp_utc.date() == day:
                tagged.append((r, base))
    tagged.sort(key=lambda p: (p[0].sensor_id, p[0].timestamp_utc))
    part_dir = root / f"date={day.isoformat()}" / f"device={device}"
    _parquet, gate = build_partition(tagged, device, day, root)
    ok = gate["rows"] == len(tagged) and gate["raw_sum"] == sum(
        r.raw_value for r, _ in tagged if r.raw_value is not None
    )
    if ok:
        _delete_appends(part_dir)
    return ok


def ingest_once(files, root: Path | None = None, log=print) -> dict:
    """One ingest cycle: per source segment, append only the rows the store has not
    seen (store-derived watermark); heal any shrunken segment by whole-partition
    rebuild. Returns {appended_rows, append_files, rebuilt, failures}."""
    root = Path(root) if root else _TIER_ROOT
    stored = _store_counts(root)
    stats = {"appended_rows": 0, "append_files": 0, "rebuilt": [], "failures": []}
    paths_by_base = {Path(f).name: str(f) for f in files}
    for f in files:
        base = Path(f).name
        readings = _soil_rows(f)
        seen = stored.get(base, 0)
        if len(readings) < seen:
            log(f"{base}: shrank ({seen} stored > {len(readings)} parsed) — rebuilding")
            for device, day in _partitions_fed_by(root, base):
                if _rebuild_partition(paths_by_base, device, day, root):
                    stats["rebuilt"].append(f"{day} {device}")
                else:
                    stats["failures"].append(f"rebuild {day} {device}")
            continue
        new = readings[seen:]
        if not new:
            continue
        buckets: dict = defaultdict(list)
        for r in new:
            buckets[(r.device_id, r.timestamp_utc.date())].append((r, base))
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        for (device, day), tagged in sorted(buckets.items()):
            tagged.sort(key=lambda p: (p[0].sensor_id, p[0].timestamp_utc))
            out, gate = build_partition(
                tagged, device, day, root, filename=f"append-{stamp}.parquet"
            )
            ok = gate["rows"] == len(tagged) and gate["raw_sum"] == sum(
                r.raw_value for r, _ in tagged if r.raw_value is not None
            )
            if ok:
                stats["appended_rows"] += gate["rows"]
                stats["append_files"] += 1
            else:  # a bad append never stays — the watermark self-heals next cycle
                out.unlink(missing_ok=True)
                stats["failures"].append(f"append {day} {device}")
    return stats


def compact(
    files, root: Path | None = None, include_today: bool = False, log=print
) -> dict:
    """Rebuild every partition that holds appends, whole, from source; remove its
    appends on a passing gate. Closed (pre-today UTC) days only, unless asked."""
    root = Path(root) if root else _TIER_ROOT
    today = datetime.now(timezone.utc).date()
    paths_by_base = {Path(f).name: str(f) for f in files}
    stats = {"compacted": [], "skipped_open": 0, "failures": []}
    for append in sorted(root.glob("date=*/device=*/append-*.parquet")):
        part_dir = append.parent
        day_s = part_dir.parent.name.split("=", 1)[1]
        device = part_dir.name.split("=", 1)[1]
        day = datetime.strptime(day_s, "%Y-%m-%d").date()
        key = f"{day_s} {device}"
        if key in stats["compacted"] or f"compact {key}" in stats["failures"]:
            continue  # one rebuild covers every append in the partition
        if day >= today and not include_today:
            stats["skipped_open"] += 1
            continue
        if _rebuild_partition(paths_by_base, device, day, root):
            stats["compacted"].append(key)
        else:
            stats["failures"].append(f"compact {key}")
            log(f"FIDELITY MISMATCH compacting {key} — appends kept")
    return stats


def freshness(files, root: Path | None = None, now: datetime | None = None) -> dict:
    """The §8 freshness readout: per-file pending rows (parsed but not yet stored),
    the oldest pending row's age in seconds, and the compaction debt."""
    root = Path(root) if root else _TIER_ROOT
    now = now or datetime.now(timezone.utc)
    stored = _store_counts(root)
    pending: dict[str, int] = {}
    oldest_pending_s = 0.0
    for f in files:
        base = Path(f).name
        readings = _soil_rows(f)
        lag = len(readings) - stored.get(base, 0)
        if lag > 0:
            pending[base] = lag
            age = (now - readings[-lag].timestamp_utc).total_seconds()
            oldest_pending_s = max(oldest_pending_s, age)
    appends = list(root.glob("date=*/device=*/append-*.parquet"))
    return {
        "pending_rows": sum(pending.values()),
        "pending_by_file": pending,
        "oldest_pending_s": oldest_pending_s,
        "append_files": len(appends),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1241 D3: live ingest + compaction")
    ap.add_argument("verb", choices=["ingest", "compact", "status"])
    ap.add_argument("--logs", default=str(_HERE.parents[1] / "logs"))
    ap.add_argument("--out", default=None, help="tier root (default reports/tier/raw)")
    ap.add_argument("--include-today", action="store_true")
    args = ap.parse_args(argv)
    files = sorted(
        str(p) for pat in ("*.csv", "*.csv.gz") for p in Path(args.logs).glob(pat)
    )
    root = Path(args.out) if args.out else None
    if args.verb == "ingest":
        s = ingest_once(files, root)
        print(
            f"ingest: +{s['appended_rows']} rows in {s['append_files']} appends · "
            f"{len(s['rebuilt'])} rebuilt · {len(s['failures'])} failures"
        )
        return 1 if s["failures"] else 0
    if args.verb == "compact":
        s = compact(files, root, include_today=args.include_today)
        print(
            f"compact: {len(s['compacted'])} partitions · "
            f"{s['skipped_open']} open skipped · {len(s['failures'])} failures"
        )
        return 1 if s["failures"] else 0
    s = freshness(files, root)
    print(
        f"freshness: {s['pending_rows']} pending rows "
        f"(oldest {s['oldest_pending_s']:.0f}s) · "
        f"{s['append_files']} append files awaiting compaction"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
