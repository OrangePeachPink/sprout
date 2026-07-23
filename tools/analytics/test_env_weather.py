#!/usr/bin/env python3
"""Tests for weather ingestion (PRD-0002 R2, #198). No network: the fetcher is injected.

python tools/analytics/test_env_weather.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.analytics import env_weather  # noqa: E402

_LAT, _LON = 41.8781, -87.6298  # public reference, not anyone's home

# A minimal but shape-valid Open-Meteo archive response (2 hours).
_FIXTURE = {
    "latitude": _LAT,
    "longitude": _LON,
    "hourly": {
        "time": ["2026-06-24T12:00", "2026-06-24T13:00"],
        "cloud_cover": [90, 20],
        "shortwave_radiation": [180.0, 720.0],
        "temperature_2m": [19.4, 24.1],
        "precipitation": [0.0, 0.0],
    },
}


def test_parse_hourly() -> None:
    recs = env_weather.parse_hourly(_FIXTURE)
    assert len(recs) == 2
    assert recs[0]["time_utc"] == "2026-06-24T12:00"
    assert recs[0]["cloud_cover"] == 90 and recs[1]["cloud_cover"] == 20
    assert recs[1]["shortwave_radiation"] == 720.0
    # no coordinates leak into the per-hour records
    assert "latitude" not in recs[0] and "longitude" not in recs[0]
    assert env_weather.parse_hourly({}) == []  # empty/malformed -> clean empty


def test_source_record_trust_and_no_coords() -> None:
    src = env_weather.source_record()
    assert src["trust_class"] == "derived/model"  # never authoritative
    assert src["cadence"] == "hourly" and "Open-Meteo" in src["origin"]
    # privacy: provenance carries no coordinates (it may be surfaced/committed)
    assert "latitude" not in src and "longitude" not in src


def test_source_record_has_the_full_registry_field_set() -> None:
    # #367 R7: origin, jurisdiction, cadence, trust class, schema version, discovery
    # date - complete on its own, no cross-referencing code needed.
    src = env_weather.source_record()
    assert src["jurisdiction"] == "global model grid"
    assert isinstance(src["schema_version"], int) and src["schema_version"] >= 1
    assert src["discovery_date"] == "2026-06-27"  # fixed historical fact, never "today"


def test_get_weather_caches_then_serves_offline() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        calls = {"n": 0}

        def fake_get(url: str) -> dict:
            calls["n"] += 1
            assert "archive-api.open-meteo.com" in url and "latitude" in url
            return _FIXTURE

        first = env_weather.get_weather(
            _LAT, _LON, "2026-06-24", "2026-06-24", get=fake_get, cache_dir=tmp
        )
        assert first["cached"] is False and len(first["hourly"]) == 2
        assert calls["n"] == 1  # fetched once
        # the raw response is cached as dated evidence
        assert any(tmp.glob("openmeteo_*_2026-06-24_2026-06-24.json"))

        def boom(url: str) -> dict:  # must NOT be called once cached
            raise AssertionError("refetched a cached window")

        second = env_weather.get_weather(
            _LAT, _LON, "2026-06-24", "2026-06-24", get=boom, cache_dir=tmp
        )
        assert second["cached"] is True and len(second["hourly"]) == 2
        assert calls["n"] == 1  # still 1 - served from cache, no network
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_offline_no_cache_propagates() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:

        def offline(url: str) -> dict:
            raise OSError("no network")

        # no cache + no network -> raises; the caller degrades to solar-only (R9)
        try:
            env_weather.get_weather(
                _LAT, _LON, "2026-06-24", "2026-06-24", get=offline, cache_dir=tmp
            )
        except OSError:
            return
        raise AssertionError("expected OSError when offline with no cache")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_parse_hourly,
        test_source_record_trust_and_no_coords,
        test_get_weather_caches_then_serves_offline,
        test_offline_no_cache_propagates,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
