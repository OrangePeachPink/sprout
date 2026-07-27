"""Tests for context_source through the ADR-0021 boundary (#562, ADR-0023 v2).

The tag rides payload k=v (the #559 review decision); the values ride the
long-reserved context columns. Additive: a pre-#562 row parses exactly as
before, tags honestly None.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tools.analytics.parse_v1 import CONTEXT_SOURCE_CLASS, context_class, parse_file

_LOGGER = Path(__file__).resolve().parents[1] / "logger"
from tools.logger.context_fill import ContextFiller  # noqa: E402
from tools.logger.plants_logger import RotatingCsv, parse_device_line  # noqa: E402

_UTC_0 = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def _crc(body: str) -> str:
    c = 0
    for ch in body:
        c ^= ord(ch) & 0xFF
    return f"{body}*{c:02X}"


_SOIL = _crc(
    "plants.soil,sess1,plants_esp32_test,0.8.0,60000,"
    "UMLIFE_v2_TLC555,s1,origplant,soil_moisture,1500,,,OK,"
    "level=well watered;gpio=36"
)
_ENV_T = _crc(
    "plants.env,sess1,plants_esp32_test,0.8.0,59000,"
    "SHT45,sht45,breadboard_near_esp32,ambient_temp,24312,21.84,degC,OK,"
    "mount=breadboard_near_esp32"
)
_ENV_RH = _crc(
    "plants.env,sess1,plants_esp32_test,0.8.0,59000,"
    "SHT45,sht45,breadboard_near_esp32,ambient_rh,31544,48.10,pctRH,OK,"
    "mount=breadboard_near_esp32"
)


def test_golden_roundtrip_env_then_soil_carries_tagged_context(
    tmp_path: Path,
) -> None:
    """The full spine: env rows feed the filler, the soil row lands in the CSV
    with values in columns + tags in payload, and parse_v1 reads both back."""
    rc = RotatingCsv(str(tmp_path))
    filler = ContextFiller(clock=lambda: 100.0)
    for sid, line in enumerate((_ENV_T, _ENV_RH, _SOIL), start=1):
        dev = parse_device_line(line)
        assert dev is not None
        filler.observe(dev)
        ctx = (
            filler.context_for()
            if dev["record_type"].startswith("plants.soil")
            else None
        )
        rc.write(dev, sid, _UTC_0, context=ctx)

    data = parse_file(next(iter(tmp_path.glob("*.csv"))))
    soil = [r for r in data.readings if r.record_type == "plants.soil"]
    assert len(soil) == 1
    r = soil[0]
    assert r.temp_context_c == 21.84
    assert r.rh_context_pct == 48.10
    assert r.context_source == "sht45_onrig"
    assert context_class(r.context_source) == "plant_local"  # trust travels
    assert r.raw_value == 1500 and r.band == "well watered"  # soil untouched
    # the env rows remain their own fully-queryable rows, un-contextualized
    env = [r for r in data.readings if r.record_type == "plants.env"]
    assert len(env) == 2
    assert all(e.context_source is None for e in env)


def test_pre_562_row_parses_with_honest_none_tags(tmp_path: Path) -> None:
    rc = RotatingCsv(str(tmp_path))
    rc.write(parse_device_line(_SOIL), 1, _UTC_0)  # no context arg at all
    r = parse_file(next(iter(tmp_path.glob("*.csv")))).readings[0]
    assert r.context_source is None
    assert r.pressure_context_source is None
    assert r.temp_context_c is None and r.rh_context_pct is None


def test_context_class_vocabulary() -> None:
    assert context_class("sht45_onrig") == "plant_local"
    assert context_class("zigbee_room") == "room"
    assert context_class("weather_openmeteo") == "exterior"
    assert context_class("mystery_sensor") is None  # unknown -> never guessed
    assert context_class(None) is None
    # interior classes only ever come from interior tags
    interior = {
        t for t, c in CONTEXT_SOURCE_CLASS.items() if c in ("plant_local", "room")
    }
    assert "weather_openmeteo" not in interior
