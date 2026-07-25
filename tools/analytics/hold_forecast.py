#!/usr/bin/env python3
"""#1586 (G5) — the post-watering hold: "this drink should hold ~N days".

A forecast anchored to a detected watering, issued *at the moment of the drink* and
checkable afterwards against what actually happened. That second half is the point:
every watering becomes a **testable** prediction, which is what feeds a real track
record (#1535's R4/G6) instead of a confidence we assert about ourselves.

**Why this cannot use the drying rate, which is the whole design constraint.** At the
instant of a drink the plant is in **rebound** — equilibrating, raw rising, the arc that
`segment_classifier` explicitly excludes from trend fitting because it is a different
physical process. There is no drying slope yet, by construction. So a hold issued at t=0
has exactly one honest source: **how long this plant's previous drinks held**. The rate
extrapolator answers later, once an arc exists; it cannot answer here.

That makes the honest-absence case common and important: a plant's **first** drink
has no prior interval, so there is nothing to predict from. It says so. A default
dressed as a forecast ("~3 days") would be indistinguishable, to the operator, from a
real one — and
would then be scored, polluting the very track record this exists to build.

Causality is enforced rather than assumed: :func:`predict_hold` only ever reads
waterings strictly *before* the anchor. A prediction that peeked at the future is not
a prediction, and this module's output feeds a scorer that would otherwise report the
resulting accuracy as if it meant something.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from tools.analytics.predictor import median_interval_h

# What counts as "the drink held": the operator watered again within this fraction
# of the predicted hold. Generous on purpose — a hold forecast is a planning aid,
# not an alarm clock, and calling a 3-day prediction wrong because she watered at
# 2.6 days would make
# the score say more about her schedule than about the model.
HOLD_TOLERANCE = 0.35


@dataclass(frozen=True)
class HoldPrediction:
    """One issued-at-the-drink forecast, carrying its own basis and sample size so a
    consumer can never mistake a two-cycle guess for a settled one."""

    plant_id: str
    issued_ts: datetime  # the watering this is anchored to
    hold_h: float | None  # predicted hours the drink should last; None = no answer
    basis: str  # "history" | "none"
    n_cycles: int  # completed cycles the estimate rests on
    reason: str  # plain language, rendered verbatim when hold_h is None

    @property
    def hold_days(self) -> float | None:
        """Whole days, FLOORED — 60 h is "about 2 days", never "about 3". Rounding up
        over-promises the exact thing this line promises (Design hit the same edge in
        G3's all-clear and floored it there; same rule, one behaviour)."""
        return None if self.hold_h is None else float(int(self.hold_h // 24))


def predict_hold(
    plant_id: str, waterings: list[datetime], at: datetime
) -> HoldPrediction:
    """The hold forecast for the drink at ``at``, using only what was known then.

    ``waterings`` is that plant's watering instants (the pass-clustered record —
    classifier onsets plus the glug journal, as ``backtest.actual_waterings`` assembles
    it). Only entries strictly before ``at`` are used."""
    prior = sorted(w for w in waterings if w < at)
    interval_h, n_cycles = median_interval_h(prior)
    if interval_h is None:
        return HoldPrediction(
            plant_id,
            at,
            None,
            "none",
            n_cycles,
            (
                "First drink on record — there's no previous cycle to compare, so how "
                "long it holds is genuinely unknown until the next one."
                if not prior
                else "Only one drink on record — two are needed before a cycle exists."
            ),
        )
    return HoldPrediction(
        plant_id,
        at,
        interval_h,
        "history",
        n_cycles,
        f"Based on this plant's own {n_cycles} previous cycle(s).",
    )


def score_hold(p: HoldPrediction, waterings: list[datetime]) -> dict:
    """Did the drink hold? Compares the prediction to the ACTUAL next watering.

    Three outcomes, and the third is not a failure: ``unresolved`` means no watering has
    happened since — the prediction may still come true, so scoring it now would invent
    a verdict. Abstentions (``hold_h is None``) are ``abstained``, never counted as
    wrong; a model that says "I don't know" is behaving correctly and must not be
    punished for it in its own track record (backtest.py draws the same line)."""
    out = {
        "plant_id": p.plant_id,
        "issued_ts": p.issued_ts,
        "predicted_h": p.hold_h,
        "basis": p.basis,
    }
    if p.hold_h is None:
        return {**out, "outcome": "abstained", "actual_h": None, "error_h": None}
    nxt = next((w for w in sorted(waterings) if w > p.issued_ts), None)
    if nxt is None:
        return {**out, "outcome": "unresolved", "actual_h": None, "error_h": None}
    actual_h = (nxt - p.issued_ts) / timedelta(hours=1)
    err = actual_h - p.hold_h
    held = abs(err) <= HOLD_TOLERANCE * p.hold_h
    return {
        **out,
        "outcome": "held" if held else "missed",
        "actual_h": actual_h,
        "error_h": err,
    }


def hold_record(plant_id: str, waterings: list[datetime]) -> dict:
    """Every drink this plant has had, each as a prediction issued at the time and
    scored against what followed — the plant's hold track record.

    Replays causally: each drink is predicted from only the drinks before it, exactly as
    it would have been at the time. That is what makes the resulting accuracy a real
    claim rather than a curve fitted with hindsight."""
    ws = sorted(waterings)
    scored = [score_hold(predict_hold(plant_id, ws, w), ws) for w in ws]
    resolved = [s for s in scored if s["outcome"] in ("held", "missed")]
    errs = [abs(s["error_h"]) for s in resolved]
    return {
        "plant_id": plant_id,
        "n_drinks": len(ws),
        "n_scored": len(resolved),
        "n_held": sum(1 for s in resolved if s["outcome"] == "held"),
        "n_abstained": sum(1 for s in scored if s["outcome"] == "abstained"),
        "n_unresolved": sum(1 for s in scored if s["outcome"] == "unresolved"),
        # None, not 0.0: no scored drinks means no accuracy to report (ADR-0028)
        "mae_h": round(sum(errs) / len(errs), 1) if errs else None,
        "predictions": scored,
    }
