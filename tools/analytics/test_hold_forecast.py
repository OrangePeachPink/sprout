#!/usr/bin/env python3
"""#1586 (G5) — the post-watering hold is causal, honest when it can't answer, and
scored.

The value of G5 is not the sentence "this drink should hold ~3 days" — it is that the
sentence is **checkable afterwards**, which is what turns every watering into evidence
for a real track record instead of a confidence we assert about ourselves.

So these tests pin the three properties that make the record trustworthy: predictions
use only what was known at the time, an absent answer is stated rather than defaulted,
and abstentions/unresolved outcomes are never scored as wrong.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.analytics.hold_forecast import (
    hold_record,
    predict_hold,
    score_hold,
)

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _days(*ds: float) -> list[datetime]:
    return [T0 + timedelta(days=d) for d in ds]


# --------------------------------------------------------------------------- #
# causality — a prediction that peeked at the future is not a prediction
# --------------------------------------------------------------------------- #
def test_only_waterings_before_the_anchor_are_used() -> None:
    """The drink at day 10 must be predicted from days 0/5 alone. If the day-20 drink
    leaked in, the 'prediction' would be fitted with hindsight and the track record
    built on it would be meaningless."""
    ws = _days(0, 5, 10, 20)
    p = predict_hold("p01", ws, at=ws[2])
    assert p.hold_h == 5 * 24  # median of the single prior gap (0 -> 5)
    assert p.n_cycles == 1


def test_a_later_watering_cannot_change_an_earlier_prediction() -> None:
    early = predict_hold("p01", _days(0, 5, 10), at=T0 + timedelta(days=10))
    with_future = predict_hold(
        "p01", _days(0, 5, 10, 11, 12), at=T0 + timedelta(days=10)
    )
    assert early.hold_h == with_future.hold_h


# --------------------------------------------------------------------------- #
# honest absence — the first drink genuinely cannot be predicted
# --------------------------------------------------------------------------- #
def test_the_first_drink_gets_no_number_and_says_why() -> None:
    """A default dressed as a forecast would be indistinguishable to the operator from
    a real one — and would then be scored, polluting the record it exists to build."""
    p = predict_hold("p01", _days(0), at=T0)
    assert p.hold_h is None and p.hold_days is None
    assert p.basis == "none" and p.n_cycles == 0
    assert "first drink" in p.reason.lower()


def test_one_prior_drink_is_still_not_a_cycle() -> None:
    p = predict_hold("p01", _days(0, 5), at=T0 + timedelta(days=5))
    assert p.hold_h is None
    assert "two are needed" in p.reason.lower()


def test_two_prior_drinks_make_a_prediction_with_its_sample_size() -> None:
    p = predict_hold("p01", _days(0, 5, 10), at=T0 + timedelta(days=10))
    assert p.hold_h == 5 * 24 and p.basis == "history" and p.n_cycles == 1


# --------------------------------------------------------------------------- #
# the days figure floors, matching G3's all-clear
# --------------------------------------------------------------------------- #
def test_days_floor_rather_than_round_up() -> None:
    """60 h is "about 2 days", never 3 — rounding up over-promises the precise thing
    this line promises (same rule Design floored in G3)."""
    ws = [T0, T0 + timedelta(hours=60), T0 + timedelta(hours=120)]
    p = predict_hold("p01", ws, at=ws[2])
    assert p.hold_h == 60.0
    assert p.hold_days == 2.0


# --------------------------------------------------------------------------- #
# scoring — abstain and unresolved are not failures
# --------------------------------------------------------------------------- #
def test_a_drink_that_held_scores_held() -> None:
    ws = _days(0, 5, 10, 15)
    p = predict_hold("p01", ws, at=ws[2])  # predicts 5 days
    s = score_hold(p, ws)
    assert s["outcome"] == "held" and s["actual_h"] == 5 * 24 and s["error_h"] == 0


def test_a_drink_that_ran_out_early_scores_missed_with_the_error() -> None:
    ws = _days(0, 10, 20, 22)  # predicted 10 days, actually needed at 2
    p = predict_hold("p01", ws, at=ws[2])
    s = score_hold(p, ws)
    assert s["outcome"] == "missed"
    assert s["error_h"] < 0  # actual came sooner than predicted


def test_no_watering_since_is_UNRESOLVED_never_wrong() -> None:
    """The prediction may still come true; scoring it now would invent a verdict."""
    ws = _days(0, 5, 10)
    s = score_hold(predict_hold("p01", ws, at=ws[2]), ws)
    assert s["outcome"] == "unresolved" and s["error_h"] is None


def test_an_abstention_is_never_counted_as_wrong() -> None:
    """A model that says "I don't know" is behaving correctly and must not be punished
    for it in its own track record."""
    ws = _days(0, 5)
    s = score_hold(predict_hold("p01", ws, at=ws[0]), ws)
    assert s["outcome"] == "abstained" and s["error_h"] is None


# --------------------------------------------------------------------------- #
# the record
# --------------------------------------------------------------------------- #
def test_the_record_replays_every_drink_causally() -> None:
    ws = _days(0, 5, 10, 15, 20)
    rec = hold_record("p01", ws)
    assert rec["n_drinks"] == 5
    # drinks 1 and 2 can't be predicted; 3 and 4 resolve; 5 has nothing after it
    assert rec["n_abstained"] == 2
    assert rec["n_scored"] == 2
    assert rec["n_unresolved"] == 1
    assert rec["n_held"] == 2  # a perfectly regular 5-day cadence
    assert rec["mae_h"] == 0.0


def test_a_record_with_nothing_scored_reports_no_accuracy_not_zero() -> None:
    """ADR-0028: `mae_h` of None means "no answer yet". 0.0 would read as perfect."""
    rec = hold_record("p01", _days(0, 5))
    assert rec["n_scored"] == 0 and rec["mae_h"] is None


def test_a_wrong_prediction_is_recorded_as_wrong_not_softened() -> None:
    """A steady 5-day plant that then goes 20 days: the drink at day 10 predicted 5 and
    was badly wrong, and the record must say so. A track record that only ever reports
    successes is worth nothing — the point of scoring is that it can come back negative.

    (An earlier version of this test asserted that any IRREGULAR plant must miss. That
    was wrong: irregularity doesn't guarantee a miss on any particular drink, and the
    fixture I picked happened to predict one correctly. The code was right; the test's
    premise wasn't.)"""
    ws = _days(0, 5, 10, 30)
    rec = hold_record("p01", ws)
    scored = [s for s in rec["predictions"] if s["outcome"] in ("held", "missed")]
    assert len(scored) == 1
    assert scored[0]["outcome"] == "missed"
    assert scored[0]["predicted_h"] == 5 * 24
    assert scored[0]["actual_h"] == 20 * 24
    assert rec["n_held"] == 0
    assert rec["mae_h"] == 15 * 24  # 15 days out, reported plainly
