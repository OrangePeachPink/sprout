"""#921 slice 3 — the /registry/apply write path (classic-save a batch of ops onto the
temporal model). Data owns the seam; Design-QA builds the edit/map UI against it.

Proves the three answers to Design-QA's seam questions:
- batch of operations (not full desired-state), temporal logic server-side;
- the server owns next-id allocation (exposed on /registry, never reused);
- the server validates and returns structured errors atomically (whole-or-nothing).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry_model import (
    Plant,
    RegistryModel,
    Sensor,
    apply_operations,
    next_plant_id,
    next_sensor_id,
    purge_device_files,
    registry_payload,
    save_registry_model,
)


def _model() -> RegistryModel:
    return RegistryModel(
        plants=[Plant(plant_id="p01", pet_name="Bernie")],
        sensors=[Sensor(sensor_id="s01")],
        devices=[{"device_id": "y9d41p", "base_url": "http://192.168.1.9"}],
    )


# --------------------------------------------------------------------------- #
# next-id allocation (server is the source of truth, never reuses a number)
# --------------------------------------------------------------------------- #
def test_next_ids_are_max_plus_one_and_never_reuse_retired() -> None:
    m = RegistryModel(
        plants=[Plant("p01"), Plant("p03", lifecycle="deleted")],  # p02 was never used
        sensors=[Sensor("s02")],
    )
    assert next_plant_id(m) == "p04"  # max(3)+1 — a deleted p03 still holds its number
    assert next_sensor_id(m) == "s03"
    assert registry_payload(m)["next_ids"] == {"plant": "p04", "sensor": "s03"}


def test_next_ids_on_an_empty_registry() -> None:
    assert next_plant_id(RegistryModel()) == "p01"
    assert next_sensor_id(RegistryModel()) == "s01"


# --------------------------------------------------------------------------- #
# add / edit
# --------------------------------------------------------------------------- #
def test_add_plant_with_explicit_and_server_allocated_ids() -> None:
    m = _model()
    r = apply_operations(
        m,
        {"plants": {"add": [{"plant_type": "pothos"}, {"plant_id": "p09"}]}},
    )
    assert r["ok"] and r["applied"]["plants_added"] == 2
    ids = {p.plant_id for p in m.plants}
    assert "p02" in ids  # server-allocated next
    assert "p09" in ids  # honored the explicit id


def test_add_sensor_requires_a_number() -> None:
    r = apply_operations(_model(), {"sensors": {"add": [{"friendly_name": "left"}]}})
    assert not r["ok"]
    assert r["errors"][0]["field"] == "sensor_id"


def test_edit_changes_fields_but_not_identity() -> None:
    m = _model()
    r = apply_operations(
        m, {"plants": {"edit": [{"plant_id": "p01", "pet_name": "Ern"}]}}
    )
    assert r["ok"] and r["applied"]["edited"] == 1
    assert m.plants[0].pet_name == "Ern"
    assert m.plants[0].plant_id == "p01"  # identity is immutable


def test_edit_a_nonexistent_entity_is_a_structured_error() -> None:
    r = apply_operations(_model(), {"plants": {"edit": [{"plant_id": "p99"}]}})
    assert not r["ok"]
    assert r["errors"][0]["op"] == "plants.edit[0]"
    assert r["errors"][0]["field"] == "plant_id"


def test_device_friendly_label_writes_the_name_key() -> None:
    m = _model()
    r = apply_operations(
        m, {"devices": {"edit": [{"device_id": "y9d41p", "friendly_name": "Board A"}]}}
    )
    assert r["ok"]
    assert m.devices[0]["name"] == "Board A"  # `name` is the mutable label (#583)


# --------------------------------------------------------------------------- #
# device adopt (#1027) — register an answering-but-unknown board in-UI, no JSON edit
# --------------------------------------------------------------------------- #
def test_adopt_registers_an_answering_board() -> None:
    m = _model()
    r = apply_operations(
        m,
        {
            "devices": {
                "add": [
                    {
                        "device_id": "n3jhsp",
                        "base_url": "http://192.168.1.89",
                        "name": "c5yellow2",
                    }
                ]
            }
        },
    )
    assert r["ok"] and r["applied"]["devices_added"] == 1
    new = next(d for d in m.devices if d["device_id"] == "n3jhsp")
    assert new["base_url"] == "http://192.168.1.89"
    assert new["name"] == "c5yellow2"  # the label the operator gave it
    assert new["lifecycle"] == "active"  # a freshly adopted board polls immediately


def test_adopt_requires_a_base_url() -> None:
    m = _model()
    r = apply_operations(m, {"devices": {"add": [{"device_id": "n3jhsp"}]}})
    assert not r["ok"]  # no address to poll — rejected whole, nothing added
    assert r["errors"][0]["field"] == "base_url"
    assert len(m.devices) == 1


def test_adopting_an_already_registered_id_is_an_error_not_a_dup() -> None:
    m = _model()  # y9d41p already registered
    r = apply_operations(
        m, {"devices": {"add": [{"device_id": "y9d41p", "base_url": "http://x"}]}}
    )
    assert not r["ok"]  # edit the label instead — never a silent duplicate device row
    assert r["errors"][0]["field"] == "device_id"
    assert len(m.devices) == 1


def test_adopt_then_map_in_one_batch_resolves() -> None:
    # the real adopt flow: register the board AND wire a plant to it atomically.
    m = _model()
    r = apply_operations(
        m,
        {
            "devices": {"add": [{"device_id": "8gtt1h", "base_url": "http://y"}]},
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p01",
                        "sensor_id": "s01",
                        "device_id": "8gtt1h",  # the just-added board
                        "channel": "s1",
                    }
                ]
            },
        },
    )
    assert r["ok"]
    assert r["applied"]["devices_added"] == 1 and r["applied"]["mapped"] == 1
    assert m.current_for_channel("8gtt1h", "s1").plant_id == "p01"


# --------------------------------------------------------------------------- #
# mapping — assign is the temporal close-old-open-new boundary (Q8)
# --------------------------------------------------------------------------- #
def test_assign_opens_a_mapping_and_a_remap_closes_the_old() -> None:
    m = _model()
    r1 = apply_operations(
        m,
        {
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p01",
                        "sensor_id": "s01",
                        "device_id": "y9d41p",
                        "channel": "s1",
                    }
                ]
            }
        },
        now="2026-07-11T00:00:00Z",
    )
    assert r1["ok"] and r1["applied"]["mapped"] == 1
    assert len(m.open_assignments()) == 1

    # add a second plant + sensor, then remap the SAME channel to it
    apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p02"}]},
            "sensors": {"add": [{"sensor_id": "s02"}]},
        },
    )
    r2 = apply_operations(
        m,
        {
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p02",
                        "sensor_id": "s02",
                        "device_id": "y9d41p",
                        "channel": "s1",
                    }
                ]
            }
        },
        now="2026-07-11T01:00:00Z",
    )
    assert r2["ok"]
    open_now = m.open_assignments()
    assert len(open_now) == 1  # the channel still holds exactly one open mapping
    assert open_now[0].plant_id == "p02"  # the new binding
    # the old binding is CLOSED, not deleted — history is never stitched away (Q8)
    closed = [a for a in m.assignments if not a.is_open]
    assert len(closed) == 1 and closed[0].plant_id == "p01"


def test_assign_to_a_channel_already_held_is_not_an_error() -> None:
    # a channel already bound is a REMAP, the whole point of the temporal boundary.
    m = _model()
    ops = {
        "mappings": {
            "assign": [
                {
                    "plant_id": "p01",
                    "sensor_id": "s01",
                    "device_id": "y9d41p",
                    "channel": "s1",
                }
            ]
        }
    }
    assert apply_operations(m, ops)["ok"]
    assert apply_operations(m, ops)["ok"]  # again — still fine, not a conflict


def test_assign_with_an_unknown_ref_is_rejected_whole() -> None:
    m = _model()
    r = apply_operations(
        m,
        {
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p01",
                        "sensor_id": "sXX",
                        "device_id": "y9d41p",
                        "channel": "s1",
                    }
                ]
            }
        },
    )
    assert not r["ok"]
    assert any(e["field"] == "sensor_id" for e in r["errors"])
    assert m.open_assignments() == []  # atomic — nothing opened


def test_close_channel_unmaps() -> None:
    m = _model()
    apply_operations(
        m,
        {
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p01",
                        "sensor_id": "s01",
                        "device_id": "y9d41p",
                        "channel": "s1",
                    }
                ]
            }
        },
    )
    r = apply_operations(
        m, {"mappings": {"close": [{"device_id": "y9d41p", "channel": "s1"}]}}
    )
    assert r["ok"] and r["applied"]["closed"] == 1
    assert m.open_assignments() == []


# --------------------------------------------------------------------------- #
# lifecycle + atomicity
# --------------------------------------------------------------------------- #
def test_lifecycle_transition_and_validation() -> None:
    m = _model()
    assert apply_operations(
        m, {"lifecycle": [{"kind": "plant", "entity_id": "p01", "state": "paused"}]}
    )["ok"]
    assert m.plants[0].lifecycle == "paused"
    bad = apply_operations(
        m, {"lifecycle": [{"kind": "plant", "entity_id": "p01", "state": "banished"}]}
    )
    assert not bad["ok"] and bad["errors"][0]["field"] == "state"


def test_a_batch_with_any_error_mutates_nothing() -> None:
    # one good op + one bad op — the WHOLE batch must be rejected, nothing applied.
    m = _model()
    before = len(m.plants)
    r = apply_operations(
        m,
        {
            "plants": {
                "add": [{"plant_id": "p02"}, {"plant_id": "p01"}]
            },  # p01 collides
        },
    )
    assert not r["ok"]
    assert len(m.plants) == before  # the valid p02 add did NOT slip through


# --------------------------------------------------------------------------- #
# save preserves unknown top-level keys (devices.local.json is shared)
# --------------------------------------------------------------------------- #
def test_purge_removes_a_device_and_its_assignments(tmp_path: Path) -> None:
    # #921 s4 / Q3: delete = entity AND history out of the records (the yyvvpd case).
    m = _model()
    apply_operations(
        m,
        {
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p01",
                        "sensor_id": "s01",
                        "device_id": "y9d41p",
                        "channel": "s1",
                    }
                ]
            }
        },
    )
    r = apply_operations(m, {"purge": {"devices": ["y9d41p"]}})
    assert r["ok"]
    assert r["applied"]["purged"] == {
        "devices": 1,
        "plants": 0,
        "sensors": 0,
        "assignments": 1,
    }
    assert m.devices == []  # gone from the registry -> gone from the poll set
    assert m.assignments == []  # its history is out of the records too


def test_purge_an_unknown_device_is_an_error_never_silent(tmp_path: Path) -> None:
    # a delete is irreversible — a typo'd id must NOT "succeed" at deleting nothing.
    m = _model()
    r = apply_operations(m, {"purge": {"devices": ["nope"]}})
    assert not r["ok"]
    assert r["errors"][0]["op"] == "purge.devices"
    assert m.devices  # untouched


def test_purge_device_files_deletes_segments_and_reports_archive(
    tmp_path: Path,
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "yyvvpd_20260711_120000.csv").write_text("x", encoding="utf-8")
    (logs / "y9d41p_20260711_120000.csv").write_text(
        "keep", encoding="utf-8"
    )  # other dev
    (logs / "notes.txt").write_text("keep", encoding="utf-8")  # not a segment
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "yyvvpd_20260701_120000.csv.gz").write_bytes(b"gz")  # deep history
    out = purge_device_files(["yyvvpd"], logdir=logs, archive_dir=archive)
    assert len(out["removed"]) == 1  # only yyvvpd's active segment
    assert not (logs / "yyvvpd_20260711_120000.csv").exists()
    assert (logs / "y9d41p_20260711_120000.csv").exists()  # other device untouched
    assert (logs / "notes.txt").exists()  # non-segment untouched
    # the archive is REPORTED, never scrubbed (deferred work) - honest, not silent
    assert out["archived_remaining"] == 1
    assert (archive / "yyvvpd_20260701_120000.csv.gz").exists()


def test_save_preserves_unowned_top_level_keys(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.local.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "devices": [{"device_id": "y9d41p"}],
                "sensorless": [{"device_id": "y9d41p"}],  # ADR-0028 — NOT model-owned
            }
        ),
        encoding="utf-8",
    )
    m = _model()
    save_registry_model(m, cfg)
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["sensorless"] == [{"device_id": "y9d41p"}]  # survived the commit
    assert saved["schema_version"] == 2  # model now owns the shape
    assert [p["plant_id"] for p in saved["plants"]] == ["p01"]
