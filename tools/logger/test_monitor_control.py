#!/usr/bin/env python3
"""Tests for MonitorController (#128). Uses a fake 'logger' that just sleeps, so
start/stop + the serial mutex are exercised without a real device.

    python tools/logger/test_monitor_control.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import monitor_control as mc  # noqa: E402

_CAP = _HERE.parents[0] / "capture"
if str(_CAP) not in sys.path:
    sys.path.insert(0, str(_CAP))
import serial_lock  # noqa: E402

_FAILS: list[str] = []
_FAKE_LOGGER = "import time\nwhile True:\n    time.sleep(0.2)\n"


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def _fake_logger(tmp: Path) -> Path:
    p = tmp / "fake_logger.py"
    p.write_text(_FAKE_LOGGER, encoding="utf-8")
    return p


def test_start_stop() -> None:
    print("monitor: start -> running, single-flight, stop -> stopped:")
    tmp = Path(tempfile.mkdtemp(prefix="mon_"))
    lockdir = Path(tempfile.mkdtemp(prefix="monlk_"))
    try:
        c = mc.MonitorController(logger_py=_fake_logger(tmp), lock_dir=lockdir)
        check(c.start(port="COM_FAKE")["state"] == "running", "start -> running")
        try:
            c.start()
            check(False, "single-flight: a second start should be refused")
        except mc.MonitorError:
            check(True, "single-flight: a second start is refused")
        check(c.stop()["state"] == "stopped", "stop -> stopped")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(lockdir, ignore_errors=True)


def test_mutex() -> None:
    print("monitor: refuses to start while an experiment holds the port:")
    tmp = Path(tempfile.mkdtemp(prefix="mon2_"))
    lockdir = Path(tempfile.mkdtemp(prefix="monlk2_"))
    try:
        serial_lock.write_lock("COM6", "experiment", lock_dir=lockdir)
        c = mc.MonitorController(logger_py=_fake_logger(tmp), lock_dir=lockdir)
        try:
            c.start(port="COM6")
            check(False, "should refuse while an experiment holds the port")
        except mc.MonitorError:
            check(True, "refused while an experiment holds the port")
        check(c.status()["state"] == "stopped", "nothing was launched")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(lockdir, ignore_errors=True)


def test_stop_clears_monitor_marker() -> None:
    print("monitor: stop clears a monitor-owned marker (Windows hard-kill case, #330):")
    tmp = Path(tempfile.mkdtemp(prefix="mon3_"))
    lockdir = Path(tempfile.mkdtemp(prefix="monlk3_"))
    try:
        c = mc.MonitorController(logger_py=_fake_logger(tmp), lock_dir=lockdir)
        c.start(port="COM_FAKE")
        # The real logger child writes this on open; the fake one doesn't, so stand in
        # for it — terminate() can't run the child's clean-stop release on Windows.
        serial_lock.write_lock("COM_FAKE", "monitor", lock_dir=lockdir)
        c.stop()
        remaining = serial_lock.read_lock(lock_dir=lockdir)
        assert remaining is None, f"monitor marker not cleared: {remaining}"
        check(True, "stop() cleared the monitor marker")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(lockdir, ignore_errors=True)


def test_stop_preserves_experiment_marker() -> None:
    print("monitor: stop never clears an experiment's marker (only its own):")
    tmp = Path(tempfile.mkdtemp(prefix="mon4_"))
    lockdir = Path(tempfile.mkdtemp(prefix="monlk4_"))
    try:
        c = mc.MonitorController(logger_py=_fake_logger(tmp), lock_dir=lockdir)
        c.start(port="COM_FAKE")
        serial_lock.write_lock("COM6", "experiment", lock_dir=lockdir)  # another lane's
        c.stop()
        lock = serial_lock.read_lock(lock_dir=lockdir)
        assert lock is not None and lock.get("mode") == "experiment", lock
        check(True, "experiment marker preserved through a monitor stop")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(lockdir, ignore_errors=True)


if __name__ == "__main__":
    test_start_stop()
    test_mutex()
    test_stop_clears_monitor_marker()
    test_stop_preserves_experiment_marker()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
