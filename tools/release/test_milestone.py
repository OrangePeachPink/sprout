"""#1658 — milestone propagation, and the two defects found by running it for real.

The v0.8.1 cut needed a 77-PR backfill and the loop timed out partway through. Every
rule here cost that cut something, and two of them were discovered only when this was
pointed at live PRs rather than at fixtures.
"""

from __future__ import annotations

import pytest

from tools.release import milestone as m

V081 = (10, "v0.8.1", "closed")
V082 = (11, "v0.8.2", "open")
V090 = (4, "v0.9.0", "open")


# ---- link discovery ------------------------------------------------------------


def test_a_comma_list_of_closes_is_still_fully_discovered() -> None:
    """THE defect found while building this, on PR #1685 — my own.

    GitHub's parser needs the keyword repeated per issue, so `Closes #1661, #1662,
    #1663, #1664` linked ONLY #1661. The API said one; the PR meant four. A tool
    trusting `closingIssuesReferences` alone would have propagated to a quarter of the
    work and reported success.
    """
    body = "Closes #1661, #1662, #1663, #1664."
    assert m.referenced_issues(body, api_links=[1661]) == [1661, 1662, 1663, 1664]


def test_a_bare_refs_trailer_is_discovered() -> None:
    """This repo's dominant convention, which GitHub links not at all."""
    assert m.referenced_issues("`Refs #1346`. Two things the cut needed.", []) == [1346]


def test_the_api_and_the_body_are_unioned_not_preferred() -> None:
    """Neither source is complete; over-collecting is the safe direction.

    A wrong extra reference surfaces as a CONFLICT and asks a human. A missed one
    propagates nothing and reports success — the failure that is invisible.
    """
    assert m.referenced_issues("Fixes #2", api_links=[9]) == [2, 9]


def test_prose_without_a_keyword_is_not_a_reference() -> None:
    assert m.referenced_issues("see the discussion in #99 for background", []) == []


# ---- the decision --------------------------------------------------------------


def test_one_milestone_among_the_references_is_adopted() -> None:
    assert m.decide_milestone({1: V082, 2: V082, 3: None}) == V082


def test_unmilestoned_issues_do_not_veto() -> None:
    """A PR that fixes a milestoned issue and mentions an unmilestoned one still
    belongs to the release — 'no milestone' is an absence, not a vote."""
    assert m.decide_milestone({1: None, 2: V082}) == V082


def test_no_milestone_anywhere_yields_nothing() -> None:
    assert m.decide_milestone({1: None, 2: None}) is None


def test_conflicting_milestones_raise_for_a_human() -> None:
    """A PR spanning two milestones is a SCOPE question.

    A helper that silently picks one is a helper that quietly decides what shipped —
    so it names both and stops (the accepted amendment).
    """
    with pytest.raises(m.Conflict) as exc:
        m.decide_milestone({1661: V082, 1346: V090})
    assert "v0.8.2" in str(exc.value) and "v0.9.0" in str(exc.value)
    assert "#1661" in str(exc.value) and "#1346" in str(exc.value)


# ---- the closed-milestone rule -------------------------------------------------


def test_a_closed_milestone_is_returned_with_its_state() -> None:
    """The decision layer reports state; refusing is `propagate_one`'s job.

    Found on PR #1642, which references #1346 on the already-shipped v0.8.1. Blind
    inheritance would back-date a PR onto a released version — the mirror of the
    unbounded-sweep hazard: one fabricates forward, the other backward. §1.1 settles it:
    the tag is the line, so whatever merges now ships in the NEXT version.
    """
    got = m.decide_milestone({1346: V081})
    assert got is not None and got[2] == "closed"


def test_the_docstring_records_why_closed_milestones_are_refused() -> None:
    """This rule is not in the filed spec — it came from running the tool.

    Someone will reasonably try to 'simplify' it back out, so the reason lives in the
    module rather than only in a commit message.
    """
    assert "CLOSED milestone is never propagated" in m.__doc__
    assert "the tag is the line" in m.__doc__


# ---- the rules that are easiest to skip ----------------------------------------


def test_writes_go_through_the_numeric_rest_path() -> None:
    """Rule 1: `gh pr edit --milestone <title>` resolves by title only while the
    milestone is OPEN — and §1.1's corrections happen after §2 closes it. The failing
    form is the one a releaser reaches for at exactly the moment it stops working."""
    import inspect

    src = inspect.getsource(m.set_milestone)
    # Strip the docstring: it *mentions* `gh pr edit` to explain why that form is
    # wrong, and a naive substring check on the whole source flags its own rationale.
    body = src.split('"""')[-1]
    assert "-X" in body and "PATCH" in body
    assert "milestone={ms_id}" in body
    assert "pr edit" not in body, "the title-resolving form must not be used"


def test_the_write_is_re_read_before_being_believed() -> None:
    """Rule 2: GitHub returned 504s on mutations during this cut and one write silently
    did not apply. `set_milestone` must confirm, not assume."""
    import inspect

    src = inspect.getsource(m.set_milestone)
    assert "issue_milestone(" in src, "the write is never verified"
    assert "return False" in src, "a failed verification must be reportable"
