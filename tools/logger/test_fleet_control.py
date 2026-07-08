"""Tests for the one-click Fleet Monitor control plane (#588, ADR-0014).

FleetController mirrors MonitorController (single-flight, honest refusals);
collection_control is the one-action policy layer - every degrade path the
issue names is pinned: no COM port != error, no registered fleet != error,
BOTH absent -> an honest error (one action that collected nothing must never
look like success).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collection_control import CollectionError, start_all, status_all, stop_all
from fleet_control import FleetController, FleetError, count_answering

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


_STOPPED = {"state": "stopped", "configured": 0, "answering": 0, "devices": 0}


def test_start_stop_status_lifecycle(tmp_path: Path) -> None:
    # answering_fn injected so the status shape is hermetic (no real logs/registry).
    fc = FleetController(
        fleet_py=_sleeper(tmp_path), served_count=lambda: 2, answering_fn=lambda: 2
    )
    assert fc.status() == _STOPPED
    st = fc.start()
    try:
        # all 2 configured answer -> configured == answering; `devices` back-compat.
        assert st == {
            "state": "running",
            "configured": 2,
            "answering": 2,
            "devices": 2,
        }
        assert fc.status()["state"] == "running"
    finally:
        assert fc.stop() == _STOPPED


def test_single_flight_refuses_a_second_start(tmp_path: Path) -> None:
    fc = FleetController(
        fleet_py=_sleeper(tmp_path), served_count=lambda: 1, answering_fn=lambda: 1
    )
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
    assert fc.stop() == _STOPPED


def test_crashed_child_reads_stopped(tmp_path: Path) -> None:
    crasher = tmp_path / "crash.py"
    crasher.write_text("raise SystemExit(1)\n", encoding="utf-8")
    fc = FleetController(
        fleet_py=crasher, served_count=lambda: 1, answering_fn=lambda: 1
    )
    fc.start()
    for _ in range(50):  # the child exits almost immediately
        if fc.status()["state"] == "stopped":
            break
        time.sleep(0.1)
    assert fc.status()["state"] == "stopped"  # honest: not "running" forever


# --------------------------------------------------------------------------- #
# #812: honest live count - configured vs ANSWERING
# --------------------------------------------------------------------------- #


def _touch(p: Path, mtime: float) -> None:
    p.write_text("t\n", encoding="utf-8")
    os.utime(p, (mtime, mtime))


def test_count_answering_counts_fresh_files_through_aliases(tmp_path: Path) -> None:
    now = 1_000_000.0
    served = {
        "y9d41p": ("plants_esp32_f4e9d4",),  # renamed board; old filename still counts
        "8gtt1h": (),
        "yyvvpd": (),  # the unplugged yellow-C5 - no fresh file
    }
    # a previous-id file, fresh -> aliases to y9d41p (answering)
    _touch(tmp_path / "plants_esp32_f4e9d4_20260707_120000.csv", now - 50)
    _touch(tmp_path / "8gtt1h_20260707_120000.csv", now - 10)  # answering
    _touch(tmp_path / "yyvvpd_20260701_120000.csv", now - 100_000)  # stale -> silent
    _touch(tmp_path / "stray_20260707_120000.csv", now - 5)  # not served -> ignored
    _touch(tmp_path / "notaflatfile.csv", now - 5)  # no date suffix -> ignored

    # 2 of 3 configured devices answered within the window; the silent one is excluded.
    assert count_answering(tmp_path, served, window_s=90.0, now=now) == 2


def test_count_answering_dedupes_a_board_with_current_and_previous_files(
    tmp_path: Path,
) -> None:
    now = 1_000_000.0
    served = {"y9d41p": ("plants_esp32_f4e9d4",)}
    _touch(tmp_path / "y9d41p_20260707_120000.csv", now - 5)  # current id, fresh
    _touch(
        tmp_path / "plants_esp32_f4e9d4_20260707_110000.csv", now - 20
    )  # prev, fresh
    # same physical board via two filenames -> counted once.
    assert count_answering(tmp_path, served, window_s=90.0, now=now) == 1


def test_count_answering_empty_or_missing_logdir_is_zero(tmp_path: Path) -> None:
    assert count_answering(tmp_path, {"y9d41p": ()}, window_s=90.0, now=1.0) == 0
    assert count_answering(tmp_path / "nope", {"y9d41p": ()}, window_s=90.0) == 0


def test_status_shows_answering_below_configured_when_a_device_is_silent(
    tmp_path: Path,
) -> None:
    # 3 configured, only 2 answering (the unplugged C5 is silent) - it must stay
    # visible in the total, never absorbed into a healthy-looking "3 devices".
    fc = FleetController(
        fleet_py=_sleeper(tmp_path), served_count=lambda: 3, answering_fn=lambda: 2
    )
    st = fc.start()
    try:
        assert st == {
            "state": "running",
            "configured": 3,
            "answering": 2,
            "devices": 3,
        }
    finally:
        fc.stop()


def test_answering_is_capped_at_configured(tmp_path: Path) -> None:
    # a stray extra fresh file must never push answering above the configured total.
    fc = FleetController(
        fleet_py=_sleeper(tmp_path), served_count=lambda: 2, answering_fn=lambda: 5
    )
    st = fc.start()
    try:
        assert st["answering"] == 2  # min(answering, configured)
        assert st["configured"] == 2
    finally:
        fc.stop()


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
