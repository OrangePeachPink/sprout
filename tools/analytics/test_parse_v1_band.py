"""#1094 — band_for_raw(): the pure raw-ADC -> band-name classifier (parse_v1).

Table-driven against the CURRENT shipped cal bounds + band vocabulary. The #995/#1174
ratification may re-partition / re-name the bands under this, so the test references the
module's OWN band constants (never hardcoded names) — a rename won't break it. What it
locks is the threshold CONTRACT: a descending-bounds scan where ``raw >= edge`` picks
that band (equality inclusive), a raw below the wettest edge falls to the wettest band,
and ``None -> None``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import (
    BANDS_DRY_TO_WET,
    BANDS_WET_TO_DRY,
    DEFAULT_CAL_BOUNDS,
    band_for_raw,
)

DRIEST = BANDS_DRY_TO_WET[0]  # current shipped: "air-dry"
WETTEST = BANDS_WET_TO_DRY[0]  # current shipped: "submerged"


def test_none_raw_is_none() -> None:
    assert band_for_raw(None) is None


def test_dry_endpoint_at_and_above_the_driest_edge() -> None:
    dry_edge = DEFAULT_CAL_BOUNDS[0]  # 3050
    assert band_for_raw(dry_edge) == DRIEST  # equality is inclusive (>=)
    assert band_for_raw(dry_edge + 1000) == DRIEST  # anything drier stays driest


def test_wet_endpoint_below_the_wettest_edge_falls_to_wettest() -> None:
    wet_edge = DEFAULT_CAL_BOUNDS[-1]  # 1050
    assert band_for_raw(wet_edge - 1) == WETTEST  # one count below the last edge
    assert band_for_raw(0) == WETTEST  # a floating / near-zero raw


def test_each_descending_edge_picks_its_own_band_inclusive() -> None:
    # boundary-equality across the whole ladder: raw == edge[i] -> BANDS_DRY_TO_WET[i]
    # (>= is inclusive), and one count below flips to the next-wetter band.
    for i, edge in enumerate(DEFAULT_CAL_BOUNDS):
        assert band_for_raw(edge) == BANDS_DRY_TO_WET[i]
        below = BANDS_DRY_TO_WET[i + 1] if i + 1 < len(DEFAULT_CAL_BOUNDS) else WETTEST
        assert band_for_raw(edge - 1) == below


def test_a_custom_bounds_list_overrides_the_default() -> None:
    # the classifier is driven by the caller's cal bounds, not tied to the default.
    b = (3000, 2000, 1000, 800, 600, 400)
    assert band_for_raw(3000, b) == BANDS_DRY_TO_WET[0]
    assert band_for_raw(999, b) == BANDS_DRY_TO_WET[3]  # >= 800, < 1000
    assert band_for_raw(399, b) == WETTEST
