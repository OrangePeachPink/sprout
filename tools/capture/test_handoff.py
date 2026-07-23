#!/usr/bin/env python3
"""Tests for the Monitor->Experiment handoff (#129), with fake controllers (no device).

python tools/capture/test_handoff.py
"""

from __future__ import annotations

import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.capture import handoff  # noqa: E402

_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def _wait(pred, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.01)
    return False


class FakeMonitor:
    def __init__(self, *, running: bool = False, port: str | None = None) -> None:
        self._running = running
        self._port = port
        self.stops = 0
        self.starts = 0
        self.resume_port: str | None = None

    def status(self) -> dict:
        return {
            "state": "running" if self._running else "stopped",
            "port": self._port if self._running else None,
        }

    def stop(self) -> dict:
        self._running = False
        self.stops += 1
        return self.status()

    def start(self, *, port: str | None = None) -> dict:
        self._running = True
        self._port = port
        self.starts += 1
        self.resume_port = port
        return self.status()


class FakeCapture:
    def __init__(self, running_polls: int = 2) -> None:
        self._polls = running_polls
        self.started = False

    def start(self, **kw) -> dict:
        self.started = True
        return {"state": "running", "experiment_id": "x"}

    def status(self) -> dict:
        if self._polls > 0:
            self._polls -= 1
            return {"state": "running"}
        return {"state": "done"}


def test_serial_handoff() -> None:
    print("handoff: serial start while logging -> stop, run, then resume:")
    mon = FakeMonitor(running=True, port="COM6")
    cap = FakeCapture(running_polls=2)
    result = handoff.start_experiment(
        mon, cap, source="serial", port="COM6", poll_s=0.02
    )
    check(mon.stops == 1, "monitor stopped for the handoff")
    check(cap.started, "experiment started")
    check(result.get("handoff") is True, "handoff flagged in the result")
    check(_wait(lambda: mon.starts == 1, 3.0), "monitor resumed after the test")
    check(mon.resume_port == "COM6", "logging resumed on the same port")


def test_no_handoff_when_idle() -> None:
    print("handoff: serial start with the monitor stopped -> no handoff:")
    mon = FakeMonitor(running=False)
    cap = FakeCapture(running_polls=1)
    result = handoff.start_experiment(
        mon, cap, source="serial", port="COM6", poll_s=0.02
    )
    check(mon.stops == 0, "monitor not stopped (it wasn't running)")
    check(result.get("handoff") is False, "no handoff flag")
    time.sleep(0.1)
    check(mon.starts == 0, "monitor not (re)started")


def test_synthetic_no_handoff() -> None:
    print("handoff: a synthetic start never touches the monitor:")
    mon = FakeMonitor(running=True, port="COM6")
    cap = FakeCapture(running_polls=1)
    result = handoff.start_experiment(
        mon, cap, source="synthetic", port=None, poll_s=0.02
    )
    check(mon.stops == 0, "monitor untouched for a synthetic capture")
    check(result.get("handoff") is False, "no handoff for synthetic")
    time.sleep(0.1)
    check(mon.starts == 0, "monitor still logging (not restarted)")


def test_resume_on_failed_start() -> None:
    print("handoff: if the experiment fails to start, logging is put back:")
    mon = FakeMonitor(running=True, port="COM6")

    class FailCap:
        def start(self, **kw) -> dict:
            raise RuntimeError("device busy")

        def status(self) -> dict:
            return {"state": "stopped"}

    raised = False
    try:
        handoff.start_experiment(
            mon, FailCap(), source="serial", port="COM6", poll_s=0.02
        )
    except RuntimeError:
        raised = True
    check(raised, "the start error propagated")
    check(mon.starts == 1 and mon.resume_port == "COM6", "monitor restored")


if __name__ == "__main__":
    test_serial_handoff()
    test_no_handoff_when_idle()
    test_synthetic_no_handoff()
    test_resume_on_failed_start()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
