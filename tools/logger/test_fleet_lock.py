"""Tests for the fleet-logger singleton lock (#493 F2).

The contract: at most one fleet_logger writes to a logdir at a time. WiFi has no
COM-port mutex, so two pollers would interleave one CSV - this lock is the mutex.
Contention is exercised in-process with two separate ``FleetLock`` objects on one
dir: each ``os.open`` is a distinct file description, so the OS lock genuinely
contends between them (no subprocess needed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ANALYTICS = os.path.normpath(os.path.join(_HERE, "..", "analytics"))

from tools.analytics.device_registry import Registry  # noqa: E402
from tools.logger.fleet_lock import (  # noqa: E402
    FleetAlreadyRunning,
    FleetLock,
    incumbent,
    lock_path,
)
from tools.logger.fleet_logger import FleetLogger  # noqa: E402

# --------------------------------------------------------------------------- #
# the mutex itself
# --------------------------------------------------------------------------- #


def test_acquire_on_a_free_dir_succeeds(tmp_path: Path) -> None:
    lock = FleetLock(tmp_path)
    assert not lock.held
    lock.acquire()
    assert lock.held
    assert lock_path(tmp_path).exists()
    lock.release()
    assert not lock.held


def test_second_acquirer_is_refused_by_name(tmp_path: Path) -> None:
    first = FleetLock(tmp_path).acquire()
    try:
        with pytest.raises(FleetAlreadyRunning) as ei:
            FleetLock(tmp_path).acquire()
        # the refusal names the live incumbent (this very process) + why
        assert ei.value.pid == os.getpid()
        assert "#493" in str(ei.value)
    finally:
        first.release()


def test_release_frees_it_for_the_next_acquirer(tmp_path: Path) -> None:
    a = FleetLock(tmp_path).acquire()
    a.release()
    b = FleetLock(tmp_path)  # the stale file may linger; it must still acquire
    b.acquire()
    assert b.held
    b.release()


def test_acquire_is_idempotent(tmp_path: Path) -> None:
    lock = FleetLock(tmp_path)
    lock.acquire()
    lock.acquire()  # a second acquire on the SAME object is a no-op, not a lock-up
    assert lock.held
    lock.release()


def test_marker_is_readable_while_the_lock_is_held(tmp_path: Path) -> None:
    # the OS lock sits on a sentinel byte far past EOF; the {pid,...} marker at
    # offset 0 stays freely readable (F1 / the server card / sprout_processes).
    with FleetLock(tmp_path):
        raw = lock_path(tmp_path).read_text(encoding="utf-8")
        marker = json.loads(raw)
        assert marker["pid"] == os.getpid()
        assert marker["started_utc"].endswith("Z")


def test_context_manager_acquires_and_releases(tmp_path: Path) -> None:
    with FleetLock(tmp_path) as lock:
        assert lock.held
        with pytest.raises(FleetAlreadyRunning):
            FleetLock(tmp_path).acquire()
    # left the block -> released -> re-acquirable
    again = FleetLock(tmp_path).acquire()
    assert again.held
    again.release()


# --------------------------------------------------------------------------- #
# incumbent() - the read-only probe (no device reset, no port open)
# --------------------------------------------------------------------------- #


def test_incumbent_is_none_when_nothing_runs(tmp_path: Path) -> None:
    assert incumbent(tmp_path) is None  # no file at all


def test_incumbent_names_a_live_holder(tmp_path: Path) -> None:
    with FleetLock(tmp_path):
        who = incumbent(tmp_path)
        assert who is not None and who["pid"] == os.getpid()


def test_incumbent_is_none_for_a_stale_file(tmp_path: Path) -> None:
    # a lock file whose owner is gone (released) is re-acquirable -> reported free
    FleetLock(tmp_path).acquire().release()
    # simulate a crash-litter file the release() didn't remove
    lock_path(tmp_path).write_text('{"pid": 999999, "started_utc": "x"}', "utf-8")
    assert incumbent(tmp_path) is None


# --------------------------------------------------------------------------- #
# the gate in context: run() refuses a second poller instead of double-writing
# --------------------------------------------------------------------------- #


def test_run_refuses_when_the_lock_is_already_held(tmp_path: Path) -> None:
    held = FleetLock(tmp_path).acquire()
    try:
        logs: list[str] = []
        fl = FleetLogger(str(tmp_path), registry=Registry(devices=[]), log=logs.append)
        ran = fl.run(max_polls=1)
        assert ran is False  # refused
        assert fl.polls == 0  # never polled
        assert any("#493" in m for m in logs)  # said why, by name
        # and it wrote no archive segment (the whole point: no second writer)
        assert not list(tmp_path.glob("*.csv"))
    finally:
        held.release()


def test_run_acquires_and_releases_the_real_lock(tmp_path: Path) -> None:
    # a normal bounded run holds the lock for its duration, frees it after - so a
    # follow-on run succeeds (no self-deadlock, no leaked lock). An empty fleet
    # keeps this fast + deterministic; we only assert the lock lifecycle here.
    fl = FleetLogger(str(tmp_path), registry=Registry(devices=[]), log=str)
    assert fl.run(max_polls=1) is True
    assert incumbent(tmp_path) is None  # released after the run
    # and it can run again
    assert fl.run(max_polls=1) is True


def test_injected_lock_is_used(tmp_path: Path) -> None:
    calls: list[str] = []

    class _FakeLock:
        def acquire(self) -> None:
            calls.append("acquire")

        def release(self) -> None:
            calls.append("release")

    fl = FleetLogger(str(tmp_path), registry=Registry(devices=[]), log=str)
    fl.run(max_polls=1, lock=_FakeLock())
    assert calls == ["acquire", "release"]  # run() drives the injected lock
