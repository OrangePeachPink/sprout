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
    device: str,
    sid: str,
    raw: int,
    *,
    quality: str = "OK",
    level: str = "well watered",
    extra: str = "",
) -> str:
    ts = "2026-07-04T00:00:30.000Z"
    payload = f"level={level};gpio=36" + (f";{extra}" if extra else "")
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


def test_registered_channel_with_no_plant_is_unassigned_not_no_signal(
    tmp_path: Path,
) -> None:
    # bench feedback (2026-07-04, live QA over WiFi): a registered board reporting
    # a REAL reading with no plant assigned yet is *unassigned*, NOT *no signal*.
    # The old gate blanked it - reading a connected probe's valid air-dry ADC as
    # "the probe is dead". The honest split: show the raw (raw counts are truth),
    # but make NO plant-moisture claim (the floating-pin protection lives in the
    # suppressed MOOD, not in hiding the reading).
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3",
                label=None,
                channels={},  # no plant assigned yet
                base_url="http://s3.local",
            )
        ]
    )
    log = _write(tmp_path, [_soil("sprout-s3-01", "s1", 1650, quality="OK")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["no_signal"] is False  # a live reading is NOT "no signal"
    assert s["unassigned"] is True
    assert s["band_ui"] == "unassigned" and s["mood"] == "No plant"
    assert s["band_color"] == "#9A8480"  # neutral, never a moisture-band colour
    # the raw is now SHOWN (not blanked): the bench can watch the signal live
    assert s["raw_last"] == 1650


def test_unassigned_channel_makes_no_plant_moisture_claim(tmp_path: Path) -> None:
    # the #616 protection preserved differently: a floating pin can read a
    # plausible band, so an unassigned channel must never present a moisture MOOD
    # or a plant name - even though its raw is shown.
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={},
                base_url="http://classic.local",
            )
        ]
    )
    # 1500 would classify as a wet band if we (wrongly) claimed one
    log = _write(tmp_path, [_soil("classic", "s1", 1500, quality="OK")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["unassigned"] is True
    assert s["plant_name"] is None and s["plant_id"] is None
    assert s["mood"] == "No plant"  # never "Thriving"/"Moist" for an unmapped pin
    assert s["raw_last"] == 1500  # ...but the truth is still visible


def test_unassigned_channel_exposes_fw_band_for_the_bench_label(tmp_path: Path) -> None:
    # #658: the fw-band bench affordance renders `fw · <band>` from s.band_fw on an
    # unassigned card - the label your eyes need as probes move between cups. Pin
    # that the data is present AND the #656 honesty line holds: the instrument's
    # own band is exposed, but NO moisture mood and NO band colour are claimed.
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={},
                base_url="http://classic.local",
            )
        ]
    )
    # the real bench read: air-dry ADC on a connected-but-unassigned probe
    log = _write(tmp_path, [_soil("classic", "s1", 3057, level="air-dry")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["unassigned"] is True
    assert s["band_fw"] == "air-dry"  # the instrument's band the label renders
    assert s["mood"] == "No plant"  # ...with no moisture mood (the honesty line)
    assert s["band_color"] == "#9A8480"  # neutral - never a band-coloured chip
    assert s["raw_last"] == 3057  # the raw the bench watches during calibration


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
# #670: a sub-wet-rail soil raw is a SENSOR FAULT, never a moisture band
# --------------------------------------------------------------------------- #


def test_sub_wet_rail_reading_is_a_sensor_fault_not_a_band(tmp_path: Path) -> None:
    # the P11 s3 case: an assigned channel whose probe shorted and stuck at ~420 -
    # below the physical wet rail. It must read "sensor fault", NOT the moisture
    # band the firmware emitted (submerged) - a dead probe can't be a drowning plant.
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s3": {"plant_id": "p11", "plant_name": "corn-plant"}},
            )
        ]
    )
    log = _write(tmp_path, [_soil("classic", "s3", 420, level="submerged")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["sensor_fault"] is True
    assert s["band_ui"] == "sensor fault" and s["mood"] == "Implausible"
    assert s["band_ui"] != "Saturated"  # never renders the impossible band
    assert s["raw_last"] == 420  # ...but the raw is preserved (truth, still shown)


def test_dead_board_near_zero_reads_as_fault_not_saturated(tmp_path: Path) -> None:
    # the live s3-1 board case: a disconnected board floating to ~0-7 raw was
    # rendering all four channels as "Saturated - soaked". Zero is a fault.
    reg = Registry(
        devices=[
            Device(device_id="s3-1", board=None, label=None, channels={}),
        ]
    )
    log = _write(tmp_path, [_soil("s3-1", "s1", 4, level="submerged")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["sensor_fault"] is True
    assert s["band_ui"] == "sensor fault"


def test_genuine_saturation_is_not_a_fault(tmp_path: Path) -> None:
    # a real saturated reading (just below the wettest cal bound, but ABOVE the
    # physical rail) is honest wet soil - it must keep its band, not trip the fault.
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s1": {"plant_id": "p01", "plant_name": "pothos"}},
            )
        ]
    )
    log = _write(tmp_path, [_soil("classic", "s1", 980, level="submerged")])
    s = build_context(parse_files([str(log)]), registry=reg)["sensors"][0]
    assert s["sensor_fault"] is False
    assert s["band_ui"] != "sensor fault"  # 980 is real saturation, not a fault


def test_implausible_wet_is_a_parse_boundary_flag_raw_untouched(tmp_path: Path) -> None:
    # the flag lives on Reading (the single boundary), raw preserved; env readings
    # (huge raw) never trip it.
    from parse_v1 import IMPLAUSIBLE_WET_FLOOR

    log = _write(
        tmp_path,
        [_soil("classic", "s1", 420), _soil("classic", "s2", 980)],
    )
    readings = {r.sensor_id: r for r in parse_files([str(log)]).readings}
    assert readings["s1"].implausible_wet is True
    assert readings["s1"].raw_value == 420  # raw never altered
    assert readings["s2"].implausible_wet is False
    assert IMPLAUSIBLE_WET_FLOOR == 500  # documented, tunable floor


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
