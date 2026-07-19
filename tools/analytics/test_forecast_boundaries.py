"""#1095 — the forecast boundary helpers: next_drier_boundary() + thirsty_boundary().

Two tiny pure helpers off a descending cal-bounds list (forecast.py). No fixtures. The
line-fit and ETA gate are tested elsewhere; these two edges weren't, so this locks them:
the "next drier edge" is the smallest bound *strictly* above the raw (or None past the
driest), and the "thirsty" trigger is the third descending edge (the needs-water floor).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from forecast import next_drier_boundary, thirsty_boundary
from parse_v1 import DEFAULT_CAL_BOUNDS

B = list(DEFAULT_CAL_BOUNDS)  # [3050, 2140, 1830, 1520, 1150, 1050]


def test_next_drier_boundary_is_the_smallest_edge_above_the_raw() -> None:
    assert next_drier_boundary(1600, B) == 1830  # smallest bound > 1600
    assert next_drier_boundary(2000, B) == 2140
    assert next_drier_boundary(1000, B) == 1050  # below the wettest edge -> that edge


def test_next_drier_boundary_is_strict_not_inclusive() -> None:
    # AT an edge, the returned edge is the NEXT one up (strictly above): 1830 -> 2140.
    assert next_drier_boundary(1830, B) == 2140
    assert next_drier_boundary(1829, B) == 1830


def test_next_drier_boundary_is_none_past_the_driest_edge() -> None:
    assert next_drier_boundary(3050, B) is None  # nothing strictly above the driest
    assert next_drier_boundary(3100, B) is None


def test_thirsty_boundary_is_the_third_descending_edge() -> None:
    # the needs-water lower edge = the A2 watering-trigger proxy (index 2, descending).
    assert thirsty_boundary(B) == 1830
    assert thirsty_boundary(list(reversed(B))) == 1830  # it sorts descending itself


def test_thirsty_boundary_falls_back_on_a_short_list() -> None:
    # documented fallback: fewer than 3 edges -> the last (driest-available) edge.
    assert thirsty_boundary([2000, 1000]) == 1000
    assert thirsty_boundary([500]) == 500
