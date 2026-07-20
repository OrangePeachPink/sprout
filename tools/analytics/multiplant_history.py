#!/usr/bin/env python3
"""#1148 — the evaluation substrate: ONE payload feeding all three round-two
candidate surfaces on real fleet data (maintainer ruling, 2026-07-19 night).

Design-QA leads placement and the evaluation register; this module supplies the data
so all three candidates read the SAME live fleet — a prune verdict then compares
surfaces, never accidentally-different numbers underneath them.

The three sections, each named for its candidate:

- ``rows`` — **candidate 1, the line-over-half-band per-plant rows.** Per plant, per
  UTC day: the day's band for the bar, plus the shape series for the lane above it.
  The day's band is the **dwell-dominant** band (the band the plant actually spent
  the most time in that day, exact integer µs per the store contract §4) — not the
  last reading, which would let one late blip rename a whole day. The full
  ``bands_us`` breakdown rides along, so the render can say "mostly Ideal, some
  Drying" if Design wants that later without a data change.
- ``envelope`` — **candidate 2, the fleet glance.** Answers act-or-ignore: the most
  recent watering across the fleet, and the longest cycle (the least-recently-watered
  plant — the desert-dweller case). Ships BOTH ink references Design-QA flagged as an
  open question (most-recently-watered vs closest-to-needing-you), so that ruling can
  land as a render switch, not a rebuild. Per-plant sawtooth series + the pass ticks
  underneath — tick clusters ARE the watering rounds (the #1245 §3 PASS concept).
- ``ledger`` — **candidate 3, the saturated-dot ledger.** Per plant, the ordered band
  steps the plant actually walked, at their exact transition timestamps (the #1242
  event table — events are never downsampled, so a step is real, never inferred from
  a bucket).

**The band is the device-emitted one, exactly as the shipped Home consumes it**
(``card_payload`` reads ``band_fw``; ``mood-band-map.json`` maps ``fwLevel`` -> ``mood``
at render). This module deliberately does NOT derive a parallel band from raw: that
would author a second band truth able to disagree with the Home about the same plant on
the same day — the drift these surfaces exist to expose, not to introduce. So the
candidates speak the same seven levels the Home does, and inherit the same mood
mapping. ``moods_resolved`` reports whether every level actually present in this window
has a mood in the map, with any ``unmapped_bands`` named: a render guarantee, checked
against live data rather than assumed.

Every section is absent-safe (ADR-0028): a plant with no telemetry appears with empty
series rather than vanishing, and a fleet with no watering record says so instead of
inventing a headline. Read-only over the merged tier + registry + journal.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from collections import namedtuple  # noqa: E402

from device_registry import load_registry  # noqa: E402
from segment_classifier import classify, passes  # noqa: E402
from segment_history import _journal_events  # noqa: E402
from tier_rollup import read_events  # noqa: E402

# A LOCAL row type carrying `band` — candidate 1's bar is a band-per-day, and the
# shared `segment_history.TierRow` deliberately carries only what the classifier
# needs (timestamp/raw/quality). Widening that merged namedtuple would change a
# contract three shipped consumers already read, so this module does its own read
# instead. Duck-compatible with the classifier: the first three fields match.
PlantRow = namedtuple("PlantRow", "timestamp_utc raw_value quality_flag band")

_US = timedelta(microseconds=1)
CAP_US = 120_000_000  # the §5 dwell cap: an outage never inflates a day's band
DEFAULT_WINDOW_DAYS = 7  # candidate 1's pitch fits ~11 plants at 7d (Design's note)


def _mood_levels() -> set:
    """The ``fwLevel`` keys the mood-band-map can translate — the same map the shipped
    Home renders from (consume, never author: a second copy would drift)."""
    path = _HERE.parents[1] / "docs" / "design" / "components" / "mood-band-map.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        str(e.get("fwLevel", "")).strip().lower()
        for e in (doc.get("bands") or [])
        if e.get("fwLevel")
    }


def read_series(root: Path | None = None, registry=None) -> dict:
    """``{plant_id: [PlantRow]}`` — the same read as ``segment_history.plant_series``
    but carrying ``band`` (the device-emitted level, ground truth, never re-derived —
    store contract §3). Resolution is the static registry, the live fleet truth on
    this host; unmapped rows are C2's readout job, not this surface's."""
    import duckdb
    from segment_history import TIER_RAW

    root = Path(root) if root is not None else TIER_RAW
    registry = registry if registry is not None else load_registry()
    # A store with no partitions yet is "nothing logged", not an error — the same
    # calm-empty first-run the Home already handles (tier_ingest guards identically).
    if not any(root.glob("date=*/device=*/*.parquet")):
        return {}
    pair_to_plant: dict = {}
    for dev in registry.devices:
        for channel in dev.channels or {}:
            p = dev.plant_for(channel)
            if p:
                pair_to_plant[(dev.device_id, channel)] = p["plant_id"]
    con = duckdb.connect()
    rows = con.execute(
        "SELECT device_id, sensor_id, timestamp_utc, raw_value, quality_flag, band "
        f"FROM read_parquet('{root.as_posix()}/*/*/*.parquet', "
        "hive_partitioning=false) ORDER BY timestamp_utc"
    ).fetchall()
    con.close()
    series: dict = {}
    for device_id, sensor_id, ts, raw, flag, band in rows:
        pid = pair_to_plant.get((device_id, sensor_id))
        if pid is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        series.setdefault(pid, []).append(PlantRow(ts, raw, flag, band))
    return series


def _plant_names(registry) -> dict:
    """plant_id -> the plant-first label (#718): never the machine id or GPIO."""
    out: dict = {}
    for p in registry.all_plants():
        out[p["plant_id"]] = p.get("plant_name") or p["plant_id"]
    for s in registry.sensorless_plants():
        pid = s.get("plant_id")
        if pid and pid not in out:
            out[pid] = s.get("plant_name") or pid
    return out


def daily_rows(series: dict, t0: datetime, t1: datetime) -> dict:
    """Candidate 1's substrate: ``{plant_id: [{date, band, bands_us, points, n}]}``.

    The day's ``band`` is **dwell-dominant** — the band this plant spent the most
    microseconds in that day (gaps capped at ``CAP_US``, so an outage cannot win a
    day). ``points`` is the raw shape for the lane above the bar: (hours-into-day,
    raw) pairs, which is what carries "how fast, how deep, did it plateau"."""
    out: dict = {}
    for pid, rows in series.items():
        by_day: dict = defaultdict(list)
        for r in rows:
            if t0 <= r.timestamp_utc < t1:
                by_day[r.timestamp_utc.date()].append(r)
        days = []
        for day in sorted(by_day):
            drows = sorted(by_day[day], key=lambda r: r.timestamp_utc)
            bands_us: dict = defaultdict(int)
            for i, r in enumerate(drows):
                if i + 1 < len(drows):
                    gap = (drows[i + 1].timestamp_utc - r.timestamp_utc) // _US
                    dwell = min(gap, CAP_US)
                else:
                    dwell = 0
                band = getattr(r, "band", None)
                if band and getattr(r, "quality_flag", "OK") != "NO_SIGNAL":
                    bands_us[band] += dwell
            dominant = max(bands_us, key=lambda b: bands_us[b]) if bands_us else None
            midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            days.append(
                {
                    "date": day.isoformat(),
                    "band": dominant,  # dwell-dominant, never the last blip
                    "bands_us": dict(bands_us),
                    "n": len(drows),
                    "points": [
                        {
                            "h": round(
                                ((r.timestamp_utc - midnight) // _US) / 3_600_000_000, 4
                            ),
                            "raw": r.raw_value,
                        }
                        for r in drows
                        if r.raw_value is not None
                    ],
                }
            )
        out[pid] = days
    return out


def fleet_envelope(
    series: dict, journal: Path | None, names: dict, now: datetime
) -> dict:
    """Candidate 2's substrate: the act-or-ignore glance.

    ``last_watering`` = the most recent PASS across the fleet. ``longest_cycle`` =
    the plant whose own last watering is furthest back — the desert-dweller the
    glance is meant to catch. Both ink references Design-QA flagged ship together
    (``by_recency`` / ``by_need``) so their open question resolves as a render
    switch. Honest absence: no watering record ⇒ the fields are None, never a
    fabricated 'today'."""
    events: list[tuple] = []
    per_plant_last: dict = {}
    for pid, rows in series.items():
        kinds = classify(rows)
        for i in range(1, len(rows)):
            if (
                kinds[i] == "watering-transient"
                and kinds[i - 1] != "watering-transient"
            ):
                ts = rows[i - 1].timestamp_utc
                events.append((ts, "soil", pid))
                per_plant_last[pid] = max(per_plant_last.get(pid, ts), ts)
    if journal is not None:
        for ts, src, pid in _journal_events(journal):
            events.append((ts, src, pid))
            if pid:
                per_plant_last[pid] = max(per_plant_last.get(pid, ts), ts)
    fleet_passes = passes(events)
    ticks = [
        {
            "pass_id": p.pass_id,
            "t0": p.t0.isoformat(),
            "n_events": p.n,
            "plants": sorted({e[2] for e in p.events if e[2]}),
        }
        for p in fleet_passes
    ]
    last = max(per_plant_last.values(), default=None)
    oldest_pid = (
        min(per_plant_last, key=lambda k: per_plant_last[k]) if per_plant_last else None
    )
    return {
        "last_watering": (
            {
                "t": last.isoformat(),
                "days_ago": round((now - last) / timedelta(days=1), 2),
            }
            if last
            else None
        ),
        "longest_cycle": (
            {
                "plant_id": oldest_pid,
                "plant_name": names.get(oldest_pid, oldest_pid),
                "t": per_plant_last[oldest_pid].isoformat(),
                "days_ago": round(
                    (now - per_plant_last[oldest_pid]) / timedelta(days=1), 2
                ),
            }
            if oldest_pid
            else None
        ),
        # the open ink question (Design-QA #1148 q1) — BOTH orders, one payload
        "by_recency": [
            {
                "plant_id": pid,
                "plant_name": names.get(pid, pid),
                "days_ago": round((now - ts) / timedelta(days=1), 2),
            }
            for pid, ts in sorted(
                per_plant_last.items(), key=lambda kv: -kv[1].timestamp()
            )
        ],
        "by_need": [
            {
                "plant_id": pid,
                "plant_name": names.get(pid, pid),
                "days_ago": round((now - ts) / timedelta(days=1), 2),
            }
            for pid, ts in sorted(
                per_plant_last.items(), key=lambda kv: kv[1].timestamp()
            )
        ],
        "passes": ticks,
        "n_passes": len(ticks),
    }


def band_ledger(series: dict, registry, root: Path | None = None) -> dict:
    """Candidate 3's substrate: ``{plant_id: [{t, band}]}`` — the ordered steps the
    plant actually walked, from the #1242 event table (exact transition timestamps,
    never downsampled). Falls back to deriving steps from the plant's own rows when
    no event table has been materialized, so the surface is never blank-by-plumbing.
    """
    pair_to_plant: dict = {}
    for dev in registry.devices:
        for channel in dev.channels or {}:
            p = dev.plant_for(channel)
            if p:
                pair_to_plant[(dev.device_id, channel)] = p["plant_id"]
    steps: dict = {pid: [] for pid in series}
    try:
        for ev in read_events(kind="band", root=root):
            pid = pair_to_plant.get((ev["device_id"], ev["sensor_id"]))
            if pid is None or pid not in steps:
                continue
            detail = str(ev.get("detail") or "")
            band = detail.split("->")[-1] if "->" in detail else detail
            ts = ev["timestamp_utc"]
            steps[pid].append(
                {
                    "t": (
                        ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
                    ).isoformat(),
                    "band": band,
                }
            )
    except Exception:
        steps = {pid: [] for pid in series}
    for pid, rows in series.items():
        if steps.get(pid):
            continue
        prev = None
        for r in rows:  # honest fallback: the same steps, derived in-process
            band = getattr(r, "band", None)
            if band and band != prev:
                steps[pid].append({"t": r.timestamp_utc.isoformat(), "band": band})
                prev = band
    return steps


def build_payload(
    window_days: int = DEFAULT_WINDOW_DAYS,
    registry=None,
    journal: Path | None = None,
    root: Path | None = None,
    events_root: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """The one payload behind all three candidates — same window, same plants, same
    numbers, so her prune verdict compares SURFACES rather than accidental data
    differences."""
    registry = registry if registry is not None else load_registry()
    series = read_series(root, registry)
    now = now or datetime.now(timezone.utc)
    t1 = now
    t0 = now - timedelta(days=window_days)
    names = _plant_names(registry)
    for s in registry.sensorless_plants():  # absent-safe: sensorless plants appear
        pid = s.get("plant_id")
        if pid and pid not in series:
            series[pid] = []
    seen_bands = sorted(
        {r.band for rows in series.values() for r in rows if getattr(r, "band", None)}
    )
    mapped = _mood_levels()
    unmapped = [b for b in seen_bands if b.strip().lower() not in mapped]
    return {
        "generated_utc": now.isoformat(),
        "bands_seen": seen_bands,
        # a render guarantee checked against LIVE data: every level present here has
        # a mood in mood-band-map.json, so no candidate can render a moodless bar
        "moods_resolved": not unmapped,
        "unmapped_bands": unmapped,
        "window_days": window_days,
        "t0": t0.isoformat(),
        "t1": t1.isoformat(),
        "plants": [
            {
                "plant_id": pid,
                "plant_name": names.get(pid, pid),
                "n_readings": len(rows),
            }
            for pid, rows in sorted(series.items())
        ],
        "rows": daily_rows(series, t0, t1),
        "envelope": fleet_envelope(series, journal, names, now),
        "ledger": band_ledger(series, registry, events_root),
        "candidates": {  # the evaluation register's own map, data-side
            "1-line-over-half-band": "rows",
            "2-envelope": "envelope",
            "3-saturated-dot-ledger": "ledger",
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1148 evaluation substrate")
    ap.add_argument("--registry", default=None)
    ap.add_argument("--journal", default=None)
    ap.add_argument("--days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)
    registry = load_registry(args.registry) if args.registry else None
    payload = build_payload(
        window_days=args.days,
        registry=registry,
        journal=Path(args.journal) if args.journal else None,
    )
    env = payload["envelope"]
    print(f"window {payload['window_days']}d · {len(payload['plants'])} plants")
    lw, lc = env["last_watering"], env["longest_cycle"]
    print(f"  last watering : {lw['days_ago']}d ago" if lw else "  last watering : —")
    print(
        f"  longest cycle : {lc['plant_name']} — {lc['days_ago']}d"
        if lc
        else "  longest cycle : —"
    )
    print(f"  passes        : {env['n_passes']}")
    for p in payload["plants"]:
        pid = p["plant_id"]
        days = payload["rows"].get(pid) or []
        bars = " ".join((d["band"] or "·")[:4] for d in days[-7:])
        print(
            f"  {p['plant_name'][:22]:<22} rows={len(days):<2} "
            f"steps={len(payload['ledger'].get(pid) or []):<3} {bars}"
        )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
