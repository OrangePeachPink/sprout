"""Tests for the multi-device fleet registry (#485, epic #448).

Covers the load path (explicit / example fallback / empty), device + channel lookup,
honest degradation (unknown device, unassigned channel, malformed file), and the
de-duplicated all_plants() roll-up the monitor-all view (#486) consumes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import device_registry as dr

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
