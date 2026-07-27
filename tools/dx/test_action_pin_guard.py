"""Tests for the #1346 action-pin guard.

Runs under `just test-dx`. Two of these assert against the REAL repo, because the
guard's claim is about this repository — a guard proven only against fixtures is a
guard whose green means nothing here."""

from pathlib import Path

from tools.dx import action_pin_guard as g


def _wf(tmp_path: Path, body: str) -> Path:
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True)
    (d / "w.yml").write_text(body, encoding="utf-8")
    return tmp_path


_GOOD = "      - uses: actions/checkout@" + "a" * 40 + " # v7.0.1\n"


def test_unpinned_tag_is_caught(tmp_path: Path) -> None:
    repo = _wf(tmp_path, "      - uses: actions/stale@v9\n")
    (f,) = g.check_structure(repo)
    assert "not pinned" in f.problem


def test_pinned_but_unlabelled_is_caught(tmp_path: Path) -> None:
    """The version comment is what makes the next bump legible."""
    repo = _wf(tmp_path, "      - uses: actions/checkout@" + "a" * 40 + "\n")
    (f,) = g.check_structure(repo)
    assert "unlabelled" in f.problem


def test_pinned_and_labelled_passes(tmp_path: Path) -> None:
    assert g.check_structure(_wf(tmp_path, _GOOD)) == []


def test_local_and_docker_uses_are_ignored(tmp_path: Path) -> None:
    """Neither has an upstream ref to pin, so neither is a finding."""
    repo = _wf(
        tmp_path,
        "      - uses: ./.github/actions/local\n      - uses: docker://alpine:3\n",
    )
    assert g.check_structure(repo) == []


def test_tag_object_sha_is_caught_on_resolve(tmp_path: Path) -> None:
    """The #1346 trap: a real 40-hex SHA that is a TAG OBJECT, not a commit.

    Indistinguishable from a good pin by reading the file — 422 is the only tell."""
    repo = _wf(tmp_path, _GOOD)
    (f,) = g.check_resolvable(repo, api=lambda url: (422, {}))
    assert "NOT A COMMIT" in f.problem


def test_resolve_reports_unreachable_rather_than_passing(tmp_path: Path) -> None:
    """A network failure must never read as a clean pin — the #1327 lesson."""
    repo = _wf(tmp_path, _GOOD)
    (f,) = g.check_resolvable(repo, api=lambda url: (0, {}))
    assert "not checked" in f.problem


def test_resolve_accepts_a_real_commit(tmp_path: Path) -> None:
    sha = "a" * 40
    repo = _wf(tmp_path, _GOOD)
    assert g.check_resolvable(repo, api=lambda url: (200, {"sha": sha})) == []


def test_the_real_repo_is_structurally_clean() -> None:
    """The 'lands green' claim, made executable against this tree."""
    assert g.check_structure() == []


def test_the_real_repo_has_actions_to_check() -> None:
    """Guards the worst outcome: a regex matching nothing, then passing loudly."""
    total = sum(len(g.parse_uses(w)) for w in g.workflow_files())
    assert total > 20
