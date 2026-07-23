"""Ratification guard for the plants.env schema (#373/#374): env rows (calibrated
SHT45 temp/RH + raw AS7263 NIR) coexist in a soil log without polluting the soil
views or tripping the soil raw-only contract (DEC-#38 is soil-specific).
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# fw=0.7.0  git=t  run=env\n# device_id=plants_esp32_env  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,sensor_model,sensor_id,"
    "sensor_position,channel,raw_value,value,unit,quality_flag,payload\n"
)


def _soil(ts: str, sid: str, raw: int) -> str:
    return (
        f"plants.soil,{ts},{ts.replace('Z', '')},s1,UMLIFE_v2_TLC555,{sid},"
        f"origplant,soil_moisture,{raw},,,OK,level=well watered;gpio=36\n"
    )


def _sht45(ts: str, channel: str, value: str, unit: str) -> str:
    return (
        f"plants.env,{ts},{ts.replace('Z', '')},s1,SHT45,env,"
        f"breadboard_near_esp32,{channel},,{value},{unit},OK,mount=breadboard_near_esp32\n"
    )


def _as7263(ts: str, channel: str, count: int) -> str:
    return (
        f"plants.env,{ts},{ts.replace('Z', '')},s1,AS7263,env,"
        f"breadboard_near_esp32,{channel},{count},,,OK,gain=16;itime_ms=50;aim=skylight_beam\n"
    )


def _write(path: Path) -> None:
    rows = [
        _soil("2026-06-29T00:00:30.000Z", "s1", 1500),
        _soil("2026-06-29T00:00:30.000Z", "s2", 1550),
        # env rows interleaved in the same log (the esp32dev_env build emits both)
        _sht45("2026-06-29T00:00:30.000Z", "ambient_temp", "23.5", "degC"),
        _sht45("2026-06-29T00:00:30.000Z", "ambient_rh", "45.2", "pctRH"),
        _as7263("2026-06-29T00:00:30.000Z", "nir_610", 1234),
        _as7263("2026-06-29T00:00:30.000Z", "nir_860", 2048),
        _soil("2026-06-29T00:01:00.000Z", "s1", 1505),
        _soil("2026-06-29T00:01:00.000Z", "s2", 1555),
    ]
    path.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")


def test_env_rows_parse_with_their_classes(tmp_path: Path) -> None:
    log = tmp_path / "mixed.csv"
    _write(log)
    data = parse_files([str(log)])
    by_rt = {}
    for r in data.readings:
        by_rt.setdefault(r.record_type, []).append(r)
    assert "plants.env" in by_rt and "plants.soil" in by_rt
    # SHT45 is factory-calibrated -> value/unit populated (NOT the soil raw-only rule)
    temp = next(r for r in by_rt["plants.env"] if r.channel == "ambient_temp")
    assert temp.value == 23.5 and temp.unit == "degC"
    # AS7263 stays raw-only: a raw count, no fabricated engineering value
    nir = next(r for r in by_rt["plants.env"] if r.channel == "nir_610")
    assert nir.raw_value == 1234 and nir.value is None and (nir.unit or "") == ""


def test_env_rows_do_not_pollute_soil_views(tmp_path: Path) -> None:
    log = tmp_path / "mixed.csv"
    _write(log)
    ctx = build_context(parse_files([str(log)]))
    # the soil trajectory/sensors carry ONLY soil channels — no ambient_/nir_ leakage
    sensor_ids = {s["id"] for s in ctx["sensors"]}
    assert sensor_ids == {"s1", "s2"}, sensor_ids
    assert not any(
        s["id"].startswith(("ambient", "nir", "env")) for s in ctx["sensors"]
    )
    # cross-channel spread is soil-only: ~50 (s2-s1), NOT polluted by NIR counts (1234+)
    # #651: spread is a per-device list; assert the max across series.
    assert ctx["spread"], ctx["spread"]
    spread_max = max(s["max"] for s in ctx["spread"])
    assert spread_max < 200, ctx["spread"]
    # integrity counts only the soil readings (4), not the 4 env rows
    assert ctx["integrity"]["total"] == 4, ctx["integrity"]["total"]


def test_calibrated_env_value_does_not_trip_soil_raw_only(tmp_path: Path) -> None:
    # the #324 contract check is soil-specific: env value/unit must NOT read as a
    # "CONTRACT VIOLATION" of the soil raw-only law.
    log = tmp_path / "mixed.csv"
    _write(log)
    ctx = build_context(parse_files([str(log)]))
    contract = ctx["provenance"]["contract"]
    assert contract["raw_only"] is True, contract
    assert "VIOLATION" not in contract["label"]
