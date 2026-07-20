"""#1335 — semantic pins for the one identity implementation (ADR-0038 §4).

Added coverage on `identity.py` (Data's module, the merged base). These pins were
written independently against a parallel implementation before the collision ruling;
porting them here is the useful residue — **two implementations converging on the same
answers is much better evidence the semantics are right than either one alone.**

Ten of the twelve agree with the base exactly, and are kept as regression pins: they
now protect behaviour that two people arrived at separately.

The last two document confirmed FORKS, marked `xfail(strict=True)` so they fail loudly
if the behaviour changes without a decision, and pass the moment the fork is resolved
in the direction the legacy path already takes. Decision list is on #1335.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from identity import build_projection
from registry_model import (
    Assignment,
    Plant,
    RegistryModel,
    Sensor,
)

T1 = "2026-07-01T00:00:00Z"
T2 = "2026-07-10T00:00:00Z"
T3 = "2026-07-20T00:00:00Z"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _reassigned() -> RegistryModel:
    """A probe reassigned mid-window: p01 until T2, p02 after — the Gertrude case
    the #1335 spec is built around."""
    return RegistryModel(
        plants=[
            Plant(plant_id="p01", pet_name="Big Green"),
            Plant(plant_id="p02", pet_name="Gertrude"),
        ],
        sensors=[Sensor(sensor_id="s1")],
        assignments=[
            Assignment(
                plant_id="p01",
                sensor_id="s1",
                device_id="dev",
                channel="ch0",
                start_ts=T1,
                end_ts=T2,
            ),
            Assignment(
                plant_id="p02",
                sensor_id="s1",
                device_id="dev",
                channel="ch0",
                start_ts=T2,
            ),
        ],
    )


# --------------------------------------------------------------------------- #
# Agreed semantics — kept as regression pins
# --------------------------------------------------------------------------- #
def test_current_binding_is_the_open_one() -> None:
    assert build_projection(model=_reassigned()).resolve_plant("dev", "ch0") == "p02"


def test_a_reading_is_attributed_to_who_was_there_then() -> None:
    """The reason at_time exists: a reading taken before the move belongs to the plant
    that was on the probe THEN, not whoever is there now. This is the #1315 class."""
    p = build_projection(model=_reassigned())
    assert p.resolve_plant("dev", "ch0", _dt("2026-07-05T00:00:00Z")) == "p01"
    assert p.resolve_plant("dev", "ch0", _dt(T3)) == "p02"


def test_the_boundary_instant_belongs_to_the_new_binding() -> None:
    """close-then-open share a timestamp; the half-open interval means exactly one
    binding covers that instant — never zero, never both."""
    assert (
        build_projection(model=_reassigned()).resolve_plant("dev", "ch0", _dt(T2))
        == "p02"
    )


def test_before_any_binding_is_none_not_a_guess() -> None:
    assert (
        build_projection(model=_reassigned()).resolve_plant(
            "dev", "ch0", _dt("2026-06-01T00:00:00Z")
        )
        is None
    )


def test_unknown_channel_or_device_is_none() -> None:
    """A declared-but-unplanted port is a real state (ADR-0028), never an error."""
    p = build_projection(model=_reassigned())
    assert p.resolve_plant("dev", "ch3") is None
    assert p.resolve_plant("nosuch", "ch0") is None


def test_grandfathered_start_is_open_to_the_past() -> None:
    """ADR-0027: start_ts=None means "it WAS there, we don't know since when" — which
    must resolve, not refuse."""
    m = RegistryModel(
        plants=[Plant(plant_id="p09", pet_name="Old-timer")],
        sensors=[Sensor(sensor_id="s9")],
        assignments=[
            Assignment(plant_id="p09", sensor_id="s9", device_id="dev", channel="ch1")
        ],
    )
    p = build_projection(model=m)
    assert p.resolve_plant("dev", "ch1", _dt("2020-01-01T00:00:00Z")) == "p09"
    assert p.resolve_plant("dev", "ch1") == "p09"


def test_current_map_omits_unmapped_channels() -> None:
    """A caller iterating the map never has to tell "unmapped" from "mapped to
    nothing"."""
    assert build_projection(model=_reassigned()).current() == {("dev", "ch0"): "p02"}


# --------------------------------------------------------------------------- #
# Confirmed forks — decision list on #1335
# --------------------------------------------------------------------------- #
@pytest.mark.xfail(
    strict=True,
    reason="#1335 fork 1: the projection resolves a DELETED plant as current, where "
    "registry_model.open_assignments() excludes it ('a deleted entity has no current "
    "mapping'). Since the projection REPLACES that path, this is a regression: delete "
    "a plant and it keeps appearing on its channel. Awaiting the Data/Trellis ruling.",
)
def test_a_deleted_plant_has_no_current_binding() -> None:
    m = RegistryModel(
        plants=[Plant(plant_id="p01", pet_name="Gone", lifecycle="deleted")],
        sensors=[Sensor(sensor_id="s1")],
        assignments=[
            Assignment(
                plant_id="p01",
                sensor_id="s1",
                device_id="dev",
                channel="ch0",
                start_ts=T1,
            )
        ],
    )
    # the path being replaced says None; the projection should agree
    assert m.current_for_channel("dev", "ch0") is None
    assert build_projection(model=m).resolve_plant("dev", "ch0") is None


@pytest.mark.xfail(
    strict=True,
    reason="#1335 fork 2: with two overlapping OPEN bindings the projection returns "
    "the first in list order; the safer rule is latest-start-wins. Defensive only — "
    "assign() closes before it opens, so overlaps shouldn't exist — but 'shouldn't "
    "exist' is how the first-match answer stays untested. Awaiting the ruling.",
)
def test_overlapping_bindings_prefer_the_latest_start() -> None:
    m = RegistryModel(
        plants=[Plant(plant_id="pA"), Plant(plant_id="pB")],
        sensors=[Sensor(sensor_id="s1")],
        assignments=[
            Assignment(
                plant_id="pA",
                sensor_id="s1",
                device_id="dev",
                channel="ch0",
                start_ts=T1,
            ),
            Assignment(
                plant_id="pB",
                sensor_id="s1",
                device_id="dev",
                channel="ch0",
                start_ts=T2,
            ),
        ],
    )
    assert build_projection(model=m).resolve_plant("dev", "ch0") == "pB"
