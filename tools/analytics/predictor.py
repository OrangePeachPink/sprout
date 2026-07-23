#!/usr/bin/env python3
"""#25 — the next-watering predictor: per-plant forecast + the predicted-vs-actual
loop. The v0.8.0 headline.

What it predicts is **her watering moment, not a band edge.** `forecast.py` already
answers "when does this cross the thirsty boundary" — a property of the ladder. This
answers "when will *this plant* want water," learned from when the operator has
actually watered it. The two coexist: the band ETA is instrument truth, this is
household truth.

**Three tiers, degrading gracefully** (the issue's own cold-start requirement):

1. ``rate`` — the real prediction: the plant's personal watering threshold (the median
   raw at which she has actually watered it) projected along the **current valid arc's
   drying rate** from the D5 bridge. Mask-bound by construction — the rate comes from
   a ``valid_for_trend`` segment, so a watering transient can never be mistaken for
   drying.
2. ``interval`` — the cold start: no usable arc yet (freshly watered, or too thin), so
   fall back to her own median inter-watering interval for that plant. A per-plant
   average interval is useful on day one and needs no curve at all.
3. ``none`` — honest abstain: fewer than two waterings on record, so there is neither
   a threshold nor an interval to learn from. The predictor says so instead of
   inventing a number (ADR-0028: absence is first-class).

**Confidence is stated, never implied.** Every forecast carries the tier, the sample
count behind it, and any profile ``probe_reading_caveat`` — a plant whose probe is
known to misread cannot hand out a confident number just because the arithmetic
worked (ADR-0029 §6).

Evaluated by the #1248 C4 harness: ``predict_fn`` plugs straight in, so every change
to this file is scored predicted-vs-actual against the real watering record before it
can claim to be better.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.plant_profiles import load_profiles  # noqa: E402
from tools.analytics.predict_bridge import current_arc, segment_rows  # noqa: E402

_US = timedelta(microseconds=1)

# A rate below this is not meaningful drying — projecting it yields absurd horizons.
MIN_RATE_C_PER_H = 1.0
# Never promise beyond this; past it the honest answer is "not soon".
MAX_HORIZON_DAYS = 30.0
# How far back to look for the driest pre-watering reading (covers glug-tap lag).
THRESHOLD_LOOKBACK_H = 3.0
# Thresholds/intervals need at least this many real waterings to be learnable.
MIN_EVENTS_THRESHOLD = 1
MIN_EVENTS_INTERVAL = 2


def personal_threshold(rows, waterings: list) -> tuple[float | None, int]:
    """The raw at which SHE actually waters this plant: the median across waterings
    of the **driest reading in the short window before each one**.

    Not simply "the last reading before the event": a watering instant can land a
    few minutes INTO the pour (her glug taps trail the pour by minutes — measured
    live), and the last row before it would then be a mid-transient raw that badly
    understates the threshold she actually acted on. Raw rises as soil dries, so the
    window's MAX is the driest moment before she intervened — the physical threshold.
    Returns ``(threshold, n_samples)``; ``(None, 0)`` when nothing is learnable."""
    samples = []
    for w in waterings:
        window = [
            r.raw_value
            for r in rows
            if r.raw_value is not None
            and w - timedelta(hours=THRESHOLD_LOOKBACK_H) <= r.timestamp_utc < w
        ]
        if window:
            samples.append(max(window))
            continue
        pre = [
            r.raw_value for r in rows if r.timestamp_utc < w and r.raw_value is not None
        ]
        if pre:
            samples.append(pre[-1])
    if len(samples) < MIN_EVENTS_THRESHOLD:
        return None, 0
    return statistics.median(samples), len(samples)


def median_interval_h(waterings: list) -> tuple[float | None, int]:
    """Her own watering cadence for this plant, in hours — the cold-start model."""
    if len(waterings) < MIN_EVENTS_INTERVAL:
        return None, 0
    gaps = [
        ((b - a) // _US) / 3_600_000_000
        for a, b in zip(waterings, waterings[1:])
        if b > a
    ]
    if not gaps:
        return None, 0
    return statistics.median(gaps), len(gaps)


def predict_plant(
    rows,
    now: datetime,
    waterings: list,
    caveat: str | None = None,
    identity_source: str | None = None,
) -> dict:
    """One plant's next-watering forecast. Always returns a dict — the tier says how
    much to trust it, and ``due_at is None`` is a first-class honest answer."""
    out = {
        "tier": "none",
        "due_at": None,
        "due_in_h": None,
        "due_in_days": None,
        "rate_c_per_h": None,
        "threshold_raw": None,
        "n_events": len(waterings),
        "n_samples": 0,
        "caveat": caveat,
        "identity_source": identity_source,
        "reason": "no watering on record yet — nothing to learn from",
    }
    if not waterings:
        return out

    threshold, n_th = personal_threshold(rows, waterings)
    causal = [r for r in rows if r.timestamp_utc <= now]
    arc = current_arc(segment_rows({"_": causal}, identity_source or "static"))
    rate = (arc or {}).get("rate_c_per_h")

    # Tier 1 — the real prediction: her threshold along the current valid arc.
    if threshold is not None and rate is not None and rate >= MIN_RATE_C_PER_H:
        raw_now = arc["raw_last"]
        remaining = threshold - raw_now
        hours = max(0.0, remaining / rate)
        if hours <= MAX_HORIZON_DAYS * 24:
            # the bridge stores ISO strings (Parquet-safe); parse at the boundary
            arc_end = datetime.fromisoformat(str(arc["t1"]))
            due = arc_end + timedelta(hours=hours)
            out.update(
                tier="rate",
                due_at=due.isoformat(),
                due_in_h=round(hours, 2),
                due_in_days=round(hours / 24, 2),
                rate_c_per_h=round(rate, 2),
                threshold_raw=threshold,
                n_samples=n_th,
                reason="her threshold projected along the current valid drying arc",
            )
            return out
        out["reason"] = "drying so slowly the crossing is beyond the honest horizon"

    # Tier 2 — cold start: her own cadence, no curve required.
    interval, n_iv = median_interval_h(waterings)
    if interval is not None:
        due = waterings[-1] + timedelta(hours=interval)
        hours = ((due - now) // _US) / 3_600_000_000
        out.update(
            tier="interval",
            due_at=due.isoformat(),
            due_in_h=round(hours, 2),
            due_in_days=round(hours / 24, 2),
            threshold_raw=threshold,
            n_samples=n_iv,
            reason=(
                "no usable drying arc yet — her median interval for this plant"
                if rate is None
                else "arc too flat to project — her median interval for this plant"
            ),
        )
        return out

    out["reason"] = "only one watering on record — no interval to learn yet"
    return out


def predict_fn(rows, now: datetime, prior_waterings: list):
    """The #1248 C4 harness adapter: same signature as ``baseline_predictor``,
    returns the predicted instant or None (an abstain the harness counts honestly)."""
    p = predict_plant(rows, now, prior_waterings)
    if p["due_at"] is None:
        return None
    return datetime.fromisoformat(p["due_at"])


def forecast_fleet(
    series: dict,
    actuals: dict,
    now: datetime | None = None,
    profiles: dict | None = None,
) -> dict:
    """Every plant's forecast, keyed by plant_id — the surface-facing payload."""
    profiles = profiles if profiles is not None else {}
    now = now or max(
        (r.timestamp_utc for rows in series.values() for r in rows), default=None
    )
    out = {}
    for pid, rows in sorted(series.items()):
        prof = profiles.get(pid) or {}
        caveat = ((prof.get("hydrology") or {}).get("probe_reading_caveat")) or None
        out[pid] = predict_plant(rows, now, actuals.get(pid, []), caveat)
    return out


def main(argv: list[str] | None = None) -> int:
    from tools.analytics.backtest import actual_waterings, backtest, baseline_predictor
    from tools.analytics.device_registry import load_registry
    from tools.analytics.predict_bridge import (
        _tier_devices,
        resolve_identity,
        series_from_pairs,
    )

    ap = argparse.ArgumentParser(description="#25 the next-watering predictor")
    ap.add_argument("--registry", default=None)
    ap.add_argument("--journal", default=None)
    ap.add_argument("--compare", action="store_true", help="score vs the C4 baseline")
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)

    registry = load_registry(args.registry) if args.registry else None
    pairs, _source = resolve_identity(registry, args.registry, _tier_devices())
    series = series_from_pairs(pairs)
    journal = Path(args.journal) if args.journal else None
    actuals = actual_waterings(series, journal)
    profiles, _ = load_profiles()
    fc = forecast_fleet(series, actuals, profiles=profiles)

    print("plant     tier      due in      rate c/h  threshold  n  caveat")
    for pid, f in fc.items():
        due = "—" if f["due_in_days"] is None else f"{f['due_in_days']:>5.1f} d"
        rate = "—" if f["rate_c_per_h"] is None else f"{f['rate_c_per_h']:+.1f}"
        thr = "—" if f["threshold_raw"] is None else f"{f['threshold_raw']:.0f}"
        print(
            f"{pid:<8}  {f['tier']:<8}  {due:>8}  {rate:>9}  {thr:>9}"
            f"  {f['n_events']}  {f['caveat'] or ''}"
        )

    if args.compare:
        print("\npredicted-vs-actual (C4 harness) — baseline vs #25")
        base = backtest(series, actuals, predictor=baseline_predictor)
        mine = backtest(series, actuals, predictor=predict_fn)
        print("plant     baseline MAE_h   #25 MAE_h   delta   scored(b/25)")
        b_all, m_all = [], []
        for pid in sorted(mine):
            b, m = base.get(pid, {}), mine[pid]
            bm, mm = b.get("mae_h"), m.get("mae_h")
            if bm is not None:
                b_all.append(bm)
            if mm is not None:
                m_all.append(mm)
            d = "—" if (bm is None or mm is None) else f"{mm - bm:+.1f}"
            print(
                f"{pid:<8}  {('—' if bm is None else f'{bm:12.1f}')}"
                f"  {('—' if mm is None else f'{mm:10.1f}')}  {d:>6}"
                f"   {b.get('n_scored', 0)}/{m['n_scored']}"
            )
        if b_all and m_all:
            print(
                f"{'FLEET':<8}  {statistics.mean(b_all):12.1f}"
                f"  {statistics.mean(m_all):10.1f}"
                f"  {statistics.mean(m_all) - statistics.mean(b_all):+6.1f}"
            )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(fc, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
