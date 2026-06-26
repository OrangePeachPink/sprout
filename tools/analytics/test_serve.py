#!/usr/bin/env python3
"""Standalone tests for the serve.py launch seam (#86, ADR-0005 §4/§5):

  * the fixed-port single-source-of-truth accessors (``--print-port`` /
    ``--print-url``) the runner + launcher reference instead of retyping ``8765``,
  * the localhost-gated in-UI shutdown (``POST /quit``) — the no-terminal stop.

    python tools/analytics/test_serve.py
"""

from __future__ import annotations

import contextlib
import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SERVE = _HERE / "serve.py"
_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def _run(*args: str) -> str:
    out = subprocess.run(
        [sys.executable, str(_SERVE), *args],
        capture_output=True, text=True, timeout=60,
    )
    return out.stdout.strip()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_port_ssot() -> None:
    print("fixed-port SSOT accessors (the launcher reads one value, never retypes it):")
    check(_run("--print-port") == "8765", "--print-port prints the fixed port 8765")
    check(
        _run("--print-url") == "http://127.0.0.1:8765/",
        "--print-url prints the dashboard URL",
    )


def test_in_ui_quit() -> None:
    print("in-UI stop: POST /quit shuts the server down (no terminal needed):")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(_SERVE), "--port", str(port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
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
        check(up, "server came up on the fixed port")

        acked = None
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/quit", method="POST"
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                acked = json.loads(resp.read().decode()).get("stopped") is True
        except Exception:
            acked = None  # the server may drop the conn as it exits - tolerated

        code = None
        with contextlib.suppress(subprocess.TimeoutExpired):
            code = proc.wait(timeout=6)
        check(code == 0, f"server exits cleanly after POST /quit (code={code})")
        if acked is not None:
            check(acked, "/quit acked {stopped: true} before exiting")
    finally:
        if proc.poll() is None:
            proc.terminate()


def test_port_in_use() -> None:
    print("port-safety: a second start on a live port exits cleanly (no traceback):")
    port = _free_port()
    srv = socket.socket()
    srv.bind(("127.0.0.1", port))
    srv.listen()
    try:
        out = subprocess.run(
            [sys.executable, str(_SERVE), "--port", str(port)],
            capture_output=True, text=True, timeout=30,
        )
        combined = (out.stdout + out.stderr).lower()
        check(out.returncode == 1, f"exit 1 on port-in-use (got {out.returncode})")
        check("already running" in combined, "clean 'already running' message shown")
        check("traceback" not in combined, "no traceback leaked to the operator")
    finally:
        srv.close()


if __name__ == "__main__":
    test_port_ssot()
    test_in_ui_quit()
    test_port_in_use()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
