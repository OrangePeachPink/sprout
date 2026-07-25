"""#1598 — the R3 confidence vocabulary has ONE home, and these are its ratified values.

The thresholds and words are a maintainer-ratified design decision recorded in
``docs/design/foundations/confidence-vocabulary.md``. R3 shipped the classifier as a
template-local ternary; the attention model (#1592) made *Watch* a second consumer,
and two copies of a ruled vocabulary drift silently until the doc is authority for
neither.

These pins exist so a future edit to one surface cannot quietly re-decide the words:
changing a boundary or a word should require changing the doc — a maintainer call, not a
refactor.
"""

from __future__ import annotations

from tools.analytics.card_payload import (
    CONFIDENCE_FIRM_MAX,
    CONFIDENCE_ROUGH_MAX,
    confidence_word,
    next_need_from_forecast,
)


def test_the_ratified_boundaries_are_the_doc_values() -> None:
    # docs/design/foundations/confidence-vocabulary.md: w <= 0.15 FIRM, w <= 0.50 ROUGH.
    assert CONFIDENCE_FIRM_MAX == 0.15
    assert CONFIDENCE_ROUGH_MAX == 0.50


def test_the_three_words_and_their_bands() -> None:
    # width = (hi - lo) / hours — relative, so a wide span on a far forecast is not the
    # same claim as the same span on a near one.
    assert confidence_word(9.1, 8.6, 9.7) == "FIRM"  # ~0.12
    assert confidence_word(53.3, 47.6, 60.5) == "ROUGH"  # ~0.24
    assert confidence_word(40, 20, 70) == "HAZY"  # ~1.25


def test_the_boundaries_are_inclusive_on_the_tighter_side() -> None:
    # exactly at a boundary belongs to the TIGHTER word — the doc writes `w <= 0.15`.
    assert confidence_word(100, 92.5, 107.5) == "FIRM"  # w == 0.15 exactly
    assert confidence_word(100, 75.0, 125.0) == "ROUGH"  # w == 0.50 exactly


def test_no_span_makes_no_claim() -> None:
    """The rule easiest to lose in an extraction that returns a string unconditionally:
    a midpoint with no computable span makes NO how-sure claim (ADR-0028 absence)."""
    assert confidence_word(41, None, None) is None
    assert confidence_word(41, 50, 50) is None  # degenerate span is not an interval
    assert confidence_word(None, 1, 2) is None
    assert confidence_word(0, 1, 2) is None


def test_the_payload_carries_the_word_for_both_consumers() -> None:
    """The card chip and the attention model's Watch level read the SAME field."""
    nn = next_need_from_forecast(
        {
            "thirsty": {
                "reachable": True,
                "hours": 53.3,
                "hours_lo": 47.6,
                "hours_hi": 60.5,
            }
        }
    )
    assert nn["confidence_word"] == "ROUGH"
    # ...and a forecast with no interval carries None, never a manufactured word.
    bare = next_need_from_forecast({"thirsty": {"reachable": True, "hours": 41}})
    assert bare["confidence_word"] is None
