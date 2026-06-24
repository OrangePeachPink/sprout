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


def _context(
    inputs: list[str], hours: float | None = None, channels: list[str] | None = None
) -> dict:
    data = parse_files(inputs)
    all_ch = sorted(
        {r.sensor_id for r in data.readings if r.record_type.startswith("plants.soil")}
    )
    data = filter_since(filter_channels(data, channels), hours)
    if not data.readings:
        raise ValueError(f"no readings parsed from {inputs}")
    ctx = build_context(data)
    ctx["meta"]["all_channels"] = all_ch  # full set, so the toggles can re-enable
    return ctx


class DashboardHandler(BaseHTTPRequestHandler):
    inputs: ClassVar[list[str]] = []

    def _send(self, body: str, ctype: str, status: int = 200) -> None:
        raw = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

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
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except Exception as exc:  # report any parse/render failure to the client
            self._send(f"error: {exc}", "text/plain; charset=utf-8", status=500)

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

    DashboardHandler.inputs = args.inputs or gather_inputs()
    httpd = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"serving live dashboard at {url}  (inputs: {DashboardHandler.inputs})")
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
