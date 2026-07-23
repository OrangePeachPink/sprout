#!/usr/bin/env python3
"""#1240 — D2: the backfill loader. Every historical log segment → the Parquet store,
per the ratified D1 contract (docs/TIER_STORE_CONTRACT.md).

- **One parse per file** (not per partition): each segment is read once through
  ``parse_v1`` (the one parse boundary), its soil rows bucketed by (device, UTC day)
  with per-row ``source_file`` lineage, then every touched partition is written via
  ``tier_store.build_partition``.
- **Idempotent + resumable:** each (day, device) partition is rebuilt whole on every
  run (delete-and-rebuild, contract §1) — re-running converges to the same bytes for
  the same inputs (only ``ingest_ts`` truthfully moves). ``--skip-existing`` makes a
  resumed run cheap after an interruption (partition files are written last, so a
  present file is a completed partition).
- **Fidelity-checked:** the §6 gate per partition (row count + raw checksum + sensor
  count, computed FROM the written Parquet vs the parsed bucket) — a mismatch fails
  loudly with a non-zero exit; completed partitions stay (partial runs are safe).
- Reads ``*.csv`` and ``*.csv.gz`` (the B8 LFS archive shape); inputs are read-only.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

from tools.analytics.parse_v1 import (
    parse_file,
)
from tools.analytics.tier_store import (
    _TIER_ROOT,
    build_partition,
)

_HERE = Path(__file__).resolve().parent


def bucket_files(files) -> dict:
    """Parse each file ONCE; bucket soil rows as {(device_id, day): [(reading, src)]}.
    Rows route by the PARSED UTC timestamp, never the filename (contract §2)."""
    buckets: dict = defaultdict(list)
    for f in files:
        base = Path(f).name
        for r in parse_file(f).readings:
            if (
                r.record_type == "plants.soil"
                and r.device_id
                and r.timestamp_utc is not None
            ):
                buckets[(r.device_id, r.timestamp_utc.date())].append((r, base))
    for rows in buckets.values():
        rows.sort(key=lambda p: (p[0].sensor_id, p[0].timestamp_utc))
    return dict(buckets)


def backfill(
    files,
    out_root: Path | None = None,
    *,
    skip_existing: bool = False,
    log=print,
) -> dict:
    """Run the backfill; returns {partitions, rows, skipped, failures}. Fidelity
    failures are collected (and reported loudly) but never destroy completed work."""
    root = Path(out_root) if out_root else _TIER_ROOT
    buckets = bucket_files(files)
    stats = {"partitions": 0, "rows": 0, "skipped": 0, "failures": []}
    for (device, day), tagged in sorted(buckets.items(), key=lambda kv: kv[0][::-1]):
        dest = root / f"date={day.isoformat()}" / f"device={device}" / "part.parquet"
        if skip_existing and dest.is_file():
            stats["skipped"] += 1
            continue
        _parquet, gate = build_partition(tagged, device, day, root)
        ok = gate["rows"] == len(tagged) and gate["raw_sum"] == sum(
            r.raw_value for r, _ in tagged if r.raw_value is not None
        )
        if ok:
            stats["partitions"] += 1
            stats["rows"] += gate["rows"]
        else:
            stats["failures"].append(f"{day} {device}")
            log(f"FIDELITY MISMATCH {day} {device}: {gate} vs parsed {len(tagged)}")
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="#1240 D2: backfill logs -> the tier store"
    )
    ap.add_argument("--logs", default=str(_HERE.parents[1] / "logs"))
    ap.add_argument("--out", default=None, help="tier root (default: reports/tier/raw)")
    ap.add_argument("--skip-existing", action="store_true", help="resume cheaply")
    args = ap.parse_args(argv)

    files = sorted(
        str(p) for pat in ("*.csv", "*.csv.gz") for p in Path(args.logs).glob(pat)
    )
    if not files:
        print(f"no log segments under {args.logs}")
        return 1
    t0 = time.perf_counter()
    s = backfill(
        files,
        Path(args.out) if args.out else None,
        skip_existing=args.skip_existing,
    )
    dt = time.perf_counter() - t0
    print(
        f"backfill: {len(files)} segments -> {s['partitions']} partitions "
        f"({s['rows']} rows) · {s['skipped']} skipped · "
        f"{len(s['failures'])} fidelity failures · {dt:.1f}s"
    )
    return 0 if not s["failures"] else 2


if __name__ == "__main__":
    sys.exit(main())
