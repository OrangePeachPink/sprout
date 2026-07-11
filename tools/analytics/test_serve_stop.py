"""#972 Stop-server must preempt the request pile — the off-switch must be prompt and
bounded, never hang.

The maintainer pressed Stop under a slow-build pileup and the UI spun "stopping…"
forever: `server_close()` joins the 14-24s build handler threads, and live-view polls
kept replenishing the pile. The fix refuses new work the instant Stop fires (a fast
503), gives in-flight handlers a bounded grace, then hard-exits (os._exit) so a slow
handler can never hold the process open.

The key test drives the exact reported failure: a deliberately-slow handler in flight
when /quit arrives, and the process must still exit within the grace window.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

_SERVE = Path(__file__).resolve().parent / "serve.py"


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_up(port: int, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _post(port: int, path: str) -> None:
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=3) as resp:
        resp.read()


def test_stop_preempts_a_slow_handler_in_flight(tmp_path: Path) -> None:
    port = _free_port()
    env = {"SPROUT_TEST_SLOW": "1", "PYTHONIOENCODING": "utf-8"}

    proc = subprocess.Popen(
        [sys.executable, str(_SERVE), str(tmp_path), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, **env},
    )
    try:
        assert _wait_up(port), "server never came up"

        # a 5s handler goes in flight (fire-and-forget; it will be killed on hard-exit)
        def _slow():
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/debug/slow?s=5", timeout=8
                ) as r:
                    r.read()
            except Exception:
                pass  # the process exits under it — the connection dropping is expected

        t = threading.Thread(target=_slow, daemon=True)
        t.start()
        time.sleep(0.4)  # ensure the slow handler is actually mid-sleep

        # press Stop and time how long the PROCESS takes to actually exit
        t0 = time.monotonic()
        _post(port, "/quit")
        rc = proc.wait(timeout=5.0)  # must exit well under the 5s slow handler + margin
        elapsed = time.monotonic() - t0

        assert rc == 0, f"non-clean exit: {rc}"
        # bounded: the grace (~2.5s) + ack/teardown, never the 5s slow handler
        assert elapsed < 4.5, f"stop was not prompt: {elapsed:.2f}s"
        out = proc.stdout.read() if proc.stdout else ""
        # the shutdown entry the maintainer saw missing is now written (the AC); the
        # post-grace "stopped" line races os._exit's teardown so we don't require it.
        assert "shutting down" in out, f"no shutdown entry logged: {out!r}"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_new_requests_are_refused_once_stopping(tmp_path: Path) -> None:
    # after Stop, a live-view poll must get a fast 503, not queue behind the shutdown
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(_SERVE), str(tmp_path), "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    try:
        assert _wait_up(port)
        _post(port, "/quit")
        time.sleep(0.4)  # inside the grace window, before the hard-exit
        code = None
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/data.json", timeout=2
            ) as r:
                code = r.status
        except urllib.error.HTTPError as exc:
            code = exc.code
        except Exception:
            code = "refused"  # socket closed already — also an acceptable "not served"
        assert code in (503, "refused"), f"a poll during stop was served ({code})"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_stop_preempts_a_slow_handler_in_flight(Path(d))
    print("  PASS  test_stop_preempts_a_slow_handler_in_flight")
    with tempfile.TemporaryDirectory() as d:
        test_new_requests_are_refused_once_stopping(Path(d))
    print("  PASS  test_new_requests_are_refused_once_stopping")
    print("All checks passed.")
