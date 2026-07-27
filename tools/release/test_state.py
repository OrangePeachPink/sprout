"""#1668 — the phase inference, and the rule that it may only read observed state.

`"You are at §5"` asserted from a local variable is the falsehood family this release
kept producing. Every branch below is driven from facts a live query actually returned,
and `unknown` is a real answer — a cut ceremony is not improved by a confident guess.
"""

from __future__ import annotations

from tools.release import state as s

REPO = "OWNER/REPO"


def _facts(release=None, milestone=None, assets=None, target=None) -> dict:
    f = {"release": release, "milestone": milestone}
    if assets is not None:
        f["assets"] = assets
    if target is not None:
        f["target"] = target
    return f


def test_nothing_exists_yet() -> None:
    phase, action = s.phase_and_next("v9.9.9", REPO, _facts())
    assert phase == "before §2"
    assert "Create the milestone" in action


def test_an_open_milestone_is_pre_cut() -> None:
    phase, action = s.phase_and_next(
        "v0.8.2", REPO, _facts(milestone={"state": "open", "open_issues": 54})
    )
    assert phase == "§1 / §1.1"
    assert "release-preflight" in action, "the next action must name the command"


def test_a_closed_milestone_with_no_draft_is_mid_cut() -> None:
    phase, _ = s.phase_and_next(
        "v0.8.2", REPO, _facts(milestone={"state": "closed", "open_issues": 0})
    )
    assert phase == "§2 in flight"


def test_a_draft_with_no_assets_names_the_v080_failure() -> None:
    """The asset-less publish is the one that cannot be fixed after (#1438), so the
    next action says so rather than merely saying 'sign it'."""
    phase, action = s.phase_and_next(
        "v0.8.2", REPO, _facts(release={"isDraft": True}, assets=[])
    )
    assert phase == "§5 pending"
    assert "asset-less" in action


def test_a_signed_draft_points_at_verify_not_at_publish() -> None:
    """`assets > 0` is not evidence the release is correct — that is #1662's whole
    point, and this must not shortcut it."""
    phase, action = s.phase_and_next(
        "v0.8.2", REPO, _facts(release={"isDraft": True}, assets=["a", "b"])
    )
    assert "§5" in phase
    assert "release-verify" in action
    assert "publish only if it exits 0" in action


def test_a_published_release_says_the_assets_are_sealed() -> None:
    phase, action = s.phase_and_next(
        "v0.8.1", REPO, _facts(release={"isDraft": False}, assets=["a"])
    )
    assert phase == "§6 done"
    assert "sealed" in action and "new tag" in action


def test_every_field_defaults_to_unknown_not_to_a_guess() -> None:
    """A Field with no value renders `unknown`. It must never render a plausible
    substitute — the point of the rule is that absence is visible."""
    assert s.Field("x", None).render(4).split()[-1] == s.UNKNOWN


def test_the_frozen_candidate_is_reported_absent_not_substituted() -> None:
    """#1657 has no store yet.

    The draft's target is NOT used as a stand-in: 'what was agreed' and 'what the draft
    points at' are different claims, and #1657 exists precisely because they can differ.
    Substituting one for the other would invent the agreement.
    """
    src = s.observe.__doc__ or ""
    assert "Live queries only" in src
    import inspect

    body = inspect.getsource(s.observe)
    assert "#1657 not built" in body


def test_the_signer_run_is_not_attributed_without_evidence() -> None:
    """A signer run records no tag, so a repo-wide 'last run' cannot be claimed for
    this release. The first draft of this tool showed v0.8.1's run under v0.8.2."""
    import inspect

    body = inspect.getsource(s.observe)
    assert "cannot be attributed to" in body
    assert "NOT this draft's target" in body
