"""#715 watering-status data-shape: within-band position + sortable dryness so
two plants in the SAME band are distinguishable by need ("water now?")."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=t  run=water\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _soil(port: str, raw: int, level: str, quality: str = "OK") -> str:
    ts = "2026-07-04T00:00:30.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},sess1,classic,{port},{raw},{quality},"
        f"level={level};gpio=35\n"
    )


def _reg(*ports: str) -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={p: {"plant_id": f"p{i}"} for i, p in enumerate(ports, 1)},
            )
        ]
    )


def _sensors(tmp_path: Path, rows, reg):
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    return {
        s["id"]: s
        for s in build_context(parse_files([str(p)]), registry=reg)["sensors"]
    }


def test_same_band_plants_differ_by_within_band_position(tmp_path: Path) -> None:
    # both in DRY (2140..3050): s1 near the wet edge, s2 near the dry edge. The
    # one closer to needing water (higher raw) must have the higher band_pos.
    sens = _sensors(
        tmp_path,
        [_soil("s1", 2265, "DRY"), _soil("s2", 2894, "DRY")],
        _reg("s1", "s2"),
    )
    assert sens["s1"]["band_lo"] == 2140 and sens["s1"]["band_hi"] == 3050
    assert sens["s1"]["band_pos"] < sens["s2"]["band_pos"]  # 2265 wetter than 2894
    assert 0.0 <= sens["s1"]["band_pos"] <= 1.0
    assert round(sens["s2"]["band_pos"], 2) == round((2894 - 2140) / (3050 - 2140), 2)


def test_dryness_is_a_monotonic_sortable_urgency_scalar(tmp_path: Path) -> None:
    sens = _sensors(
        tmp_path,
        [_soil("s1", 1400, "well watered"), _soil("s2", 2894, "DRY")],
        _reg("s1", "s2"),
    )
    # drier plant -> higher dryness -> sorts first for "most urgent"
    assert sens["s2"]["dryness"] > sens["s1"]["dryness"]
    assert round(sens["s2"]["dryness"], 3) == round((2894 - 900) / (3400 - 900), 3)


def test_no_position_where_there_is_no_signal(tmp_path: Path) -> None:
    sens = _sensors(
        tmp_path, [_soil("s1", 0, "submerged", quality="NO_SIGNAL")], _reg("s1")
    )
    s = sens["s1"]
    assert s["no_signal"] is True
    assert s["band_pos"] is None and s["dryness"] is None
    assert s["band_lo"] is None and s["band_hi"] is None


def test_no_position_for_an_unassigned_channel(tmp_path: Path) -> None:
    # registered board, no plant mapped -> unassigned -> no urgency invented
    reg = Registry(
        devices=[Device(device_id="classic", board=None, label=None, channels={})]
    )
    sens = _sensors(tmp_path, [_soil("s1", 2400, "DRY")], reg)
    assert sens["s1"]["unassigned"] is True
    assert sens["s1"]["band_pos"] is None and sens["s1"]["dryness"] is None
