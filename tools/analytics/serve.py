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

Scope boundary (ADR-0014 §5, #296): serve.py is **transport + routing + wiring** — HTTP
serving, request routing, and *holding* the CaptureController / MonitorController
instances. It does **not** implement capture/monitor lifecycle logic (those controllers
do); the control-plane state (the two instances + the Monitor/Experiment handoff) lives
here as module-globals. That co-location is the known seam, extracted into an
``operator_plane`` module only when a second UI context (#243's device UI) needs to
share it — not for hygiene alone.
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

from bench_packages import render_bench_detail  # noqa: E402  (bench detail #444)
from dashboard import (  # noqa: E402  (sibling import)
    FONTS_CSS,
    RANGE_HOURS,
    TOKENS_CSS,
    build_context,
    filter_channels,
    filter_since,
    gather_inputs,
    render,
)
from device_registry import load_registry  # noqa: E402  (the fleet config, #486)
from experiments_catalog import (  # noqa: E402  (Lab #154; #444 combined source)
    load_combined,
    render_catalog,
)
from lab_detail import render_detail  # noqa: E402  (Lab detail #157)
from lab_drafts import list_drafts, load_draft  # noqa: E402  (agent drafts #326)
from lab_notes import (  # noqa: E402  (Lab notes #158; path for save resilience #327)
    load_notes,
    notes_rel_path,
    save_notes,
)
from lab_studies import (  # noqa: E402  (Lab studies #159)
    list_studies,
    render_studies_catalog,
    render_study_detail,
    save_study,
)
from source_adapter import (  # noqa: E402  (the source-adapter seam, #277/#486)
    DeviceAdapter,
    FleetAdapter,
    TetheredAdapter,
)

_REPO = _HERE.parents[1]

# #808: the Diagnostics "Reference" front-door links (#758) point at docs/ files,
# but serve.py had no /docs route so they 404'd live. A scoped, read-only,
# traversal-guarded static route serves the repo docs/ tree (localhost only).
_DOCS_ROOT = _REPO / "docs"
_DOCS_CTYPES = {
    ".md": "text/plain; charset=utf-8",  # readable in-browser, never a download
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",  # e.g. the .dc.html's support.js
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
}


def docs_content_type(name: str) -> str:
    """The Content-Type for a docs file by extension; an unknown type degrades to
    readable ``text/plain`` (never an octet-stream download)."""
    return _DOCS_CTYPES.get(Path(name).suffix.lower(), "text/plain; charset=utf-8")


def resolve_docs_path(rel: str, *, root: Path = _DOCS_ROOT) -> Path | None:
    """Resolve a ``/docs/`` request to a real file **inside** ``root``, or ``None``
    if it escapes the tree or isn't a file. The traversal guard resolves ``..`` and
    symlinks and confirms the target stays under ``root`` (#808: reject ``..``)."""
    rel = (rel or "").lstrip("/")
    root_r = root.resolve()
    try:
        target = (root_r / rel).resolve()
    except (OSError, ValueError):
        return None
    if target != root_r and root_r not in target.parents:
        return None  # escaped the docs tree - reject
    return target if target.is_file() else None


_CAPTURE_DIR = _REPO / "tools" / "capture"
if str(_CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_DIR))
import handoff  # noqa: E402  (capture sibling - the Monitor<->Experiment handoff, #129)
import serial_lock  # noqa: E402  (capture sibling - the #64 advisory-lock contract)
from control import CaptureController, ControlError  # noqa: E402  (capture sibling)

_LOGGER_DIR = _REPO / "tools" / "logger"
if str(_LOGGER_DIR) not in sys.path:
    sys.path.insert(0, str(_LOGGER_DIR))
from collection_control import (  # noqa: E402  (logger sibling - #588)
    CollectionError,
    start_all,
    status_all,
    stop_all,
)
from fleet_control import FleetController, FleetError  # noqa: E402  (#588)
from monitor_control import (  # noqa: E402  (logger sibling)
    MonitorController,
    MonitorError,
)

# The operator control plane (ADR-0011, extended #128): serve.py owns the lifecycle of
# both modes - Experiment captures AND the Monitor logger - launching each as its own
# process that owns the port. serve.py never touches the serial port itself.
_CAPTURE = CaptureController()
_MONITOR = MonitorController()
# #588 (ADR-0014 ratification note): the fleet poller rides the same operator
# plane - one Start governs all collection; serve.py just holds + routes.
_FLEET = FleetController()

# The fixed port (ADR-0005 §4/§5). Data owns it as the single source of truth: the
# runner (`just start`) and the double-click launcher reference THIS value — via
# `--print-port` / `--print-url` — instead of re-typing the literal anywhere else.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_EID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from a status id


class NoDataYet(Exception):
    """Discovery found zero readings (#543) - not a parse error. ``had_any_logged``
    distinguishes a genuinely fresh checkout (nothing logged at all) from an
    existing install whose current range/channel filter excludes everything
    logged so far, so the first-run page never overclaims "fresh checkout" when
    real data actually exists. do_GET renders a real page for this instead of
    the bare 500 the ValueError used to produce."""

    def __init__(self, resolved: list[str], *, had_any_logged: bool) -> None:
        super().__init__(f"no readings parsed from {resolved}")
        self.had_any_logged = had_any_logged


def _empty_state_html(had_any_logged: bool) -> str:
    """A genuine first-run page (#543) - no readings yet is not an error state, so
    it gets its own honest, on-tone response rather than the 500 error path.

    On a genuinely fresh checkout it is also the operator's **launchpad** (#644):
    the ``Start all collection`` control lives on the full dashboard shell, which
    only renders once data exists - so at zero data the "one Start" moment had no
    button to press (chicken-and-egg). This page carries a working Start control
    so install day is never a dead-end. It posts the same ``/collection/start``
    (ADR-0014's one action) the shell's button does, then watches ``/data.json``
    and hands off to the live dashboard the instant the first reading lands - it
    never fakes progress. (The filtered-to-zero case already has data, so it gets
    a plain clear-the-filter message, no Start control.)"""
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    if had_any_logged:
        message = (
            "<p>No readings match the current range/channel filter.</p>"
            '<p><a href="/">Clear the filter</a>, or widen the time range, to see '
            "logged data.</p>"
        )
        launchpad = ""
        script = ""
    else:
        message = (
            "<p>No readings yet - this is a fresh checkout with nothing logged.</p>"
            "<p>Press <strong>Start all collection</strong> below to begin polling "
            "every registered device. This page opens the live dashboard the moment "
            "the first reading lands.</p>"
        )
        launchpad = (
            '<div class="launch">'
            '<button class="btn primary" id="collStart" type="button">'
            "▶ Start all collection</button>"
            '<p class="status" id="collStatus" role="status" aria-live="polite"></p>'
            "</div>"
        )
        script = _EMPTY_STATE_SCRIPT
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Sprout</title>
<style>
{fonts}
{tokens}
body {{ font-family: var(--font-ui); background: var(--bg); color: var(--ink);
  display: flex; align-items: center; justify-content: center; min-height: 100vh;
  margin: 0; }}
.empty {{ max-width: 32rem; text-align: center; padding: 2rem; }}
.empty h1 {{ font-family: var(--font-display); color: var(--leaf); }}
.empty p {{ color: var(--muted); }}
.empty a {{ color: var(--leaf); font-family: var(--font-ui); font-weight: 600;
  text-decoration: none; }}
.empty a:hover {{ text-decoration: underline; }}
.launch {{ margin-top: 1.5rem; }}
/* mirrors the ratified .btn/.btn.primary (dashboard_template.html) - the empty
   page loads only tokens+fonts, not the shell CSS, so the shared button style is
   restated here from the SAME tokens, never re-invented. */
.btn {{ font-family: var(--font-ui); font-size: 12px; font-weight: 600;
  cursor: pointer; border: 1px solid var(--border); background: var(--surface);
  color: var(--ink); border-radius: var(--r-pill); padding: 6px 14px;
  text-decoration: none; }}
.btn:hover {{ border-color: var(--leaf); }}
.btn:disabled {{ opacity: .5; cursor: not-allowed; }}
.btn.primary {{ background: var(--leaf); border-color: var(--leaf); color: #fff; }}
.btn.primary:hover {{ background: #2C9247; border-color: #2C9247; }}
.status {{ margin-top: .75rem; min-height: 1.2em; color: var(--muted);
  font-family: var(--font-ui); font-size: 12px; }}
</style>
</head>
<body>
<div class="empty">
<h1>Sprout</h1>
{message}
{launchpad}
</div>
{script}
</body>
</html>
"""


# The launchpad's behavior (kept out of the f-string so its JS braces need no
# doubling). Posts ADR-0014's one action, surfaces an honest refusal (the server
# returns 400 "nothing to collect from" when no device is registered yet - never
# a fake success), and on success polls /data.json, handing off to the live
# dashboard exactly when real data exists (#644).
_EMPTY_STATE_SCRIPT = """<script>
(function () {
  var btn = document.getElementById('collStart');
  var box = document.getElementById('collStatus');
  if (!btn) return;
  var watching = null;
  function watch() {
    if (watching) return;
    watching = setInterval(function () {
      fetch('data.json', { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j.empty) { clearInterval(watching); location.reload(); }
        })
        .catch(function () { /* transient - keep waiting for a first reading */ });
    }, 5000);
  }
  btn.addEventListener('click', function () {
    btn.disabled = true;
    box.textContent = 'starting…';
    fetch('/collection/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ port: null })
    })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, status: r.status, j: j };
        });
      })
      .then(function (res) {
        if (!res.ok || (res.j && res.j.error)) {
          btn.disabled = false;
          box.textContent = '⚠ ' + ((res.j && res.j.error) || ('HTTP ' + res.status));
          return;
        }
        box.textContent = '✓ collection started — waiting for the first reading…';
        watch();
      })
      .catch(function (e) {
        btn.disabled = false;
        box.textContent = '⚠ start failed: ' + e;
      });
  });
})();
</script>"""


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
        ctx = build_context(TetheredAdapter().load([str(csv)]))
        return ctx.get("trajectory", {}).get("datasets", [])
    except Exception:  # a partial mid-write read must not break the status poll
        return []


def _fleet_adapter(registry=None):
    """The live view's telemetry source (#486): the tethered CSV history plus one
    DeviceAdapter per fleet-registry device with a ``base_url``. With no served
    devices configured this is exactly the plain TetheredAdapter path - a
    tethered-only install sees zero behavior change. ``registry`` is injectable
    for tests; None loads the real fleet config per request (same re-discover
    rationale as #39: a config edit shouldn't need a server restart).

    #567: served devices get the weather-pressure seam (ADR-0023 §3) - a
    cache-only reader (never a fetch inside a request), import-guarded so a
    missing weather layer degrades to no pressure fill, never a broken view."""
    reg = registry if registry is not None else load_registry()
    served = reg.served_devices()
    tethered = TetheredAdapter()
    if not served:
        return tethered
    try:
        from weather_pressure import latest_pressure as _pressure
    except ImportError:
        _pressure = None
    # #676: address each board by its stable mDNS hostname first (sprout-<id>.local,
    # survives DHCP), the configured IP as a fallback; self-heal the registry when a
    # board answers at a fresh address. A missing mDNS responder degrades to the IP.
    from fleet_resolve import candidate_base_urls, make_healer

    return FleetAdapter(
        [
            tethered,
            *(
                DeviceAdapter(
                    d.base_url,
                    candidates=candidate_base_urls(d),
                    on_resolved=make_healer(d),
                    pressure_source=_pressure,
                )
                for d in served
            ),
        ]
    )


def _context(
    inputs: list[str] | None = None,
    hours: float | None = None,
    channels: list[str] | None = None,
    registry=None,
) -> dict:
    # Re-discover files on every request (fix #39): a list frozen at startup
    # misses log files created later (a UTC-midnight rotation, a reconnect), so
    # a long-running server would silently go stale. None => auto-discover.
    resolved = inputs or gather_inputs()
    # #602: one registry load per request, shared by the fleet adapter, the
    # channel filter's identity coalesce, and build_context's grouping.
    reg = registry if registry is not None else load_registry()
    # #277/#486: reads through the source-adapter seam - see source_adapter.py.
    data = _fleet_adapter(reg).load(resolved)
    all_ch = sorted(
        {r.sensor_id for r in data.readings if r.record_type.startswith("plants.soil")}
    )
    had_any_logged = bool(all_ch)
    data = filter_since(
        filter_channels(data, channels, canonical=reg.canonical_for), hours
    )
    if not data.readings:
        raise NoDataYet(resolved, had_any_logged=had_any_logged)  # #543
    ctx = build_context(data, registry=reg)
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

    def _send_raw(self, raw: bytes, ctype: str, status: int = 200) -> None:
        """Send already-encoded bytes (for #808 docs static files, incl. images/JS
        the ``str``-only ``_send`` can't carry)."""
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _serve_docs(self, rel: str) -> None:
        """#808: serve a read-only file from the repo ``docs/`` tree, traversal-
        guarded. 403 on an escape attempt, 404 on a miss - never reads outside."""
        target = resolve_docs_path(rel)
        if target is None:
            # a traversal attempt is forbidden; a plain missing file is a 404
            traversal = ".." in rel or rel.startswith(("/", "\\"))
            self._send(
                "forbidden" if traversal else "not found",
                "text/plain; charset=utf-8",
                status=403 if traversal else 404,
            )
            return
        try:
            raw = target.read_bytes()
        except OSError:
            self._send("not found", "text/plain; charset=utf-8", status=404)
            return
        self._send_raw(raw, docs_content_type(target.name))

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
            elif parsed.path == "/fleet/status":  # the fleet poller (#588)
                self._send_json(_FLEET.status())
            elif parsed.path == "/collection/status":  # both paths, one view (#588)
                self._send_json(status_all(_MONITOR, _FLEET))
            elif parsed.path == "/serial/owner":  # who holds the port (#330)
                self._send_json(serial_lock.owner_status())
            elif parsed.path.startswith("/docs/"):  # #808: front-door docs, guarded
                self._serve_docs(unquote(parsed.path[len("/docs/") :]))
            elif parsed.path == "/lab":  # the Lab Notebook catalog (#154 + bench #444)
                self._send(render_catalog(load_combined()), "text/html; charset=utf-8")
            elif parsed.path == "/lab/experiments.json":
                self._send_json(load_combined())
            elif parsed.path == "/lab/drafts":  # agent-prepared draft list (#326)
                self._send_json({"drafts": list_drafts()})
            elif parsed.path.startswith("/lab/draft/"):  # one draft, for prefill (#326)
                name = unquote(parsed.path[len("/lab/draft/") :])
                draft = load_draft(name)
                if draft is None:
                    self._send_json({"error": "draft not found"}, status=404)
                else:
                    self._send_json(draft)
            elif parsed.path == "/lab/studies":  # the studies catalog (#159)
                self._send(
                    render_studies_catalog(list_studies()),
                    "text/html; charset=utf-8",
                )
            elif parsed.path.startswith("/lab/study/"):  # a study detail (#159)
                sid = unquote(parsed.path[len("/lab/study/") :])
                page = render_study_detail(sid)
                if page is None:
                    self._send("study not found", "text/plain", status=404)
                else:
                    self._send(page, "text/html; charset=utf-8")
            elif parsed.path.startswith("/lab/") and parsed.path.endswith("/notes"):
                eid = unquote(parsed.path[len("/lab/") : -len("/notes")])  # notes #158
                self._send_json(load_notes(eid))
            elif parsed.path.startswith("/lab/bench/"):  # a bench-package detail (#444)
                pkg = unquote(parsed.path[len("/lab/bench/") :])
                page = render_bench_detail(pkg)
                if page is None:
                    self._send("bench package not found", "text/plain", status=404)
                else:
                    self._send(page, "text/html; charset=utf-8")
            elif parsed.path.startswith("/lab/"):  # an experiment detail page (#157)
                eid = unquote(parsed.path[len("/lab/") :])
                page = render_detail(eid)
                if page is None:
                    self._send("experiment not found", "text/plain", status=404)
                else:
                    self._send(page, "text/html; charset=utf-8")
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except NoDataYet as exc:  # #543: the honest empty state, not an error
            if parsed.path == "/data.json":
                self._send_json({"empty": True, "had_any_logged": exc.had_any_logged})
            else:
                self._send(
                    _empty_state_html(exc.had_any_logged), "text/html; charset=utf-8"
                )
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
            elif parsed.path == "/fleet/start":  # single-flight (#588)
                self._send_json(_FLEET.start())
            elif parsed.path == "/fleet/stop":
                self._send_json(_FLEET.stop())
            elif parsed.path == "/collection/start":
                # ADR-0014: ONE operator action = all collection running; each
                # absent path skips with a stated reason (policy lives in
                # collection_control, not here - serve stays wiring, section 5)
                self._send_json(
                    start_all(_MONITOR, _FLEET, port=self._body().get("port"))
                )
            elif parsed.path == "/collection/stop":
                self._send_json(stop_all(_MONITOR, _FLEET))
            elif parsed.path == "/serial/owner/clear":  # clear a STALE marker (#330)
                self._send_json(serial_lock.clear_if_stale())
            elif parsed.path.startswith("/lab/study/"):  # save a study (#159)
                sid = unquote(parsed.path[len("/lab/study/") :])
                self._send_json(save_study(sid, self._body()))
            elif parsed.path.startswith("/lab/bench/") and parsed.path.endswith(
                "/notes"
            ):
                # Back-fill notes onto a landed bench package (#450 slice 3). Must
                # precede the generic /lab/*/notes route, which mis-reads "bench/<id>".
                pkg = unquote(parsed.path[len("/lab/bench/") : -len("/notes")])
                try:
                    result = save_notes(pkg, self._body())
                    result["path"] = notes_rel_path(pkg)
                    self._send_json(result)
                except Exception as exc:
                    self._send_json(
                        {"error": str(exc), "path": notes_rel_path(pkg)}, status=500
                    )
            elif parsed.path.startswith("/lab/") and parsed.path.endswith("/notes"):
                eid = unquote(parsed.path[len("/lab/") : -len("/notes")])  # notes #158
                try:
                    body = self._body()
                    # #450: optional lifecycle status + edit author ride the same body,
                    # backward-compatible (absent -> carried / "unknown").
                    result = save_notes(
                        eid, body, status=body.get("status"), author=body.get("author")
                    )
                    result["path"] = notes_rel_path(eid)  # #327: show where it landed
                    self._send_json(result)
                except Exception as exc:  # #327: surface the failed target path so the
                    # operator knows what failed; client keeps the text + retries
                    self._send_json(
                        {"error": str(exc), "path": notes_rel_path(eid)}, status=500
                    )
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
                    # One-action quit (#151 AC3): tear down any child the server
                    # started - the capture/logger process - so "Stop server" closes
                    # the WHOLE stack, not just the web server. Best-effort: a child
                    # that's already gone or slow to stop must not block shutdown.
                    for controller in (_CAPTURE, _MONITOR, _FLEET):
                        with contextlib.suppress(Exception):
                            controller.stop()
                    self.server.shutdown()

                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                self._send("not found", "text/plain; charset=utf-8", status=404)
        except (
            ControlError,
            MonitorError,
            FleetError,
            CollectionError,
        ) as exc:  # rejected (bad input / busy / nothing to collect)
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
        "- an explicit force-fresh (e.g. after a code update)",
    )
    ap.add_argument(
        "--serve-or-focus",
        action="store_true",
        help="single-instance (the launcher default, #151): if Sprout is already "
        "running, just open its tab and exit - never a second server or window",
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

    # Port-safety (#126/#127/#151): if a Sprout server is already on this port, don't
    # half-bind behind it (Windows SO_REUSEADDR would let us). Three ways to resolve,
    # in order: --restart takes over (ask the old one to /quit); --serve-or-focus (the
    # launcher default) is single-instance - open the existing tab and bow out, so a
    # second double-click never spawns a second server or window (#151 AC1/AC2/AC4);
    # otherwise say so + exit non-zero.
    if _port_in_use(args.host, args.port):
        if args.restart and _stop_existing(url, args.host, args.port):
            pass  # took over the port; fall through to bind our own
        elif args.serve_or_focus:
            print(f"Sprout is already running at {url} - opening that tab.")
            if args.open:
                webbrowser.open(url)
            return 0  # single-instance: exactly one server, no second window
        else:
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
    except OSError as exc:  # lost the race between the probe and the bind
        if getattr(exc, "errno", None) == errno.EADDRINUSE:
            # Someone bound between our probe and here. Single-instance still holds:
            # focus the winner instead of erroring (closes the double-launch race).
            if args.serve_or_focus:
                print(f"Sprout is already running at {url} - opening that tab.")
                if args.open:
                    webbrowser.open(url)
                return 0
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
