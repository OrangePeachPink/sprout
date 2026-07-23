"""#969 a client abort mid-response must not cascade into a double traceback.

A browser that gives up mid-response (tab close / refresh / back) aborts the socket, so
`wfile.write` raises ConnectionAbortedError (WinError 10053). Before the fix, the do_GET
catch-all then wrote a 500 down the same dead socket, a second abort cascaded, and
socketserver dumped a ~40-line double traceback for a routine disconnect. The send
helpers now swallow a dead-client abort with one quiet line, so the 500 never fires.
"""

from __future__ import annotations

import io
import sys

from tools.analytics.serve import DashboardHandler


class _FakeWfile:
    def __init__(self, *, dead: bool) -> None:
        self.dead = dead
        self.written = b""

    def write(self, b: bytes) -> None:
        if self.dead:
            raise ConnectionAbortedError(10053, "An established connection was aborted")
        self.written += b


class _FakeHandler:
    """Borrows the real send helpers (the code under test) with a mock socket."""

    _client_gone = DashboardHandler._client_gone
    _send = DashboardHandler._send
    _send_json = DashboardHandler._send_json
    _send_raw = DashboardHandler._send_raw

    def __init__(self, *, dead: bool) -> None:
        self.command = "GET"
        self.path = "/data.json?range=7d"
        self.wfile = _FakeWfile(dead=dead)
        self.responses: list[int] = []

    def send_response(self, status: int) -> None:
        self.responses.append(status)

    def send_header(self, *_a) -> None:
        pass

    def end_headers(self) -> None:
        pass


def test_dead_client_abort_is_swallowed_with_one_quiet_line(monkeypatch) -> None:
    h = _FakeHandler(dead=True)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    # must NOT raise — the abort is swallowed
    h._send("some body", "text/html; charset=utf-8")
    out = buf.getvalue()
    assert out.count("\n") == 1  # exactly one line, never a traceback
    assert "client disconnected mid-response" in out
    assert "/data.json?range=7d" in out  # carries the context


def test_live_client_send_writes_normally() -> None:
    h = _FakeHandler(dead=False)
    h._send("hello", "text/plain; charset=utf-8")
    assert h.wfile.written == b"hello"
    assert h.responses == [200]


def test_dead_client_500_fallback_does_not_cascade(monkeypatch) -> None:
    # the exact cascade: a real error tries to send a 500, but the socket is already
    # dead — the 500 send must ALSO swallow, not raise a second abort.
    h = _FakeHandler(dead=True)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    h._send("error: boom", "text/plain; charset=utf-8", status=500)  # must not raise
    assert "client disconnected mid-response" in buf.getvalue()


def test_send_raw_dead_client_is_swallowed(monkeypatch) -> None:
    h = _FakeHandler(dead=True)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    h._send_raw(b"\x89PNG...", "image/png")  # docs-image path, same guard
    assert "client disconnected mid-response" in buf.getvalue()


if __name__ == "__main__":

    class _MP:
        def setattr(self, obj, name, val):
            setattr(obj, name, val)

    test_dead_client_abort_is_swallowed_with_one_quiet_line(_MP())
    print("  PASS  swallowed with one line")
    sys.stderr = sys.__stderr__
    test_live_client_send_writes_normally()
    print("  PASS  live send writes normally")
    test_dead_client_500_fallback_does_not_cascade(_MP())
    sys.stderr = sys.__stderr__
    print("  PASS  500 fallback does not cascade")
    test_send_raw_dead_client_is_swallowed(_MP())
    sys.stderr = sys.__stderr__
    print("All checks passed.")
