"""Live-serving wrapper for the E7 dashboard (backlog E1 / live E7).

Serves the dashboard at ``/`` and exposes ``/data.json``, which re-parses the
logs fresh on every request via the E6 parser. The page's in-built Refresh /
Auto controls call ``/data.json`` and re-render in place, so the view tracks
the host logger as it appends. Read-only: it never writes the logs.

    python tools/analytics/serve.py                 # serve repo logs/ on :8765
    python tools/analytics/serve.py logs/ -p 8000   # custom inputs + port

Stop with Ctrl-C. The static ``dashboard.py`` snapshot is still the right tool
for a shareable one-file artifact; this is for live monitoring on the host.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from dashboard import (  # noqa: E402  (sibling import)
    RANGE_HOURS,
    build_context,
    filter_channels,
    filter_since,
    gather_inputs,
    render,
)
from parse_v1 import parse_files  # noqa: E402

_REPO = _HERE.parents[1]

_CAPTURE_DIR = _REPO / "tools" / "capture"
if str(_CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_DIR))
from control import CaptureController, ControlError  # noqa: E402  (capture sibling)

# The operator capture control plane (ADR-0011 Option A, #66): serve.py owns the
# control API and launches the bounded capture process; it never touches the port.
_CAPTURE = CaptureController()


def _context(
    inputs: list[str] | None = None,
    hours: float | None = None,
    channels: list[str] | None = None,
) -> dict:
    # Re-discover files on every request (fix #39): a list frozen at startup
    # misses log files created later (a UTC-midnight rotation, a reconnect), so
    # a long-running server would silently go stale. None => auto-discover.
    resolved = inputs or gather_inputs()
    data = parse_files(resolved)
    all_ch = sorted(
        {r.sensor_id for r in data.readings if r.record_type.startswith("plants.soil")}
    )
    data = filter_since(filter_channels(data, channels), hours)
    if not data.readings:
        raise ValueError(f"no readings parsed from {resolved}")
    ctx = build_context(data)
    ctx["meta"]["all_channels"] = all_ch  # full set, so the toggles can re-enable
    return ctx


class DashboardHandler(BaseHTTPRequestHandler):
    inputs: ClassVar[list[str] | None] = None  # None => auto-discover per request

    def _send(self, body: str, ctype: str, status: int = 200) -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_json(self, obj: object, status: int = 200) -> None:
        self._send(json.dumps(obj), "application/json; charset=utf-8", status=status)

    def do_GET(self) -> None:  # http.server dispatch name
        parsed = urlparse(self.path)
        q = parse_qs(parsed.query)
        hours = RANGE_HOURS.get(q.get("range", ["all"])[0])  # unknown/"all" -> None
        channels = [c for c in q.get("channels", [""])[0].split(",") if c] or None
        try:
            if parsed.path in ("/", "/index.html"):
                self._send(
                    render(_context(self.inputs, hours, channels)),
                    "text/html; charset=utf-8",
                )
            elif parsed.path == "/data.json":
                blob = json.dumps(
                    _context(self.inputs, hours, channels),
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                self._send(blob, "application/json; charset=utf-8")
            elif parsed.path == "/capture/status":
                self._send_json(_CAPTURE.status())
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except Exception as exc:  # report any parse/render failure to the client
            self._send(f"error: {exc}", "text/plain; charset=utf-8", status=500)

    def do_POST(self) -> None:  # http.server dispatch name (the control plane)
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/capture/start":
                b = self._body()
                self._send_json(_CAPTURE.start(
                    subject=b.get("subject", "unspecified"),
                    rate_s=b.get("rate_s", 1.0),
                    duration_s=b.get("duration_s", 60.0),
                    labels=b.get("labels"),
                    experiment_id=b.get("experiment_id"),
                    source=b.get("source", "synthetic"),
                    port=b.get("port"),
                ))
            elif parsed.path == "/capture/stop":
                self._send_json(_CAPTURE.stop())
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except ControlError as exc:  # a rejected request (bad input / busy)
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ControlError("request body must be a JSON object")
        return data

    def log_message(self, *args: object) -> None:  # quiet the per-request log
        return


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Serve the live plants dashboard.")
    ap.add_argument(
        "inputs", nargs="*", help="log files / dirs / globs (default: repo logs/)"
    )
    ap.add_argument("-p", "--port", type=int, default=8765, help="port (default 8765)")
    ap.add_argument("--host", default="127.0.0.1", help="bind host (default localhost)")
    args = ap.parse_args(argv)

    # Explicit CLI inputs are pinned; otherwise leave None so each request
    # re-discovers logs/ + the B8 archive (fix #39).
    DashboardHandler.inputs = args.inputs or None
    httpd = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}/"
    src = DashboardHandler.inputs or "logs/ + B8 archive (auto-discovered each request)"
    print(f"serving live dashboard at {url}  (inputs: {src})")
    print("Ctrl-C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
