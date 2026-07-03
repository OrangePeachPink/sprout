"""Tests for the one-click Fleet Monitor control plane (#588, ADR-0014).

FleetController mirrors MonitorController (single-flight, honest refusals);
collection_control is the one-action policy layer - every degrade path the
issue names is pinned: no COM port != error, no registered fleet != error,
BOTH absent -> an honest error (one action that collected nothing must never
look like success).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collection_control import CollectionError, start_all, status_all, stop_all
from fleet_control import FleetController, FleetError

# A tiny long-running stand-in for fleet_logger.py, so controller tests spawn a
# real process without polling anything.
_SLEEPER = "import time\ntime.sleep(60)\n"


def _sleeper(tmp_path: Path) -> Path:
    p = tmp_path / "sleeper.py"
    p.write_text(_SLEEPER, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# FleetController
# --------------------------------------------------------------------------- #


def test_start_stop_status_lifecycle(tmp_path: Path) -> None:
    fc = FleetController(fleet_py=_sleeper(tmp_path), served_count=lambda: 2)
    assert fc.status() == {"state": "stopped", "devices": 0}
    st = fc.start()
    try:
        assert st == {"state": "running", "devices": 2}
        assert fc.status()["state"] == "running"
    finally:
        assert fc.stop() == {"state": "stopped", "devices": 0}


def test_single_flight_refuses_a_second_start(tmp_path: Path) -> None:
    fc = FleetController(fleet_py=_sleeper(tmp_path), served_count=lambda: 1)
    fc.start()
    try:
        raised = False
        try:
            fc.start()
        except FleetError as e:
            raised = "already running" in str(e)
        assert raised
    finally:
        fc.stop()


def test_no_registered_devices_refuses_with_a_clear_reason(tmp_path: Path) -> None:
    fc = FleetController(fleet_py=_sleeper(tmp_path), served_count=lambda: 0)
    raised = ""
    try:
        fc.start()
    except FleetError as e:
        raised = str(e)
    assert "no registered fleet devices" in raised
    assert fc.status()["state"] == "stopped"  # nothing spawned


def test_stop_when_already_stopped_is_a_noop(tmp_path: Path) -> None:
    fc = FleetController(fleet_py=_sleeper(tmp_path), served_count=lambda: 1)
    assert fc.stop() == {"state": "stopped", "devices": 0}


def test_crashed_child_reads_stopped(tmp_path: Path) -> None:
    crasher = tmp_path / "crash.py"
    crasher.write_text("raise SystemExit(1)\n", encoding="utf-8")
    fc = FleetController(fleet_py=crasher, served_count=lambda: 1)
    fc.start()
    for _ in range(50):  # the child exits almost immediately
        if fc.status()["state"] == "stopped":
            break
        time.sleep(0.1)
    assert fc.status()["state"] == "stopped"  # honest: not "running" forever


# --------------------------------------------------------------------------- #
# collection_control: the one-action policy matrix
# --------------------------------------------------------------------------- #


class _FakeMon:
    def __init__(self, *, fail: str | None = None) -> None:
        self.fail = fail
        self.running = False

    def start(self, *, port=None):
        if self.fail:
            raise RuntimeError(self.fail)
        self.running = True
        return {"state": "running", "port": port}

    def stop(self):
        self.running = False
        return {"state": "stopped", "port": None}

    def status(self):
        return {"state": "running" if self.running else "stopped"}


class _FakeFleet(_FakeMon):
    def start(self):  # fleet takes no port
        if self.fail:
            raise RuntimeError(self.fail)
        self.running = True
        return {"state": "running", "devices": 2}


def test_both_paths_present_both_start() -> None:
    out = start_all(_FakeMon(), _FakeFleet(), port="COM6", port_present=lambda p: True)
    assert out["monitor"]["state"] == "running"
    assert out["fleet"]["state"] == "running"
    assert out["collecting"] is True


def test_no_serial_port_skips_monitor_not_error() -> None:
    out = start_all(_FakeMon(), _FakeFleet(), port=None, port_present=lambda p: False)
    assert out["monitor"]["state"] == "skipped"
    assert "no serial port" in out["monitor"]["reason"]
    assert out["fleet"]["state"] == "running"  # WiFi-only install: first-class
    assert out["collecting"] is True


def test_no_fleet_skips_fleet_not_error() -> None:
    out = start_all(
        _FakeMon(),
        _FakeFleet(fail="no registered fleet devices - nothing to poll"),
        port="COM6",
        port_present=lambda p: True,
    )
    assert out["fleet"]["state"] == "skipped"
    assert out["monitor"]["state"] == "running"  # tethered-only: first-class
    assert out["collecting"] is True


def test_both_absent_is_an_honest_error() -> None:
    raised = ""
    try:
        start_all(
            _FakeMon(),
            _FakeFleet(fail="no registered fleet devices"),
            port=None,
            port_present=lambda p: False,
        )
    except CollectionError as e:
        raised = str(e)
    assert "nothing to collect" in raised
    assert "no serial port" in raised and "no registered fleet" in raised


def test_already_running_counts_as_collecting() -> None:
    # pressing Start twice must not error out - the operator's intent is met
    out = start_all(
        _FakeMon(fail="monitor is already running"),
        _FakeFleet(fail="fleet logger is already running"),
        port="COM6",
        port_present=lambda p: True,
    )
    assert out["collecting"] is True


def test_stop_all_and_status_all() -> None:
    mon, fleet = _FakeMon(), _FakeFleet()
    start_all(mon, fleet, port="COM6", port_present=lambda p: True)
    st = status_all(mon, fleet)
    assert st["collecting"] is True
    out = stop_all(mon, fleet)
    assert out["collecting"] is False
    assert status_all(mon, fleet)["collecting"] is False
