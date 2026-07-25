"""Tests for #1553 `just doctor`.

The doctor's whole value is that its verdicts are trustworthy, so these pin the two
things that would quietly destroy that: the ok/warn/fail *grading* (a warn that grades
as a failure trains people to ignore red), and the clone-path budget agreeing with the
guard that owns it.
"""

import json
import socket

import pytest

from tools.dx import doctor as d


def test_only_fail_sets_a_nonzero_exit(monkeypatch, capsys) -> None:
    """Warnings are states, not faults. A newcomer with no board and no serial port
    must get exit 0 — grading that as failure is how red stops meaning anything."""
    monkeypatch.setattr(
        d,
        "CHECKS",
        (lambda: d.Check("a", d.OK, "-"), lambda: d.Check("b", d.WARN, "-")),
    )
    assert d.main([]) == 0
    monkeypatch.setattr(d, "CHECKS", (lambda: d.Check("c", d.FAIL, "-"),))
    assert d.main([]) == 1


def test_the_fix_hint_prints_only_for_problems(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        d,
        "CHECKS",
        (
            lambda: d.Check("fine", d.OK, "-", fix="SHOULD-NOT-PRINT"),
            lambda: d.Check("bad", d.FAIL, "-", fix="run-this"),
        ),
    )
    d.main([])
    out = capsys.readouterr().out
    assert "run-this" in out
    assert "SHOULD-NOT-PRINT" not in out


def test_json_is_machine_readable(monkeypatch, capsys) -> None:
    """The onboarding guard (#1562) consumes this — it must stay parseable."""
    monkeypatch.setattr(d, "CHECKS", (lambda: d.Check("x", d.WARN, "detail", "fix"),))
    d.main(["--json"])
    doc = json.loads(capsys.readouterr().out)
    assert doc == [{"name": "x", "status": "warn", "detail": "detail", "fix": "fix"}]


def test_clone_budget_agrees_with_the_guard_that_owns_it() -> None:
    """path_length_guard sets the tracked-path limit; the doctor only measures what is
    left. If the guard's budget ever changes, this fails instead of the doctor quietly
    reporting headroom nobody actually has."""
    src = (d.REPO_ROOT / "tools" / "dx" / "path_length_guard.py").read_text(
        encoding="utf-8"
    )
    assert f"limit is {d.TRACKED_LIMIT}" in src or f"{d.TRACKED_LIMIT}, not" in src
    assert f"{d.MAX_PATH} characters" in src or f"{d.MAX_PATH} minus" in src
    assert d.CLONE_BUDGET == d.MAX_PATH - d.TRACKED_LIMIT


def test_a_missing_binary_is_a_result_never_a_crash(monkeypatch) -> None:
    """`_run` must survive a binary that isn't there — 'not installed' is the answer
    this tool exists to give, not an exception it dies on."""
    code, out = d._run(["definitely-not-a-real-binary-xyz"])
    assert code == 127 and out


def test_unreadable_registry_is_a_fail_not_a_crash(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(d, "REPO_ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "devices.local.json").write_text(
        "{not json", encoding="utf-8"
    )
    r = d.check_boards_declared()
    assert r.status == d.FAIL and "unreadable" in r.detail


def test_no_registry_warns_and_names_the_wall(monkeypatch, tmp_path) -> None:
    """The #1541 state that presented as 'waiting for the first reading' forever."""
    monkeypatch.setattr(d, "REPO_ROOT", tmp_path)
    r = d.check_boards_declared()
    assert r.status == d.WARN
    assert "no readings" in r.detail or "nothing is registered" in r.detail
    assert r.fix  # it must say what to do about it


def test_declared_devices_are_counted(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(d, "REPO_ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "devices.local.json").write_text(
        json.dumps({"devices": [{"id": "a"}, {"id": "b"}]}), encoding="utf-8"
    )
    r = d.check_boards_declared()
    assert r.status == d.OK and "2 device" in r.detail


def test_a_busy_port_is_a_warn_not_a_failure() -> None:
    """Sprout already running is the likeliest reason :8765 is busy. Calling that a
    failure would be a lie, and would make `doctor` useless while Sprout is up."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        original = d.PORT
        try:
            d.PORT = port
            r = d.check_port()
        finally:
            d.PORT = original
    assert r.status == d.WARN and r.fix


@pytest.mark.parametrize("name", [c.__name__ for c in d.CHECKS])
def test_every_check_returns_a_graded_result(name) -> None:
    """No check may invent a status, and every non-ok one must be actionable or
    self-explanatory — a bare 'warn' with no detail helps nobody."""
    r = getattr(d, name)()
    assert r.status in (d.OK, d.WARN, d.FAIL)
    assert r.name and r.detail
