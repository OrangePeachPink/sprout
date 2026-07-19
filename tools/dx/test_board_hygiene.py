"""Tests for the #732 board-hygiene lint (pure classification — no network)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from board_hygiene import (
    classify_closed_not_done,
    classify_stale_in_progress,
    milestone_counts,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def _item(status, typename="Issue", state="OPEN", closed=None, updated=None, ms=None):
    return {
        "status": status,
        "content": {
            "__typename": typename,
            "number": 1,
            "title": "x",
            "state": state,
            "closedAt": closed,
            "updatedAt": updated,
            "milestone": {"title": ms} if ms else None,
        },
    }


# --- class 1: closed-not-Done ---------------------------------------------------


def test_closed_issue_not_done_flags() -> None:
    it = _item("Needs Verification", state="CLOSED", closed="2026-07-19T10:00:00Z")
    assert classify_closed_not_done(it, NOW)


def test_merged_pr_in_ready_to_merge_flags() -> None:
    it = _item(
        "Ready to Merge",
        typename="PullRequest",
        state="MERGED",
        closed="2026-07-19T09:00:00Z",
    )
    assert classify_closed_not_done(it, NOW)


def test_closed_done_and_wont_do_pass() -> None:
    assert not classify_closed_not_done(
        _item("Done", state="CLOSED", closed="2026-07-19T09:00:00Z"), NOW
    )
    assert not classify_closed_not_done(
        _item("Won't Do", state="CLOSED", closed="2026-07-19T09:00:00Z"), NOW
    )


def test_grace_window_absorbs_automation_lag() -> None:
    fresh = (NOW - timedelta(minutes=5)).isoformat()
    assert not classify_closed_not_done(
        _item("Ready to Merge", state="MERGED", typename="PullRequest", closed=fresh),
        NOW,
    )


def test_open_items_never_class1() -> None:
    assert not classify_closed_not_done(_item("In Progress", state="OPEN"), NOW)


def test_closed_with_no_status_flags() -> None:
    it = _item(None, state="CLOSED", closed="2026-07-19T08:00:00Z")
    assert classify_closed_not_done(it, NOW)


# --- class 2: stale In Progress -------------------------------------------------


def test_stale_in_progress_flags_at_threshold() -> None:
    it = _item("In Progress", updated=(NOW - timedelta(days=4)).isoformat())
    assert classify_stale_in_progress(it, NOW, 4)


def test_active_in_progress_passes() -> None:
    it = _item("In Progress", updated=(NOW - timedelta(days=1)).isoformat())
    assert not classify_stale_in_progress(it, NOW, 4)


def test_stale_check_ignores_prs_and_other_columns() -> None:
    pr = _item(
        "In Progress",
        typename="PullRequest",
        updated=(NOW - timedelta(days=9)).isoformat(),
    )
    assert not classify_stale_in_progress(pr, NOW, 4)
    backlog = _item("Backlog", updated=(NOW - timedelta(days=30)).isoformat())
    assert not classify_stale_in_progress(backlog, NOW, 4)


# --- class 3: milestone counts --------------------------------------------------


def test_milestone_counts_open_issues_only() -> None:
    items = [
        _item("Backlog", ms="v0.8.0"),
        _item("In Progress", ms="v0.8.0"),
        _item("Done", state="CLOSED", ms="v0.8.0"),  # closed: not counted
        _item("Backlog", typename="PullRequest", ms="v0.8.0"),  # PR: not counted
        _item("Backlog", ms="v0.9.0"),
    ]
    assert milestone_counts(items) == Counter({"v0.8.0": 2, "v0.9.0": 1})
