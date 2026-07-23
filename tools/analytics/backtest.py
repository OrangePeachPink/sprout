#!/usr/bin/env python3
"""#1248 — C4: the predicted-vs-actual backtest harness. Replay history through a
predictor and score its forecasts against the actual watering record (glug + detected)
— #25's evaluation loop, and the release's proof that Predict predicts.

- **Causality is the harness's job, not the predictor's honor.** At each prediction
  instant the predictor receives ONLY rows with ``timestamp_utc <= now`` — the harness
  slices; a predictor cannot peek even if it wants to (tested with a probe).
- **Actuals are the operator's record**: per plant, the classifier's watering-transient
  onsets (contract §1) unioned with that plant's glug journal entries, clustered by
  the calibrated PASS gap so a 14-tap session is ONE event, not fourteen.
- **Abstention is honest, and scored as such** (ADR-0028 absence doctrine): a
  predictor returning ``None`` (not enough signal) is counted, never coerced; a
  forecast with no actual-after to compare against is ``unresolved``, never scored.
- **The baseline predictor** (#25 refines it in place): least-squares slope over the
  trailing steady-drying rows of the CURRENT valid segment (taxonomy contract §2 —
  the mask binds forecasts too), projected to the plant's own historical pre-watering
  raw (the median of where the operator ACTUALLY watered before now — humane
  calibration: predict her cadence, never a fleet constant). Exact integer µs
  arithmetic per the store contract §4 doctrine.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.device_registry import load_registry  # noqa: E402
from tools.analytics.segment_classifier import classify, passes  # noqa: E402
from tools.analytics.segment_history import _journal_events, plant_series  # noqa: E402

_US = timedelta(microseconds=1)

# Harness cadence: one prediction attempt per plant per this many hours, only at
# instants where the plant is mid-segment (config, not doctrine).
PREDICT_EVERY_H = 6.0
# Baseline: the trailing steady-drying window the slope is fit over.
FIT_WINDOW_H = 24.0
FIT_MIN_ROWS = 20


def actual_waterings(series: dict, journal: Path | None = None) -> dict[str, list]:
    """Per-plant actual watering instants: classifier transient onsets + that
    plant's glugs, clustered into passes (one session = one event); each plant's
    list is the pass start-times of passes that touched it, sorted."""
    events = []
    for pid, rows in series.items():
        kinds = classify(rows)
        for i in range(1, len(rows)):
            if (
                kinds[i] == "watering-transient"
                and kinds[i - 1] != "watering-transient"
            ):
                events.append((rows[i - 1].timestamp_utc, "soil", pid))
    if journal is not None:
        events.extend(_journal_events(journal))
    out: dict[str, list] = {}
    for p in passes(events):
        for pid in {e[2] for e in p.events if e[2]}:
            out.setdefault(pid, []).append(p.t0)
    for pid in out:
        out[pid].sort()
    return out


def baseline_predictor(rows, now: datetime, prior_waterings: list) -> datetime | None:
    """The #25 starting point: trailing steady-drying slope → the plant's OWN
    historical pre-watering raw. Abstains (None) without a prior watering to learn
    the threshold from, without enough steady rows, or on a non-drying slope."""
    if not prior_waterings:
        return None  # no personal threshold yet — honest abstain, never a guess
    thresholds = []
    for w in prior_waterings:
        pre = [r.raw_value for r in rows if r.timestamp_utc < w][-3:]
        if pre:
            thresholds.append(pre[-1])
    if not thresholds:
        return None
    target = statistics.median(thresholds)
    # Fit ONLY the current inter-watering arc (#1133's boundary, rediscovered by
    # this very harness: a window spanning the watering's level-drop fits a bogus
    # negative slope across two unrelated arcs). Kinds already drop the transient
    # and rebound rows; the time cut keeps the fit to the trailing window.
    cut = max(
        now - timedelta(hours=FIT_WINDOW_H),
        prior_waterings[-1] if prior_waterings else now - timedelta(hours=FIT_WINDOW_H),
    )
    kinds = classify(rows)
    fit = [
        (r.timestamp_utc, r.raw_value)
        for r, k in zip(rows, kinds)
        if k == "steady-drying"
        and cut <= r.timestamp_utc <= now
        and r.raw_value is not None
    ]
    if len(fit) < FIT_MIN_ROWS:
        return None
    t0 = fit[0][0]
    xs = [(t - t0) // _US for t, _ in fit]  # exact integer µs (contract §4)
    ys = [v for _, v in fit]
    n = len(fit)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom  # counts/µs
    if slope <= 0:
        return None  # not drying — no honest crossing to project
    last = fit[-1]
    remaining = target - last[1]
    if remaining <= 0:
        return last[0]  # already at her watering point
    return last[0] + timedelta(microseconds=remaining / slope)


def backtest(
    series: dict,
    actuals: dict[str, list],
    predictor=baseline_predictor,
    predict_every_h: float = PREDICT_EVERY_H,
) -> dict:
    """Replay each plant's history: at each cadence instant, hand the predictor the
    CAUSAL slice + the prior actuals, then score the forecast against the next real
    watering. Returns per-plant {n_attempts, n_scored, n_abstain, n_unresolved,
    mae_h, median_err_h, p90_abs_h, errors_h}."""
    report: dict[str, dict] = {}
    step = timedelta(hours=predict_every_h)
    for pid, rows in sorted(series.items()):
        if not rows:
            continue
        waterings = actuals.get(pid, [])
        stats = {"n_attempts": 0, "n_scored": 0, "n_abstain": 0, "n_unresolved": 0}
        errors: list[float] = []
        now = rows[0].timestamp_utc + step
        end = rows[-1].timestamp_utc
        i = 0
        while now <= end:
            while i < len(rows) and rows[i].timestamp_utc <= now:
                i += 1
            causal = rows[:i]  # the harness enforces causality — never the predictor
            prior = [w for w in waterings if w <= now]
            stats["n_attempts"] += 1
            predicted = predictor(causal, now, prior)
            if predicted is None:
                stats["n_abstain"] += 1
            else:
                nxt = next((w for w in waterings if w > now), None)
                if nxt is None:
                    stats["n_unresolved"] += 1  # no actual to compare — never scored
                else:
                    err_h = ((predicted - nxt) // _US) / 3_600_000_000.0
                    errors.append(err_h)
                    stats["n_scored"] += 1
            now += step
        abs_errs = sorted(abs(e) for e in errors)
        report[pid] = {
            **stats,
            "errors_h": [round(e, 2) for e in errors],
            "mae_h": round(sum(abs_errs) / len(abs_errs), 2) if abs_errs else None,
            "median_err_h": round(statistics.median(errors), 2) if errors else None,
            "p90_abs_h": (
                round(abs_errs[min(len(abs_errs) - 1, int(0.9 * len(abs_errs)))], 2)
                if abs_errs
                else None
            ),
        }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1248 C4: predicted-vs-actual backtest")
    ap.add_argument("--registry", default=None)
    ap.add_argument("--journal", default=None)
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)
    registry = load_registry(args.registry) if args.registry else None
    series, _unmapped = plant_series(registry=registry)
    journal = Path(args.journal) if args.journal else None
    actuals = actual_waterings(series, journal)
    report = backtest(series, actuals)
    print("plant     attempts  scored  abstain  unresolved  MAE_h  median_err_h  p90_h")
    for pid, m in report.items():
        mae = "—" if m["mae_h"] is None else f"{m['mae_h']:.1f}"
        med = "—" if m["median_err_h"] is None else f"{m['median_err_h']:+.1f}"
        p90 = "—" if m["p90_abs_h"] is None else f"{m['p90_abs_h']:.1f}"
        print(
            f"{pid:<8}  {m['n_attempts']:>8}  {m['n_scored']:>6}  {m['n_abstain']:>7}"
            f"  {m['n_unresolved']:>10}  {mae:>5}  {med:>12}  {p90:>5}"
        )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
