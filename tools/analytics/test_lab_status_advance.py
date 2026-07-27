"""#545 item 2 — the control-plane status stamp (ruling A): forward-only,
idempotent, machine-attributed, and never inventing a plan that isn't there."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.analytics.lab_notes import (
    CONTROL_PLANE_AUTHOR,
    advance_status,
    load_notes,
    save_notes,
)

EID = "2026-07-20-corn-drydown"


def _plan(docs: Path) -> None:
    save_notes(
        EID, {"hypothesis": "watch the arc"}, docs, status="planned", author="Sage"
    )


def test_the_lifecycle_advances_planned_running_complete(tmp_path: Path) -> None:
    _plan(tmp_path)
    r1 = advance_status(EID, "running", tmp_path)
    assert (r1["moved"], r1["from"], r1["to"]) == (True, "planned", "running")
    r2 = advance_status(EID, "complete", tmp_path)
    assert (r2["moved"], r2["from"], r2["to"]) == (True, "running", "complete")
    assert load_notes(EID, tmp_path)["status"] == "complete"


def test_it_never_bumps_the_prose_version_or_credits_a_human(tmp_path: Path) -> None:
    # the whole reason this isn't save_notes(status=...): a machine stamping a run
    # must not inflate the version of prose nobody wrote
    _plan(tmp_path)
    before = load_notes(EID, tmp_path)
    advance_status(EID, "running", tmp_path)
    after = load_notes(EID, tmp_path)
    assert after["version"] == before["version"]
    assert after["hypothesis"] == before["hypothesis"]  # prose untouched
    assert after["edit_log"][-1]["by"] == CONTROL_PLANE_AUTHOR
    assert after["edit_log"][-1]["fields"] == ["status"]


def test_a_repeated_signal_is_a_safe_no_op(tmp_path: Path) -> None:
    _plan(tmp_path)
    advance_status(EID, "running", tmp_path)
    n_before = len(load_notes(EID, tmp_path)["edit_log"])
    again = advance_status(EID, "running", tmp_path)
    assert again["moved"] is False and again["reason"] == "already"
    assert len(load_notes(EID, tmp_path)["edit_log"]) == n_before  # no write


def test_a_late_signal_cannot_un_complete_a_finished_run(tmp_path: Path) -> None:
    _plan(tmp_path)
    advance_status(EID, "complete", tmp_path)
    back = advance_status(EID, "running", tmp_path)
    assert back["moved"] is False and back["reason"] == "backwards"
    assert load_notes(EID, tmp_path)["status"] == "complete"  # history intact


def test_an_unplanned_capture_has_no_plan_to_advance(tmp_path: Path) -> None:
    r = advance_status("2026-07-20-never-planned", "running", tmp_path)
    assert r["moved"] is False and r["reason"] == "no-sidecar"
    assert not list(tmp_path.rglob("*.json"))  # nothing fabricated on disk


def test_create_opts_in_to_stamping_an_unplanned_capture(tmp_path: Path) -> None:
    r = advance_status(EID, "running", tmp_path, create=True)
    assert r["moved"] is True and r["from"] is None
    assert load_notes(EID, tmp_path)["status"] == "running"


def test_an_unknown_status_is_refused(tmp_path: Path) -> None:
    _plan(tmp_path)
    with pytest.raises(ValueError):
        advance_status(EID, "finished", tmp_path)
    assert load_notes(EID, tmp_path)["status"] == "planned"


def test_the_sidecar_stays_valid_json_with_its_other_keys(tmp_path: Path) -> None:
    _plan(tmp_path)
    p = next(tmp_path.rglob("*.json"))
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["anchors"] = {"kept": True}
    p.write_text(json.dumps(doc), encoding="utf-8")
    advance_status(EID, "running", tmp_path)
    after = json.loads(p.read_text(encoding="utf-8"))
    assert after["anchors"] == {"kept": True}  # never clobbers neighbouring keys
