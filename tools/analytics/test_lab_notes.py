#!/usr/bin/env python3
"""Tests for lab notes persistence (Lab Notebook #158).

python tools/analytics/test_lab_notes.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import lab_notes  # noqa: E402


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


if __name__ == "__main__":
    for fn in (
        test_empty_when_missing,
        test_guards,
        test_save_load_roundtrip_and_version_bump,
        test_preserves_existing_sidecar_keys,
        test_notes_rel_path,
        test_save_stays_pure,
        test_save_failure_path_raises,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
