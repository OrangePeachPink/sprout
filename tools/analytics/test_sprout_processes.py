"""Tests for the Sprout orphan-process finder (#493, identifiability).

Covers role classification, the injected-query path (so tests never touch the real
OS process table), unrelated-process filtering, and honest degradation when the
platform query is unavailable or fails.
"""

from __future__ import annotations

from tools.analytics import sprout_processes as sp


def _row(pid: int, command: str, ppid: int | None = None) -> dict:
    return {"pid": pid, "command": command, "ppid": ppid}


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


# --- #811: count logical collectors by launch tree, not tree-member rows ---


def test_list_carries_ppid_through() -> None:
    rows = [_row(24608, "pythonw.exe tools/logger/fleet_logger.py", ppid=39692)]
    found = sp.list_sprout_processes(raw_query=lambda: rows)
    assert found[0]["ppid"] == 39692


def test_group_collapses_parent_child_into_one_collector() -> None:
    # The launch tree: parent launcher + worker child, both naming the script
    # (#811). One logical fleet, reported launcher-first.
    rows = [
        _row(39692, "python.exe tools/logger/fleet_logger.py", ppid=1200),  # launcher
        _row(24608, "python.exe tools/logger/fleet_logger.py", ppid=39692),  # worker
    ]
    procs = sp.list_sprout_processes(raw_query=lambda: rows)
    trees = sp.group_launch_trees(procs)
    assert len(trees) == 1
    assert trees[0]["role"] == "fleet"
    assert trees[0]["pids"] == [39692, 24608]  # launcher first


def test_report_counts_logical_collectors_not_tree_members() -> None:
    rows = [
        _row(39692, "python.exe fleet_logger.py", ppid=1200),
        _row(24608, "python.exe fleet_logger.py", ppid=39692),
    ]
    procs = sp.list_sprout_processes(raw_query=lambda: rows)
    report = sp._report(procs)
    assert "1 live Sprout collector" in report  # NOT "2"
    assert "39692->24608" in report  # the tree, one line
    assert report.count("fleet") == 1  # one row, not two


def test_two_independent_same_role_stay_separate() -> None:
    # Two real fleets (unrelated parents) must not be merged just by shared role.
    rows = [
        _row(100, "python.exe fleet_logger.py", ppid=1),
        _row(200, "python.exe fleet_logger.py", ppid=2),
    ]
    procs = sp.list_sprout_processes(raw_query=lambda: rows)
    assert len(sp.group_launch_trees(procs)) == 2


def test_group_without_ppid_each_stands_alone() -> None:
    # No parentage available -> honest degradation: one entry per proc, never merged.
    rows = [
        _row(100, "python.exe fleet_logger.py"),
        _row(200, "python.exe fleet_logger.py"),
    ]
    procs = sp.list_sprout_processes(raw_query=lambda: rows)
    assert len(sp.group_launch_trees(procs)) == 2


# --------------------------------------------------------------------------- #
# #1392 — the dashboard server, and the false all-clear it produced
# --------------------------------------------------------------------------- #
def test_a_live_server_is_reported() -> None:
    """DX's incident: a stuck server, and a diagnostic that said nothing was live."""
    rows = [
        _row(39824, r"python.exe C:\dev\plants\tools\analytics\serve.py --port 8765")
    ]
    servers = sp.list_sprout_servers(raw_query=lambda: rows)
    assert [s["pid"] for s in servers] == [39824]


def test_a_pytest_run_is_not_mistaken_for_the_server() -> None:
    """This directory holds test_serve.py and seven siblings, so a substring match
    would report a test run as the live server — a false positive replacing a false
    negative is not a fix."""
    rows = [
        _row(1, "python.exe -m pytest test_serve.py"),
        _row(2, "python.exe -m pytest test_serve_stop.py -q"),
        _row(3, "python.exe test_served_cal_state.py"),
    ]
    assert sp.list_sprout_servers(raw_query=lambda: rows) == []


def test_the_server_never_leaks_into_the_collector_list() -> None:
    """collection.py consumes list_sprout_processes() treating every row as a
    collector; a server appearing there would corrupt another lane's surface."""
    rows = [_row(39824, "python.exe serve.py")]
    assert sp.list_sprout_processes(raw_query=lambda: rows) == []


def test_the_empty_report_no_longer_overclaims() -> None:
    assert "collectors or dashboard servers" in sp._report([], [])


def test_a_stuck_server_with_no_collectors_is_still_reported() -> None:
    """The exact reported shape: children all gone, server immortal. The old report
    said 'no live Sprout-spawned processes found' and sent the operator away."""
    report = sp._report([], [{"pid": 39824, "ppid": 1, "command": "python serve.py"}])
    assert "1 live dashboard server" in report
    assert "39824" in report
    assert "no live Sprout collectors found." in report


def test_servers_and_collectors_both_survive_the_same_report() -> None:
    """Regression: the collector header used to reassign the line list, silently
    dropping the server block above it."""
    procs = sp.list_sprout_processes(
        raw_query=lambda: [_row(100, "python.exe fleet_logger.py")]
    )
    report = sp._report(
        procs, [{"pid": 39824, "ppid": 1, "command": "python serve.py"}]
    )
    assert "39824" in report  # the server
    assert "fleet" in report  # and the collector
