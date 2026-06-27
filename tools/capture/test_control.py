#!/usr/bin/env python3
"""Standalone tests for the capture control plane (#66).

    python tools/capture/test_control.py

Exercises the real seam: CaptureController launches `experiment_capture.py` as a
child process (synthetic source, no device), and we drive start / status / stop,
single-flight, auto-stop vs operator-stop, and input sanitization.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import control  # noqa: E402
import serial_lock  # noqa: E402

_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def raises(fn, exc, msg: str) -> None:
    try:
        fn()
    except exc:
        check(True, msg)
    except Exception as other:
        check(False, f"{msg} (raised {type(other).__name__})")
    else:
        check(False, f"{msg} (did not raise)")


def _await(pred, timeout: float, step: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(step)
    return False


def test_start_status_stop() -> None:
    print("start -> running -> file written -> operator stop -> clean:")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_"))
    try:
        c = control.CaptureController(experiments_dir=tmp)
        r = c.start(subject="common-cup", rate_s=0.2, duration_s=120)
        check(r["state"] == "running" and r.get("pid"), "start launches a capture")
        check(c.status()["state"] == "running", "status reports running")
        f = tmp / r["experiment_id"] / f"{r['experiment_id']}.csv"
        check(_await(f.exists, 6.0), "capture process writes its isolated file")
        st = c.stop()
        check(st["state"] in ("done", "error"), "stop -> process exited")
        check(st.get("stopped_by") == "operator", "operator stop honored")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_single_flight() -> None:
    print("single-flight - a second start while running is refused:")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_sf_"))
    try:
        c = control.CaptureController(experiments_dir=tmp)
        c.start(subject="a", rate_s=0.3, duration_s=120)
        raises(
            lambda: c.start(subject="b", rate_s=0.3, duration_s=120),
            control.ControlError,
            "second start -> ControlError (already running)",
        )
        c.stop()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_auto_stop() -> None:
    print("fail-safe auto-stop - a bounded capture ends itself:")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_as_"))
    try:
        c = control.CaptureController(experiments_dir=tmp)
        c.start(subject="brief", rate_s=0.2, duration_s=2)
        ended = _await(lambda: c.status()["state"] != "running", 8.0)
        st = c.status()
        check(ended and st["state"] == "done", "auto-stopped to 'done'")
        check(st.get("stopped_by") == "duration", "manifest: auto-stopped")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sanitization() -> None:
    print("input validation - traversal / bad chars / out-of-range refused:")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_san_"))
    try:
        c = control.CaptureController(experiments_dir=tmp)
        bad_id = "../evil"
        raises(
            lambda: c.start(subject="x", rate_s=1, duration_s=5, experiment_id=bad_id),
            control.ControlError,
            "path-traversal experiment_id refused",
        )
        raises(
            lambda: c.start(subject="!!!", rate_s=1, duration_s=10),
            control.ControlError,
            "all-punctuation subject (empty slug) refused",
        )
        raises(
            lambda: c.start(subject="ok", rate_s=99999, duration_s=10),
            control.ControlError,
            "out-of-range rate refused",
        )
        check(c.status()["state"] == "idle", "nothing was launched (still idle)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_slug_and_title() -> None:
    print("human subjects are slugified, the title is preserved (#150):")
    check(
        control._slugify("open bench", "subject") == "open_bench",
        "'open bench' -> 'open_bench'",
    )
    check(
        control._slugify("common-cup", "subject") == "common-cup",
        "an already-valid token is unchanged",
    )
    check(control._slugify("a/b c", "subject") == "a_b_c", "slashes + spaces -> '_'")
    check(
        control._subject_title("open bench", "subject") == "open bench",
        "the human title keeps its spaces",
    )
    raises(
        lambda: control._slugify("...", "subject"),
        control.ControlError,
        "all-punctuation -> empty slug refused",
    )
    raises(
        lambda: control._subject_title("a,b", "subject"),
        control.ControlError,
        "comma in title refused",
    )


def test_live_rows() -> None:
    print("status reports a live, climbing row count while running (#162):")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_rows_"))
    try:
        c = control.CaptureController(experiments_dir=tmp)
        c.start(subject="liverows", rate_s=0.1, duration_s=5)
        got = _await(
            lambda: (
                isinstance(c.status().get("rows"), int)
                and c.status().get("rows", 0) >= 1
            ),
            4.0,
        )
        st = c.status()
        check(got and st.get("state") == "running", "running status carries rows >= 1")
        check(isinstance(st.get("rows"), int), "'rows' is an int while running")
        c.stop()
        check(
            "rows" not in c.status() or c.status().get("state") != "running",
            "stopped -> no longer reports a running row count",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_stop_idle() -> None:
    print("stop when idle is a safe no-op:")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_si_"))
    try:
        c = control.CaptureController(experiments_dir=tmp)
        check(c.stop()["state"] == "idle", "stop with nothing running -> idle")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_serial_gating() -> None:
    print("serial source: needs a port; refused while the port is locked:")
    tmp = Path(tempfile.mkdtemp(prefix="ctl_ser_"))
    lockdir = Path(tempfile.mkdtemp(prefix="ctl_serlk_"))
    try:
        c = control.CaptureController(experiments_dir=tmp, lock_dir=lockdir)
        raises(
            lambda: c.start(subject="x", rate_s=1, duration_s=5, source="serial"),
            control.ControlError,
            "serial without a port refused",
        )
        serial_lock.write_lock("COM6", "monitor", lock_dir=lockdir)  # a live owner
        raises(
            lambda: c.start(
                subject="x", rate_s=1, duration_s=5, source="serial", port="COM6"
            ),
            control.ControlError,
            "serial refused while the port is locked",
        )
        check(c.status()["state"] == "idle", "nothing launched while refused")
        serial_lock.clear_lock(lockdir)
        c.start(subject="x", rate_s=1, duration_s=5, source="serial", port="COM_NX_99")
        ended = _await(lambda: c.status()["state"] != "running", 8.0)
        check(ended and c.status()["state"] == "error", "no-device launch -> error")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(lockdir, ignore_errors=True)


if __name__ == "__main__":
    test_start_status_stop()
    test_single_flight()
    test_auto_stop()
    test_sanitization()
    test_slug_and_title()
    test_live_rows()
    test_stop_idle()
    test_serial_gating()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
