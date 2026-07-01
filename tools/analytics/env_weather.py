#!/usr/bin/env python3
"""Weather ingestion - the optional environmental layer (PRD-0002 R2, #198).

Fetches hourly cloud cover + shortwave radiation (+ temperature, precip) for the rig
location from the Open-Meteo archive (free, keyless, global) and CACHES the raw response
as dated evidence under the gitignored ``reports/weather/``. Offline-first (R9): a
cached window is reused and **never refetched or rewritten**, so the layer works once
primed and degrades cleanly to solar-only (``env_solar``) when there's no network and no
cache.

Weather is a **derived/model** source - interpolated grid output, *not* an authoritative
station reading - labeled as such everywhere and never promoted to authoritative
(ADR-0013 §2/§4, R7). Location comes from the caller (``env_solar.load_location``); this
module never hardcodes, commits, or logs coordinates, and the cache lives under the
gitignored ``reports/`` tree (coords never appear in the cache filename).
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_CACHE = _REPO / "reports" / "weather"  # under the gitignored reports/ tree
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
_HOURLY = ["cloud_cover", "shortwave_radiation", "temperature_2m", "precipitation"]
# This registry entry's OWN shape version (bump if a field is added/renamed/removed) -
# distinct from Open-Meteo's API, which publishes no schema_version of its own (#367).
_REGISTRY_SCHEMA_VERSION = 1
# When this source was first onboarded to the project (git-log-confirmed: the date
# env_weather.py was first added) - a fixed historical fact, never a "today" stamp.
_DISCOVERY_DATE = "2026-06-27"


def _cache_path(
    lat: float, lon: float, start: str, end: str, cache_dir: Path | None
) -> Path:
    # The coords are HASHED into the filename so it leaks no location; the cached body
    # (which echoes the coords) lives under gitignored reports/ - dated evidence only.
    key = hashlib.sha1(f"{lat},{lon}".encode()).hexdigest()[:10]
    root = cache_dir or _CACHE
    return root / f"openmeteo_{key}_{start}_{end}.json"


def _http_get(url: str) -> dict:  # the only network call; injected in tests
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_archive(lat: float, lon: float, start: str, end: str, get=None) -> dict:
    """Raw Open-Meteo archive response for a date window (one network call).

    ``get`` is the HTTP fetcher (default ``_http_get``); inject a fake in tests so no
    network is touched."""
    query = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(_HOURLY),
        "timezone": "UTC",
    }
    url = _ARCHIVE_URL + "?" + urllib.parse.urlencode(query)
    return (get or _http_get)(url)


def parse_hourly(raw: dict) -> list[dict]:
    """Flatten the Open-Meteo hourly block to per-hour records (UTC). No coordinates."""
    hourly = (raw or {}).get("hourly") or {}
    times = hourly.get("time") or []
    out: list[dict] = []
    for i, t in enumerate(times):
        rec: dict = {"time_utc": t}
        for key in _HOURLY:
            vals = hourly.get(key) or []
            rec[key] = vals[i] if i < len(vals) else None
        out.append(rec)
    return out


def source_record() -> dict:
    """The source-registry entry (R7): origin, jurisdiction, cadence, trust class,
    schema version, discovery date - the full field set the registry doctrine calls
    for, so this entry is complete on its own without cross-referencing code.

    Deliberately carries **no coordinates** - it may be surfaced/committed, and the home
    location must never leak (R6)."""
    return {
        "origin": "Open-Meteo archive API (open-meteo.com)",
        "jurisdiction": "global model grid",
        "cadence": "hourly",
        "trust_class": "derived/model",  # NOT an authoritative station reading
        "schema_version": _REGISTRY_SCHEMA_VERSION,
        "discovery_date": _DISCOVERY_DATE,
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": (
            "interpolated grid output; never authoritative; cached as dated evidence "
            "under gitignored reports/, never refetched or rewritten"
        ),
    }


def get_weather(
    lat: float,
    lon: float,
    start: str,
    end: str,
    get=None,
    cache_dir: Path | None = None,
) -> dict:
    """Hourly weather for a window - **offline-first + cached**.

    A cached window is reused and **never refetched** (immutable dated evidence);
    otherwise it's fetched once, cached, then parsed. Returns
    ``{"hourly": [...], "source": {...}, "cached": bool}``. Raises only when there is no
    cache *and* the fetch fails - the caller degrades to solar-only (R9)."""
    path = _cache_path(lat, lon, start, end, cache_dir)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {
                "hourly": parse_hourly(raw),
                "source": source_record(),
                "cached": True,
            }
        except (json.JSONDecodeError, OSError):
            pass  # corrupt cache -> refetch below
    raw = fetch_archive(lat, lon, start, end, get=get)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"hourly": parse_hourly(raw), "source": source_record(), "cached": False}
