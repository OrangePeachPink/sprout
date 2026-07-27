#!/usr/bin/env python3
"""Tests for serial_lock owner status + stale-only clear (#330).

python tools/capture/test_serial_lock.py
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.capture import serial_lock  # noqa: E402

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
        assert not (st["present"] or st["live"] or st["stale"]), st
        check(True, "absent lock -> present/live/stale all False")
        assert "No one" in st["explain"], st
        check(True, "the free port still says so in words (#1554)")
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


# --------------------------------------------------------------------------- #
# #1554 — the lock explains itself: WHICH holder, and what to do about it
# --------------------------------------------------------------------------- #
def test_lock_records_which_checkout_started_the_holder() -> None:
    print("#1554: the lock names the origin checkout, not just a pid:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        rec = serial_lock.write_lock("COM4", "monitor", lock_dir=d, pid=os.getpid())
        assert rec["origin"] == Path.cwd().name, rec
        check(True, "origin recorded = the invoking checkout's directory name")
        # the privacy fence: a BASENAME, never a full path. This string is rendered
        # in-app and lands in screenshots; a full path carries the home directory.
        assert "/" not in rec["origin"] and "\\" not in rec["origin"], rec
        check(
            True, "origin is a basename — no home directory in a screenshottable line"
        )
        assert serial_lock.owner_status(lock_dir=d)["origin"] == rec["origin"]
        check(True, "origin surfaced to the UI")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_live_holder_is_named_and_the_advice_is_stop_that_one() -> None:
    print("#1554: a live holder's sentence names it and says stop THAT process:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM4", "monitor", lock_dir=d, pid=os.getpid())
        say = serial_lock.owner_status(lock_dir=d)["explain"]
        assert "monitor" in say and str(os.getpid()) in say and "COM4" in say, say
        assert Path.cwd().name in say, say
        check(True, "the sentence carries mode + pid + port + origin")
        # The bench failure was doing the wrong thing: clearing the marker looks like
        # the fix and isn't — the port stays held and a second opener resets the board.
        assert "clearing the marker would not release it" in say, say
        check(True, "live sentence steers away from the clear button")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_stale_marker_says_the_port_is_already_free() -> None:
    print("#1554: a stale marker's sentence is a different sentence:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM4", "monitor", lock_dir=d, pid=_DEAD_PID)
        say = serial_lock.owner_status(lock_dir=d)["explain"]
        assert "already free" in say and "Safe to clear" in say, say
        check(True, "stale sentence: the port is free, clearing is safe")
        assert "Stop that one" not in say, say
        check(True, "stale sentence does NOT tell her to hunt a process that's gone")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_a_lock_written_before_1554_degrades_honestly() -> None:
    print("#1554: a lock with no origin says less, never guesses (ADR-0028):")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        # exactly the pre-#1554 record shape — an older Sprout could still be running
        # when this code reads its marker.
        (d / serial_lock.LOCK_NAME).write_text(
            '{"pid": 4242, "mode": "monitor", "port": "COM4"}', encoding="utf-8"
        )
        st = serial_lock.owner_status(lock_dir=d)
        assert st["origin"] is None, st
        check(True, "missing origin -> None, not a guess at which checkout")
        assert "started from" not in st["explain"], st["explain"]
        check(True, "the sentence drops the clause rather than inventing one")
        assert "4242" in st["explain"] and "COM4" in st["explain"], st["explain"]
        check(True, "what IS known is still said")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_the_refusal_to_clear_a_live_lock_now_names_the_holder() -> None:
    print("#1554: clear_if_stale still refuses a live owner — and explains which:")
    d = Path(tempfile.mkdtemp(prefix="lk_"))
    try:
        serial_lock.write_lock("COM4", "monitor", lock_dir=d, pid=os.getpid())
        res = serial_lock.clear_if_stale(lock_dir=d)
        assert res["cleared"] is False, res
        assert serial_lock.read_lock(lock_dir=d) is not None, "live lock must remain"
        check(True, "the safety is unchanged: a held port is never freed")
        assert str(os.getpid()) in res["reason"], res
        check(True, "the refusal names the holder instead of saying 'owner is live'")
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    test_owner_status_none()
    test_owner_status_live()
    test_owner_status_stale()
    test_clear_if_stale_removes_stale()
    test_clear_if_stale_refuses_live()
    test_clear_if_stale_no_lock()
    test_lock_records_which_checkout_started_the_holder()
    test_a_live_holder_is_named_and_the_advice_is_stop_that_one()
    test_a_stale_marker_says_the_port_is_already_free()
    test_a_lock_written_before_1554_degrades_honestly()
    test_the_refusal_to_clear_a_live_lock_now_names_the_holder()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
