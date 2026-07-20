"""Tests for the #1386 untracked-file notice (runs under `just test-dx`)."""

import subprocess

import untracked_notice as n


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_untracked_file_is_listed(tmp_path) -> None:
    _git(tmp_path, "init")
    (tmp_path / "tracked.md").write_text("x")
    _git(tmp_path, "add", "tracked.md")
    (tmp_path / "brand_new.py").write_text("import nope")
    assert n.untracked_files(tmp_path) == ["brand_new.py"]


def test_ignored_files_are_not_listed(tmp_path) -> None:
    """A legitimate scratch/local file that .gitignore covers must stay silent."""
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text("scratch/\n")
    _git(tmp_path, "add", ".gitignore")
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "notes.txt").write_text("local only")
    assert n.untracked_files(tmp_path) == []


def test_clean_tree_lists_nothing(tmp_path) -> None:
    _git(tmp_path, "init")
    (tmp_path / "a.md").write_text("x")
    _git(tmp_path, "add", "a.md")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "x")
    assert n.untracked_files(tmp_path) == []


def test_main_never_fails_even_with_untracked(tmp_path, monkeypatch) -> None:
    """The whole point: the notice reports, it never blocks the gate."""
    monkeypatch.setattr(n, "untracked_files", lambda: ["something_new.py"])
    assert n.main([]) == 0
