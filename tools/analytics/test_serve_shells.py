"""#1173 (the #1160 cert follow-up) — route coverage for the two front doors.

`GET /` is the Home shell and `GET /classic` is the Workbench shell. Both are #1018
FAST shells: they render the template and hydrate lazily (Home from /cards.json, the
Workbench from /data.json) — they never run the analytics pipeline inline, so a fresh
raw value logged to disk must NOT appear in the served HTML (the "no context blob"
contract, and the proof the pipeline didn't block the door). At zero segments, `/`
falls back to the honest empty-state page.

End-to-end against a real running server (the routing + the _has_segments gate are the
point — a pure-function test would miss both). Mirrors test_serve_empty_state's harness.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

_SERVE = Path(__file__).resolve().parent / "serve.py"

# A distinctive raw value: it rides the log to disk but must never surface in a SHELL
# (shells don't parse). If it appears, the pipeline ran inline — the #1018 regression.
_CANARY_RAW = "424242"
_HEADER = "# fw=0.7.0  git=test123  run=t\n"
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_ROW = (
    "plants.soil,2026-06-28T00:00:30.000Z,2026-06-28T00:00:30.000,"
    f"sess1,s1,{_CANARY_RAW},OK,level=well watered;gpio=36\n"
)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _boot(inputs_dir: Path) -> tuple[subprocess.Popen, int]:
    """Launch serve.py against ``inputs_dir`` on a free port; wait until it accepts a
    socket. --no-autostart keeps it hermetic (no serial/fleet probing, #872)."""
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_SERVE),
            str(inputs_dir),
            "--port",
            str(port),
            "--no-autostart",
        ],
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


def _get(port: int, path: str) -> tuple[int, str, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, body, time.perf_counter() - t0


def _with_data(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    (d / "a.csv").write_text(_HEADER + _COLS + _ROW, encoding="utf-8")
    return d


def test_root_serves_the_home_shell_that_hydrates_lazily(tmp_path: Path) -> None:
    proc, port = _boot(_with_data(tmp_path))
    try:
        status, body, _ = _get(port, "/")
        assert status == 200
        assert "Sprout — home" in body  # the Home, not the Workbench
        assert "cards.json" in body  # the hydrate hook — it fetches its own data
        assert _CANARY_RAW not in body  # NO context blob — the shell never inlined data
        assert "function renderRegistry(" not in body  # Home is not the Workbench
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_classic_serves_the_workbench_shell_fast(tmp_path: Path) -> None:
    proc, port = _boot(_with_data(tmp_path))
    try:
        status, body, dt = _get(port, "/classic")
        assert status == 200
        assert 'data-r="7d"' in body  # the Workbench range selector — it IS Classic
        assert "function renderRegistry(" in body  # the Workbench app shell
        assert _CANARY_RAW not in body  # #1018: SHELL only — no inline pipeline run
        assert dt < 8.0  # fast: a shell render, never the ~10s pipeline build
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_root_at_zero_segments_is_the_honest_empty_state(tmp_path: Path) -> None:
    # a genuinely fresh checkout (empty dir, no *.csv) -> the empty-state page, never a
    # 500 and never a data-pretending shell (the _has_segments gate, #543/#1018).
    empty = tmp_path / "empty"
    empty.mkdir()
    proc, port = _boot(empty)
    try:
        status, body, _ = _get(port, "/")
        assert status == 200
        assert "fresh checkout" in body  # the honest first-run copy
        assert "Sprout — home" not in body  # not the hydrating Home yet
    finally:
        proc.terminate()
        proc.wait(timeout=5)
