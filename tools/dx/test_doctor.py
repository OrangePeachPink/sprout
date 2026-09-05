"""Tests for #1553 `just doctor`.

The doctor's whole value is that its verdicts are trustworthy, so these pin the two
things that would quietly destroy that: the ok/warn/fail *grading* (a warn that grades
as a failure trains people to ignore red), and the clone-path budget agreeing with the
guard that owns it.
"""

import json
import os
import socket
from pathlib import Path

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


# ---- #1688: a worktree can read a registry the running app never sees ----------
# Measured when filed: root checkout had `hydrology` on 11/11 plants, a worktree had
# 7/11. The dangerous case is a TEST asserting profile-dependent behaviour in a
# worktree — it asserts against a registry nobody runs, so it can pass while the
# product is broken, and the failure is invisible because both files legitimately exist.


def _config(root: Path, **files: str) -> Path:
    (root / "config").mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (root / "config" / name.replace("__", ".")).write_text(body, encoding="utf-8")
    return root


def test_backup_files_are_not_treated_as_registries(tmp_path: Path) -> None:
    """The operator's backups live only in the main checkout, by design.

    `*.local.json*` also matches devices.local.json.bak-20260706_200920 and eight
    siblings. Listing twelve files, nine of them noise, produces a warning people skim —
    and a warning people skim is not a warning.
    """
    root = _config(
        tmp_path,
        devices__local__json="{}",
    )
    (root / "config" / "devices.local.json.bak-20260706_200920").write_text(
        "{}", "utf-8"
    )
    (root / "config" / "devices.local.json.v5-parked-20260720").write_text(
        "{}", "utf-8"
    )
    found = d._local_configs(root)
    assert set(found) == {"devices.local.json"}


def test_jsonl_registries_are_included(tmp_path: Path) -> None:
    """watering_log.local.jsonl is a registry too — the list is not just .json."""
    root = _config(tmp_path, watering_log__local__jsonl="{}\n")
    assert "watering_log.local.jsonl" in d._local_configs(root)


def test_a_checkout_with_no_config_dir_is_not_an_error(tmp_path: Path) -> None:
    assert d._local_configs(tmp_path) == {}


def test_git_names_the_main_worktree() -> None:
    """The whole reason this needs no env var or marker file.

    #1688 weighed a canonical-root scheme against 'make it loud', noting that a
    canonical root 'couples every worktree to a path outside itself'. Git already
    maintains exactly that coupling — `git worktree list` reports it — so whoever wants
    the canonical-root shape has a cheaper path than the issue assumed.
    """
    root = d.main_worktree()
    assert root is not None and root.exists()


def test_the_drift_check_is_registered() -> None:
    assert d.check_local_config_drift in d.CHECKS


def test_drift_is_a_warn_never_a_fail() -> None:
    """It reports; it does not resolve.

    Redirecting reads to one canonical root is a behaviour change in another lane's
    modules, and #1688 filed shapes rather than a decision. A `fail` here would also
    make `doctor` non-zero in every worktree, which trains people to stop running it.
    """
    c = d.check_local_config_drift()
    assert c.status in (d.OK, d.WARN)


# --------------------------------------------------------------------------- #
# #1718 — the records lane: is the corpus actually off this machine?
# --------------------------------------------------------------------------- #
def _lane(monkeypatch, tmp_path, *, unpushed=0, pending=(), age_days=0):
    """Stand up a fake data worktree and the git answers the check reads.

    The real failure was invisible to every cheaper question, so the fake has to be able
    to reproduce it: a working tree full of records, no local commits, and a remote that
    has none of it.
    """
    import time as _t

    wt = tmp_path / ".data-worktree"
    (wt / "data" / "archive").mkdir(parents=True)
    porcelain = ""
    for name in pending:
        f = wt / "data" / "archive" / name
        f.write_text("x", encoding="utf-8")
        old = _t.time() - age_days * 86400
        os.utime(f, (old, old))
        porcelain += f"A  data/archive/{name}\n"
    stamp = str(int(_t.time() - age_days * 86400))

    def fake_run(cmd, timeout=20):
        if "rev-list" in cmd:
            return 0, str(unpushed)
        if "status" in cmd:
            return 0, porcelain
        if "log" in cmd:
            return 0, "\n".join([stamp] * unpushed)
        return 0, ""

    monkeypatch.setattr(d, "_DATA_WORKTREE", wt)
    monkeypatch.setattr(d, "_run", fake_run)
    return d.check_records_lane()


def test_a_landed_lane_is_ok(monkeypatch, tmp_path) -> None:
    assert _lane(monkeypatch, tmp_path).status == d.OK


def test_records_older_than_the_window_FAIL_because_they_are_one_copy(
    monkeypatch, tmp_path
) -> None:
    """The #1718 case, reproduced: files staged and never landed, ageing on one disk.
    Every cheaper question said fine — the branch had no local commits, and 'is the
    worktree clean' was never asked of a tree holding 236 unlanded records."""
    c = _lane(
        monkeypatch,
        tmp_path,
        pending=("y9d41p_20260705_002734.csv.gz", "8gtt1h_20260705_002735.csv.gz"),
        age_days=70,
    )
    assert c.status == d.FAIL
    assert "ONE copy" in c.detail
    assert "archive_logs" in c.fix


def test_a_fresh_backlog_only_WARNS(monkeypatch, tmp_path) -> None:
    """Yesterday's segment not yet pushed is normal operation, not an alarm — the lane
    lands on a timer. Severity is age, not count."""
    c = _lane(
        monkeypatch, tmp_path, pending=("y9d41p_20260904_000100.csv.gz",), age_days=1
    )
    assert c.status == d.WARN


def test_UNPUSHED_COMMITS_count_even_with_a_clean_worktree(
    monkeypatch, tmp_path
) -> None:
    """The blind spot that hid this for ten weeks: 'committed' is not 'safe'. A clean
    worktree with commits the remote has never seen is still one copy on one disk."""
    c = _lane(monkeypatch, tmp_path, unpushed=3, age_days=30)
    assert c.status == d.FAIL
    assert "3 unpushed" in c.detail


def test_the_check_measures_against_the_REMOTE(monkeypatch, tmp_path) -> None:
    """Pinning the mechanism, not just the verdict: the comparison must be
    `origin/data..data`. A local-only check is what this issue is about."""
    seen = []

    def fake_run(cmd, timeout=20):
        seen.append(cmd)
        return 0, "0"

    wt = tmp_path / ".data-worktree"
    (wt / "data").mkdir(parents=True)
    monkeypatch.setattr(d, "_DATA_WORKTREE", wt)
    monkeypatch.setattr(d, "_run", fake_run)
    d.check_records_lane()
    flat = [" ".join(c) for c in seen]
    assert any("origin/data..data" in f for f in flat), flat
    assert any("fetch" in f for f in flat), "must refresh the remote ref before judging"


def test_a_machine_with_no_data_worktree_is_not_a_failure(
    monkeypatch, tmp_path
) -> None:
    """A contributor's clone has no records lane; do not fail them for it."""
    monkeypatch.setattr(d, "_DATA_WORKTREE", tmp_path / "nope")
    assert d.check_records_lane().status == d.OK
