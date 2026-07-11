"""#872 verify-then-assert auto-start of collection at server launch.

The honest promise of Monitor: the app logs the moment it launches, no operator click.
The maintainer lost ~19h of data because collection didn't come back after a restart and
died silently. Auto-start fixes the resume, and verify-then-assert makes it honest — it
confirms collection is *actually* running (status), not just that start() returned, and
says so loudly either way. Never a silent DEVNULL death.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serve import _auto_start_collection


class _FakeCtl:
    """A stand-in monitor/fleet controller: `start()` reports one state, `status()`
    another — so a test can make start() lie (report running) while status() tells the
    truth (stopped), exercising the verify-then-assert catch."""

    def __init__(self, start_state, status_state) -> None:
        self._start = start_state
        self._status = status_state
        self.stopped = False

    def start(self, port=None):
        if isinstance(self._start, Exception):
            raise self._start
        return {"state": self._start}

    def status(self):
        return {"state": self._status}

    def stop(self):
        self.stopped = True
        return {"state": "stopped"}


_NO_SERIAL = (lambda _p: False,)  # port_present -> False (WiFi-only rig, no COM port)


def test_autostart_announces_success_when_really_collecting() -> None:
    mon = _FakeCtl("stopped", "stopped")  # serial skipped (no port)
    fleet = _FakeCtl("running", "running")
    lines: list[str] = []
    _auto_start_collection(mon, fleet, port_present=_NO_SERIAL[0], log=lines.append)
    blob = " ".join(lines)
    assert "auto-started" in blob and "logging" in blob
    assert "fleet" in blob  # names what's actually running


def test_autostart_is_honest_empty_when_nothing_reachable() -> None:
    # no serial port + no fleet -> start_all raises CollectionError -> honest "nothing",
    # never a fake success (the #872 anti-pattern that masked the outage).
    mon = _FakeCtl("stopped", "stopped")
    fleet = _FakeCtl(RuntimeError("no registered devices"), "stopped")
    lines: list[str] = []
    _auto_start_collection(mon, fleet, port_present=_NO_SERIAL[0], log=lines.append)
    assert any("nothing to log yet" in line for line in lines)


def test_verify_then_assert_catches_a_start_that_did_not_take() -> None:
    # the whole point: start() SAYS running, but status() reveals it's stopped — the
    # verify step catches the lie and shouts, instead of asserting a phantom recording.
    mon = _FakeCtl("stopped", "stopped")
    fleet = _FakeCtl("running", "stopped")  # start lies, status tells the truth
    lines: list[str] = []
    _auto_start_collection(mon, fleet, port_present=_NO_SERIAL[0], log=lines.append)
    assert any("NOT running" in line for line in lines)
    assert not any("auto-started" in line for line in lines)  # never claims success


def test_autostart_reports_a_start_exception_loudly() -> None:
    mon = _FakeCtl("stopped", "stopped")

    class _Boom:
        def start(self):
            raise ValueError("fleet controller exploded")

        def status(self):
            return {"state": "stopped"}

    lines: list[str] = []
    _auto_start_collection(mon, _Boom(), port_present=_NO_SERIAL[0], log=lines.append)
    # start_all wraps a fleet-start exception into a skipped reason, so the net
    # effect is
    # "nothing collecting" -> the honest-empty message (still loud, never silent)
    assert any("nothing to log yet" in line or "failed" in line for line in lines)


if __name__ == "__main__":
    for fn in (
        test_autostart_announces_success_when_really_collecting,
        test_autostart_is_honest_empty_when_nothing_reachable,
        test_verify_then_assert_catches_a_start_that_did_not_take,
        test_autostart_reports_a_start_exception_loudly,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
