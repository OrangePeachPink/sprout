"""#1339 / ADR-0035 §4 (amended) — above the Faint-ceiling the band is WITHHELD,
never clamped. At-ceiling and above-ceiling must render distinctly."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import (
    BOARD_CLASS_CEILING,
    DEFAULT_CAL_BOUNDS,
    DRIER_THAN_CALIBRATED,
    band_for_raw,
    board_class,
    range_exception,
)

CLASSIC = BOARD_CLASS_CEILING["classic"]  # 2500, ratified #1174
C5 = BOARD_CLASS_CEILING["c5"]  # 2213, measured on its own envelope


def test_the_ratified_ceilings_are_consumed_not_reinvented() -> None:
    assert CLASSIC == 2500 and C5 == 2213
    assert BOARD_CLASS_CEILING[board_class("esp32dev")] == CLASSIC
    assert BOARD_CLASS_CEILING[board_class("esp32-c5-devkitc-1")] == C5


def test_at_ceiling_and_above_ceiling_render_DISTINCTLY() -> None:
    # the defect this closes: "drier than anything we've measured" and "at the dry
    # ceiling" currently render identically, so the clamp hides the extreme
    at = band_for_raw(CLASSIC, DEFAULT_CAL_BOUNDS, CLASSIC)
    above = band_for_raw(CLASSIC + 1, DEFAULT_CAL_BOUNDS, CLASSIC)
    assert at == "air-dry"  # the top in-soil band, unchanged
    assert above is None  # WITHHELD — not clamped to air-dry
    assert at != above


def test_the_exception_is_the_range_family_token_not_an_eighth_band() -> None:
    assert range_exception(CLASSIC + 1, CLASSIC) == DRIER_THAN_CALIBRATED
    assert range_exception(CLASSIC, CLASSIC) is None  # at ceiling is IN the envelope
    # the token is off-ladder: it never appears among the seven band names
    from parse_v1 import BANDS_WET_TO_DRY

    assert DRIER_THAN_CALIBRATED not in BANDS_WET_TO_DRY
    assert len(BANDS_WET_TO_DRY) == 7  # no eighth mood was minted


def test_the_xxl_torture_test_is_the_documented_evidence_case() -> None:
    # p02 (Pothos XXL) ran 2,847-2,971 across 07-04 -> 07-06 while the maintainer
    # deliberately explored its recovery limit. An experiment working, not a cal
    # failure — every one of those readings must withhold rather than clamp.
    for raw in (2847, 2900, 2971):
        assert band_for_raw(raw, DEFAULT_CAL_BOUNDS, CLASSIC) is None
        assert range_exception(raw, CLASSIC) == DRIER_THAN_CALIBRATED


def test_the_c5_withholds_on_its_OWN_ceiling_not_the_classics() -> None:
    # 2300 is above the C5's envelope but well inside the classic's
    assert band_for_raw(2300, DEFAULT_CAL_BOUNDS, C5) is None
    assert range_exception(2300, C5) == DRIER_THAN_CALIBRATED
    assert band_for_raw(2300, DEFAULT_CAL_BOUNDS, CLASSIC) == "air-dry"
    assert range_exception(2300, CLASSIC) is None


def test_the_ceiling_does_not_move_the_ladder() -> None:
    # the amendment defines behaviour ABOVE the ceiling; it must not reopen it
    assert DEFAULT_CAL_BOUNDS == (2293, 2086, 1879, 1636, 1393, 1150)
    for raw in (1200, 1500, 1900, 2100, 2293, 2400):
        assert band_for_raw(raw, DEFAULT_CAL_BOUNDS, CLASSIC) == band_for_raw(
            raw, DEFAULT_CAL_BOUNDS
        )


def test_opting_out_keeps_the_historical_behaviour() -> None:
    # ceiling=None is the un-migrated caller: additive, nothing breaks under it
    assert band_for_raw(2971, DEFAULT_CAL_BOUNDS) == "air-dry"
    assert range_exception(2971, None) is None


def test_absent_raw_stays_absent_never_an_exception() -> None:
    assert band_for_raw(None, DEFAULT_CAL_BOUNDS, CLASSIC) is None
    assert range_exception(None, CLASSIC) is None
