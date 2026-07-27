#!/usr/bin/env python3
"""#1246 C2 — full-history classification over the tier + per-plant validity metrics.

The honest readout of how much signal each plant actually has: classify every stored
reading (SEGMENT_TAXONOMY_CONTRACT) over the whole #828 raw tier, then report, per
plant: coverage (how much of its wall-clock span we actually observed), segment counts
by kind, and **pct-valid** — the share of observed time in ``steady-drying``, the only
segments a trend/forecast may fit (contract §2).

Identity: rows resolve (device_id, channel) → plant via the STATIC device registry —
the live fleet truth on this host. (``tier_store.registry_plant_map`` resolves via the
temporal registry_model per the store contract §3; on a host with no local temporal
instance that ladder lands on the committed example and maps nothing real. The bridge
is the known two-registries seam — flagged for the #1243 views.) Rows whose pair
resolves nowhere are counted in an ``unmapped`` bucket, never silently dropped, and
sensorless plants appear as first-class coverage-0 rows (ADR-0028) — absence is part
of the honest readout.

Time discipline (TIER_STORE_CONTRACT §4): every duration is exact integer
microseconds end-to-end; hours appear only at render. Occupancy gaps cap at
``tier_store.CAP_US`` (an outage is not "observed"). Derived-only: the raw tier and
the glug journal are read, never written (taxonomy contract §3).
"""

from __future__ import annotations

import argparse
import json
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.channel_identity import (  # noqa: E402  (#1454 — the one S1-seam join)
    build_plant_index,
    resolve_plant_id,
)
from tools.analytics.device_registry import load_registry  # noqa: E402
from tools.analytics.segment_classifier import (  # noqa: E402
    KINDS,
    classify,
    passes,
    segments,
)
from tools.analytics.tier_store import CAP_US  # noqa: E402

_REPO = _HERE.parents[1]
TIER_RAW = _REPO / "reports" / "tier" / "raw"
_US = timedelta(microseconds=1)

# Duck-typed for the classifier: .timestamp_utc / .raw_value / .quality_flag
TierRow = namedtuple("TierRow", "timestamp_utc raw_value quality_flag")


def plant_series(root: Path | None = None, registry=None) -> tuple[dict, dict]:
    """Read the whole raw tier, time-ordered, resolved to plants via the static
    registry: ``({plant_id: [TierRow...]}, {(device_id, channel): n_unmapped})``."""
    import duckdb

    root = Path(root) if root is not None else TIER_RAW
    registry = registry if registry is not None else load_registry()
    # #1454: the one S1-seam join — v4 sN rows and v5 chN rows both resolve, whether
    # or not the registry has migrated (was an inline pair_to_plant here; #1315).
    index = build_plant_index(registry)
    con = duckdb.connect()
    rows = con.execute(
        # *.parquet, not part.parquet: a partition may hold D3 live-ingest
        # append-*.parquet siblings between compactions (store contract §8)
        "SELECT device_id, sensor_id, timestamp_utc, raw_value, quality_flag "
        f"FROM read_parquet('{root.as_posix()}/*/*/*.parquet', "
        "hive_partitioning=false) ORDER BY timestamp_utc"
    ).fetchall()
    series: dict[str, list[TierRow]] = {}
    unmapped: dict[tuple[str, str], int] = {}
    for device_id, sensor_id, ts, raw, flag in rows:
        pid = resolve_plant_id(index, device_id, sensor_id)
        if pid is None:
            unmapped[(device_id, sensor_id)] = (
                unmapped.get((device_id, sensor_id), 0) + 1
            )
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        series.setdefault(pid, []).append(TierRow(ts, raw, flag))
    return series, unmapped


def summarize(rows) -> dict:
    """One plant's validity metrics — exact integer µs throughout. Each inter-row gap
    (capped at CAP_US) is attributed to the EARLIER row's kind, the same forward-gap
    convention as ``tier_store.hours_per_band_*``; the final row carries no gap."""
    rows = list(rows)
    if not rows:
        return {
            "n_obs": 0,
            "t_first": None,
            "t_last": None,
            "span_us": 0,
            "observed_us": 0,
            "coverage": None,
            "kind_us": dict.fromkeys(KINDS, 0),
            "segment_counts": dict.fromkeys(KINDS, 0),
            "pct_valid": None,
        }
    kinds = classify(rows)
    kind_us = dict.fromkeys(KINDS, 0)
    observed_us = 0
    for i in range(len(rows) - 1):
        gap = (rows[i + 1].timestamp_utc - rows[i].timestamp_utc) // _US
        gap = min(gap, CAP_US)
        observed_us += gap
        kind_us[kinds[i]] += gap
    counts = dict.fromkeys(KINDS, 0)
    for seg in segments(rows):
        counts[seg.kind] += 1
    span_us = (rows[-1].timestamp_utc - rows[0].timestamp_utc) // _US
    return {
        "n_obs": len(rows),
        "t_first": rows[0].timestamp_utc.isoformat(),
        "t_last": rows[-1].timestamp_utc.isoformat(),
        "span_us": span_us,
        "observed_us": observed_us,
        "coverage": (observed_us / span_us) if span_us else None,
        "kind_us": kind_us,
        "segment_counts": counts,
        "pct_valid": (kind_us["steady-drying"] / observed_us) if observed_us else None,
    }


def _journal_events(path: Path) -> list[tuple]:
    """Manual glug evidence from the append-only journal as pass events
    ``(ts, "glug", plant_id)`` — read-only, malformed lines skipped honestly."""
    events: list[tuple] = []
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
            ts = datetime.fromisoformat(str(doc["ts"]).replace("Z", "+00:00"))
        except (ValueError, KeyError, TypeError):
            continue
        events.append((ts, "glug", doc.get("plant_id")))
    return events


def full_history(
    root: Path | None = None, registry=None, journal: Path | None = None
) -> dict:
    """The C2 report: per-plant validity metrics over the whole tier (wired plants
    from telemetry; sensorless plants as first-class coverage-0 rows), the unmapped
    bucket, and the fleet watering-pass roll (soil onsets + the glug journal)."""
    registry = registry if registry is not None else load_registry()
    series, unmapped = plant_series(root, registry)
    plants: dict[str, dict] = {}
    for pid in sorted(series):
        plants[pid] = summarize(series[pid])
        plants[pid]["source"] = "telemetry"
    for s in registry.sensorless_plants():
        pid = s.get("plant_id")
        if pid and pid not in plants:
            plants[pid] = summarize([])
            plants[pid]["source"] = "sensorless"
    # #1027 (the data taxonomy under the adopt flow): an unmapped (device, channel)
    # is NOT one thing. Classify against the registry's device list so the readout
    # tells the truth the adopt trigger needs: `unknown-device` (not registered —
    # the adopt case) vs `retired-unassigned` (a known bench/retired board; its
    # rows stay, honestly labeled) vs `unassigned-channel` (a live board's spare
    # port). Only `unknown-device` is adopt-flow material.
    dev_index = {d.device_id: d for d in registry.devices}
    unmapped_classed: dict[str, dict] = {}
    for (dev, ch), n in sorted(unmapped.items()):
        d = dev_index.get(dev)
        if d is None:
            klass, board = "unknown-device", None
        elif getattr(d, "retired", False):
            klass, board = "retired-unassigned", d.board
        else:
            klass, board = "unassigned-channel", d.board
        unmapped_classed[f"{dev}/{ch}"] = {"rows": n, "class": klass, "board": board}
    events = [
        (seg.t0, "soil", pid)
        for pid, rows in series.items()
        for seg in segments(rows)
        if seg.kind == "watering-transient"
    ]
    if journal is not None:
        events.extend(_journal_events(journal))
    fleet_passes = passes(events)
    return {
        "generated_from": "reports/tier/raw (derived-only; tier + journal read-only)",
        "plants": plants,
        "unmapped": unmapped_classed,
        "passes": [
            {
                "pass_id": p.pass_id,
                "t0": p.t0.isoformat(),
                "t1": p.t1.isoformat(),
                "n_events": p.n,
                "plants": sorted({e[2] for e in p.events if e[2]}),
                "sources": sorted({e[1] for e in p.events}),
            }
            for p in fleet_passes
        ],
    }


def _h(us: int) -> float:
    return us / 3_600_000_000.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--root", default=None, help="tier raw root (default reports/tier/raw)"
    )
    ap.add_argument(
        "--registry",
        default=None,
        help="static device-registry JSON (default: this checkout's discovery ladder"
        " — pass the runtime home's file when running from a worktree)",
    )
    ap.add_argument("--journal", default=None, help="glug journal JSONL (optional)")
    ap.add_argument(
        "--json", dest="json_out", default=None, help="write the full report here"
    )
    args = ap.parse_args(argv)
    report = full_history(
        Path(args.root) if args.root else None,
        registry=load_registry(args.registry) if args.registry else None,
        journal=Path(args.journal) if args.journal else None,
    )
    hdr = "plant     obs      span_h  obs_h   cov    "
    print(hdr + "steady  trans  rebnd  flag   pct_valid")
    for pid, m in report["plants"].items():
        if m["source"] == "sensorless":
            note = "sensorless — no telemetry by design (coverage 0)"
            print(f"{pid:<8}  {'—':>6}  " + note)
            continue
        c = m["segment_counts"]
        left = (
            f"{pid:<8}  {m['n_obs']:>6}  {_h(m['span_us']):>6.1f}"
            f"  {_h(m['observed_us']):>5.1f}  {m['coverage']:.3f}"
        )
        right = (
            f"{c['steady-drying']:>5}  {c['watering-transient']:>5}"
            f"  {c['rebound']:>5}  {c['flagged']:>4}   {m['pct_valid']:.3f}"
        )
        print(left + "  " + right)
    _WHY = {  # #1027: say WHICH honesty class — only unknown-device is adopt material
        "unknown-device": "UNKNOWN device — the #1027 adopt case",
        "retired-unassigned": "retired bench board — rows kept, honestly unassigned",
        "unassigned-channel": "live board, spare port — no plant on this channel",
    }
    for pair, m in report["unmapped"].items():
        board = f" [{m['board']}]" if m.get("board") else ""
        print(f"unmapped  {pair}: {m['rows']} rows ({_WHY[m['class']]}{board})")
    print(f"fleet watering passes: {len(report['passes'])}")
    for p in report["passes"]:
        print(
            f"  {p['pass_id']}  n={p['n_events']}"
            f"  sources={'+'.join(p['sources'])}  plants={','.join(p['plants'])}"
        )
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
