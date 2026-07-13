#!/usr/bin/env python3
"""Solar geometry - the zero-dependency environmental layer (PRD-0002 R1, #198).

Computes sun elevation/azimuth, sunrise/sunset/solar-noon, and the operator-calibrated
skylight window from latitude/longitude + time. **No network, no dependencies** - pure
stdlib math over the local config, so the environmental overlay's bottom rung
(R9: solar-only) is *always available* even fully offline. Weather (R2) is the optional
layer on top of this.

Solar position is a **derived/computed** source (an algorithm over location + time, no
external call) - labeled as such, never authoritative (ADR-0013 §4).

**Location privacy (R6 / ADR-0013 §3):** coordinates are the operator's home and the
repo is public-ready, so they live ONLY in the gitignored ``config/location.local.json``
(a committed ``.example`` documents the shape). This module reads that config; it never
hardcodes or logs coordinates.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_LOCATION = _REPO / "config" / "location.local.json"

# Standard sunrise/sunset definition: geometric center 0.833° below the horizon
# (atmospheric refraction + solar semi-diameter).
_HORIZON_DEG = -0.833


def load_location(path: str | Path | None = None) -> dict | None:
    """The rig location from gitignored local config, or None if absent/unreadable.

    None is a *clean* outcome (R9 offline-first): callers degrade to "no solar overlay",
    never crash. Never commits or logs the coordinates."""
    p = Path(path) if path else _LOCATION
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(doc, dict):
        return None
    if "latitude" not in doc or "longitude" not in doc:
        return None
    return doc


def location_status(path: str | Path | None = None) -> dict:
    """#966: whether a rig location is configured - NAME ONLY, not the coordinates. The
    privacy fence (ADR-0013 §3 / PRD-0002 R6): coords never cross onto a screenshottable
    surface, so the status endpoint that feeds the UI cannot leak them."""
    loc = load_location(path)
    return {"configured": loc is not None, "name": (loc or {}).get("name")}


def save_location(doc: dict, path: str | Path | None = None) -> dict:
    """#966: write the rig location to the GITIGNORED local config (never a tracked
    file). Validates lat/long are present, numeric, in range. Returns NAME-ONLY
    status (never echoes coordinates). NEVER logs the coordinates (ADR-0013 §3). Atomic
    temp-swap so a crash mid-write can't truncate the config."""
    try:
        lat = float(doc.get("latitude"))
        lon = float(doc.get("longitude"))
    except (TypeError, ValueError):
        raise ValueError("latitude and longitude are required numbers") from None
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise ValueError("latitude must be -90..90 and longitude -180..180")
    try:
        tz = float(doc.get("tz_offset_hours") or 0)
    except (TypeError, ValueError):
        raise ValueError("tz_offset_hours must be a number") from None
    out = {
        "name": (str(doc.get("name")).strip() if doc.get("name") else "my rig"),
        "latitude": lat,
        "longitude": lon,
        "tz_offset_hours": tz,
    }
    target = Path(path) if path else _LOCATION
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    tmp.replace(target)
    return {"configured": True, "name": out["name"]}  # name only, never coords


def _to_julian(when_utc: datetime) -> float:
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    return when_utc.timestamp() / 86400.0 + 2440587.5


def solar_position(lat: float, lon: float, when_utc: datetime) -> dict:
    """Sun elevation + azimuth (degrees) for a location at an instant.

    Low-precision Astronomical-Almanac / NOAA algorithm: elevation good to ~0.01°,
    plenty for a day/night + skylight overlay. Azimuth is clockwise from true North."""
    n = _to_julian(when_utc) - 2451545.0  # days from J2000.0
    mean_long = (280.460 + 0.9856474 * n) % 360.0
    mean_anom = math.radians((357.528 + 0.9856003 * n) % 360.0)
    ecl_long = math.radians(
        (mean_long + 1.915 * math.sin(mean_anom) + 0.020 * math.sin(2 * mean_anom))
        % 360.0
    )
    obliquity = math.radians(23.439 - 0.0000004 * n)
    decl = math.asin(math.sin(obliquity) * math.sin(ecl_long))
    right_asc = math.atan2(math.cos(obliquity) * math.sin(ecl_long), math.cos(ecl_long))
    gmst = (280.46061837 + 360.98564736629 * n) % 360.0
    hour_angle = math.radians((gmst + lon) % 360.0) - right_asc  # local, rad
    latr = math.radians(lat)
    elev = math.asin(
        math.sin(latr) * math.sin(decl)
        + math.cos(latr) * math.cos(decl) * math.cos(hour_angle)
    )
    cos_az = (math.sin(decl) - math.sin(elev) * math.sin(latr)) / (
        math.cos(elev) * math.cos(latr)
    )
    az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
    if math.sin(hour_angle) > 0:  # afternoon -> sun in the western half
        az = 360.0 - az
    return {"elevation_deg": math.degrees(elev), "azimuth_deg": az}


def solar_series(
    lat: float,
    lon: float,
    start_utc: datetime,
    end_utc: datetime,
    step_min: int = 10,
) -> list[dict]:
    """Elevation/azimuth sampled across a UTC range - the overlay's data (R4)."""
    out: list[dict] = []
    step = timedelta(minutes=max(1, step_min))
    t = start_utc
    while t <= end_utc:
        p = solar_position(lat, lon, t)
        out.append({"t": t, **p})
        t += step
    return out


def sun_events(lat: float, lon: float, date_local: str, tz_offset_hours: float) -> dict:
    """Sunrise / sunset / solar-noon (local ``HH:MM``) for a local calendar date.

    Sampled at 1-min resolution off ``solar_position`` (robust at any latitude/season;
    polar day/night fall out as None sunrise/sunset)."""
    y, m, d = (int(x) for x in date_local.split("-"))
    tz = timezone(timedelta(hours=tz_offset_hours))
    local_midnight = datetime(y, m, d, tzinfo=tz)
    prev_el: float | None = None
    sunrise = sunset = noon = None
    max_el = -91.0
    for minute in range(0, 24 * 60 + 1):
        t = local_midnight + timedelta(minutes=minute)
        el = solar_position(lat, lon, t.astimezone(timezone.utc))["elevation_deg"]
        local = t.strftime("%H:%M")
        if el > max_el:
            max_el, noon = el, local
        if prev_el is not None:
            if prev_el < _HORIZON_DEG <= el and sunrise is None:
                sunrise = local
            if prev_el >= _HORIZON_DEG > el:
                sunset = local
        prev_el = el
    return {
        "sunrise": sunrise,
        "sunset": sunset,
        "solar_noon": noon,
        "max_elevation_deg": round(max_el, 2),
    }


def _local_hhmm(when_utc: datetime, tz_offset_hours: float) -> str:
    tz = timezone(timedelta(hours=tz_offset_hours))
    if when_utc.tzinfo is None:
        when_utc = when_utc.replace(tzinfo=timezone.utc)
    return when_utc.astimezone(tz).strftime("%H:%M")


def in_skylight_window(when_utc: datetime, location: dict) -> bool | None:
    """Whether an instant falls in the operator-calibrated skylight window, or None if
    the window isn't configured (the window is location-specific, so it's opt-in)."""
    win = location.get("skylight_window_local")
    if not (isinstance(win, list) and len(win) == 2):
        return None
    hhmm = _local_hhmm(when_utc, location.get("tz_offset_hours", 0))
    return str(win[0]) <= hhmm <= str(win[1])


def solar_context(when_utc: datetime, location: dict) -> dict:
    """The join-ready solar context for one soil timestamp (R3): elevation, azimuth,
    daylight flag, and skylight-window flag. ``source`` marks it derived/computed."""
    pos = solar_position(
        float(location["latitude"]), float(location["longitude"]), when_utc
    )
    return {
        **pos,
        "is_daylight": pos["elevation_deg"] > _HORIZON_DEG,
        "in_skylight_window": in_skylight_window(when_utc, location),
        "source": "derived/computed (solar algorithm; not authoritative)",
    }
