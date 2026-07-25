#!/usr/bin/env python3
"""#1555 (B5, from the #1541 clean-checkout walk) — the port is announced before it can
fail, and a busy port says who holds it.

Two findings from the walk, both about the moment startup goes wrong:

* the URL was printed only *after* a successful bind, so the one case where you most
  need to know which port Sprout wanted — it couldn't get it — never told you;
* "Sprout is already running" was asserted on the strength of *something* accepting a
  TCP connection, which is equally true of an unrelated program on 8765. Sending an
  operator to hunt for a Sprout window that does not exist is the kind of confident-
  wrong message this project treats as a defect, not a papercut.

So the claim now carries evidence (a probe of a read-only Sprout route) and the
not-Sprout case is a different sentence with a different fix.
"""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tools.analytics import serve


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Sproutish(BaseHTTPRequestHandler):
    """Answers /monitor/status the way a real Sprout does."""

    def do_GET(self) -> None:
        body = json.dumps({"state": "stopped"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a: object) -> None:
        return


class _Stranger(BaseHTTPRequestHandler):
    """Accepts connections but is not Sprout — the case the old message got wrong."""

    def do_GET(self) -> None:
        self.send_response(404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a: object) -> None:
        return


def _serving(handler) -> tuple[ThreadingHTTPServer, str, int]:
    port = _free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/", port


def test_a_real_sprout_is_recognized() -> None:
    httpd, url, _ = _serving(_Sproutish)
    try:
        assert serve._looks_like_sprout(url) is True
    finally:
        httpd.shutdown()


def test_a_stranger_on_the_port_is_not_called_sprout() -> None:
    """Accepting a TCP connection is not evidence of being Sprout — so we don't say
    it is."""
    httpd, url, _ = _serving(_Stranger)
    try:
        assert serve._looks_like_sprout(url) is False
    finally:
        httpd.shutdown()


def test_nothing_listening_is_not_sprout_and_never_raises() -> None:
    port = _free_port()  # closed again — nothing is there
    assert serve._looks_like_sprout(f"http://127.0.0.1:{port}/") is False


def test_the_sprout_advice_offers_just_restart() -> None:
    """B5's ask: the recipe that resolves the common case is named, not left in the
    justfile comments where the walk found it."""
    httpd, url, port = _serving(_Sproutish)
    try:
        lines = serve._port_busy_advice(url, port)
    finally:
        httpd.shutdown()
    text = "\n".join(lines)
    assert "already running" in text
    assert "just restart" in text  # the fix, named


def test_the_stranger_advice_says_so_and_offers_another_port() -> None:
    httpd, url, port = _serving(_Stranger)
    try:
        lines = serve._port_busy_advice(url, port)
    finally:
        httpd.shutdown()
    text = "\n".join(lines)
    assert str(port) in text
    assert "not answering as Sprout" in text
    assert "already running" not in text  # never the unevidenced claim
    assert f"-p {port + 1}" in text  # a way forward that doesn't need the port freed


def test_the_port_is_announced_before_the_busy_check(capsys) -> None:
    """The ordering fix: a run that CANNOT bind still prints the URL it wanted first."""
    httpd, url, port = _serving(_Sproutish)
    try:
        rc = serve.main(["--port", str(port), "--no-autostart"])
    finally:
        httpd.shutdown()
    out = capsys.readouterr().out
    assert rc == 1  # busy, and not --restart/--serve-or-focus
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines[0] == f"Sprout: starting on {url}"  # announced FIRST, before the news
    assert "just restart" in out
