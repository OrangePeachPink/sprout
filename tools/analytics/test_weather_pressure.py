"""Tests for the live weather-pressure cache (#567, ADR-0023 §3).

The rolling current-conditions cache: refreshed opportunistically by the
dashboard's env path, read cache-only by both fill paths (logger ContextFiller
+ DeviceAdapter). Staleness bound and offline behavior are the design decisions
the issue named - pinned here.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import weather_pressure as wp

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)

_FORECAST_RESPONSE = {
    "current": {"time": "2026-07-03T11:45", "surface_pressure": 1013.2},
}


def _prime(cache: Path, *, hpa: float = 1013.2, age_s: float = 0.0) -> None:
    fetched = _NOW - timedelta(seconds=age_s)
    cache.write_text(
        json.dumps(
            {
                "fetched_utc": fetched.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_utc": "2026-07-03T11:45",
                "surface_pressure_hpa": hpa,
                "source": "weather_openmeteo",
            }
        ),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# fetch_current_pressure - the one network call, injected
# --------------------------------------------------------------------------- #


def test_fetch_parses_the_forecast_current_block() -> None:
    got = wp.fetch_current_pressure(0.0, 0.0, get=lambda url: _FORECAST_RESPONSE)
    assert got == {"time_utc": "2026-07-03T11:45", "surface_pressure_hpa": 1013.2}


def test_fetch_requests_surface_pressure_current() -> None:
    seen = {}

    def _get(url: str) -> dict:
        seen["url"] = url
        return _FORECAST_RESPONSE

    wp.fetch_current_pressure(1.0, 2.0, get=_get)
    assert "current=surface_pressure" in seen["url"]
    assert "api.open-meteo.com/v1/forecast" in seen["url"]


def test_fetch_malformed_response_is_none() -> None:
    assert wp.fetch_current_pressure(0.0, 0.0, get=lambda url: {}) is None
    assert (
        wp.fetch_current_pressure(
            0.0, 0.0, get=lambda url: {"current": {"surface_pressure": "n/a"}}
        )
        is None
    )


# --------------------------------------------------------------------------- #
# latest_pressure - the CACHE-ONLY reader both fill paths inject
# --------------------------------------------------------------------------- #


def test_fresh_cache_yields_value_and_tag(tmp_path: Path) -> None:
    cache = tmp_path / "p.json"
    _prime(cache, hpa=1008.7, age_s=600)  # 10 min old
    assert wp.latest_pressure(cache_path=cache, now=_NOW) == (
        1008.7,
        "weather_openmeteo",
    )


def test_stale_cache_never_fills(tmp_path: Path) -> None:
    cache = tmp_path / "p.json"
    _prime(cache, age_s=wp.MAX_AGE_S + 1)
    assert wp.latest_pressure(cache_path=cache, now=_NOW) is None


def test_absent_or_malformed_cache_is_none(tmp_path: Path) -> None:
    assert wp.latest_pressure(cache_path=tmp_path / "nope.json", now=_NOW) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert wp.latest_pressure(cache_path=bad, now=_NOW) is None


def test_future_stamped_cache_is_distrusted(tmp_path: Path) -> None:
    cache = tmp_path / "p.json"
    _prime(cache, age_s=-3600)  # fetched_utc an hour in the future - clock skew
    assert wp.latest_pressure(cache_path=cache, now=_NOW) is None


def test_latest_pressure_never_touches_the_network(tmp_path: Path) -> None:
    # structural: the reader has no `get` parameter at all - the only network
    # entry point is fetch_current_pressure, which only refresh_if_stale calls.
    import inspect

    params = inspect.signature(wp.latest_pressure).parameters
    assert "get" not in params


# --------------------------------------------------------------------------- #
# refresh_if_stale - the dashboard-owned opportunistic writer
# --------------------------------------------------------------------------- #

_LOC = {"latitude": 1.0, "longitude": 2.0}


def test_refresh_writes_a_fresh_cache(tmp_path: Path) -> None:
    cache = tmp_path / "p.json"
    wrote = wp.refresh_if_stale(
        cache_path=cache, location=_LOC, get=lambda url: _FORECAST_RESPONSE, now=_NOW
    )
    assert wrote is True
    assert wp.latest_pressure(cache_path=cache, now=_NOW) == (
        1013.2,
        "weather_openmeteo",
    )


def test_refresh_skips_when_cache_is_fresh(tmp_path: Path) -> None:
    cache = tmp_path / "p.json"
    _prime(cache, age_s=60)

    def _boom(url: str) -> dict:
        raise AssertionError("a fresh cache must not trigger a fetch")

    assert (
        wp.refresh_if_stale(cache_path=cache, location=_LOC, get=_boom, now=_NOW)
        is False
    )


def test_refresh_without_location_noops(tmp_path: Path) -> None:
    # R9: no location config -> no weather, cleanly (no fetch attempted)
    cache = tmp_path / "p.json"

    def _boom(url: str) -> dict:
        raise AssertionError("no location must mean no fetch")

    assert (
        wp.refresh_if_stale(cache_path=cache, location=None, get=_boom, now=_NOW)
        is False
    )
    assert not cache.exists()


def test_refresh_fetch_failure_keeps_the_old_cache(tmp_path: Path) -> None:
    cache = tmp_path / "p.json"
    _prime(cache, hpa=1001.0, age_s=wp.REFRESH_AGE_S + 60)  # due for refresh

    def _down(url: str) -> dict:
        raise OSError("offline")

    assert (
        wp.refresh_if_stale(cache_path=cache, location=_LOC, get=_down, now=_NOW)
        is False
    )
    # the old value is still there (and still fillable while within MAX_AGE_S)
    assert wp.latest_pressure(cache_path=cache, now=_NOW) == (
        1001.0,
        "weather_openmeteo",
    )


# --------------------------------------------------------------------------- #
# End-to-end, both spines: the REAL latest_pressure as the injected source
# --------------------------------------------------------------------------- #


def test_serial_spine_cache_to_csv_to_parse(tmp_path: Path) -> None:
    """Cache file -> latest_pressure -> ContextFiller -> RotatingCsv ->
    parse_v1: the full serial spine with the real reader, no network."""
    _LOGGER = Path(__file__).resolve().parents[1] / "logger"
    sys.path.insert(0, str(_LOGGER))
    from context_fill import ContextFiller
    from parse_v1 import context_class, parse_file
    from plants_logger import RotatingCsv, parse_device_line

    cache = tmp_path / "p.json"
    _prime(cache, hpa=1009.4, age_s=600)
    filler = ContextFiller(
        clock=lambda: 100.0,
        pressure_source=lambda: wp.latest_pressure(cache_path=cache, now=_NOW),
    )
    body = (
        "plants.soil,sessP,plants_esp32_test,0.8.0,60000,"
        "UMLIFE_v2_TLC555,s1,origplant,soil_moisture,1500,,,OK,"
        "level=well watered;gpio=36"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    dev = parse_device_line(f"{body}*{crc:02X}")
    logdir = tmp_path / "logs"
    rc = RotatingCsv(str(logdir))
    rc.write(dev, 1, _NOW, context=filler.context_for())

    r = parse_file(next(iter(logdir.glob("*.csv")))).readings[0]
    assert r.pressure_context_hpa == 1009.4
    assert r.pressure_context_source == "weather_openmeteo"
    assert context_class(r.pressure_context_source) == "exterior"
    # the fence held on the way through: interior stayed honestly empty
    assert r.temp_context_c is None and r.context_source is None


def test_untethered_spine_cache_to_fleet_to_reading(tmp_path: Path) -> None:
    """Cache file -> latest_pressure -> DeviceAdapter (real http.server serving
    the exact #276 bytes) -> FleetAdapter -> tagged Reading."""
    import http.server
    import threading

    from source_adapter import DeviceAdapter, FleetAdapter

    cache = tmp_path / "p.json"
    _prime(cache, hpa=1009.4, age_s=600)

    body = (
        "plants.soil,sessW,sprout-s3-01,0.8.0,60000,UMLIFE_v2_TLC555,"
        "s1,shelf,soil_moisture,1900,,,OK,level=needs water;gpio=4"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    line = f"{body}*{crc:02X}"
    cols = (
        "# device_cols: record_type,session_id,device_id,fw,millis_ms,"
        "sensor_model,sensor_id,sensor_position,channel,raw_value,value,unit,"
        "quality_flag,payload"
    )

    class _H(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            raw = f"{cols}\n{line}\n".encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _H)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        fleet = FleetAdapter(
            [
                DeviceAdapter(
                    f"http://127.0.0.1:{port}",
                    pressure_source=lambda: wp.latest_pressure(
                        cache_path=cache, now=_NOW
                    ),
                )
            ]
        )
        r = fleet.load().readings[0]
        assert r.pressure_context_hpa == 1009.4
        assert r.pressure_context_source == "weather_openmeteo"
        assert r.context_source is None  # interior untouched on this spine too
    finally:
        server.shutdown()
        thread.join(timeout=5)
