"""Tests for the R3 env-join layer in dashboard.py (#198 R3/R4)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import (
    _night_bands,
    _weather_hourly_join,
    build_env_context,
)

# A fixed UTC window: 2026-06-25 00:00 → 06:00 UTC (6h — short + deterministic)
_START = datetime(2026, 6, 25, 0, 0, 0, tzinfo=timezone.utc)
_END = datetime(2026, 6, 25, 6, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# _night_bands
# --------------------------------------------------------------------------- #


def test_night_bands_empty_series() -> None:
    assert _night_bands([], _START, _END) == []


def test_night_bands_all_night() -> None:
    # elevation always below horizon -> one continuous night band for the window
    pts = [
        {"t": _START + timedelta(minutes=i * 10), "elevation_deg": -10.0}
        for i in range(37)
    ]
    bands = _night_bands(pts, _START, _END)
    assert len(bands) == 1
    assert bands[0]["x0"] == 0.0
    assert bands[0]["x1"] == pytest_approx(6.0, abs=0.1)


def test_night_bands_all_day() -> None:
    pts = [
        {"t": _START + timedelta(minutes=i * 10), "elevation_deg": 30.0}
        for i in range(37)
    ]
    assert _night_bands(pts, _START, _END) == []


def test_night_bands_single_transition() -> None:
    # Day for first half, night for second (transitions at hour 3)
    pts = []
    for i in range(37):
        t = _START + timedelta(minutes=i * 10)
        h = i * 10 / 60  # hours into window
        pts.append({"t": t, "elevation_deg": 5.0 if h < 3 else -5.0})
    bands = _night_bands(pts, _START, _END)
    assert len(bands) == 1
    assert bands[0]["x0"] == pytest_approx(3.0, abs=0.2)
    assert bands[0]["x1"] == pytest_approx(6.0, abs=0.1)


def test_night_bands_starts_with_night_then_day() -> None:
    pts = []
    for i in range(37):
        t = _START + timedelta(minutes=i * 10)
        h = i * 10 / 60
        pts.append({"t": t, "elevation_deg": -5.0 if h < 2 else 5.0})
    bands = _night_bands(pts, _START, _END)
    assert len(bands) == 1
    assert bands[0]["x0"] == 0.0
    assert bands[0]["x1"] == pytest_approx(2.0, abs=0.2)


# --------------------------------------------------------------------------- #
# _weather_hourly_join
# --------------------------------------------------------------------------- #


def test_weather_hourly_join_basic() -> None:
    hourly = [
        {"time_utc": "2026-06-25T01:00", "cloud_cover": 75, "shortwave_radiation": 0},
        {"time_utc": "2026-06-25T03:00", "cloud_cover": 20, "shortwave_radiation": 50},
        {"time_utc": "2026-06-25T08:00", "cloud_cover": 5, "shortwave_radiation": 200},
    ]
    result = _weather_hourly_join(hourly, _START, _END)
    assert len(result) == 2  # 08:00 is after _END (06:00)
    assert result[0]["cloud_cover"] == 75
    assert result[0]["x"] == pytest_approx(1.0, abs=0.01)
    assert result[1]["cloud_cover"] == 20
    assert result[1]["x"] == pytest_approx(3.0, abs=0.01)


def test_weather_hourly_join_empty() -> None:
    assert _weather_hourly_join([], _START, _END) == []


def test_weather_hourly_join_bad_time_skipped() -> None:
    hourly = [
        {"time_utc": "not-a-date", "cloud_cover": 50, "shortwave_radiation": 0},
        {"time_utc": "2026-06-25T02:00", "cloud_cover": 30, "shortwave_radiation": 0},
    ]
    result = _weather_hourly_join(hourly, _START, _END)
    assert len(result) == 1
    assert result[0]["cloud_cover"] == 30


def test_weather_hourly_join_none_time_skipped() -> None:
    hourly = [{"time_utc": None, "cloud_cover": 50, "shortwave_radiation": 0}]
    assert _weather_hourly_join(hourly, _START, _END) == []


# --------------------------------------------------------------------------- #
# build_env_context — no location config present (offline / no-config path)
# --------------------------------------------------------------------------- #


def test_build_env_context_no_location(tmp_path: Path) -> None:
    """No location config → available=False (offline-first, R9)."""
    # Temporarily point env_solar's _LOCATION to a nonexistent file.
    import env_solar

    orig = env_solar._LOCATION
    env_solar._LOCATION = tmp_path / "no_such_file.json"
    try:
        result = build_env_context(_START, _END)
    finally:
        env_solar._LOCATION = orig

    assert result["available"] is False


def test_build_env_context_with_location(tmp_path: Path) -> None:
    """With a valid location config, solar layer populates night_bands + sun_events."""
    import json

    import env_solar

    loc = {"latitude": 38.9, "longitude": -77.0, "tz_offset_hours": -4.0}
    loc_file = tmp_path / "location.local.json"
    loc_file.write_text(json.dumps(loc))
    orig = env_solar._LOCATION
    env_solar._LOCATION = loc_file
    try:
        # Use a window during summer midnight in DC: should be all-night at UTC 00-06
        result = build_env_context(_START, _END)
    finally:
        env_solar._LOCATION = orig

    assert result["available"] is True
    assert "night_bands" in result
    assert "sun_events" in result
    # DC in late June: UTC 00:00 = ~20:00 EDT; sunset ~20:22 EDT means ~5.6h of the
    # 6h window is night. Accept anywhere in [4.5, 6.0].
    assert len(result["night_bands"]) >= 1
    total_night_h = sum(b["x1"] - b["x0"] for b in result["night_bands"])
    assert 4.5 <= total_night_h <= 6.0
    assert result["solar_source"].startswith("derived/computed")


# import pytest approx once (avoids per-test import)
from pytest import approx as pytest_approx  # noqa: E402
