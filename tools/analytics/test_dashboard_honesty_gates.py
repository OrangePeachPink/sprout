"""The two #486-blocking honesty gates (#616 / #617), code-located by Design-QA.

#616: an unwired channel (registered device, no plant assigned) earns no band -
the display gate consults the registry, not just the firmware quality_flag.
#617: cal_provisional fails CLOSED - a WiFi board can't claim 'bench-verified'
from the absence of a banner it never carries.
Both gate DISPLAY only; raw rows stay fully queryable (house rule).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=t  run=honesty\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _soil(
    device: str, sid: str, raw: int, *, quality: str = "OK", extra: str = ""
) -> str:
    ts = "2026-07-04T00:00:30.000Z"
    payload = "level=well watered;gpio=36" + (f";{extra}" if extra else "")
    return (
        f"plants.soil,{ts},{ts[:-1]},sess1,{device},{sid},{raw},{quality},{payload}\n"
    )


def _write(tmp_path: Path, rows: list[str], name="a.csv", header=_HEADER) -> Path:
    p = tmp_path / name
    p.write_text(header + _COLS + "".join(rows), encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# #616: unwired-by-registry channels earn no band (even at firmware quality OK)
# --------------------------------------------------------------------------- #


def test_registered_channel_with_no_plant_reads_unwired_despite_ok_quality(
    tmp_path: Path,
) -> None:
    # the S3 case: a registered board, a floating pin reading OK at firmware
    # level, no plant assigned -> unwired, no band. This is the exact HONESTY FAIL.
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3",
                label=None,
                channels={},  # declared unwired
                base_url="http://s3.local",
            )
        ]
    )
    log = _write(tmp_path, [_soil("sprout-s3-01", "s1", 1650, quality="OK")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["no_signal"] is True
    assert s["band_ui"] == "no signal" and s["mood"] == "Unwired"
    assert s["band_color"] == "#9A8480"  # never a band colour
    # ...but the raw row is still fully present + queryable (display gates only)
    assert s["raw_last"] == 1650


def test_registered_channel_with_a_plant_still_earns_its_band(tmp_path: Path) -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s1": {"plant_id": "p01", "plant_name": "Monstera"}},
            )
        ]
    )
    log = _write(tmp_path, [_soil("classic", "s1", 1500, quality="OK")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["no_signal"] is False
    assert s["band_ui"] != "no signal"  # a wired, assigned channel keeps its band


def test_UNregistered_device_is_never_gated_no_false_unwired(tmp_path: Path) -> None:
    """The guard against regressing the common case: a board NOT in the registry
    (a fresh checkout with no config) still renders its real readings - we don't
    claim to know its wiring, so an OK reading keeps its band."""
    log = _write(tmp_path, [_soil("some-unregistered-board", "s1", 1500, quality="OK")])
    s = build_context(parse_files([str(log)]), registry=Registry())["sensors"][0]
    assert s["no_signal"] is False  # empty registry -> not gated
    assert s["band_ui"] != "no signal"


def test_firmware_no_signal_still_gates_even_when_registered(tmp_path: Path) -> None:
    # the original signal is preserved: firmware NO_SIGNAL gates regardless of
    # registry state (a wired-and-assigned channel can still lose signal)
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board=None,
                label=None,
                channels={"s1": {"plant_id": "p01"}},
            )
        ]
    )
    log = _write(tmp_path, [_soil("classic", "s1", 1234, quality="NO_SIGNAL")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["no_signal"] is True


# --------------------------------------------------------------------------- #
# #617: cal_provisional fails CLOSED - WiFi can't claim bench-verified from silence
# --------------------------------------------------------------------------- #


def test_wifi_group_is_provisional_without_a_banner(tmp_path: Path) -> None:
    # a WiFi board carries no cal banner; absence must NOT read as verified
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3",
                label=None,
                channels={"s1": {"plant_id": "p05", "plant_name": "Fern"}},
                base_url="http://s3.local",
            )
        ]
    )
    log = _write(
        tmp_path,
        [_soil("sprout-s3-01", "s1", 1500, extra="transport=wifi_poll;device_seq=1")],
    )
    d = build_context(parse_files([str(log)]), registry=reg)["devices"][0]
    assert d["transport"] == "wifi"
    assert d["cal_provisional"] is True  # earned by evidence, not inferred from silence


def test_serial_group_without_placeholder_stays_bench_verified(tmp_path: Path) -> None:
    # the tethered classic: its banner IS meaningful - no PLACEHOLDER over serial
    # is the firmware positively asserting cal_verified=true. Not regressed.
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s1": {"plant_id": "p01", "plant_name": "Monstera"}},
            )
        ]
    )
    log = _write(tmp_path, [_soil("classic", "s1", 1500)])  # serial, no banner
    d = build_context(parse_files([str(log)]), registry=reg)["devices"][0]
    assert d["transport"] == "serial"
    assert d["cal_provisional"] is False  # banner-absence over serial = verified


def test_serial_group_with_placeholder_is_provisional(tmp_path: Path) -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3",
                label=None,
                channels={"s1": {"plant_id": "p05"}},
            )
        ]
    )
    header = (
        "# fw=0.8.0  git=t  run=honesty\n"
        "# board cal: PLACEHOLDER (classic endpoints, not bench-verified - #443)\n"
        "# device_id=sprout-s3-01\n"
        "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
    )
    log = _write(tmp_path, [_soil("sprout-s3-01", "s1", 1500)], header=header)
    d = build_context(parse_files([str(log)]), registry=reg)["devices"][0]
    assert d["cal_provisional"] is True
