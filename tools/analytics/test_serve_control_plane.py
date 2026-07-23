#!/usr/bin/env python3
"""#1468 AC2 — the control plane's localhost floor: one central gate, one refused bind.

Two halves, per the AC:

* **The bind**: ``--host`` with anything non-loopback is refused OUTRIGHT (exit 2,
  nothing bound) — ADR-0014's "localhost-only" becomes a property of the process, not a
  default a flag can flip.
* **The gate**: EVERY control-plane POST passes one central local-origin check —
  loopback peer + loopback ``Host`` (the DNS-rebinding fence: a page resolving
  evil.com→127.0.0.1 still sends ``Host: evil.com``) + loopback ``Origin`` when a
  browser attaches one (the cross-site POST fence; ``Origin: null`` refused). This
  replaces the per-route ``_is_local()`` sprinkle that guarded six routes and left the
  rest of the write plane open — the inconsistency the re-audit called a security
  finding, not a maintainability one.

Unit tests pin the predicate's edges (the spoofable spellings); the end-to-end half
proves the running server refuses/admits at the real HTTP boundary, on a route that has
no side effects (an unknown path: 403 means the gate fired, 404 means it passed).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serve
from serve import _host_header_name, _is_loopback_host

_SERVE = Path(__file__).resolve().parent / "serve.py"


# ---- the predicate (unit) --------------------------------------------------- #
def test_loopback_spellings_are_accepted() -> None:
    for h in ("localhost", "LOCALHOST", "127.0.0.1", "127.9.8.7", "::1", "[::1]"):
        assert _is_loopback_host(h), h


def test_non_loopback_and_spoof_spellings_are_refused() -> None:
    for h in (
        "0.0.0.0",
        "192.168.1.20",
        "10.0.0.5",
        "example.com",
        "127.evil.com",  # startswith("127.") is NOT loopback — no DNS trust
        "1270.0.0.1",
        "127.0.0",  # not a full quad
        "localhost.evil.com",
        "",
        None,
    ):
        assert not _is_loopback_host(h), h


def test_host_header_port_and_bracket_handling() -> None:
    assert _host_header_name("localhost:8765") == "localhost"
    assert _host_header_name("127.0.0.1:8765") == "127.0.0.1"
    assert _host_header_name("[::1]:8765") == "::1"
    assert _host_header_name("[::1]") == "::1"
    assert _host_header_name("localhost") == "localhost"
    assert _host_header_name(None) == ""


# ---- the bind refusal (in-process; returns before anything binds) ------------ #
def test_a_non_loopback_bind_is_refused_outright(capsys) -> None:
    rc = serve.main(["--host", "0.0.0.0", "--print-port"])
    assert rc == 2  # refused BEFORE --print-port, before any socket exists
    err = capsys.readouterr().err
    assert "localhost-only" in err and "0.0.0.0" in err


def test_loopback_binds_still_pass_the_gate() -> None:
    # --print-port exits right after the host check — proves the check admits loopback
    # without standing up a server inside the test process.
    for host in ("127.0.0.1", "localhost", "::1"):
        assert serve.main(["--host", host, "--print-port"]) == 0


# ---- the central gate at the real HTTP boundary ------------------------------ #
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _boot(tmp_path: Path) -> tuple[subprocess.Popen, int]:
    d = tmp_path / "logs"
    d.mkdir(exist_ok=True)
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(_SERVE), str(d), "--port", str(port), "--no-autostart"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return proc, port
        except OSError:
            time.sleep(0.1)
    proc.terminate()
    raise AssertionError("server did not come up")


def _post(port: int, path: str, headers: dict | None = None) -> int:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=b"{}", method="POST"
    )
    for k, v in (headers or {}).items():
        # urllib sets Host itself unless overridden; add_unredirected keeps ours.
        req.add_unredirected_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_the_gate_refuses_a_rebinding_host_and_admits_localhost(tmp_path: Path) -> None:
    """The end-to-end floor on a side-effect-free path: 403 = the gate fired,
    404 = it passed to normal routing. Same peer (loopback) in every case — the
    HEADERS are what decide, which is exactly the rebinding/CSRF fence."""
    proc, port = _boot(tmp_path)
    try:
        # a rebinding page: TCP reaches 127.0.0.1 but the browser says evil.com
        assert _post(port, "/nope", {"Host": "evil.com"}) == 403
        assert _post(port, "/nope", {"Host": f"evil.com:{port}"}) == 403
        # a cross-site form POST carries its own Origin — refused; null likewise
        assert _post(port, "/nope", {"Origin": "http://evil.com"}) == 403
        assert _post(port, "/nope", {"Origin": "null"}) == 403
        # the app's own requests: localhost Host (urllib default), local Origin ok
        assert _post(port, "/nope") == 404  # gate passed; the route just doesn't exist
        assert _post(port, "/nope", {"Origin": f"http://127.0.0.1:{port}"}) == 404
        assert _post(port, "/nope", {"Origin": f"http://localhost:{port}"}) == 404
        # GETs are read-only and NOT gated — the dashboard itself keeps working
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/monitor/status", timeout=10
        ) as resp:
            assert resp.status == 200
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_formerly_guarded_and_formerly_unguarded_routes_are_now_equal(
    tmp_path: Path,
) -> None:
    """The inconsistency is closed: /quit (formerly guarded) and /monitor/stop
    (formerly UNguarded) refuse a bad Host identically — one gate, whole plane."""
    proc, port = _boot(tmp_path)
    try:
        assert _post(port, "/quit", {"Host": "evil.com"}) == 403
        assert _post(port, "/monitor/stop", {"Host": "evil.com"}) == 403
        # and with honest headers, /monitor/stop reaches its handler (200: a no-op
        # stop of a monitor that isn't running still answers, not 403/404)
        assert _post(port, "/monitor/stop") == 200
    finally:
        proc.terminate()
        proc.wait(timeout=5)
