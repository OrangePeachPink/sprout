"""Tests for the interior-ambient context fill (#562, ADR-0023 v2).

Pins the fences as TESTS, not conventions (the issue's explicit ask):
weather never fills interior temp/RH; die temp never fills anything, even
misconfigured; pressure alone may cross from the exterior family, tagged.
"""

from __future__ import annotations

from datetime import datetime, timezone

from tools.logger.context_fill import DEFAULT_FRESHNESS_S, ContextFiller
from tools.logger.plants_logger import LOGGER_VERSION, parse_device_line, stamp_row

_UTC_0 = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)


def _env_line(
    *,
    model: str = "SHT45",
    sensor: str = "sht45",
    position: str = "breadboard_near_esp32",
    channel: str = "ambient_temp",
    raw: str = "24312",
    value: str = "21.84",
    unit: str = "degC",
    quality: str = "OK",
    payload: str = "mount=breadboard_near_esp32",
) -> dict:
    body = (
        f"plants.env,sess1,plants_esp32_test,0.8.0,60000,"
        f"{model},{sensor},{position},{channel},{raw},{value},{unit},"
        f"{quality},{payload}"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    d = parse_device_line(f"{body}*{crc:02X}")
    assert d is not None
    return d


def _die_temp_line(quality: str = "OK") -> dict:
    """The firmware's exact die-temp identity (#345): ESP32/esp32_die/on_chip/
    die_temp + the board-proxy payload label."""
    body = (
        "plants.env,sess1,plants_esp32_test,0.8.0,60000,"
        f"ESP32,esp32_die,on_chip,die_temp,,53.33,degC,{quality},"
        "source=esp32_die;cal=uncalibrated_board_proxy;api=temperatureRead"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    d = parse_device_line(f"{body}*{crc:02X}")
    assert d is not None
    return d


def _clock(t: list[float]):
    return lambda: t[0]


# --------------------------------------------------------------------------- #
# the happy path: SHT45 fills as a plant_local instance
# --------------------------------------------------------------------------- #


def test_sht45_fills_temp_and_rh_tagged_sht45_onrig() -> None:
    t = [100.0]
    f = ContextFiller(clock=_clock(t))
    f.observe(_env_line(channel="ambient_temp", value="21.84", unit="degC"))
    f.observe(_env_line(channel="ambient_rh", value="48.10", unit="pctRH"))
    ctx = f.context_for()
    assert ctx == {
        "temp_context_c": "21.84",
        "rh_context_pct": "48.10",
        "context_source": "sht45_onrig",
    }


def test_nothing_fresh_means_honestly_empty() -> None:
    f = ContextFiller(clock=lambda: 100.0)
    assert f.context_for() == {}


def test_stale_reading_never_fills() -> None:
    t = [100.0]
    f = ContextFiller(clock=_clock(t))
    f.observe(_env_line())
    t[0] = 100.0 + DEFAULT_FRESHNESS_S + 1
    assert f.context_for() == {}  # the plant's air NOW, not minutes ago


def test_non_ok_quality_never_fills() -> None:
    f = ContextFiller(clock=lambda: 100.0)
    f.observe(_env_line(quality="SUSPECT"))
    f.observe(_env_line(channel="ambient_rh", quality="NO_SIGNAL", value="48.1"))
    assert f.context_for() == {}


def test_nir_bands_are_not_ambient_quantities() -> None:
    f = ContextFiller(clock=lambda: 100.0)
    f.observe(_env_line(model="SHT45", channel="nir_730", value="512", unit=""))
    assert f.context_for() == {}


def test_soil_rows_never_feed_the_cache() -> None:
    f = ContextFiller(clock=lambda: 100.0)
    body = (
        "plants.soil,sess1,plants_esp32_test,0.8.0,60000,"
        "UMLIFE_v2_TLC555,s1,origplant,soil_moisture,1500,,,OK,gpio=36"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    f.observe(parse_device_line(f"{body}*{crc:02X}"))
    assert f.context_for() == {}


# --------------------------------------------------------------------------- #
# the room class: a seam - structure now, integrations later (#563)
# --------------------------------------------------------------------------- #

_SEAM_MAP = {
    "SHT45": ("plant_local", "sht45_onrig"),
    "ZBTEMP": ("room", "zigbee_room"),  # a hypothetical future integration
}


def test_room_class_fills_when_no_plant_local_exists() -> None:
    f = ContextFiller(_SEAM_MAP, clock=lambda: 100.0)
    f.observe(_env_line(model="ZBTEMP", sensor="zb1", value="20.50"))
    ctx = f.context_for()
    assert ctx["temp_context_c"] == "20.50"
    assert ctx["context_source"] == "zigbee_room"


def test_plant_local_beats_room() -> None:
    f = ContextFiller(_SEAM_MAP, clock=lambda: 100.0)
    f.observe(_env_line(model="ZBTEMP", sensor="zb1", value="20.50"))
    f.observe(_env_line(model="SHT45", value="21.84"))
    ctx = f.context_for()
    # exactly ONE source fills - the nearer class, never a blend (ADR-0022)
    assert ctx["context_source"] == "sht45_onrig"
    assert ctx["temp_context_c"] == "21.84"


# --------------------------------------------------------------------------- #
# the fences - pinned by test, not convention (#562's explicit ask)
# --------------------------------------------------------------------------- #


def test_weather_can_never_be_configured_as_an_interior_source() -> None:
    # the ADR-0023 fence, structural: an interior map entry declaring an
    # exterior/weather class is refused at construction, not silently accepted
    raised = False
    try:
        ContextFiller({"OPENMETEO": ("exterior", "weather_openmeteo")})
    except ValueError:
        raised = True
    assert raised, "weather in the interior source map must be refused"


def test_interior_stays_empty_even_when_weather_pressure_exists() -> None:
    """The #562 AC verbatim: a row with no plant_local/room source has EMPTY
    interior context even when weather data exists for that window."""
    f = ContextFiller(
        clock=lambda: 100.0,
        pressure_source=lambda: (1013.2, "weather_openmeteo"),
    )
    ctx = f.context_for()
    assert "temp_context_c" not in ctx and "rh_context_pct" not in ctx
    assert "context_source" not in ctx  # no interior tag without interior values
    # ... while the pressure exception fills, tagged per-quantity (§3)
    assert ctx["pressure_context_hpa"] == "1013.2"
    assert ctx["pressure_context_source"] == "weather_openmeteo"


def test_pressure_exception_rides_alongside_an_interior_fill() -> None:
    # mixed-source rows are the COMMON case (SHT45 has no pressure) - the
    # per-quantity tags keep both provenances separately resolvable
    f = ContextFiller(
        clock=lambda: 100.0,
        pressure_source=lambda: (1013.2, "weather_openmeteo"),
    )
    f.observe(_env_line())
    ctx = f.context_for()
    assert ctx["context_source"] == "sht45_onrig"
    assert ctx["pressure_context_source"] == "weather_openmeteo"


def test_die_temp_never_fills_even_with_a_hostile_source_map() -> None:
    """ADR-0023 §5 pinned structurally: the die-temp identity is excluded
    BEFORE the source map is consulted, so even a misconfigured map entry
    (ESP32 declared plant_local) cannot make chip junction temp ambient."""
    hostile = {"ESP32": ("plant_local", "esp32_die")}
    f = ContextFiller(hostile, clock=lambda: 100.0)
    f.observe(_die_temp_line(quality="OK"))  # OK quality - still excluded
    assert f.context_for() == {}


def test_die_temp_in_the_same_window_never_pollutes_a_real_fill() -> None:
    f = ContextFiller(clock=lambda: 100.0)
    f.observe(_env_line(value="21.84"))
    f.observe(_die_temp_line())  # 53.33 degC chip junction, same sweep
    ctx = f.context_for()
    assert ctx["temp_context_c"] == "21.84"  # the SHT45's value, untouched
    assert ctx["context_source"] == "sht45_onrig"


# --------------------------------------------------------------------------- #
# stamp_row carries the fill: values in columns, tags in payload
# --------------------------------------------------------------------------- #


def test_stamp_row_places_values_in_columns_and_tags_in_payload() -> None:
    body = (
        "plants.soil,sess1,plants_esp32_test,0.8.0,60000,"
        "UMLIFE_v2_TLC555,s1,origplant,soil_moisture,1500,,,OK,"
        "level=well watered;gpio=36"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    dev = parse_device_line(f"{body}*{crc:02X}")
    row = stamp_row(
        dev,
        1,
        _UTC_0,
        LOGGER_VERSION,
        context={
            "temp_context_c": "21.84",
            "rh_context_pct": "48.10",
            "context_source": "sht45_onrig",
            "pressure_context_hpa": "1013.2",
            "pressure_context_source": "weather_openmeteo",
        },
    )
    assert row["temp_context_c"] == "21.84"
    assert row["rh_context_pct"] == "48.10"
    assert row["pressure_context_hpa"] == "1013.2"
    # tags ride payload k=v (the #559 review decision), after device keys
    assert "context_source=sht45_onrig" in row["payload"]
    assert "pressure_context_source=weather_openmeteo" in row["payload"]
    assert row["payload"].startswith("level=well watered;gpio=36")


def test_stamp_row_without_context_is_byte_identical_to_before() -> None:
    body = (
        "plants.soil,sess1,plants_esp32_test,0.8.0,60000,"
        "UMLIFE_v2_TLC555,s1,origplant,soil_moisture,1500,,,OK,gpio=36"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    dev = parse_device_line(f"{body}*{crc:02X}")
    assert stamp_row(dev, 1, _UTC_0, LOGGER_VERSION) == stamp_row(
        dev, 1, _UTC_0, LOGGER_VERSION, context=None
    )
    row = stamp_row(dev, 1, _UTC_0, LOGGER_VERSION, context={})
    assert row["temp_context_c"] == "" and "context_source" not in row["payload"]
