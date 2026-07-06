"""#713 plant-first identity — the data-shape half.

The dashboard must lead with the plant, use the user's physical sensor label
(her sN sticker = the registry `probe`, NOT the board port token), name boards by
their friendly name + physical side, and keep the machine device_id as a hidden
key. This pins the fields build_context exposes for DesignQA's template half.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=t  run=identity\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _soil(device: str, port: str, raw: int) -> str:
    ts = "2026-07-04T00:00:30.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},sess1,{device},{port},{raw},OK,level=DRY;gpio=35\n"
    )


def _ctx(tmp_path: Path, rows, reg):
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=reg)


def test_probe_is_the_physical_sensor_label_not_the_port(tmp_path: Path) -> None:
    # the crux: the telemetry PORT is "s2", but the user's physical sticker on that
    # cable is "s6". `probe` must be her sticker; the port stays as channel/debug.
    reg = Registry(
        devices=[
            Device(
                device_id="y9d41p",
                board="esp32dev",
                label=None,
                name="ESPclassic",
                side="left",
                channels={
                    "s2": {
                        "probe": "s6",
                        "plant_id": "p02",
                        "plant_name": "Pothos (XXL)",
                        "plant_type": "pothos",
                        "pot_size": "10in",
                    }
                },
            )
        ]
    )
    s = _ctx(tmp_path, [_soil("y9d41p", "s2", 2400)], reg)["sensors"][0]
    assert s["probe"] == "s6"  # HER sticker, not the port
    assert s["sensor_id"] == "s2"  # the board port token, demoted to wiring/debug
    # plant-first enrichment
    assert s["plant_id"] == "p02" and s["plant_name"] == "Pothos (XXL)"
    assert s["plant_type"] == "pothos" and s["pot_size"] == "10in"
    # board named + placed as the user named it
    assert s["device_name"] == "ESPclassic" and s["device_side"] == "left"
    # the machine id is present as a (hidden) key, never the label
    assert s["device_id"] == "y9d41p"


def test_identity_fields_are_absent_safe(tmp_path: Path) -> None:
    # a minimal assignment (plant only, no probe/type/pot/side) yields None on the
    # optional fields - never a crash, never an invented value.
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                name="ESPclassic",
                channels={"s1": {"plant_id": "p01", "plant_name": "pothos small"}},
            )
        ]
    )
    s = _ctx(tmp_path, [_soil("classic", "s1", 2200)], reg)["sensors"][0]
    assert s["probe"] is None
    assert s["plant_type"] is None and s["pot_size"] is None
    assert s["device_name"] == "ESPclassic"
    assert s["device_side"] is None  # not configured -> honest None


def test_device_group_carries_the_side(tmp_path: Path) -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="c5",
                board="esp32-c5",
                label=None,
                name="C5Official",
                side="right",
                channels={"s1": {"probe": "s9", "plant_id": "p07"}},
            )
        ]
    )
    d = _ctx(tmp_path, [_soil("c5", "s1", 2300)], reg)["devices"][0]
    assert d["name"] == "C5Official" and d["side"] == "right"


def test_registry_parses_side_and_plant_meta(tmp_path: Path) -> None:
    import json

    from device_registry import load_registry

    p = tmp_path / "devices.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "devices": [
                    {
                        "device_id": "d1",
                        "name": "ESPclassic",
                        "side": "left",
                        "channels": {
                            "s2": {
                                "probe": "s6",
                                "plant_id": "p02",
                                "plant_type": "pothos",
                                "pot_size": "10in",
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    dev = load_registry(p).device("d1")
    assert dev.side == "left"
    assert dev.probe_for("s2") == "s6"
    plant = dev.plant_for("s2")
    assert plant["plant_type"] == "pothos" and plant["pot_size"] == "10in"
