#!/usr/bin/env python3
"""Tests for serial_lock owner status + stale-only clear (#330).

python tools/capture/test_serial_lock.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import serial_lock  # noqa: E402

_FAILS: list[str] = []
# A pid no live process will plausibly have — the "crashed owner" stand-in.
_DEAD_PID = 2_147_483_646


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def test_owner_status_none() -> None:
    print("owner_status: no lock -> not present:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        st = serial_lock.owner_status(lock_dir=d)
        assert st == {"present": False, "live": False, "stale": False}, st
        check(True, "absent lock -> present/live/stale all False")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_owner_status_live() -> None:
    print("owner_status: a lock held by this (live) process is live, not stale:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM6", "monitor", lock_dir=d, pid=os.getpid())
        st = serial_lock.owner_status(lock_dir=d)
        assert st["present"] and st["live"] and not st["stale"], st
        assert st["mode"] == "monitor" and st["port"] == "COM6", st
        check(True, "live owner: present+live, fields surfaced (pid/mode/port/opened)")
        assert "opened_utc" in st, st
        check(True, "opened_utc surfaced for the UI")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_owner_status_stale() -> None:
    print("owner_status: a lock from a dead pid is stale:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM6", "monitor", lock_dir=d, pid=_DEAD_PID)
        st = serial_lock.owner_status(lock_dir=d)
        assert st["present"] and not st["live"] and st["stale"], st
        assert st["pid"] == _DEAD_PID, st
        check(True, "dead-pid owner: present+stale, not live")
        # current_owner() still ignores it (so it never blocks a start)
        assert serial_lock.current_owner(lock_dir=d) is None, "stale must not block"
        check(True, "current_owner() ignores the stale lock")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_clear_if_stale_removes_stale() -> None:
    print("clear_if_stale: removes a dead-owner marker:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM6", "monitor", lock_dir=d, pid=_DEAD_PID)
        res = serial_lock.clear_if_stale(lock_dir=d)
        assert res["cleared"] is True, res
        assert serial_lock.read_lock(lock_dir=d) is None, "marker should be gone"
        check(True, "stale marker cleared, file removed")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_clear_if_stale_refuses_live() -> None:
    print("clear_if_stale: refuses to free a live-owned port (the safety):")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM6", "experiment", lock_dir=d, pid=os.getpid())
        res = serial_lock.clear_if_stale(lock_dir=d)
        assert res["cleared"] is False, res
        assert serial_lock.read_lock(lock_dir=d) is not None, "live lock must remain"
        check(True, "live marker preserved (never free a held port)")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_clear_if_stale_no_lock() -> None:
    print("clear_if_stale: a no-op when there's nothing to clear:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        res = serial_lock.clear_if_stale(lock_dir=d)
        assert res["cleared"] is False, res
        check(True, "no lock -> cleared False, no error")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_owner_status_none()
    test_owner_status_live()
    test_owner_status_stale()
    test_clear_if_stale_removes_stale()
    test_clear_if_stale_refuses_live()
    test_clear_if_stale_no_lock()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
