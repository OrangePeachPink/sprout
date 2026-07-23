"""#966 — rig-location setup surface. The maintainer owns the repo and still didn't know
day/night shading / solar / weather gated on a hand-edited JSON file. This adds a write
path + the NAME-ONLY status, with the ADR-0013 §3 privacy fence: coordinates are written
ONLY to the gitignored local config and NEVER echoed back to a screenshottable surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.analytics import env_solar


def test_save_writes_the_local_config_and_round_trips(tmp_path: Path) -> None:
    cfg = tmp_path / "location.local.json"
    status = env_solar.save_location(
        {
            "name": "wsill",
            "latitude": 41.88,
            "longitude": -87.63,
            "tz_offset_hours": -5,
        },
        path=cfg,
    )
    assert status == {"configured": True, "name": "wsill"}
    # written to disk with the real coordinates...
    doc = json.loads(cfg.read_text(encoding="utf-8"))
    assert doc["latitude"] == 41.88 and doc["longitude"] == -87.63
    # ...and load_location reads it back, so shading/solar/weather now turn on
    loaded = env_solar.load_location(cfg)
    assert loaded["latitude"] == 41.88 and loaded["name"] == "wsill"


def test_the_status_is_name_only_never_coordinates(tmp_path: Path) -> None:
    cfg = tmp_path / "location.local.json"
    assert env_solar.location_status(cfg) == {"configured": False, "name": None}
    status = env_solar.save_location(
        {"name": "home", "latitude": 51.5, "longitude": -0.12}, path=cfg
    )
    after = env_solar.location_status(cfg)
    assert after == {"configured": True, "name": "home"}
    # the privacy fence: NEITHER the save return NOR the status carries the coordinates
    for surface in (status, after):
        assert "latitude" not in surface and "longitude" not in surface


def test_missing_or_out_of_range_coordinates_are_rejected(tmp_path: Path) -> None:
    cfg = tmp_path / "location.local.json"
    with pytest.raises(ValueError, match="required numbers"):
        env_solar.save_location({"name": "x"}, path=cfg)
    with pytest.raises(ValueError, match="-90"):
        env_solar.save_location({"latitude": 200, "longitude": 0}, path=cfg)
    with pytest.raises(ValueError, match="-180"):
        env_solar.save_location({"latitude": 0, "longitude": 999}, path=cfg)
    assert not cfg.exists()  # nothing written on a rejected save


def test_name_defaults_and_tz_is_optional(tmp_path: Path) -> None:
    cfg = tmp_path / "location.local.json"
    env_solar.save_location({"latitude": 0, "longitude": 0}, path=cfg)  # no name, no tz
    doc = json.loads(cfg.read_text(encoding="utf-8"))
    assert doc["name"] and doc["tz_offset_hours"] == 0.0  # sensible defaults, no crash
