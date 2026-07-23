"""Tests for the source-adapter seam (#277).

Covers TetheredAdapter's behavior-preserving wrap of parse_files()/gather_inputs(),
so refactoring dashboard.py/serve.py's call sites onto the seam is provably a
no-behavior-change move. Also covers DeviceAdapter (#276/#277 AC1): the WiFi-served
transport, proven both against an injected fake fetch (fast, deterministic) and a
real HTTP server (the actual byte-level contract, no physical hardware needed).
"""

from __future__ import annotations

import http.server
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from tools.analytics.parse_v1 import parse_files
from tools.analytics.source_adapter import (
    DEVICE_ADAPTER_VERSION,
    DeviceAdapter,
    FleetAdapter,
    TetheredAdapter,
)

_COLS = "record_type,timestamp_utc,session_id,raw_value,quality_flag,payload"
_ROW = "plants.soil,2026-06-27T00:00:30.000Z,sess001,1312,OK,level=well watered;gpio=36"
_HEADER = "# log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00\n"


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "one.csv"
    p.write_text(f"{_HEADER}{_COLS}\n{_ROW}\n", encoding="utf-8")
    return p


def test_explicit_inputs_match_parse_files_directly(tmp_path: Path) -> None:
    csv = _write(tmp_path)
    direct = parse_files([str(csv)])
    via_adapter = TetheredAdapter().load([str(csv)])
    assert len(via_adapter.readings) == len(direct.readings) == 1
    assert via_adapter.readings[0].raw_value == direct.readings[0].raw_value
    assert via_adapter.sources == direct.sources


def test_no_inputs_uses_the_injected_discover_callable(tmp_path: Path) -> None:
    csv = _write(tmp_path)
    calls = {"n": 0}

    def fake_discover() -> list[str]:
        calls["n"] += 1
        return [str(csv)]

    data = TetheredAdapter(discover=fake_discover).load()
    assert calls["n"] == 1
    assert len(data.readings) == 1


def test_no_inputs_and_no_discover_is_empty_not_raise() -> None:
    data = TetheredAdapter().load()
    assert data.readings == [] and data.segments == []


def test_explicit_inputs_bypass_discover(tmp_path: Path) -> None:
    csv = _write(tmp_path)
    calls = {"n": 0}

    def fake_discover() -> list[str]:
        calls["n"] += 1
        return ["should-not-be-used.csv"]

    data = TetheredAdapter(discover=fake_discover).load([str(csv)])
    assert calls["n"] == 0  # explicit inputs win; discover never called
    assert len(data.readings) == 1


# --------------------------------------------------------------------------- #
# DeviceAdapter (#276/#277 AC1): the WiFi-served transport
# --------------------------------------------------------------------------- #

_DEVICE_COLS_HEADER = (
    "# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
    "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload"
)


def _device_line(
    *,
    record_type: str = "plants.soil",
    session: str = "wifi001",
    device: str = "sprout-classic-01",
    fw: str = "0.8.0",
    millis: int = 60000,
    sensor_model: str = "UMLIFE_v2_TLC555",
    sensor: str = "s1",
    position: str = "origplant",
    channel: str = "soil_moisture",
    raw: int = 1400,
    quality: str = "OK",
    payload: str = "level=well watered;role=diag;spread=18;gpio=36",
    bad_crc: bool = False,
) -> str:
    """One device line exactly as handleTelemetry() (firmware/src/main.cpp) emits
    it - same DEVICE_COLS order, same *HH XOR checksum as the serial wire."""
    body = (
        f"{record_type},{session},{device},{fw},{millis},"
        f"{sensor_model},{sensor},{position},{channel},"
        f"{raw},,,{quality},{payload}"
    )
    calc = 0
    for ch in body:
        calc ^= ord(ch) & 0xFF
    if bad_crc:
        calc ^= 0xFF  # deliberately wrong
    return f"{body}*{calc:02X}"


def _telemetry_response(lines: list[str]) -> str:
    return _DEVICE_COLS_HEADER + "\n" + "\n".join(lines) + "\n"


def test_device_adapter_parses_the_real_telemetry_shape() -> None:
    text = _telemetry_response(
        [_device_line(sensor="s1", raw=1400), _device_line(sensor="s2", raw=1600)]
    )
    fixed_now = datetime(2026, 7, 2, tzinfo=timezone.utc)
    da = DeviceAdapter(
        "http://192.0.2.1", fetch=lambda url: text, clock=lambda: fixed_now
    )
    data = da.load()
    assert len(data.readings) == 2
    ids = {r.sensor_id: r.raw_value for r in data.readings}
    assert ids == {"s1": 1400, "s2": 1600}
    assert data.segments[0].device_id == "sprout-classic-01"
    assert data.sources == ["http://192.0.2.1"]


def test_device_adapter_stamps_host_observed_time_and_own_logger_version() -> None:
    text = _telemetry_response([_device_line()])
    fixed_now = datetime(2026, 7, 2, 12, 30, 0, tzinfo=timezone.utc)
    da = DeviceAdapter(
        "http://192.0.2.1", fetch=lambda url: text, clock=lambda: fixed_now
    )
    r = da.load().readings[0]
    assert r.timestamp_utc == fixed_now
    assert r.logger_version == DEVICE_ADAPTER_VERSION  # never plants_logger's own


def test_device_adapter_carries_device_owned_time_fields_through() -> None:
    """Firmware's forward-compat note on PR #553: once a bench pass syncs NTP,
    real rows gain device_seq/time_source=device_synced/device_timestamp_utc in
    payload - additive, no shape change. DeviceAdapter never touches payload
    contents (stamp_row() passes dev["payload"] through unmodified for this
    adapter, since it's never given a host_monotonic_ms to append), so these
    already reach Reading via the existing generic parse_payload() properties -
    this proves it with a real post-sync-shaped payload, not just theory."""
    text = _telemetry_response(
        [
            _device_line(
                sensor="s1",
                payload=(
                    "level=well watered;role=diag;spread=18;gpio=36;"
                    "device_seq=4821;time_source=device_synced;"
                    "device_timestamp_utc=2026-07-02T06:15:00Z"
                ),
            )
        ]
    )
    da = DeviceAdapter("http://192.0.2.1", fetch=lambda url: text)
    r = da.load().readings[0]
    assert r.device_seq == 4821
    assert r.time_source == "device_synced"
    assert r.device_timestamp_utc == datetime(2026, 7, 2, 6, 15, 0, tzinfo=timezone.utc)
    assert r.band == "well watered"  # the device-emitted fields all survive too


def test_device_adapter_drops_a_crc_failed_row_not_the_whole_poll() -> None:
    text = _telemetry_response(
        [_device_line(sensor="s1", bad_crc=True), _device_line(sensor="s2")]
    )
    da = DeviceAdapter("http://192.0.2.1", fetch=lambda url: text)
    data = da.load()
    assert len(data.readings) == 1
    assert data.readings[0].sensor_id == "s2"


def test_device_adapter_unreachable_device_is_empty_not_a_crash() -> None:
    def _boom(url: str) -> str:
        raise OSError("Connection refused")

    da = DeviceAdapter("http://192.0.2.1", fetch=_boom)
    data = da.load()
    assert data.readings == [] and data.segments == []


def test_device_adapter_empty_response_is_honest_empty() -> None:
    # every channel empty (g_last_row[ch][0] == '\0') -> just the header line
    da = DeviceAdapter("http://192.0.2.1", fetch=lambda url: _DEVICE_COLS_HEADER + "\n")
    data = da.load()
    assert data.readings == [] and data.segments == []


def test_device_adapter_sample_id_increments_across_polls() -> None:
    text = _telemetry_response([_device_line()])
    da = DeviceAdapter("http://192.0.2.1", fetch=lambda url: text)
    first = da.load().readings[0].sample_id
    second = da.load().readings[0].sample_id
    assert second == first + 1


# --------------------------------------------------------------------------- #
# DeviceAdapter end-to-end: a real HTTP server, the actual byte-level contract
# --------------------------------------------------------------------------- #


class _TelemetryHandler(http.server.BaseHTTPRequestHandler):
    """Serves the exact bytes handleTelemetry() (#276) would - proves
    DeviceAdapter's real _http_get() path, not just the injected-fetch unit
    tests above."""

    def do_GET(self) -> None:  # http.server dispatch name
        if self.path == "/telemetry":
            body = _telemetry_response([_device_line(sensor="s1", raw=1777)]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # keep test output quiet


def test_device_adapter_end_to_end_over_real_http() -> None:
    server = http.server.HTTPServer(("127.0.0.1", 0), _TelemetryHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        data = DeviceAdapter(f"http://127.0.0.1:{port}").load()
        assert len(data.readings) == 1
        assert data.readings[0].sensor_id == "s1"
        assert data.readings[0].raw_value == 1777
        assert data.readings[0].device_id == "sprout-classic-01"
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert len(data.readings) == 1


# --------------------------------------------------------------------------- #
# FleetAdapter (#486): N sources -> one LogData, deduped on device_seq
# --------------------------------------------------------------------------- #


def test_fleet_combines_tethered_and_device_sources(tmp_path: Path) -> None:
    csv = _write(tmp_path)  # one tethered reading (no device_seq)
    wifi = _telemetry_response(
        [_device_line(device="sprout-s3-01", sensor="s1", raw=1900)]
    )
    fleet = FleetAdapter(
        [
            TetheredAdapter(),
            DeviceAdapter("http://192.0.2.7", fetch=lambda url: wifi),
        ]
    )
    data = fleet.load([str(csv)])
    assert len(data.readings) == 2
    assert {r.raw_value for r in data.readings} == {1312, 1900}
    assert str(csv) in data.sources and "http://192.0.2.7" in data.sources


def test_fleet_dedupes_an_exact_replay_across_transports() -> None:
    # the same physical reading (same device_seq) arriving via two transports
    # is a store-and-forward replay - kept once, dropped once (#521's boundary)
    line = _device_line(
        payload="level=OK;gpio=36;device_seq=77;time_source=device_synced"
    )
    text = _telemetry_response([line])
    fleet = FleetAdapter(
        [
            DeviceAdapter("http://192.0.2.7", fetch=lambda url: text),
            DeviceAdapter("http://192.0.2.8", fetch=lambda url: text),
        ]
    )
    data = fleet.load()
    assert len(data.readings) == 1


def test_fleet_never_dedupes_rows_without_device_seq() -> None:
    # no device_seq -> no dedupe signal -> always kept (Store's honest degrade;
    # a false-positive drop would silently lose real data)
    text = _telemetry_response([_device_line()])  # payload has no device_seq
    fleet = FleetAdapter(
        [
            DeviceAdapter("http://192.0.2.7", fetch=lambda url: text),
            DeviceAdapter("http://192.0.2.8", fetch=lambda url: text),
        ]
    )
    assert len(fleet.load().readings) == 2


def test_fleet_unreachable_device_contributes_nothing(tmp_path: Path) -> None:
    csv = _write(tmp_path)

    def _boom(url: str) -> str:
        raise OSError("Connection refused")

    fleet = FleetAdapter([TetheredAdapter(), DeviceAdapter("http://x", fetch=_boom)])
    data = fleet.load([str(csv)])
    assert len(data.readings) == 1  # the tethered view survives untouched


def test_fleet_inputs_reach_only_the_first_adapter() -> None:
    seen: dict[str, object] = {}

    class _Probe:
        def __init__(self, name: str) -> None:
            self._name = name

        def load(self, inputs=None):  # matches the SourceAdapter contract
            seen[self._name] = inputs
            from tools.analytics.parse_v1 import LogData

            return LogData()

    FleetAdapter([_Probe("first"), _Probe("second")]).load(["a.csv"])
    assert seen == {"first": ["a.csv"], "second": None}


# --------------------------------------------------------------------------- #
# FleetAdapter parallel device-fetch (#953): the ~14s the maintainer's [perf]
# lines exposed was N served devices' HTTP timeouts paid IN SERIES on the load
# path. The device fetches now run concurrently — one unreachable board no longer
# stalls the whole dashboard — while the tethered source + ingest order (dedupe)
# stay exactly as the serial loop had them.
# --------------------------------------------------------------------------- #


def _slow_fetch(seconds: float, text: str):
    def _f(url: str) -> str:
        time.sleep(seconds)
        return text

    return _f


def test_fleet_fetches_devices_concurrently_not_serially() -> None:
    # three devices that each block 0.3s: serial would be ~0.9s, parallel ~0.3s.
    text = _telemetry_response([_device_line()])  # no device_seq -> all kept
    fleet = FleetAdapter(
        [
            TetheredAdapter(),  # adapter 0: instant (no inputs/discover) — the CSV slot
            DeviceAdapter("http://a", fetch=_slow_fetch(0.3, text)),
            DeviceAdapter("http://b", fetch=_slow_fetch(0.3, text)),
            DeviceAdapter("http://c", fetch=_slow_fetch(0.3, text)),
        ]
    )
    data = fleet.load()
    assert len(data.readings) == 3  # every device contributed
    # the whole point: the parallel block is ~one device's wait, not three summed
    assert fleet.last_fetch_s < 0.6, f"fetch not parallel: {fleet.last_fetch_s:.2f}s"
    assert fleet.last_fetch_s > 0.0  # it did run


def test_fleet_one_slow_device_does_not_stall_the_others() -> None:
    # a single hung board is the real-world case (an unplugged unit). With a serial
    # loop its timeout blocked everything; concurrent, the others return immediately.
    fast = _telemetry_response([_device_line(device="fast", raw=1500)])
    slow = _telemetry_response([_device_line(device="slow", raw=1900)])
    fleet = FleetAdapter(
        [
            DeviceAdapter("http://fast1", fetch=lambda url: fast),
            DeviceAdapter("http://slow", fetch=_slow_fetch(0.4, slow)),
        ]
    )
    data = fleet.load()
    # adapter 0 (fast1) is the sequential "first" slot; the one pooled device is slow.
    assert {r.raw_value for r in data.readings} == {1500, 1900}


def test_fleet_parallel_preserves_ingest_order_and_dedupe() -> None:
    # order is deterministic (tethered, then devices in registry order) even though
    # the fetches race — ex.map returns in input order, ingest stays sequential.
    a = _telemetry_response([_device_line(device="a", raw=1100)])
    b = _telemetry_response([_device_line(device="b", raw=1200)])
    c = _telemetry_response([_device_line(device="c", raw=1300)])
    fleet = FleetAdapter(
        [
            DeviceAdapter("http://a", fetch=_slow_fetch(0.15, a)),  # first (sequential)
            DeviceAdapter("http://b", fetch=_slow_fetch(0.20, b)),  # pooled
            DeviceAdapter("http://c", fetch=_slow_fetch(0.05, c)),  # pooled, ends first
        ]
    )
    data = fleet.load()
    # c's fetch completes first, but the merge order follows adapter order, not
    # completion order — so the sequence is a, b, c regardless of the race.
    assert [r.raw_value for r in data.readings] == [1100, 1200, 1300]


def test_fleet_tethered_only_has_zero_fetch_time(tmp_path: Path) -> None:
    # no device adapters -> no parallel block -> last_fetch_s stays 0.0 (a tethered-
    # only install sees no fetch cost, and the [perf] split shows fetch=0).
    csv = _write(tmp_path)
    fleet = FleetAdapter([TetheredAdapter()])
    data = fleet.load([str(csv)])
    assert len(data.readings) == 1
    assert fleet.last_fetch_s == 0.0


def test_fleet_no_adapters_is_empty_not_raise() -> None:
    data = FleetAdapter([]).load()
    assert data.readings == [] and data.segments == [] and data.sources == []


# --------------------------------------------------------------------------- #
# DeviceAdapter pressure exception (#567, ADR-0023 §3): the untethered spine
# --------------------------------------------------------------------------- #


def test_device_adapter_fills_pressure_tagged_per_quantity() -> None:
    text = _telemetry_response([_device_line(sensor="s1"), _device_line(sensor="s2")])
    da = DeviceAdapter(
        "http://192.0.2.1",
        fetch=lambda url: text,
        pressure_source=lambda: (1013.2, "weather_openmeteo"),
    )
    for r in da.load().readings:
        assert r.pressure_context_hpa == 1013.2
        assert r.pressure_context_source == "weather_openmeteo"
        # the fence, on THIS spine too: weather touched pressure ONLY -
        # interior temp/RH and their tag stay honestly empty
        assert r.temp_context_c is None and r.rh_context_pct is None
        assert r.context_source is None


def test_device_adapter_pressure_source_none_yield_fills_nothing() -> None:
    text = _telemetry_response([_device_line()])
    da = DeviceAdapter(
        "http://192.0.2.1", fetch=lambda url: text, pressure_source=lambda: None
    )
    r = da.load().readings[0]
    assert r.pressure_context_hpa is None
    assert r.pressure_context_source is None  # no value -> no tag, ever


def test_device_adapter_without_pressure_source_is_unchanged() -> None:
    text = _telemetry_response([_device_line()])
    plain = DeviceAdapter("http://192.0.2.1", fetch=lambda url: text)
    r = plain.load().readings[0]
    assert r.pressure_context_hpa is None and r.pressure_context_source is None


def test_device_adapter_reads_pressure_once_per_poll() -> None:
    # one observed-at moment per poll -> one pressure read, not one per row
    calls = {"n": 0}

    def _src():
        calls["n"] += 1
        return (1013.2, "weather_openmeteo")

    text = _telemetry_response([_device_line(sensor="s1"), _device_line(sensor="s2")])
    DeviceAdapter(
        "http://192.0.2.1", fetch=lambda url: text, pressure_source=_src
    ).load()
    assert calls["n"] == 1
