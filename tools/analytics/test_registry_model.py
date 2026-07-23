"""#921 slice 1 — the temporal registry model (Data foundation).

Proves the load-bearing Q8 ruling: the mapping is an append-only assignment log, the
current mapping is *derived* from the open assignments, and map/remap/swap/re-enable are
one atomic boundary (close old, open new) so history is never silently rewritten.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics.registry_model import (
    Plant,
    Profile,
    RegistryModel,
    Sensor,
    load_model,
    save_model,
)

_T0 = "2026-07-11T10:00:00Z"
_T1 = "2026-07-11T11:00:00Z"


def _model() -> RegistryModel:
    return RegistryModel(
        plants=[Plant(plant_id="p01", pet_name="Bernie"), Plant(plant_id="p02")],
        sensors=[Sensor(sensor_id="s01"), Sensor(sensor_id="s02")],
        devices=[{"device_id": "y9d41p", "lifecycle": "active"}],
        profiles=[
            Profile(profile_id="cap-v2", name="Capacitive v2", sensor_type="capacitive")
        ],
    )


# --------------------------------------------------------------------------- #
# the temporal boundary — assign closes the old + opens the new
# --------------------------------------------------------------------------- #


def test_assign_opens_a_current_mapping() -> None:
    m = _model()
    a = m.assign(
        plant_id="p01", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T0
    )
    assert a.is_open and a.start_ts == _T0
    cur = m.current_for_channel("y9d41p", "s1")
    assert cur is not None and cur.plant_id == "p01"


def test_remap_closes_the_old_and_opens_the_new_no_stitch() -> None:
    m = _model()
    m.assign(plant_id="p01", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T0)
    # remap the channel to p02 — the boundary: old closes as the new opens
    m.assign(plant_id="p02", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T1)
    open_ = m.open_assignments()
    assert len(open_) == 1  # only ONE current mapping per channel
    assert open_[0].plant_id == "p02"
    # the old binding is preserved as history, closed exactly at the boundary
    p01_hist = m.history_for_plant("p01")
    assert (
        len(p01_hist) == 1 and p01_hist[0].end_ts == _T1
    )  # closed, never mutated away


def test_close_channel_disables_without_a_new_mapping() -> None:
    m = _model()
    m.assign(plant_id="p01", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T0)
    assert m.close_channel("y9d41p", "s1", now=_T1) is True
    assert m.current_for_channel("y9d41p", "s1") is None  # nothing current
    assert m.history_for_plant("p01")[0].end_ts == _T1  # but history intact
    assert m.close_channel("y9d41p", "s1") is False  # already closed -> no-op


# --------------------------------------------------------------------------- #
# lifecycle — a deleted entity has no current mapping
# --------------------------------------------------------------------------- #


def test_deleted_plant_drops_out_of_the_current_mapping_but_keeps_history() -> None:
    m = _model()
    m.assign(plant_id="p01", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T0)
    assert m.set_lifecycle("plant", "p01", "deleted") is True
    assert m.open_assignments() == []  # a deleted plant has no current mapping
    assert len(m.history_for_plant("p01")) == 1  # the record still exists in the log


def test_paused_is_a_reversible_state_not_a_fault() -> None:
    m = _model()
    assert m.set_lifecycle("sensor", "s01", "paused") is True
    assert m.sensors[0].lifecycle == "paused"
    assert m.set_lifecycle("sensor", "s01", "active") is True  # trivially reversible
    assert m.sensors[0].lifecycle == "active"


def test_unknown_lifecycle_state_is_rejected() -> None:
    m = _model()
    try:
        m.set_lifecycle("plant", "p01", "banished")
    except ValueError:
        return
    raise AssertionError("an unknown lifecycle state must raise")


# --------------------------------------------------------------------------- #
# moves are events (Q7)
# --------------------------------------------------------------------------- #


def test_move_plant_is_a_timestamped_event() -> None:
    m = _model()
    m.move_plant("p01", "windowsill-left", now=_T0)
    m.move_plant("p01", "windowsill-right", now=_T1)
    open_moves = [e for e in m.location_events if e.is_open]
    assert len(open_moves) == 1 and open_moves[0].location == "windowsill-right"
    # the bench→windowsill migration class is never silently lost: the old event closed
    closed = [e for e in m.location_events if not e.is_open]
    assert len(closed) == 1 and closed[0].location == "windowsill-left"
    assert m.plants[0].location == "windowsill-right"  # cheap current-spot mirror


# --------------------------------------------------------------------------- #
# migration from the static (v1) registry — grandfather in, unknown origin
# --------------------------------------------------------------------------- #


def test_migrate_static_derives_open_assignments_with_unknown_start() -> None:
    static = {
        "devices": [
            {
                "device_id": "y9d41p",
                "channels": {
                    "s1": {"plant_id": "p01", "plant_name": "Bernie", "probe": "s07"},
                    "s2": {"plant_id": "p02"},
                },
            }
        ]
    }
    m = RegistryModel.from_dict(static)  # auto-detects the static shape
    assert {p.plant_id for p in m.plants} == {"p01", "p02"}
    assert m.plants[0].pet_name == "Bernie"  # plant_name -> pet_name
    open_ = m.open_assignments()
    assert len(open_) == 2
    assert all(
        a.start_ts is None for a in open_
    )  # grandfathered: origin unknown, never faked
    s1 = m.current_for_channel("y9d41p", "s1")
    assert (
        s1.plant_id == "p01" and s1.sensor_id == "s07"
    )  # probe sticker becomes the sensor id


def test_migrate_static_honors_retired_as_paused() -> None:
    # #1036: a `retired: true` raw device (the fleet excludes it via _active_served)
    # must migrate to a NON-active lifecycle, so the tab's truth matches the fleet's and
    # renders the calm Paused chip - not a normal active board with Pause/Delete (Q2).
    static = {
        "devices": [
            {"device_id": "y9d41p"},  # normal board
            {"device_id": "yyvvpd", "retired": True},  # the unplugged yellow C5
        ]
    }
    m = RegistryModel.from_dict(static)
    by_id = {d["device_id"]: d["lifecycle"] for d in m.devices}
    assert by_id["y9d41p"] == "active"
    assert by_id["yyvvpd"] == "paused"  # off-by-choice, reversible, calm - not active


def test_migrate_static_brings_sensorless_plants_into_the_model() -> None:
    # #1027: the ADR-0028 `sensorless` roster (plants present by design, not probed)
    # must become first-class, lifecycle-manageable Plant entities — not a Monitor-only
    # block the registry tab can't see. No open assignment => "alive · not probed".
    static = {
        "devices": [{"device_id": "y9d41p", "channels": {"s1": {"plant_id": "p01"}}}],
        "sensorless": [
            {"plant_id": "p05", "plant_name": "Pothos cutting", "pot_size": "4in"},
            {"plant_id": "p08"},
        ],
    }
    m = RegistryModel.from_dict(static)
    assert {p.plant_id for p in m.plants} == {"p01", "p05", "p08"}
    p05 = next(p for p in m.plants if p.plant_id == "p05")
    assert p05.pet_name == "Pothos cutting"  # plant_name -> pet_name
    assert p05.pot_size == "4in"
    assert p05.lifecycle == "active"  # present + alive, just unprobed
    # unprobed == no open assignment; only the probed p01 has a current mapping
    assert {a.plant_id for a in m.open_assignments()} == {"p01"}


def test_plant_photo_round_trips_and_defaults_absent() -> None:
    # #875 card contract: the optional identity-block photo is absent by default and
    # round-trips through the model when set (a local, gitignored path).
    assert Plant(plant_id="p01").photo is None  # absent-safe default
    m = RegistryModel(plants=[Plant(plant_id="p01", photo="config/photos/p01.jpg")])
    back = RegistryModel.from_dict(m.to_dict())
    assert back.plants[0].photo == "config/photos/p01.jpg"


def test_migrate_static_a_probed_plant_is_not_duplicated_by_sensorless() -> None:
    # a plant can't be both probed and sensorless — a live reading wins, no dup Plant.
    static = {
        "devices": [{"device_id": "y9d41p", "channels": {"s1": {"plant_id": "p01"}}}],
        "sensorless": [{"plant_id": "p01", "plant_name": "should not overwrite"}],
    }
    m = RegistryModel.from_dict(static)
    assert [p.plant_id for p in m.plants] == ["p01"]  # exactly one
    assert next(a for a in m.open_assignments()).plant_id == "p01"  # still probed


# --------------------------------------------------------------------------- #
# serialization round-trip
# --------------------------------------------------------------------------- #


def test_to_dict_from_dict_round_trip() -> None:
    m = _model()
    m.assign(plant_id="p01", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T0)
    m.move_plant("p01", "bench", now=_T0)
    doc = m.to_dict()
    assert doc["schema_version"] == 2
    m2 = RegistryModel.from_dict(doc)
    assert m2.current_for_channel("y9d41p", "s1").plant_id == "p01"
    assert m2.plants[0].pet_name == "Bernie"
    assert [e.location for e in m2.location_events] == ["bench"]


def test_from_dict_tolerates_unknown_future_fields() -> None:
    doc = {
        "schema_version": 2,
        "plants": [{"plant_id": "p01", "some_future_field": 42}],
        "assignments": [],
    }
    m = RegistryModel.from_dict(doc)
    assert m.plants[0].plant_id == "p01"  # unknown field ignored, no crash


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    m = _model()
    m.assign(plant_id="p01", sensor_id="s01", device_id="y9d41p", channel="s1", now=_T0)
    p = tmp_path / "registry.json"
    save_model(m, p)
    assert json.loads(p.read_text(encoding="utf-8"))["schema_version"] == 2
    loaded = load_model(p)
    assert loaded.current_for_channel("y9d41p", "s1").plant_id == "p01"


def test_load_missing_file_is_empty_not_a_crash(tmp_path: Path) -> None:
    m = load_model(tmp_path / "does-not-exist.json")  # first-run signal
    assert m.open_assignments() == [] and m.plants == []


if __name__ == "__main__":
    import tempfile

    fns = [
        test_assign_opens_a_current_mapping,
        test_remap_closes_the_old_and_opens_the_new_no_stitch,
        test_close_channel_disables_without_a_new_mapping,
        test_deleted_plant_drops_out_of_the_current_mapping_but_keeps_history,
        test_paused_is_a_reversible_state_not_a_fault,
        test_unknown_lifecycle_state_is_rejected,
        test_move_plant_is_a_timestamped_event,
        test_migrate_static_derives_open_assignments_with_unknown_start,
        test_to_dict_from_dict_round_trip,
        test_from_dict_tolerates_unknown_future_fields,
    ]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    with tempfile.TemporaryDirectory() as d:
        test_save_and_load_round_trip(Path(d))
        test_load_missing_file_is_empty_not_a_crash(Path(d))
    print("All checks passed.")


# --------------------------------------------------------------------------- #
# #1188 — a location edit is a MOVE (the #921 "c" ruling)
# --------------------------------------------------------------------------- #


def test_a_location_edit_records_a_move_and_never_loses_the_old_spot() -> None:
    from tools.analytics.registry_model import Plant, RegistryModel, apply_operations

    m = RegistryModel(plants=[Plant(plant_id="p01", location="windowsill left")])
    apply_operations(
        m, {"plants": {"edit": [{"plant_id": "p01", "location": "windowsill right"}]}}
    )
    hist = m.location_history("p01")
    assert [e.location for e in hist] == ["windowsill left", "windowsill right"]
    # the grandfathered prior: it WAS there, we don't know since when
    assert hist[0].start_ts is None and hist[0].end_ts is not None
    assert hist[-1].is_open  # the new spot is current
    assert m.plants[0].location == "windowsill right"  # cheap-read mirror kept


def test_a_second_move_chains_without_a_hole() -> None:
    from tools.analytics.registry_model import Plant, RegistryModel, apply_operations

    m = RegistryModel(plants=[Plant(plant_id="p01", location="left")])
    for spot in ("right", "office"):
        apply_operations(
            m, {"plants": {"edit": [{"plant_id": "p01", "location": spot}]}}
        )
    hist = m.location_history("p01")
    assert [e.location for e in hist] == ["left", "right", "office"]
    assert sum(1 for e in hist if e.is_open) == 1  # exactly one current spot
    # every closed span's end is the next span's start — a hole-free chain
    assert hist[0].end_ts == hist[1].start_ts and hist[1].end_ts == hist[2].start_ts


def test_move_boundaries_are_the_context_edges_consumers_gate_on() -> None:
    from tools.analytics.registry_model import Plant, RegistryModel, apply_operations

    m = RegistryModel(plants=[Plant(plant_id="p01", location="left")])
    assert m.move_boundaries("p01") == []  # never moved -> one continuous context
    apply_operations(
        m, {"plants": {"edit": [{"plant_id": "p01", "location": "right"}]}}
    )
    bounds = m.move_boundaries("p01")
    assert len(bounds) == 1 and isinstance(bounds[0], str)


def test_a_non_location_edit_is_not_a_move() -> None:
    from tools.analytics.registry_model import Plant, RegistryModel, apply_operations

    m = RegistryModel(plants=[Plant(plant_id="p01", location="left")])
    apply_operations(
        m, {"plants": {"edit": [{"plant_id": "p01", "pet_name": "Bernie"}]}}
    )
    assert m.location_events == []  # renaming a plant never moved it
    # and re-saving the SAME location is not a move either (the editor round-trips
    # every field on save — an unchanged value must not manufacture history)
    apply_operations(m, {"plants": {"edit": [{"plant_id": "p01", "location": "left"}]}})
    assert m.location_events == []


def test_the_payload_carries_the_move_record_for_movers_only() -> None:
    from tools.analytics.registry_model import (
        Plant,
        RegistryModel,
        apply_operations,
        registry_payload,
    )

    m = RegistryModel(
        plants=[Plant(plant_id="p01", location="left"), Plant(plant_id="p02")]
    )
    apply_operations(
        m, {"plants": {"edit": [{"plant_id": "p01", "location": "right"}]}}
    )
    doc = registry_payload(m)
    assert "p01" in doc["location_history"]
    assert "p02" not in doc["location_history"]  # present-or-silent: no move, no key
    assert doc["location_history"]["p01"][-1]["end_ts"] is None
