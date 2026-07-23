#!/usr/bin/env python3
"""Tests for lab notes persistence (Lab Notebook #158).

python tools/analytics/test_lab_notes.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.analytics import lab_notes  # noqa: E402


def test_empty_when_missing() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        n = lab_notes.load_notes("nope", tmp)
        assert n["version"] == 0
        assert n["hypothesis"] == "" and n["saved_at"] is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_guards() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        assert lab_notes.load_notes("../etc", tmp)["version"] == 0  # traversal -> empty
        assert lab_notes.load_notes("a/b", tmp)["version"] == 0
        for bad in ("../etc", "a/b"):
            try:
                lab_notes.save_notes(bad, {"hypothesis": "x"}, tmp)
            except ValueError:
                continue
            raise AssertionError(f"expected ValueError for {bad!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_load_roundtrip_and_version_bump() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        s1 = lab_notes.save_notes(
            "exp1",
            {"hypothesis": "h", "method": "m", "findings": "f", "conclusion": "c"},
            tmp,
        )
        assert s1["version"] == 1 and s1["saved_at"] and s1["hypothesis"] == "h"
        assert lab_notes.load_notes("exp1", tmp) == s1  # round-trips
        s2 = lab_notes.save_notes("exp1", {"conclusion": "c2"}, tmp)
        assert s2["version"] == 2 and s2["conclusion"] == "c2"
        assert s2["hypothesis"] == "h"  # untouched field persists across partial save
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_preserves_existing_sidecar_keys() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        # a findings-report sidecar with non-notes keys must survive a notes save
        (tmp / "rep.json").write_text(
            json.dumps({"experiment_id": "rep", "states": {"air": 3170}}),
            encoding="utf-8",
        )
        lab_notes.save_notes("rep", {"findings": "ff"}, tmp)
        doc = json.loads((tmp / "rep.json").read_text(encoding="utf-8"))
        assert doc["states"] == {"air": 3170}  # anchors preserved
        assert doc["notes"]["findings"] == "ff" and doc["notes"]["version"] == 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_notes_rel_path() -> None:
    # #327: the UI shows the save target on success + failure
    assert lab_notes.notes_rel_path("expA") == "docs/experiments/expA.json"
    assert lab_notes.notes_rel_path("../etc") is None  # bad id -> no path
    assert lab_notes.notes_rel_path("a/b") is None


def test_save_stays_pure() -> None:
    # save_notes returns the persisted notes only (no transient 'path'); serve.py adds
    # the save path to the response, keeping save==load symmetric (#327).
    tmp = Path(tempfile.mkdtemp())
    try:
        n = lab_notes.save_notes("expB", {"hypothesis": "h"}, tmp)
        assert "path" not in n
        assert lab_notes.load_notes("expB", tmp) == n
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_save_failure_path_raises() -> None:
    # #327 failure path: an unwritable target (docs_dir is a FILE) raises, so the
    # endpoint reports {error, path} and the client keeps the typed text to retry.
    tmp = Path(tempfile.mkdtemp())
    try:
        blocker = tmp / "not_a_dir"
        blocker.write_text("x", encoding="utf-8")  # parent can't be a directory
        raised = False
        try:
            lab_notes.save_notes("expC", {"hypothesis": "h"}, blocker)
        except OSError:
            raised = True
        assert raised, "save into a non-directory must raise (the failure path)"
        # the target path is still computable for the error message
        assert lab_notes.notes_rel_path("expC", blocker).endswith("expC.json")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_lifecycle_status_set_and_carried() -> None:
    # #450 slice 1: status is settable, carried across saves, and advanceable.
    tmp = Path(tempfile.mkdtemp())
    try:
        s1 = lab_notes.save_notes("e", {"hypothesis": "h"}, tmp, status="planned")
        assert s1["status"] == "planned"
        s2 = lab_notes.save_notes("e", {"method": "m"}, tmp)  # no status -> carried
        assert s2["status"] == "planned"
        s3 = lab_notes.save_notes("e", {"findings": "f"}, tmp, status="complete")
        assert s3["status"] == "complete"
        assert lab_notes.load_notes("e", tmp)["status"] == "complete"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_invalid_status_raises() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        raised = False
        try:
            lab_notes.save_notes("e", {"hypothesis": "h"}, tmp, status="bogus")
        except ValueError:
            raised = True
        assert raised, "an unknown status must raise"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_edit_log_records_provenance() -> None:
    # #450 slice 1: every save appends who/when/what (Sage-as-author).
    tmp = Path(tempfile.mkdtemp())
    try:
        s1 = lab_notes.save_notes(
            "e", {"hypothesis": "h"}, tmp, status="planned", author="Sage"
        )
        assert len(s1["edit_log"]) == 1
        e1 = s1["edit_log"][0]
        assert e1["by"] == "Sage" and e1["at"] == s1["saved_at"]
        assert "hypothesis" in e1["fields"] and "status" in e1["fields"]
        s2 = lab_notes.save_notes("e", {"conclusion": "c"}, tmp)  # author defaults
        assert len(s2["edit_log"]) == 2
        assert s2["edit_log"][-1]["by"] == "unknown"
        assert s2["edit_log"][-1]["fields"] == ["conclusion"]  # no status change
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_legacy_notes_load_backward_compatible() -> None:
    # A pre-#450 sidecar (no status / edit_log) still loads with defaults, and a save
    # onto it adds the lifecycle fields without breaking the version chain.
    tmp = Path(tempfile.mkdtemp())
    try:
        (tmp / "old.json").write_text(
            json.dumps(
                {"experiment_id": "old", "notes": {"hypothesis": "h", "version": 3}}
            ),
            encoding="utf-8",
        )
        n = lab_notes.load_notes("old", tmp)
        assert n["hypothesis"] == "h" and n["version"] == 3
        assert n["status"] is None and n["edit_log"] == []  # defaults, no crash
        s = lab_notes.save_notes("old", {"findings": "f"}, tmp, status="complete")
        assert (
            s["version"] == 4 and s["status"] == "complete" and len(s["edit_log"]) == 1
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_empty_when_missing,
        test_guards,
        test_save_load_roundtrip_and_version_bump,
        test_preserves_existing_sidecar_keys,
        test_notes_rel_path,
        test_save_stays_pure,
        test_save_failure_path_raises,
        test_lifecycle_status_set_and_carried,
        test_invalid_status_raises,
        test_edit_log_records_provenance,
        test_legacy_notes_load_backward_compatible,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
