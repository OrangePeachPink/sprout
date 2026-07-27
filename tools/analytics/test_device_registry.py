"""Tests for the multi-device fleet registry (#485, epic #448).

Covers the load path (explicit / example fallback / empty), device + channel lookup,
honest degradation (unknown device, unassigned channel, malformed file), and the
de-duplicated all_plants() roll-up the monitor-all view (#486) consumes.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics import device_registry as dr

_CONFIG = Path(__file__).resolve().parents[1] / "config"


def _write(tmp_path: Path, doc: object) -> Path:
    p = tmp_path / "devices.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _fleet() -> dict:
    return {
        "schema_version": 1,
        "devices": [
            {
                "device_id": "sprout-classic-01",
                "board": "esp32dev",
                "label": "classic",
                "channels": {
                    "s1": {"plant_id": "P01", "plant_name": "Monstera"},
                    "s2": {"plant_id": "P02", "plant_name": "Pothos"},
                    "s3": {},  # present but unassigned
                },
            },
            {
                "device_id": "sprout-s3-01",
                "board": "esp32-s3-devkitc-1",
                "channels": {"s1": {"plant_id": "P05", "plant_name": "Fern"}},
            },
        ],
    }


def test_loads_devices_and_channels(tmp_path: Path) -> None:
    reg = dr.load_registry(_write(tmp_path, _fleet()))
    assert reg.device_ids() == ["sprout-classic-01", "sprout-s3-01"]
    d = reg.device("sprout-classic-01")
    assert d is not None and d.board == "esp32dev"
    assert reg.plant_for("sprout-classic-01", "s1") == {
        "plant_id": "P01",
        "plant_name": "Monstera",
        "plant_type": None,  # #713 plant-first enrichment, absent-safe
        "pot_size": None,
    }


def test_unknown_device_and_unassigned_channel_return_none(tmp_path: Path) -> None:
    reg = dr.load_registry(_write(tmp_path, _fleet()))
    assert reg.plant_for("no-such-device", "s1") is None  # unknown device
    assert reg.plant_for("sprout-classic-01", "s4") is None  # channel absent
    assert reg.plant_for("sprout-classic-01", "s3") is None  # present but unassigned


def test_all_plants_dedupes_and_sorts(tmp_path: Path) -> None:
    reg = dr.load_registry(_write(tmp_path, _fleet()))
    plants = reg.all_plants()
    assert [p["plant_id"] for p in plants] == ["P01", "P02", "P05"]
    assert plants[0] == {
        "plant_id": "P01",
        "plant_name": "Monstera",
        "device_id": "sprout-classic-01",
        "channel": "s1",
    }


def test_all_plants_keeps_first_placement_of_duplicate(tmp_path: Path) -> None:
    doc = {
        "devices": [
            {
                "device_id": "a",
                "channels": {"s2": {"plant_id": "P09"}, "s1": {"plant_id": "P09"}},
            }
        ]
    }
    reg = dr.load_registry(_write(tmp_path, doc))
    plants = reg.all_plants()
    assert len(plants) == 1
    assert plants[0]["channel"] == "s1"  # first by sorted channel


def test_device_without_id_is_skipped(tmp_path: Path) -> None:
    doc = {"devices": [{"board": "x"}, {"device_id": "ok"}]}
    reg = dr.load_registry(_write(tmp_path, doc))
    assert reg.device_ids() == ["ok"]


def test_missing_file_is_empty_registry(tmp_path: Path) -> None:
    reg = dr.load_registry(tmp_path / "nope.json")
    assert reg.devices == [] and reg.all_plants() == []
    assert reg.plant_for("anything", "s1") is None


def test_malformed_file_is_empty_registry(tmp_path: Path) -> None:
    p = tmp_path / "devices.json"
    p.write_text("{not json", encoding="utf-8")
    assert dr.load_registry(p).devices == []
    # a dict without a list "devices" also degrades to empty
    p2 = tmp_path / "d2.json"
    p2.write_text(json.dumps({"devices": "not-a-list"}), encoding="utf-8")
    assert dr.load_registry(p2).devices == []


def test_committed_example_is_valid_and_loads() -> None:
    # The shape template ships valid so the app has a working default (AC).
    example = _CONFIG / "devices.example.json"
    if not example.exists():
        return
    reg = dr.load_registry(example)
    assert len(reg.devices) >= 1
    # placeholders are fine; the point is the shape parses + attributes.
    assert all(d.device_id for d in reg.devices)


# --------------------------------------------------------------------------- #
# base_url / served_devices (#486 - the WiFi-polled part of the fleet)
# --------------------------------------------------------------------------- #


def test_base_url_parsed_and_served_devices_filters(tmp_path: Path) -> None:
    doc = _fleet()
    doc["devices"][1]["base_url"] = "http://192.168.1.42"
    reg = dr.load_registry(_write(tmp_path, doc))
    assert reg.device("sprout-classic-01").base_url is None  # absent -> None
    assert reg.device("sprout-s3-01").base_url == "http://192.168.1.42"
    assert [d.device_id for d in reg.served_devices()] == ["sprout-s3-01"]


def test_base_url_empty_or_wrong_type_degrades_to_none(tmp_path: Path) -> None:
    doc = _fleet()
    doc["devices"][0]["base_url"] = ""  # empty string is not a served device
    doc["devices"][1]["base_url"] = 42  # wrong type - never trusted
    reg = dr.load_registry(_write(tmp_path, doc))
    assert reg.served_devices() == []


def test_committed_example_serves_no_devices() -> None:
    # The example is the fresh-checkout fallback (load_registry's default) - a
    # base_url in it would make every first-run dashboard request block polling
    # a placeholder address. It must stay tethered-only.
    example = _CONFIG / "devices.example.json"
    if not example.exists():
        return
    assert dr.load_registry(example).served_devices() == []


# --------------------------------------------------------------------------- #
# name / hostname / first-seen order (#583 - the ratified card-header fields)
# --------------------------------------------------------------------------- #


def test_name_and_hostname_parse_for_the_card_header(tmp_path: Path) -> None:
    doc = _fleet()
    doc["devices"][0]["name"] = "the classic"
    doc["devices"][0]["hostname"] = "sprout-classic-8ccd.local"
    reg = dr.load_registry(_write(tmp_path, doc))
    d = reg.device("sprout-classic-01")
    assert d.name == "the classic"
    assert d.hostname == "sprout-classic-8ccd.local"


def test_name_falls_back_to_label_hostname_absent_is_none(tmp_path: Path) -> None:
    # A legacy config carrying only `label` still populates `name` (non-breaking
    # migration); hostname absent/blank -> None, never invented (a tethered
    # device shows its port instead of a fabricated `.local` name).
    doc = _fleet()  # devices[0] has label "classic", no name/hostname
    reg = dr.load_registry(_write(tmp_path, doc))
    d = reg.device("sprout-classic-01")
    assert d.name == "classic"  # fell back to label
    assert d.hostname is None  # absent -> None


def test_hostname_wrong_type_or_blank_degrades_to_none(tmp_path: Path) -> None:
    doc = _fleet()
    doc["devices"][0]["hostname"] = ""  # blank is not a hostname
    doc["devices"][1]["hostname"] = 42  # wrong type - never trusted
    reg = dr.load_registry(_write(tmp_path, doc))
    assert reg.device("sprout-classic-01").hostname is None
    assert reg.device("sprout-s3-01").hostname is None


def test_devices_preserve_registry_first_seen_order(tmp_path: Path) -> None:
    # #583 ORDER rule: `devices` list order == registry first-seen == the
    # dashboard's card order, never re-sorted by state. Reverse-alphabetical
    # ids must stay in file order.
    doc = {"devices": [{"device_id": "z-first"}, {"device_id": "a-second"}]}
    reg = dr.load_registry(_write(tmp_path, doc))
    assert [d.device_id for d in reg.devices] == ["z-first", "a-second"]


def test_committed_example_carries_name_for_every_device() -> None:
    # The ratified shape (#583): every device has a friendly `name` for its card
    # header. hostname may be null (tethered) - name may not.
    example = _CONFIG / "devices.example.json"
    if not example.exists():
        return
    reg = dr.load_registry(example)
    assert all(d.name for d in reg.devices)


# --------------------------------------------------------------------------- #
# #619 — UUID-keyed registry: stable-id key + probe labels (ADR-0027 W1)
# --------------------------------------------------------------------------- #


def test_probe_for_returns_the_sticker_label(tmp_path: Path) -> None:
    doc = {
        "devices": [
            {
                "device_id": "k7m2rt",  # a stable minted id (opaque key)
                "channels": {
                    "s1": {"probe": "s3", "plant_id": "p01", "plant_name": "Fern"},
                    "s2": {"plant_id": "p02"},  # plant but no probe assigned
                },
            }
        ]
    }
    reg = dr.load_registry(_write(tmp_path, doc))
    assert reg.probe_for("k7m2rt", "s1") == "s3"  # the sticker, not the port
    assert reg.probe_for("k7m2rt", "s2") is None  # port bound, probe unassigned
    assert reg.probe_for("k7m2rt", "s4") is None  # channel absent
    assert reg.probe_for("no-such", "s1") is None  # unknown device
    # channel + probe are distinct: the port is s1, the probe on it is s3
    assert reg.plant_for("k7m2rt", "s1") == {
        "plant_id": "p01",
        "plant_name": "Fern",
        "plant_type": None,
        "pot_size": None,
    }


def test_probe_for_resolves_through_a_legacy_rename(tmp_path: Path) -> None:
    # a probe binding survives a legacy name->uuid rename the same way plant
    # attribution does (canonical_for, #602/#604)
    doc = {
        "devices": [
            {
                "device_id": "k7m2rt",
                "previous_ids": ["classic"],
                "channels": {"s1": {"probe": "s3", "plant_id": "p01"}},
            }
        ]
    }
    reg = dr.load_registry(_write(tmp_path, doc))
    assert reg.probe_for("classic", "s1") == "s3"  # old id resolves to the probe


def test_device_id_is_an_opaque_key_any_string(tmp_path: Path) -> None:
    # the registry never validates the id format - a base32 stable id and a
    # legacy friendly name are both valid keys (#619: stable-id-ness is a wire
    # property #618, not a registry-key check)
    for did in ("k7m2rt", "sprout-classic-01", "Sprout ESP32"):
        reg = dr.load_registry(_write(tmp_path, {"devices": [{"device_id": did}]}))
        assert reg.device(did) is not None


def test_committed_example_is_uuid_shaped_with_probes() -> None:
    # the template demonstrates the ADR-0027 target shape: base32-ish keys,
    # name as the label, a probe sticker per bound channel
    example = _CONFIG / "devices.example.json"
    if not example.exists():
        return
    reg = dr.load_registry(example)
    classic = reg.devices[0]
    assert classic.name and classic.name != classic.device_id  # key != label
    assert reg.probe_for(classic.device_id, "s1")  # a probe sticker is bound
    # and the fresh-checkout guard still holds (no base_url in the example)
    assert reg.served_devices() == []
