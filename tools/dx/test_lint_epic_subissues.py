"""Unit tests for the epic hygiene lint (tools/dx/lint_epic_subissues.py, #810).

Covers the pure detection + rendering (no network): body-checkbox detection
(AC1), bundle/scope-ref detection (AC2), the per-epic findings, and the
idempotency invariant — both the finding and the resolved comment carry the
MARKER, so the upsert path updates ONE comment in place rather than spamming
(AC4).
"""

from __future__ import annotations

from lint_epic_subissues import (
    MARKER,
    body_has_checkboxes,
    comment_body,
    epic_findings,
    resolved_body,
    scope_section_refs,
)


def _epic(number=1, body="", subs=()):
    return {
        "number": number,
        "title": "Epic: a thing",
        "body": body,
        "labels": {"nodes": [{"name": "epic"}]},
        "subIssues": {"nodes": [{"number": n} for n in subs]},
    }


# --- AC1: ANY body task-list checkbox is the second-tracker smell ----------


def test_bare_checkbox_detected():
    assert body_has_checkboxes("- [ ] do a thing")


def test_checked_and_star_and_indented_detected():
    assert body_has_checkboxes("* [x] done")
    assert body_has_checkboxes("  - [X] indented")


def test_plain_list_and_empty_are_not_checkboxes():
    assert not body_has_checkboxes("- a bullet\n- another")
    assert not body_has_checkboxes("")


def test_findings_flag_bare_checkbox_epic():
    fs = epic_findings(_epic(body="Plan:\n- [ ] ship it"))
    assert len(fs) == 1
    assert "Body task-list checkboxes" in fs[0]


def test_findings_note_unwired_checkbox_refs():
    fs = epic_findings(_epic(body="- [ ] #200\n- [ ] #201", subs=(200,)))
    assert "#201" in fs[0]  # #201 unwired; #200 is a native sub-issue


def test_clean_epic_native_only_has_no_findings():
    assert epic_findings(_epic(body="Doctrine text, no checkboxes.", subs=(9,))) == []


# --- AC2: bundle/scope-section refs not attached as sub-issues -------------


def test_scope_section_refs_scoped_to_the_section():
    body = "## Bundle\n- #300 a\n- #301 b\n## Notes\n- #999 unrelated"
    assert scope_section_refs(body) == [300, 301]  # #999 is under a different heading


def test_scope_finding_only_for_unattached():
    fs = epic_findings(_epic(body="## Scope\n#400 and #401", subs=(400,)))
    assert len(fs) == 1
    assert "#401" in fs[0] and "#400" not in fs[0]


def test_scope_ref_not_double_reported_with_checkbox():
    fs = epic_findings(_epic(body="## Bundle\n- [ ] #500"))
    assert len(fs) == 1  # only the checkbox finding, not a duplicate scope finding
    assert "Body task-list checkboxes" in fs[0]


# --- AC4: idempotency invariant (marker present in both comment states) ----


def test_comment_body_carries_marker():
    assert comment_body(["a finding"]).startswith(MARKER)


def test_resolved_body_carries_marker():
    assert resolved_body().startswith(MARKER)
