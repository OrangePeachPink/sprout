"""Tests for the Sprout orphan-process finder (#493, identifiability).

Covers role classification, the injected-query path (so tests never touch the real
OS process table), unrelated-process filtering, and honest degradation when the
platform query is unavailable or fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sprout_processes as sp


def _row(pid: int, command: str) -> dict:
    return {"pid": pid, "command": command}


def test_classifies_monitor_capture_and_fleet() -> None:
    rows = [
        _row(111, r"C:\python.exe C:\tools\logger\plants_logger.py --port COM6"),
        _row(222, r"C:\pythonw.exe tools/capture/experiment_capture.py --subject x"),
        _row(333, r"C:\pythonw.exe tools/logger/fleet_logger.py --cadence-s 30"),
    ]
    found = sp.list_sprout_processes(raw_query=lambda: rows)
    assert {(p["pid"], p["role"]) for p in found} == {
        (111, "monitor"),
        (222, "capture"),
        (333, "fleet"),  # #493 F1: the untethered poller is now discoverable
    }


def test_ignores_unrelated_python_processes() -> None:
    rows = [
        _row(333, "python.exe some_other_script.py"),
        _row(444, "pythonw.exe -m http.server"),
    ]
    assert sp.list_sprout_processes(raw_query=lambda: rows) == []


def test_empty_process_table_is_empty() -> None:
    assert sp.list_sprout_processes(raw_query=lambda: []) == []


def test_failing_query_degrades_to_empty_not_raise() -> None:
    def _boom():
        raise OSError("no powershell here")

    assert sp.list_sprout_processes(raw_query=_boom) == []


def test_report_lists_pid_role_and_kill_hint() -> None:
    rows = [_row(555, "python.exe tools/logger/plants_logger.py --port COM6")]
    found = sp.list_sprout_processes(raw_query=lambda: rows)
    report = sp._report(found)
    assert "555" in report and "monitor" in report
    assert "Stop-Process" in report  # the exact operator action, not just a finding


def test_report_empty_is_reassuring_not_blank() -> None:
    assert "no live" in sp._report([])


def test_main_prints_report(capsys) -> None:
    rc = sp.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.strip()  # never silent - always says found-or-not
