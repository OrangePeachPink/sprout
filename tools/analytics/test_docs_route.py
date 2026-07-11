"""#808 — serve.py's traversal-guarded /docs static route, so the Diagnostics
front-door links (#758) resolve instead of 404. Read-only, localhost, confined to
the repo docs/ tree (`..` rejected).
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
from serve import docs_content_type, resolve_docs_path

_HERE = Path(__file__).resolve().parent
_SERVE = _HERE / "serve.py"


# --------------------------------------------------------------------------- #
# traversal guard (the security-critical core) — pure, no server
# --------------------------------------------------------------------------- #
def test_resolves_the_front_door_files() -> None:
    readme = resolve_docs_path("README.md")
    assert readme is not None and readme.is_file() and readme.name == "README.md"
    lib = resolve_docs_path("design/Sprout Design Library.dc.html")
    assert lib is not None and lib.is_file() and lib.suffix == ".html"


def test_rejects_parent_traversal_even_to_a_real_file() -> None:
    # serve.py is a real file, but it lives OUTSIDE docs/ — the guard must block it
    assert resolve_docs_path("../tools/analytics/serve.py") is None
    assert resolve_docs_path("../../tools/analytics/serve.py") is None
    assert (
        resolve_docs_path("../README.md") is None
    )  # the repo-root README, outside docs


def test_absolute_and_missing_are_none() -> None:
    assert resolve_docs_path("/etc/passwd") is None  # lstrip'd, scoped, not a file
    assert resolve_docs_path("nope/missing.md") is None


def test_content_types() -> None:
    assert docs_content_type("README.md") == "text/plain; charset=utf-8"
    assert (
        docs_content_type("Sprout Design Library.dc.html") == "text/html; charset=utf-8"
    )
    assert docs_content_type("support.js").startswith("application/javascript")
    assert docs_content_type("thumb.png") == "image/png"
    assert docs_content_type("weird.xyz") == "text/plain; charset=utf-8"  # safe default


# --------------------------------------------------------------------------- #
# integration — the live route answers the front-door links + blocks traversal
# --------------------------------------------------------------------------- #
def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _status(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def test_docs_route_serves_and_guards_live() -> None:
    port = _free_port()
    proc = subprocess.Popen(
        # --no-autostart (#872): docs-route test — don't probe serial/fleet on launch
        [sys.executable, str(_SERVE), "--port", str(port), "--no-autostart"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        up = False
        for _ in range(80):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    up = True
                    break
            except OSError:
                time.sleep(0.1)
        assert up, "server came up"
        base = f"http://127.0.0.1:{port}"
        # the two front-door links resolve (AC1/AC2)
        assert _status(f"{base}/docs/README.md") == 200
        assert _status(f"{base}/docs/design/Sprout%20Design%20Library.dc.html") == 200
        # traversal rejected (AC3) — not a 200, never leaks a file outside docs/
        assert _status(f"{base}/docs/../tools/analytics/serve.py") in (403, 404)
    finally:
        proc.terminate()
        with __import__("contextlib").suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=6)
        if proc.poll() is None:
            proc.kill()
