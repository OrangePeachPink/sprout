"""Tests for the live view's fleet wiring (#486): serve.py's _context() reads
the tethered CSV history PLUS every fleet-registry device with a base_url, via
FleetAdapter - "all plants across all devices, one live view." Proven against a
real http.server serving the exact #276 /telemetry shape, not a mock.
"""

from __future__ import annotations

import http.server
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from serve import _context, _fleet_adapter
from source_adapter import FleetAdapter, TetheredAdapter

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_HEADER = (
    "# fw=0.7.0  git=test123  run=fleetlive\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_TETHERED_ROW = (
    "plants.soil,2026-07-03T00:00:30.000Z,2026-07-03T00:00:30.000,"
    "sessT,sprout-classic-01,s1,1500,OK,level=well watered;gpio=36\n"
)

# One /telemetry line exactly as handleTelemetry() emits (14 cols + *HH CRC).
_WIFI_BODY = (
    "plants.soil,sessW,sprout-s3-01,0.8.0,60000,UMLIFE_v2_TLC555,"
    "s1,shelf,soil_moisture,1900,,,OK,level=needs water;gpio=4"
)
_crc = 0
for _ch in _WIFI_BODY:
    _crc ^= ord(_ch) & 0xFF
_WIFI_LINE = f"{_WIFI_BODY}*{_crc:02X}"
_DEVICE_COLS = (
    "# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
    "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload"
)


class _TelemetryHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # http.server dispatch name
        body = f"{_DEVICE_COLS}\n{_WIFI_LINE}\n".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass


def _registry(base_url: str | None) -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3-devkitc-1",
                label="the S3",
                channels={"s1": {"plant_id": "P05", "plant_name": "Fern"}},
                base_url=base_url,
            )
        ]
    )


def test_fleet_adapter_factory_is_plain_tethered_without_served_devices() -> None:
    # zero behavior change for a tethered-only install: no base_url anywhere ->
    # the factory returns the exact pre-#486 adapter, not a 1-element fleet
    assert isinstance(_fleet_adapter(_registry(None)), TetheredAdapter)
    assert isinstance(_fleet_adapter(Registry()), TetheredAdapter)


def test_fleet_adapter_factory_composes_served_devices() -> None:
    assert isinstance(_fleet_adapter(_registry("http://192.0.2.9")), FleetAdapter)


def test_context_merges_tethered_and_wifi_devices(tmp_path: Path) -> None:
    """The literal #486 payoff, desk-provable half: one _context() call returns
    readings from a tethered CSV AND a live-served device in one view."""
    log = tmp_path / "tethered.csv"
    log.write_text(_HEADER + _COLS + _TETHERED_ROW, encoding="utf-8")

    server = http.server.HTTPServer(("127.0.0.1", 0), _TelemetryHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ctx = _context([str(log)], registry=_registry(f"http://127.0.0.1:{port}"))
        by_id = {s["id"]: s for s in ctx["sensors"]}
        # both transports landed in one view (same channel token, two devices -
        # sensors are keyed by sensor_id today; both readings are present)
        raws = {r for s in ctx["sensors"] for r in (s["raw_min"], s["raw_max"])}
        assert 1500 in raws and 1900 in raws
        assert by_id  # the view rendered
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_context_survives_an_unreachable_fleet_device(tmp_path: Path) -> None:
    log = tmp_path / "tethered.csv"
    log.write_text(_HEADER + _COLS + _TETHERED_ROW, encoding="utf-8")
    # 192.0.2.0/24 is TEST-NET-1 (RFC 5737) - guaranteed unroutable... but a
    # real connect attempt can still hang for seconds. Use a closed local port
    # instead: connection refused is immediate AND offline-deterministic.
    ctx = _context([str(log)], registry=_registry("http://127.0.0.1:9"))
    assert len(ctx["sensors"]) == 1  # the tethered view is untouched


# --------------------------------------------------------------------------- #
# #588: the collection control plane is routed (a real serve.py subprocess)
# --------------------------------------------------------------------------- #


def test_collection_routes_are_live(tmp_path: Path) -> None:
    import json
    import socket
    import subprocess
    import sys as _sys
    import time
    import urllib.error
    import urllib.request

    serve_py = Path(__file__).resolve().parent / "serve.py"
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen(
        # --no-autostart (#872): this test drives the collection routes from a known
        # STOPPED start; auto-start would begin collecting and break that premise.
        [
            _sys.executable,
            str(serve_py),
            str(tmp_path),
            "--port",
            str(port),
            "--no-autostart",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        up = False
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    up = True
                    break
            except OSError:
                time.sleep(0.1)
        assert up

        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/collection/status", timeout=5
        ) as resp:
            doc = json.loads(resp.read().decode())
        assert doc["collecting"] is False
        assert doc["monitor"]["state"] == "stopped"
        assert doc["fleet"]["state"] == "stopped"

        # /fleet/start with zero registered devices refuses 400 with a reason.
        # Environment-robust: on a machine whose real devices.local.json DOES
        # register base_url devices, the start succeeds instead - accept that,
        # but always stop what we started (never leak a real poller from a test).
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/fleet/start", method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                started = json.loads(resp.read().decode())
            assert started["state"] == "running"  # real local fleet config exists
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://127.0.0.1:{port}/fleet/stop", method="POST"
                ),
                timeout=5,
            )
        except urllib.error.HTTPError as e:
            assert e.code == 400
            body = json.loads(e.read().decode())
            assert "no registered fleet devices" in body["error"]
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
