"""#1335 slice 1 — the identity projection (ADR-0038 §4).

Characterization first (ADR-0038 §6): these pin what identity resolution *currently*
answers, so the consumer migration in slice 2 can be proven behaviour-preserving rather
than hoped to be. The defect being foreclosed is #1315 — a second identity path living
in a template, which the host fold could not reach.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from plant_identity import IdentityProjection, resolve_plant
from registry_model import Assignment, Plant, RegistryModel, Sensor

T1 = "2026-07-01T00:00:00Z"
T2 = "2026-07-10T00:00:00Z"
T3 = "2026-07-20T00:00:00Z"


def _model() -> RegistryModel:
    """A probe reassigned mid-window: p01 until T2, p02 after — the Gertrude case."""
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


def test_current_binding_is_the_open_one() -> None:
    assert resolve_plant("dev", "ch0", model=_model()) == "p02"


def test_a_reading_is_attributed_to_who_was_there_then() -> None:
    """The whole reason at_time exists: a reading taken before the move belongs to the
    plant that was on the probe *then*, not whoever is there now."""
    m = _model()
    assert resolve_plant("dev", "ch0", "2026-07-05T00:00:00Z", model=m) == "p01"
    assert resolve_plant("dev", "ch0", T3, model=m) == "p02"


def test_the_boundary_instant_belongs_to_the_new_binding() -> None:
    """close-then-open share a timestamp; the instant itself must resolve
    once, not twice."""
    assert resolve_plant("dev", "ch0", T2, model=_model()) == "p02"


def test_before_any_binding_is_none_not_a_guess() -> None:
    assert resolve_plant("dev", "ch0", "2026-06-01T00:00:00Z", model=_model()) is None


def test_unknown_channel_is_none() -> None:
    """A declared-but-unplanted port is a real state (ADR-0028), never an error."""
    assert resolve_plant("dev", "ch3", model=_model()) is None
    assert resolve_plant("nosuch", "ch0", model=_model()) is None


def test_grandfathered_start_is_open_to_the_past() -> None:
    """ADR-0027: start_ts=None means "it WAS there, we don't know since when" — which
    must still resolve, not refuse."""
    m = RegistryModel(
        plants=[Plant(plant_id="p09", pet_name="Old-timer")],
        sensors=[Sensor(sensor_id="s9")],
        assignments=[
            Assignment(plant_id="p09", sensor_id="s9", device_id="dev", channel="ch1")
        ],
    )
    assert resolve_plant("dev", "ch1", "2020-01-01T00:00:00Z", model=m) == "p09"
    assert resolve_plant("dev", "ch1", model=m) == "p09"


def test_projection_map_omits_unmapped_channels() -> None:
    """A caller iterating the map never has to tell "unmapped" from "mapped
    to nothing"."""
    proj = IdentityProjection(model=_model())
    assert proj.as_map() == {("dev", "ch0"): "p02"}


def test_projection_at_time_is_the_historical_view() -> None:
    proj = IdentityProjection(model=_model(), at_time="2026-07-05T00:00:00Z")
    assert proj.as_map() == {("dev", "ch0"): "p01"}


def test_module_stays_in_layer_1() -> None:
    """ADR-0038's layer table: identity may not import analysis, application or
    delivery. A regression here is the boundary eroding, which is how two truths got in
    last time."""
    src = (Path(__file__).resolve().parent / "plant_identity.py").read_text(
        encoding="utf-8"
    )
    forbidden_imports = (
        "import dashboard",
        "import serve",
        "import card_payload",
        "import multiplant_history",
        "import cycle_range",
    )
    for forbidden in forbidden_imports:
        assert forbidden not in src, f"layer violation: {forbidden}"
