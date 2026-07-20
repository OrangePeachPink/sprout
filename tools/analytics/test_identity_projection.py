"""#1335 slice 1 — the projection: one identity read path that reconciles token
generation (#1315), time (#1331), and which-registry, per ADR-0038 §4."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from identity import Binding, Projection, build_projection, resolve_plant
from registry_model import Assignment, Plant, RegistryModel

T = lambda h: datetime(2026, 7, 10, h, 0, 0, tzinfo=timezone.utc)  # noqa: E731


def _model(*assignments) -> RegistryModel:
    return RegistryModel(
        plants=[Plant(plant_id="p11", pet_name="Corn")],
        assignments=list(assignments),
    )


def test_token_generations_resolve_to_the_same_channel() -> None:
    # #1315: a v4 sN token and a v5 chN token name the SAME physical channel
    proj = build_projection(
        _model(
            Assignment(plant_id="p11", sensor_id="s1", device_id="d1", channel="ch2")
        )
    )
    assert proj.resolve_plant("d1", "ch2") == "p11"
    assert proj.resolve_plant("d1", "s1") == "p11"  # v4 token, migrated registry
    # and the mirror: registry still raw, board already v5
    proj2 = build_projection(
        _model(Assignment(plant_id="p11", sensor_id="s1", device_id="d1", channel="s1"))
    )
    assert proj2.resolve_plant("d1", "ch2") == "p11"


def test_identity_resolves_on_the_covering_interval_not_todays_answer() -> None:
    # #1331: a probe moved from p11 to p02 — pre-move readings keep the OLD plant
    m = RegistryModel(
        plants=[Plant(plant_id="p11"), Plant(plant_id="p02")],
        assignments=[
            Assignment(
                "p11", "s1", "d1", "ch2", start_ts=None, end_ts="2026-07-10T12:00:00Z"
            ),
            Assignment("p02", "s1", "d1", "ch2", start_ts="2026-07-10T12:00:00Z"),
        ],
    )
    proj = build_projection(m)
    assert proj.resolve_plant("d1", "ch2", T(9)) == "p11"  # before the move
    assert proj.resolve_plant("d1", "ch2", T(15)) == "p02"  # after
    assert proj.resolve_plant("d1", "ch2") == "p02"  # now = the open one
    # the boundary instant belongs to the NEW binding (half-open): no gap, no overlap
    assert proj.resolve_plant("d1", "ch2", T(12)) == "p02"


def test_a_grandfathered_null_start_covers_earlier_history() -> None:
    proj = build_projection(
        _model(Assignment("p11", "s1", "d1", "ch2", start_ts=None, end_ts=None))
    )
    assert (
        proj.resolve_plant("d1", "ch2", datetime(2020, 1, 1, tzinfo=timezone.utc))
        == "p11"
    )


def test_a_ghost_fleet_temporal_map_is_refused_for_the_static_one() -> None:
    # the loader falls back to the committed EXAMPLE on a host with no local
    # instance; non-emptiness is not proof it describes the real fleet
    ghost = _model(Assignment("pZ", "s1", "ghostdev", "ch0"))
    static = Registry(
        devices=[
            Device(
                device_id="realdev",
                board="esp32dev",
                label="R",
                channels={"s1": {"plant_id": "pA"}},
            )
        ]
    )
    proj = build_projection(ghost, static, devices_in_data={"realdev"})
    assert proj.source == "static"
    assert proj.resolve_plant("realdev", "ch2") == "pA"  # folded from the s1 key
    # ...and when the temporal map DOES cover the data, it wins
    proj2 = build_projection(ghost, static, devices_in_data={"ghostdev"})
    assert proj2.source == "temporal"


def test_it_falls_back_and_degrades_honestly() -> None:
    static = Registry(
        devices=[
            Device(
                device_id="d1",
                board="esp32dev",
                label="D",
                channels={"s3": {"plant_id": "p11", "probe": "s7"}},
            )
        ]
    )
    proj = build_projection(None, static)
    assert proj.source == "static"
    assert proj.resolve_plant("d1", "ch0") == "p11"  # s3 IS ch0
    b = proj.binding_for("d1", "s3")
    assert b and b.probe == "s7"  # surfaces get the rich answer, not an event log
    empty = build_projection(None, None)
    assert empty.source == "empty" and empty.resolve_plant("d1", "ch0") is None


def test_unknown_channels_and_devices_stay_unresolved() -> None:
    proj = build_projection(_model(Assignment("p11", "s1", "d1", "ch2")))
    assert proj.resolve_plant("d1", "ch3") is None  # real device, wrong channel
    assert proj.resolve_plant("nope", "ch2") is None  # unknown device
    assert proj.resolve_plant("d1", "s9") is None  # untranslatable token


def test_current_is_the_folded_map_the_existing_joins_want() -> None:
    proj = build_projection(
        _model(
            Assignment("p11", "s1", "d1", "ch2"),
            Assignment("pX", "s2", "d1", "ch3", end_ts="2026-07-01T00:00:00Z"),
        )
    )
    assert proj.current() == {("d1", "ch2"): "p11"}  # closed bindings are not current


def test_the_module_level_function_matches_adr_0038_signature() -> None:
    proj = build_projection(_model(Assignment("p11", "s1", "d1", "ch2")))
    assert resolve_plant("d1", "s1", None, projection=proj) == "p11"
    assert isinstance(Binding("d1", "ch2", "p11"), Binding)
    assert isinstance(proj, Projection)
