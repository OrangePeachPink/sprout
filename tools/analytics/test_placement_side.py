#!/usr/bin/env python3
"""#1188 AC2 - structured placement on the temporal move (ADR-0029).

AC1 (PR #1470, Design) made a location edit present as a move with a temporal boundary,
but the placement was free-text. This is the model half AC2 needs: the move carries
structured ``side`` (left/right - ADR-0029 placement.ledge) and ``window``, so Design's
control writes structured placement instead of encoding it in a location string.

The load-bearing test is the **one-vocabulary seam**: ``side`` here, ``side`` on the
device (#806), and the ADR-0029 profile's ``placement.ledge`` must be the SAME two
values. A fourth copy that drifted would let a plant read ``left`` on the editor and
resolve ``right`` from its device - the two-truths shape the register exists to catch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry_model import (
    SIDE_VALUES,
    Plant,
    RegistryModel,
    apply_operations,
    load_model,
    registry_payload,
    save_model,
)

T1 = "2026-07-10T00:00:00Z"
T2 = "2026-07-20T00:00:00Z"


def test_a_move_carries_structured_side_and_window() -> None:
    m = RegistryModel(plants=[Plant(plant_id="p01", location="kitchen (right)")])
    ev = m.move_plant("p01", "bedroom shelf", side="left", window="north", now=T2)
    assert ev.side == "left" and ev.window == "north"
    assert ev.location == "bedroom shelf"  # free-text still carried (interim coexists)


def test_a_mistyped_side_is_rejected_not_silently_persisted() -> None:
    """A wrong ledge that persisted would put the plant on the wrong side for its whole
    context history - so it is a ValueError at the boundary, not a stored typo."""
    m = RegistryModel(plants=[Plant(plant_id="p01", location="x")])
    with pytest.raises(ValueError, match="side must be one of"):
        m.move_plant("p01", "y", side="middle", now=T2)


def test_a_move_may_still_be_free_text_only_backward_compatible() -> None:
    """The interim PR #1179 shape - a move with no structured placement - stays valid,
    so an old event and a control that hasn't adopted the fields both work."""
    m = RegistryModel(plants=[Plant(plant_id="p01", location="x")])
    ev = m.move_plant("p01", "y", now=T2)
    assert ev.side is None and ev.window is None


def test_structured_placement_round_trips_through_save_load(tmp_path: Path) -> None:
    m = RegistryModel(plants=[Plant(plant_id="p01", location="x")])
    m.move_plant("p01", "windowsill", side="right", window="south", now=T2)
    path = tmp_path / "reg.json"
    save_model(m, path)
    back = load_model(path)
    (ev,) = [e for e in back.location_events if e.is_open]
    assert (ev.side, ev.window) == ("right", "south")


def test_the_move_boundary_still_closes_the_old_spot() -> None:
    """AC1's guarantee is untouched by the structured fields: the old spot closes,
    history is preserved, exactly one open event remains."""
    m = RegistryModel(plants=[Plant(plant_id="p01", location="kitchen")])
    m.move_plant("p01", "bedroom", side="left", now=T2)
    hist = m.location_history("p01")
    assert sum(1 for e in hist if e.is_open) == 1
    assert any(e.end_ts == T2 for e in hist)  # the grandfathered prior spot closed


def test_the_apply_seam_carries_side_window_on_a_location_edit() -> None:
    """The editor path (plants.edit with a location change) routes structured placement
    through move_plant, and the payload surfaces it for Design's control."""
    m = RegistryModel(plants=[Plant(plant_id="p01", location="kitchen")])
    r = apply_operations(
        m,
        {
            "plants": {
                "edit": [
                    {
                        "plant_id": "p01",
                        "location": "bedroom",
                        "side": "left",
                        "window": "north",
                    }
                ]
            }
        },
        now=T2,
    )
    assert r["ok"], r.get("errors")
    doc = registry_payload(m)
    latest = next(e for e in doc["location_history"]["p01"] if e["end_ts"] is None)
    assert latest["side"] == "left" and latest["window"] == "north"


def test_the_payload_carries_side_and_window_absent_safe() -> None:
    m = RegistryModel(plants=[Plant(plant_id="p01", location="x")])
    m.move_plant("p01", "y", now=T2)  # no structured placement
    doc = registry_payload(m)
    ev = doc["location_history"]["p01"][-1]
    assert ev["side"] is None and ev["window"] is None  # present, absent-safe


def test_side_vocabulary_is_the_one_shared_ledge_vocabulary() -> None:
    """The seam. The move's side, #806's device side, and ADR-0029's profile ledge are
    ONE vocabulary - pinned here so a fourth copy can never drift them apart."""
    from plant_profiles import ENUMS

    assert ENUMS["placement.ledge"] == SIDE_VALUES, (
        "the move's side vocabulary diverged from ADR-0029's placement.ledge - one "
        "physical concept must not have two value sets (#1188 / the register)"
    )
