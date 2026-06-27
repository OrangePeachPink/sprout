"""Live-serving wrapper for the E7 dashboard (backlog E1 / live E7).

Serves the dashboard at ``/`` and exposes ``/data.json``, which re-parses the
logs fresh on every request via the E6 parser. The page's in-built Refresh /
Auto controls call ``/data.json`` and re-render in place, so the view tracks
the host logger as it appends. Read-only: it never writes the logs.

    python tools/analytics/serve.py                 # serve repo logs/ on :8765
    python tools/analytics/serve.py logs/ -p 8000   # custom inputs + port
    python tools/analytics/serve.py --open          # serve + open the browser

Stop it from the dashboard's "Stop server" control (the no-terminal door) or with
Ctrl-C. The static ``dashboard.py`` snapshot is still the right tool for a
shareable one-file artifact; this is for live monitoring on the host.
"""

from __future__ import annotations

import argparse
import contextlib
import errno
import json
import re
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, unquote, urlparse

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
from experiments_catalog import load_catalog, render_catalog  # noqa: E402  (Lab #154)
from lab_detail import render_detail  # noqa: E402  (Lab detail #157)
from lab_notes import load_notes, save_notes  # noqa: E402  (Lab notes #158)
from parse_v1 import parse_files  # noqa: E402

_REPO = _HERE.parents[1]

_CAPTURE_DIR = _REPO / "tools" / "capture"
if str(_CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_DIR))
import handoff  # noqa: E402  (capture sibling - the Monitor<->Experiment handoff, #129)
from control import CaptureController, ControlError  # noqa: E402  (capture sibling)

_LOGGER_DIR = _REPO / "tools" / "logger"
if str(_LOGGER_DIR) not in sys.path:
    sys.path.insert(0, str(_LOGGER_DIR))
from monitor_control import (  # noqa: E402  (logger sibling)
    MonitorController,
    MonitorError,
)

# The operator control plane (ADR-0011, extended #128): serve.py owns the lifecycle of
# both modes - Experiment captures AND the Monitor logger - launching each as its own
# process that owns the port. serve.py never touches the serial port itself.
_CAPTURE = CaptureController()
_MONITOR = MonitorController()

# The fixed port (ADR-0005 §4/§5). Data owns it as the single source of truth: the
# runner (`just start`) and the double-click launcher reference THIS value — via
# `--print-port` / `--print-url` — instead of re-typing the literal anywhere else.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_EID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from a status id


def _live_trace(eid: str | None, experiments_dir: object = None) -> list[dict]:
    """The running capture's per-probe trajectory, re-parsed from its (live) CSV, so the
    capture panel can chart the sub-second data as it lands (#161). Cheap (a bounded
    capture, flushed per row); returns [] on any error - never breaks the poll."""
    if not eid or not _EID_RE.match(eid) or ".." in eid:
        return []
    root = Path(experiments_dir) if experiments_dir else _REPO / "experiments"
    csv = root / eid / f"{eid}.csv"
    if not csv.exists():
        return []
    try:
        ctx = build_context(parse_files([str(csv)]))
        return ctx.get("trajectory", {}).get("datasets", [])
    except Exception:  # a partial mid-write read must not break the status poll
        return []


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
                st = _CAPTURE.status()
                if st.get("state") == "running":  # live trajectory for the panel (#161)
                    st = {**st, "trace": _live_trace(st.get("experiment_id"))}
                self._send_json(st)
            elif parsed.path == "/monitor/status":
                self._send_json(_MONITOR.status())
            elif parsed.path == "/lab":  # the Lab Notebook catalog (#154)
                self._send(render_catalog(load_catalog()), "text/html; charset=utf-8")
            elif parsed.path == "/lab/experiments.json":
                self._send_json(load_catalog())
            elif parsed.path.startswith("/lab/") and parsed.path.endswith("/notes"):
                eid = unquote(parsed.path[len("/lab/") : -len("/notes")])  # notes #158
                self._send_json(load_notes(eid))
            elif parsed.path.startswith("/lab/"):  # an experiment detail page (#157)
                eid = unquote(parsed.path[len("/lab/") :])
                page = render_detail(eid)
                if page is None:
                    self._send("experiment not found", "text/plain", status=404)
                else:
                    self._send(page, "text/html; charset=utf-8")
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except Exception as exc:  # report any parse/render failure to the client
            self._send(f"error: {exc}", "text/plain; charset=utf-8", status=500)

    def do_POST(self) -> None:  # http.server dispatch name (the control plane)
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/capture/start":
                b = self._body()
                # Route through the handoff (#129): a serial start auto-pauses the
                # monitor (frees COM6) and resumes it when the experiment ends.
                self._send_json(
                    handoff.start_experiment(
                        _MONITOR,
                        _CAPTURE,
                        subject=b.get("subject", "unspecified"),
                        rate_s=b.get("rate_s", 1.0),
                        duration_s=b.get("duration_s", 60.0),
                        labels=b.get("labels"),
                        experiment_id=b.get("experiment_id"),
                        source=b.get("source", "synthetic"),
                        port=b.get("port"),
                    )
                )
            elif parsed.path == "/capture/stop":
                self._send_json(_CAPTURE.stop())
            elif parsed.path == "/monitor/start":
                self._send_json(_MONITOR.start(port=self._body().get("port")))
            elif parsed.path == "/monitor/stop":
                self._send_json(_MONITOR.stop())
            elif parsed.path.startswith("/lab/") and parsed.path.endswith("/notes"):
                eid = unquote(parsed.path[len("/lab/") : -len("/notes")])  # notes #158
                self._send_json(save_notes(eid, self._body()))
            elif parsed.path == "/quit":
                # In-UI stop (ADR-0005 §4): a localhost-gated shutdown so the operator
                # stops the server from the browser (no terminal to Ctrl-C when it was
                # launched by a double-click). Ack first, then shut down from a separate
                # thread - serve_forever can't be stopped from its own request thread.
                if not self._is_local():
                    self._send_json({"error": "shutdown is localhost-only"}, status=403)
                    return
                self._send_json({"stopped": True})

                def _shutdown() -> None:
                    time.sleep(0.25)  # let the {stopped:true} ack flush to the browser
                    self.server.shutdown()

                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except (ControlError, MonitorError) as exc:  # rejected (bad input / busy)
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

    def _is_local(self) -> bool:  # loopback-only guard for the shutdown endpoint
        host = self.client_address[0] if self.client_address else ""
        return host in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def log_message(self, *args: object) -> None:  # quiet the per-request log
        return


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already accepting connections on host:port. A connect
    probe (not a bind) - reliable on Windows, where SO_REUSEADDR would otherwise let
    a second server silently bind a port a zombie already holds."""
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex((host, port)) == 0


def _stop_existing(url: str, host: str, port: int) -> bool:
    """Ask a Sprout server already on the port to shut down (its #96 /quit endpoint),
    then wait for the port to free. Returns True if it released the port. Only stops a
    server that answers /quit (a Sprout server) - it never force-kills anything."""
    with contextlib.suppress(Exception):  # the server drops the conn as it exits
        urllib.request.urlopen(
            urllib.request.Request(url + "quit", method="POST"), timeout=3
        )
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not _port_in_use(host, port):
            return True
        time.sleep(0.2)
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Serve the live plants dashboard.")
    ap.add_argument(
        "inputs", nargs="*", help="log files / dirs / globs (default: repo logs/)"
    )
    ap.add_argument(
        "-p",
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"port (default {DEFAULT_PORT})",
    )
    ap.add_argument(
        "--host", default=DEFAULT_HOST, help="bind host (default localhost)"
    )
    ap.add_argument(
        "--open",
        action="store_true",
        help="open the dashboard in a browser once serving (the no-terminal door)",
    )
    ap.add_argument(
        "--restart",
        action="store_true",
        help="if a Sprout server already holds the port, ask it to /quit and take over "
        "- used by the launcher so a stale server can't block entry",
    )
    ap.add_argument(
        "--print-port",
        action="store_true",
        help="print the fixed port and exit (the launcher's single source of truth)",
    )
    ap.add_argument(
        "--print-url",
        action="store_true",
        help="print the dashboard URL and exit (for `just start` / the launcher)",
    )
    args = ap.parse_args(argv)

    url = f"http://{args.host}:{args.port}/"
    if args.print_port:  # the launcher reads this; never retypes the port literal
        print(args.port)
        return 0
    if args.print_url:
        print(url)
        return 0

    # Port-safety (#126/#127): if a Sprout server is already on this port, don't
    # half-bind behind it (Windows SO_REUSEADDR would let us). With --restart the
    # launcher takes over by asking the old one to /quit; otherwise say so + exit.
    if _port_in_use(args.host, args.port) and not (
        args.restart and _stop_existing(url, args.host, args.port)
    ):
        print(f"Sprout is already running at {url}")
        print(
            '  Open that tab, or stop it first ("Stop server" in the dashboard, '
            "or close its window)."
        )
        return 1

    # Explicit CLI inputs are pinned; otherwise leave None so each request
    # re-discovers logs/ + the B8 archive (fix #39).
    DashboardHandler.inputs = args.inputs or None
    try:
        httpd = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    except OSError as exc:  # raced between the probe and the bind
        if getattr(exc, "errno", None) == errno.EADDRINUSE:
            print(f"Sprout is already running at {url} - stop it first.")
            return 1
        raise
    src = DashboardHandler.inputs or "logs/ + B8 archive (auto-discovered each request)"
    print(f"serving live dashboard at {url}  (inputs: {src})")
    print('stop from the dashboard ("Stop server") or with Ctrl-C')
    if args.open:  # the socket is bound + listening; the browser waits in the backlog
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
