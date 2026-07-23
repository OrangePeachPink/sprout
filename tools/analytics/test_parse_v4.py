"""#739 schema-v4 parse extension — config_id / rssi / uptime_s / heap / fault.

Contract: TELEMETRY_SCHEMA §13 + the merged firmware emit (#754). v4 is a strict
superset of v3, all additive (payload k=v + `#` header, ZERO new CANONICAL_COLUMNS),
so a pre-v4 row reads None on every v4 field - never stitched.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import parse_files

_V4_HEADER = (
    "# schema_version=4  fw=0.8.0  git=abc  config_id=a1b2c3d4  session_id=sess1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_V3_HEADER = (
    "# schema_version=3  fw=0.8.0  git=abc  session_id=sess1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _parse(tmp_path: Path, header: str, rows: str):
    p = tmp_path / "a.csv"
    p.write_text(header + _COLS + rows, encoding="utf-8")
    return parse_files([str(p)])


def _soil(sensor, raw, quality, payload):
    ts = "2026-07-05T00:00:30.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},sess1,y9d41p,{sensor},{raw},{quality},{payload}\n"
    )


def test_v4_payload_diagnostics_parse(tmp_path: Path) -> None:
    row = _soil(
        "s1",
        2400,
        "OK",
        "level=DRY;gpio=35;config_id=a1b2c3d4;rssi=-67;uptime_s=3600;heap=45000",
    )
    r = _parse(tmp_path, _V4_HEADER, row).readings[0]
    assert r.config_id == "a1b2c3d4"
    assert r.rssi == -67  # dBm, negative int
    assert r.uptime_s == 3600
    assert r.heap == 45000
    assert r.fault is None  # OK row -> no fault reason


def test_v4_config_id_is_header_authoritative(tmp_path: Path) -> None:
    row = _soil("s1", 2400, "OK", "level=DRY;config_id=a1b2c3d4")
    seg = _parse(tmp_path, _V4_HEADER, row).segments[0]
    assert seg.config_id == "a1b2c3d4"  # from the `# config_id=` header line


def test_v4_sensor_fault_carries_its_reason(tmp_path: Path) -> None:
    # firmware self-declares SENSOR_FAULT; the specific reason rides payload fault=
    row = _soil("s2", 400, "SENSOR_FAULT", "level=submerged;fault=stuck_wet")
    r = _parse(tmp_path, _V4_HEADER, row).readings[0]
    assert r.quality_flag == "SENSOR_FAULT"
    assert r.fault == "stuck_wet"


def test_v3_row_reads_none_on_every_v4_field_never_stitched(tmp_path: Path) -> None:
    row = _soil("s1", 2400, "OK", "level=DRY;gpio=35;device_seq=1")
    r = _parse(tmp_path, _V3_HEADER, row).readings[0]
    assert r.config_id is None
    assert r.rssi is None and r.uptime_s is None and r.heap is None
    assert r.fault is None


def test_dashboard_honors_firmware_declared_sensor_fault(tmp_path: Path) -> None:
    # the #739 consumer half: a firmware SENSOR_FAULT reads as a fault card, not a
    # moisture band - even if the raw is ABOVE the host's derived sub-rail floor.
    reg = Registry(
        devices=[
            Device(
                device_id="y9d41p",
                board="esp32dev",
                label=None,
                channels={"s2": {"plant_id": "p02", "plant_name": "pothos"}},
            )
        ]
    )
    # raw 1500 is a normal wet reading; only the firmware flag makes it a fault
    row = _soil("s2", 1500, "SENSOR_FAULT", "level=well watered;fault=dead_adc")
    p = tmp_path / "b.csv"
    p.write_text(_V4_HEADER + _COLS + row, encoding="utf-8")
    s = build_context(parse_files([str(p)]), registry=reg)["sensors"][0]
    assert s["sensor_fault"] is True
    assert s["band_ui"] == "sensor fault"  # never the moisture band
