"""Tests for the cross-board comparability guard (#832)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cross_board as cb


def test_single_board_raw_is_comparable() -> None:
    assert cb.raw_comparable(["classic", "classic", "classic"]) is True


def test_multi_board_raw_is_not_comparable() -> None:
    # the classic ESP32 and the C5 have different ADCs — different rulers.
    assert cb.raw_comparable(["classic", "c5"]) is False


def test_dryness_follows_raw() -> None:
    # dryness rides one mrange, so it is comparable exactly where raw is.
    assert cb.dryness_comparable(["classic", "c5"]) is False
    assert cb.dryness_comparable(["classic", "classic"]) is True


def test_empty_and_none_are_trivially_comparable() -> None:
    assert cb.raw_comparable([]) is True
    assert cb.raw_comparable([None, None]) is True
    assert cb.raw_comparable(["a", None]) is True  # one real board


def test_cross_board_detects_multiple_boards() -> None:
    assert cb.cross_board(["classic", "c5"]) is True
    assert cb.cross_board(["classic", "classic"]) is False
    assert cb.cross_board([]) is False
    assert cb.cross_board([None]) is False


def test_band_is_the_declared_cross_board_layer() -> None:
    # doctrine: compare across boards by band, never raw/dryness or an invented %.
    assert cb.BAND_IS_THE_CROSS_BOARD_LAYER is True
