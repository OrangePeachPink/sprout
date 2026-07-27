"""Tests for the one-click Fleet Monitor control plane (#588, ADR-0014).

FleetController mirrors MonitorController (single-flight, honest refusals);
collection_control is the one-action policy layer - every degrade path the
issue names is pinned: no COM port != error, no registered fleet != error,
BOTH absent -> an honest error (one action that collected nothing must never
look like success).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from tools.logger.collection_control import (
    CollectionError,
    start_all,
    status_all,
    stop_all,
)
from tools.logger.fleet_control import FleetController, FleetError, count_answering
from tools.logger.fleet_lock import REFUSED_EXIT

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


def test_second_start_on_a_healthy_worker_is_idempotent(tmp_path: Path) -> None:
    # #1004 guard 1: a start on a running worker NEVER restarts it (that collision is
    # what killed the worker the maintainer watched). It's a no-op returning the running
    # status — same process, zero deaths.
    fc = FleetController(
        fleet_py=_sleeper(tmp_path), served_count=lambda: 1, answering_fn=lambda: 1
    )
    fc.start()
    try:
        pid_before = fc._proc.pid
        st = fc.start()  # must NOT raise, must NOT respawn
        assert st["state"] == "running"
        assert (
            fc._proc.pid == pid_before
        )  # the very same worker, never killed/restarted
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


def _fast(fleet_py: Path, **kw):
    # fast supervision so the watchdog tests run in ~1s, not ~12s
    return FleetController(
        fleet_py=fleet_py,
        served_count=lambda: 1,
        answering_fn=lambda: 1,
        max_restarts=kw.pop("max_restarts", 2),
        restart_window_s=kw.pop("restart_window_s", 30.0),
        supervise_interval_s=0.05,
        backoff_s=0.05,
        **kw,
    )


def test_a_worker_that_keeps_crashing_gives_up_loudly(tmp_path: Path) -> None:
    # #1004 guard 3 + #968: the supervisor restarts a crashing worker, but a worker that
    # crashes past the bounded limit gives up — and says WHY (never a bare "stopped").
    crasher = tmp_path / "crash.py"
    crasher.write_text("raise SystemExit(1)\n", encoding="utf-8")
    fc = _fast(crasher, max_restarts=2)
    fc.start()
    try:
        gave_up = None
        for _ in range(100):  # bounded: ~2 restarts * (0.05 + 0.05)s + slack
            st = fc.status()
            if st["state"] == "stopped" and st.get("give_up_reason"):
                gave_up = st["give_up_reason"]
                break
            time.sleep(0.05)
        assert gave_up is not None, (
            "a repeatedly-crashing worker must give up with a reason"
        )
        assert "crashed" in gave_up and "fleet_worker.log" in gave_up  # #968 reason
    finally:
        fc.stop()


def test_supervision_restarts_a_worker_that_dies_once(tmp_path: Path) -> None:
    # #1004 guard 3, the one-job invariant: a worker that dies is restarted, logging
    # resumes, no operator action. The probe dies on run #1, sleeps on run #2.
    counter = tmp_path / "runs.txt"
    probe = tmp_path / "flaky.py"
    probe.write_text(
        "import pathlib, time\n"
        f"c = pathlib.Path(r'{counter}')\n"
        "n = (int(c.read_text()) if c.exists() else 0) + 1\n"
        "c.write_text(str(n))\n"
        "if n <= 1:\n    raise SystemExit(1)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )

    def _runs() -> int:
        try:
            return int(counter.read_text())
        except (OSError, ValueError):
            return 0

    fc = _fast(probe, max_restarts=5)
    fc.start()
    try:
        back_up = False
        for _ in range(100):
            if fc.status()["state"] == "running" and _runs() >= 2:
                back_up = True
                break
            time.sleep(0.05)
        assert back_up, "the supervisor must restart a dead worker and resume running"
        assert _runs() >= 2  # it really respawned (run #2 is alive)
    finally:
        fc.stop()


def test_worker_stderr_goes_to_a_capped_log_not_devnull(tmp_path: Path) -> None:
    # #968: the poller's last words survive a crash — stderr lands in a capped log file.
    talker = tmp_path / "talk.py"
    talker.write_text(
        "import sys, time\nsys.stderr.write('worker last words\\n')\n"
        "sys.stderr.flush()\ntime.sleep(60)\n",
        encoding="utf-8",
    )
    fc = _fast(talker, logdir=tmp_path)
    fc.start()
    try:
        log = tmp_path / "fleet_worker.log"
        seen = False
        for _ in range(60):
            if log.exists() and "worker last words" in log.read_text(
                encoding="utf-8", errors="replace"
            ):
                seen = True
                break
            time.sleep(0.05)
        assert seen, "the worker's stderr must reach fleet_worker.log (never DEVNULL)"
    finally:
        fc.stop()


def test_active_served_excludes_retired_devices(monkeypatch) -> None:
    # #1007: a retired board is off BY CHOICE — never polled, never in `configured`,
    # never counted as 'not answering' (grill Q2).
    from tools.analytics.device_registry import Device, Registry
    from tools.logger import fleet_control

    reg = Registry(
        devices=[
            Device("active1", "esp32", None, base_url="http://a"),
            Device("retired1", "esp32", None, base_url="http://b", retired=True),
        ]
    )
    monkeypatch.setattr(
        "tools.analytics.device_registry.load_registry", lambda *a, **k: reg
    )
    assert fleet_control._served_device_count() == 1  # only the active board
    assert set(fleet_control._served_map()) == {"active1"}  # retired is not polled


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


# --------------------------------------------------------------------------- #
# #1428 — a refusal is not a crash, and its explanation survives
# --------------------------------------------------------------------------- #
def test_a_refusal_is_not_counted_as_a_crash(tmp_path: Path) -> None:
    """The #493 double-writer refusal: the worker declines (another logger owns the
    archive) and exits REFUSED_EXIT. That must NOT burn the restart budget into a
    give-up — the crash-loop the maintainer watched while logging was in fact live.

    (The bug report said the worker "exited 0"; the code returns REFUSED_EXIT, distinct
    from both success and a crash — the exit code is what makes a decline legible.)"""
    refuser = tmp_path / "refuse.py"
    refuser.write_text(
        "print('a fleet logger is already running (pid 2720); "
        "refusing to start a second poller')\n"
        f"raise SystemExit({REFUSED_EXIT})\n",
        encoding="utf-8",
    )
    fc = _fast(refuser, logdir=tmp_path, max_restarts=2)
    fc.start()
    try:
        stood_down = None
        for _ in range(100):
            st = fc.status()
            if st.get("healthy_standdown"):
                stood_down = st
                break
            assert not st.get("give_up_reason"), (
                f"a refusal was mistaken for a crash: {st.get('give_up_reason')}"
            )
            time.sleep(0.05)
        assert stood_down is not None, "a refusal must stand the supervisor down"
        assert "benign_note" in stood_down
        assert "give_up_reason" not in stood_down  # healthy, never a failure
    finally:
        fc.stop()


def test_the_refusal_on_stdout_reaches_the_worker_log(tmp_path: Path) -> None:
    """Bug 1: the refusal prints to STDOUT, which #968 routed to DEVNULL. Both streams
    now land in the capped log, so the words that explain the stand-down survive."""
    refuser = tmp_path / "refuse2.py"
    refuser.write_text(
        f"print('already running (pid 999)')\nraise SystemExit({REFUSED_EXIT})\n",
        encoding="utf-8",
    )
    fc = _fast(refuser, logdir=tmp_path, max_restarts=2)
    fc.start()
    try:
        log = tmp_path / "fleet_worker.log"
        seen = False
        for _ in range(80):
            if log.is_file() and "already running (pid 999)" in log.read_text(
                encoding="utf-8", errors="replace"
            ):
                seen = True
                break
            time.sleep(0.05)
        assert seen, "the stdout refusal must reach fleet_worker.log (was DEVNULL)"
    finally:
        fc.stop()


def test_a_real_crash_still_counts_and_gives_up(tmp_path: Path) -> None:
    """A genuine crash (exit 1, not the refusal code) still exhausts the budget and
    gives up — the refusal carve-out must not weaken the #1004 crash guard."""
    crasher = tmp_path / "crash.py"
    crasher.write_text("raise SystemExit(1)\n", encoding="utf-8")
    fc = _fast(crasher, logdir=tmp_path, max_restarts=2)
    fc.start()
    try:
        reason = None
        for _ in range(120):
            st = fc.status()
            if st["state"] == "stopped" and st.get("give_up_reason"):
                reason = st["give_up_reason"]
                break
            assert not st.get("healthy_standdown"), "a real crash is not a stand-down"
            time.sleep(0.05)
        assert reason is not None, "a repeatedly-crashing worker must give up"
        assert "crashed" in reason
    finally:
        fc.stop()


def test_a_crash_give_up_does_not_cite_an_empty_log(tmp_path: Path) -> None:
    """Bug: the give-up named logs/fleet_worker.log even when 0 bytes — a diagnostic
    pointing at a file that cannot hold the answer. A worker that dies WITHOUT writing
    must not be sent there; the message says the log is empty instead."""
    silent = tmp_path / "silent_crash.py"
    silent.write_text("raise SystemExit(1)\n", encoding="utf-8")  # crash, no output
    fc = _fast(silent, logdir=tmp_path, max_restarts=2)
    fc.start()
    try:
        reason = None
        for _ in range(120):
            st = fc.status()
            if st["state"] == "stopped" and st.get("give_up_reason"):
                reason = st["give_up_reason"]
                break
            time.sleep(0.05)
        assert reason is not None, "a repeatedly-crashing worker must give up"
        log = tmp_path / "fleet_worker.log"
        if not (log.is_file() and log.stat().st_size > 0):
            assert "empty" in reason, (
                f"the log is empty but the give-up sends the reader there: {reason!r}"
            )
    finally:
        fc.stop()
