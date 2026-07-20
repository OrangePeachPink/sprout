"""Tests for the #1337 path-length guard.

Runs under `just test-dx`. The last two assert against the REAL tree: the claim is
about this repository, and a guard proven only on fixtures proves nothing here."""

import path_length_guard as g


def test_over_limit_flags_and_sorts_longest_first() -> None:
    paths = ["a" * 210, "b" * 205, "short.md"]
    found = g.over_limit(paths, limit=200)
    assert [n for n, _ in found] == [210, 205]  # longest first — worst offender leads


def test_limit_is_inclusive() -> None:
    """At the limit is already too long — the budget is what's LEFT for the user."""
    assert g.over_limit(["x" * 200], limit=200)
    assert not g.over_limit(["x" * 199], limit=200)


def test_short_paths_pass() -> None:
    assert g.over_limit(["docs/README.md", "tools/dx/x.py"], limit=200) == []


def test_the_real_tree_is_under_the_limit() -> None:
    """The '#1337 renames landed' claim, made executable."""
    assert g.over_limit(g.tracked_paths()) == []


def test_the_real_tree_actually_has_paths() -> None:
    """A `git ls-files` that returned nothing would pass loudly — the failure mode
    this whole class of guard exists to catch."""
    assert len(g.tracked_paths()) > 100
