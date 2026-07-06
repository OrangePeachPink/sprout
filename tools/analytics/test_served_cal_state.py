"""#404 host cal-state reader — the served-cal-state half of #617b.

A board that positively asserts a verified per-channel cal over the wire
(`# cal_ch … confidence=calibrated`, #507) renders NOT provisional even over WiFi;
silence still fails closed (#617). So the bench-calibrated classic stops rendering
`cal · provisional`; the uncalibrated C5 stays provisional.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_CAL_LINE = (
    "# cal_ch s1: bounds=3123,2140,1830,1520,1150,969 "
    "src=bench_248 date=2026-06-24 confidence=calibrated scope=channel\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s1": {"plant_id": "p01", "plant_name": "pothos"}},
                base_url="http://classic.local",
            )
        ]
    )


def _device(tmp_path: Path, *, cal_line: str = "", placeholder="", wifi=True):
    header = (
        "# schema_version=4  fw=0.8.0  git=t  device_id=classic  session_id=sess1\n"
        + placeholder
        + "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
        + cal_line
    )
    extra = "transport=wifi_poll;device_seq=1" if wifi else ""
    payload = "level=DRY;gpio=35" + (f";{extra}" if extra else "")
    row = f"plants.soil,2026-07-05T00:00:30.000Z,x,sess1,classic,s1,2400,OK,{payload}\n"
    p = tmp_path / "a.csv"
    p.write_text(header + _COLS + row, encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=_reg())["devices"][0]


def test_wifi_board_asserting_calibrated_cal_is_not_provisional(tmp_path: Path) -> None:
    d = _device(tmp_path, cal_line=_CAL_LINE, wifi=True)
    assert d["transport"] == "wifi"
    assert d["cal_provisional"] is False  # the classic clears — positive assertion


def test_wifi_board_with_no_cal_assertion_stays_provisional(tmp_path: Path) -> None:
    d = _device(tmp_path, cal_line="", wifi=True)
    assert d["cal_provisional"] is True  # fail-closed: silence != verified (#617)


def test_wifi_board_asserting_only_provisional_stays_provisional(
    tmp_path: Path,
) -> None:
    prov = _CAL_LINE.replace("confidence=calibrated", "confidence=provisional")
    d = _device(tmp_path, cal_line=prov, wifi=True)
    assert d["cal_provisional"] is True  # the uncalibrated C5 case


def test_placeholder_banner_forces_provisional_even_with_calibrated_cal(
    tmp_path: Path,
) -> None:
    d = _device(
        tmp_path,
        cal_line=_CAL_LINE,
        placeholder="# board cal: PLACEHOLDER (not bench-verified)\n",
        wifi=False,
    )
    assert d["cal_provisional"] is True  # a stated non-cal wins over a cal_ch


def test_serial_board_without_placeholder_stays_verified(tmp_path: Path) -> None:
    d = _device(tmp_path, cal_line="", wifi=False)
    assert d["transport"] == "serial"
    assert d["cal_provisional"] is False  # banner-absence over serial = verified
