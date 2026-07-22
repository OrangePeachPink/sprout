#!/usr/bin/env python3
"""#1431 - the reproducible C5-dropout comparison, made durable for the before/after.

Firmware characterized this at the bench (2026-07-21): the C5's ~945 "missing rows per
channel" are not per-probe row loss - they are **89 short WiFi-association dropouts
unique to the C5** over 12 days (~5 h lost, median 2.8 min, nothing over 12 min), a
bounded retry loop that always recovers. The classic, on the same window and a *weaker*
signal, has zero extra. The maintainer's ruling: the characterization is done; what
rides v0.8.1 is the **experiment** - she stands up a dedicated 2.4 GHz band for the
dual-band C5, captures a few days, and Data compares the new dropout rate against the
recorded **89-gaps / 12-days** baseline, then closes with the verdict (network-config
fix documented, or accept-and-surface with honest numbers).

This module is the comparison instrument, so both halves of that before/after use ONE
method rather than two hand-rolled scripts that might count differently. It reproduces
Firmware's eleven-line analysis:

1. per **device**, the sweep timeline (distinct poll timestamps - all a board's channels
   sweep together, so a missed sweep is a board-level gap, which is why the deficit was
   uniform across the C5's four channels);
2. sweep-to-sweep deltas over ``GAP_THRESHOLD_S`` (the same 2-minute threshold the
   dashboard's gap surface uses - consumed, not re-picked, so "a gap" means one thing);
3. gaps that coincide across boards to a tolerance are **shared host/logger outages**
   (the four big ones Firmware found aligned sub-second on both boards); the rest are
   **board-unique** - the number that actually characterizes a board's own reachability.

Read-only over parsed telemetry. The verdict is bench-gated (the maintainer's band
change + capture); this is prepped to that line.
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

from card_context import GAP_THRESHOLD_S  # noqa: E402  (the one gap threshold, #1431)

# How close two boards' gap edges must be to count as the SAME outage. A shared host
# outage stops every board's logging at once; independent WiFi dropouts do not line up.
# Sub-minute is generous - Firmware's shared gaps aligned to sub-second.
SHARED_TOL_S = 45.0


def sweep_gaps(
    readings, threshold_s: float = GAP_THRESHOLD_S
) -> dict[str, list[tuple[datetime, datetime, float]]]:
    """Per device, the sweep-to-sweep gaps over ``threshold_s``.

    A sweep is a distinct poll timestamp for that device (its channels sweep together).
    Returns ``{device_id: [(start, end, minutes), ...]}`` - a gap is the interval
    between two consecutive sweeps whose delta exceeds the threshold.
    """
    stamps: dict[str, set] = defaultdict(set)
    for r in readings:
        dev = getattr(r, "device_id", None)
        ts = getattr(r, "timestamp_utc", None)
        if not dev or ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        stamps[dev].add(ts)
    out: dict[str, list[tuple[datetime, datetime, float]]] = {}
    for dev, sset in stamps.items():
        ordered = sorted(sset)
        gaps = []
        for a, b in zip(ordered, ordered[1:]):
            secs = (b - a).total_seconds()
            if secs > threshold_s:
                gaps.append((a, b, secs / 60.0))
        out[dev] = gaps
    return out


def partition_shared(
    device_gaps: dict[str, list[tuple[datetime, datetime, float]]],
    tol_s: float = SHARED_TOL_S,
) -> dict:
    """Split each device's gaps into SHARED (a host/logger outage that hit every board
    at once) vs board-UNIQUE (its own reachability). A gap is shared when another device
    has a gap whose start AND end fall within ``tol_s``.

    The board-unique count is the one that characterizes a board: the four big outages
    Firmware found were shared to sub-second and are not the C5's doing; subtracting
    them is what leaves the 89 C5-only dropouts.
    """
    devices = list(device_gaps)
    unique: dict[str, list] = {d: [] for d in devices}
    shared: list[tuple[datetime, datetime, float]] = []
    shared_seen: set[tuple[datetime, datetime]] = set()
    for d in devices:
        for a, b, mins in device_gaps[d]:
            is_shared = any(
                other != d
                and any(
                    abs((a - oa).total_seconds()) <= tol_s
                    and abs((b - ob).total_seconds()) <= tol_s
                    for oa, ob, _ in device_gaps[other]
                )
                for other in devices
            )
            if is_shared:
                key = (a, b)
                # record each shared outage once (by its earliest-board edges)
                if not any(
                    abs((a - sa).total_seconds()) <= tol_s
                    and abs((b - sb).total_seconds()) <= tol_s
                    for sa, sb in shared_seen
                ):
                    shared.append((a, b, mins))
                    shared_seen.add(key)
            else:
                unique[d].append((a, b, mins))
    return {"shared": shared, "unique": unique}


def summarize(gaps: list[tuple[datetime, datetime, float]]) -> dict:
    """Count, hours lost, and the duration distribution - Firmware's banding, so the
    before/after tables line up. The 2-5 min band being dominant is the retry-loop
    signature (a bounded recovery), distinct from a long tail of crashes."""
    mins = [m for _, _, m in gaps]
    bands = {"2-5m": 0, "5-15m": 0, "15-60m": 0, ">60m": 0}
    for m in mins:
        if m < 5:
            bands["2-5m"] += 1
        elif m < 15:
            bands["5-15m"] += 1
        elif m < 60:
            bands["15-60m"] += 1
        else:
            bands[">60m"] += 1
    return {
        "count": len(mins),
        "hours_lost": round(sum(mins) / 60.0, 2),
        "median_min": round(sorted(mins)[len(mins) // 2], 1) if mins else None,
        "max_min": round(max(mins), 1) if mins else None,
        "bands": bands,
    }


def report(readings, threshold_s: float = GAP_THRESHOLD_S) -> dict:
    """The full #1431 comparison: per-device shared vs board-unique gap summaries. Run
    this on the current corpus for the baseline and again after the band change; the
    board-unique count is the number that answers the experiment."""
    dg = sweep_gaps(readings, threshold_s)
    part = partition_shared(dg)
    return {
        "threshold_s": threshold_s,
        "shared_outages": summarize(part["shared"]),
        "per_device_unique": {d: summarize(g) for d, g in part["unique"].items()},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1431 C5 dropout comparison")
    ap.add_argument("inputs", nargs="*", help="fleet CSVs (default: gather_inputs())")
    args = ap.parse_args(argv)
    from parse_v1 import parse_files

    inputs = args.inputs
    if not inputs:
        from dashboard import gather_inputs

        inputs = gather_inputs()
    data = parse_files([str(p) for p in inputs])
    import json

    print(json.dumps(report(data.readings), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
