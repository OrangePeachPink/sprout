#!/usr/bin/env python3
"""Live weather pressure for the ADR-0023 §3 exception (#567, deferred from #562).

``pressure_context_hpa`` may fill from the exterior family - buildings are not
pressure vessels, indoor tracks outdoor - tagged per-quantity as
``pressure_context_source=weather_openmeteo``. This module supplies that value
from Open-Meteo's **forecast** endpoint (``current=surface_pressure``): the
archive API (``env_weather``) is dated immutable evidence that lags real time,
so it cannot honestly claim to be "current" pressure.

The local-cache design (#567's named decisions):

* **One rolling cache file** (``reports/weather/pressure_current.json``,
  gitignored) - a *current-conditions* cache, deliberately NOT the archive
  layer's immutable dated evidence: it is overwritten on refresh, because
  "what is the pressure now" is inherently a rolling question. No coordinates
  in the filename (R6); the body carries only the value + stamps.
* **Fetch cadence**: refresh when the cache is older than ``REFRESH_AGE_S``
  (1 h - the source publishes hourly). Refreshing is *opportunistic*, owned by
  the dashboard's env path (which already networks inside try/except for the
  weather overlay) - **never by the logger's read loop**: fill paths call the
  cache-only reader, so logging and polling never block on a socket.
* **Staleness bound for filling**: a cached value older than ``MAX_AGE_S``
  (3 h) never fills - synoptic pressure moves slowly (~<1 hPa/h typically), so
  3 h keeps the indoor≈outdoor claim honest to a few hPa; beyond that, empty
  is honest. Offline behavior falls out: no network -> cache ages out ->
  fills stop -> columns stay empty (R9: nothing requires the network).

Trust class: derived/model (interpolated grid output, not a station reading) -
same posture as ``env_weather.source_record()``; the tag resolves to the
``exterior`` family via ``parse_v1.context_class()`` and may only ever fill
pressure (the interior fence lives in ``context_fill``/``DeviceAdapter``).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_CACHE = _REPO / "reports" / "weather" / "pressure_current.json"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

PRESSURE_TAG = "weather_openmeteo"  # the ADR-0023 §3 per-quantity tag
REFRESH_AGE_S = 3600.0  # refresh cadence: the source publishes hourly
MAX_AGE_S = 3 * 3600.0  # fill staleness bound: older than this never fills

_UNSET = object()  # sentinel: "load the real location config" vs an explicit None


def _http_get(url: str) -> dict:  # the only network call; injected in tests
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_current_pressure(lat: float, lon: float, get=None) -> dict | None:
    """One forecast-API call -> ``{"time_utc", "surface_pressure_hpa"}`` or None
    on a malformed response. ``get`` is injectable so tests touch no network."""
    query = {
        "latitude": lat,
        "longitude": lon,
        "current": "surface_pressure",
        "timezone": "UTC",
    }
    raw = (get or _http_get)(f"{_FORECAST_URL}?{urllib.parse.urlencode(query)}")
    cur = (raw or {}).get("current") or {}
    hpa = cur.get("surface_pressure")
    if not isinstance(hpa, (int, float)):
        return None
    return {"time_utc": cur.get("time"), "surface_pressure_hpa": float(hpa)}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _read_cache(cache_path: Path) -> dict | None:
    try:
        doc = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def _age_s(doc: dict, now: datetime) -> float | None:
    try:
        fetched = datetime.fromisoformat(
            str(doc.get("fetched_utc", "")).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return (now - fetched).total_seconds()


def refresh_if_stale(
    *,
    cache_path: str | Path | None = None,
    max_age_s: float = REFRESH_AGE_S,
    location=_UNSET,
    get=None,
    now=None,
) -> bool:
    """Opportunistic refresh of the rolling cache (the dashboard's env path
    owns this; fill paths never call it). True if a fresh value was written.
    Degrades silently: no location config / fetch failure / malformed response
    all leave the existing cache untouched - offline is a supported state.
    ``location``: omit to load the real rig config (#365); pass an explicit
    ``None`` to mean "no location" (tests / a caller that already knows)."""
    path = Path(cache_path) if cache_path else _CACHE
    now = now or _now_utc()
    doc = _read_cache(path)
    if doc is not None:
        age = _age_s(doc, now)
        if age is not None and 0 <= age < max_age_s:
            return False  # fresh enough - no network needed
    if location is _UNSET:
        try:
            import env_solar

            location = env_solar.load_location()
        except ImportError:
            location = None
    if location is None:
        return False  # R9: no location config -> no weather, cleanly
    try:
        got = fetch_current_pressure(
            float(location["latitude"]), float(location["longitude"]), get=get
        )
    except Exception:
        return False  # fetch failed - keep whatever cache exists
    if got is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fetched_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_utc": got["time_utc"],
                "surface_pressure_hpa": got["surface_pressure_hpa"],
                "source": PRESSURE_TAG,
                "trust_class": "derived/model",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return True


def latest_pressure(
    *,
    cache_path: str | Path | None = None,
    max_age_s: float = MAX_AGE_S,
    now=None,
) -> tuple[float, str] | None:
    """The cache-only reader both fill paths inject as ``pressure_source``:
    ``(hpa, "weather_openmeteo")`` from the rolling cache, or ``None`` when the
    cache is absent/stale/malformed. **Never touches the network** - safe in
    the logger's read loop and in a per-request poll."""
    doc = _read_cache(Path(cache_path) if cache_path else _CACHE)
    if doc is None:
        return None
    hpa = doc.get("surface_pressure_hpa")
    if not isinstance(hpa, (int, float)):
        return None
    age = _age_s(doc, now or _now_utc())
    if age is None or age < 0 or age > max_age_s:
        return None  # stale (or clock-skewed) - empty is honest
    return (float(hpa), PRESSURE_TAG)
