#!/usr/bin/env python3
"""Tests for the solar geometry layer (PRD-0002 R1, #198).

python tools/analytics/test_env_solar.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import env_solar  # noqa: E402

# A public city-center reference (NOT anyone's home) - matches config/location.example.
_LAT, _LON, _TZ = 41.8781, -87.6298, -5


def test_solstice_noon_elevations() -> None:
    # Max daily elevation = 90 - lat + decl. decl = +23.44 (summer), -23.44 (winter).
    summer = env_solar.sun_events(_LAT, _LON, "2026-06-21", _TZ)
    winter = env_solar.sun_events(_LAT, _LON, "2026-12-21", _TZ)
    assert abs(summer["max_elevation_deg"] - (90 - _LAT + 23.44)) < 1.0
    assert abs(winter["max_elevation_deg"] - (90 - _LAT - 23.44)) < 1.0
    # sunrise before solar noon before sunset; daytime is longer in summer
    assert summer["sunrise"] < summer["solar_noon"] < summer["sunset"]
    assert winter["sunrise"] < winter["solar_noon"] < winter["sunset"]
    assert summer["sunrise"] < winter["sunrise"]  # earlier sunrise in summer


def test_equator_equinox_overhead() -> None:
    # At the equator on the equinox the noon sun is ~overhead (~90°).
    ev = env_solar.sun_events(0.0, 0.0, "2026-03-20", 0)
    assert ev["max_elevation_deg"] > 89.0


def test_azimuth_and_elevation_agree_at_noon() -> None:
    ev = env_solar.sun_events(_LAT, _LON, "2026-06-21", _TZ)
    hh, mm = (int(x) for x in ev["solar_noon"].split(":"))
    tz = timezone(timedelta(hours=_TZ))
    noon = datetime(2026, 6, 21, hh, mm, tzinfo=tz).astimezone(timezone.utc)
    pos = env_solar.solar_position(_LAT, _LON, noon)
    assert abs(pos["azimuth_deg"] - 180.0) < 5.0  # due south at solar noon (N hemi)
    assert abs(pos["elevation_deg"] - ev["max_elevation_deg"]) < 0.5
    # morning sun in the east (az < 180), afternoon in the west (az > 180)
    morn = datetime(2026, 6, 21, 9, 0, tzinfo=tz).astimezone(timezone.utc)
    aft = datetime(2026, 6, 21, 16, 0, tzinfo=tz).astimezone(timezone.utc)
    assert env_solar.solar_position(_LAT, _LON, morn)["azimuth_deg"] < 180.0
    assert env_solar.solar_position(_LAT, _LON, aft)["azimuth_deg"] > 180.0


def test_daylight_flag_and_series() -> None:
    tz = timezone(timedelta(hours=_TZ))
    noon = datetime(2026, 6, 21, 13, 0, tzinfo=tz).astimezone(timezone.utc)
    midnight = datetime(2026, 6, 21, 1, 0, tzinfo=tz).astimezone(timezone.utc)
    loc = {
        "latitude": _LAT,
        "longitude": _LON,
        "tz_offset_hours": _TZ,
        "skylight_window_local": ["13:00", "14:00"],
    }
    assert env_solar.solar_context(noon, loc)["is_daylight"] is True
    assert env_solar.solar_context(midnight, loc)["is_daylight"] is False
    assert env_solar.in_skylight_window(noon, loc) is True
    # series spans the range at the requested step
    s = env_solar.solar_series(_LAT, _LON, midnight, noon, step_min=30)
    assert len(s) >= 20 and all("elevation_deg" in p for p in s)


def test_skylight_window_optional() -> None:
    # no window configured -> None (opt-in, location-specific)
    loc = {"latitude": _LAT, "longitude": _LON, "tz_offset_hours": _TZ}
    assert env_solar.in_skylight_window(datetime.now(timezone.utc), loc) is None


def test_load_location_absent_and_example() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        assert env_solar.load_location(tmp / "nope.json") is None  # clean None offline
        example = _HERE.parents[1] / "config" / "location.example.json"
        loc = env_solar.load_location(example)
        assert loc is not None and "latitude" in loc and "longitude" in loc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_solstice_noon_elevations,
        test_equator_equinox_overhead,
        test_azimuth_and_elevation_agree_at_noon,
        test_daylight_flag_and_series,
        test_skylight_window_optional,
        test_load_location_absent_and_example,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
