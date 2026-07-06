"""Unit tests for the headless collection reclaim logic (#689).

The reclaim loop is the risky part (it stops live processes), so it takes injected
``terminate`` / ``still_live`` / ``sleep`` seams - these tests exercise every outcome
(graceful / forced / failed) with fakes, no real processes and no real waiting.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collection import build_parser, reclaim


def _recorder():
    calls: list[tuple[int, bool]] = []

    def terminate(pid, *, force):
        calls.append((pid, force))

    return calls, terminate


_NO_SLEEP = lambda _s: None  # noqa: E731  (test seam)


def test_reclaim_empty_is_noop():
    # No collectors -> returns [] without touching the seams.
    assert reclaim([], terminate=None, still_live=None, sleep=_NO_SLEEP) == []


def test_reclaim_all_graceful_never_forces():
    procs = [
        {"pid": 1, "role": "monitor", "command": "a"},
        {"pid": 2, "role": "fleet", "command": "b"},
    ]
    calls, terminate = _recorder()
    out = reclaim(
        procs, terminate=terminate, still_live=lambda _pids: set(), sleep=_NO_SLEEP
    )
    assert [r["outcome"] for r in out] == ["graceful", "graceful"]
    # graceful stop sent to both, force sent to neither
    assert calls == [(1, False), (2, False)]


def test_reclaim_forces_only_survivors():
    procs = [
        {"pid": 1, "role": "monitor", "command": "a"},
        {"pid": 2, "role": "fleet", "command": "b"},
    ]
    calls, terminate = _recorder()
    state = {"n": 0}

    def still_live(_pids):
        # 1st query = survivors after graceful (pid 2 hung on); 2nd = final (gone).
        state["n"] += 1
        return {2} if state["n"] == 1 else set()

    out = reclaim(procs, terminate=terminate, still_live=still_live, sleep=_NO_SLEEP)
    by_pid = {r["pid"]: r["outcome"] for r in out}
    assert by_pid == {1: "graceful", 2: "forced"}
    assert (2, True) in calls  # force sent to the survivor
    assert (1, True) not in calls  # NOT to the one that stopped gracefully


def test_reclaim_reports_failed_when_hardkill_misses():
    procs = [{"pid": 9, "role": "monitor", "command": "x"}]
    calls, terminate = _recorder()
    out = reclaim(
        procs, terminate=terminate, still_live=lambda _pids: {9}, sleep=_NO_SLEEP
    )
    assert out[0]["outcome"] == "failed"
    assert (9, False) in calls and (9, True) in calls  # tried graceful, then force


def test_parser_requires_an_action():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_parser_stop_defaults():
    args = build_parser().parse_args(["stop"])
    assert args.action == "stop"
    assert args.role == "all"
    assert args.dry_run is False
