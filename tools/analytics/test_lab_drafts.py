"""Tests for agent-prepared experiment drafts (#326).

python tools/analytics/test_lab_drafts.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_drafts


def test_save_load_roundtrip() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        d = lab_drafts.save_draft(
            "shade-recovery",
            {
                "subject": "s1 shade removal",
                "rate_s": 1.0,
                "duration_s": 600,
                "source": "serial",
                "port": "COM6",
                "labels": {"s1": "under shade"},
                "notes": {
                    "hypothesis": "shade off raises ADC",
                    "method": "@t+180s remove shade",
                    "findings": "",
                    "conclusion": "",
                },
            },
            tmp,
        )
        assert d["subject"] == "s1 shade removal"
        assert d["duration_s"] == 600.0 and d["rate_s"] == 1.0
        assert d["labels"]["s1"] == "under shade"
        # drafts carry the full lab-note plan + the @t+ intervention markers (#326)
        assert d["notes"]["hypothesis"] == "shade off raises ADC"
        assert "@t+180s" in d["notes"]["method"]
        assert lab_drafts.load_draft("shade-recovery", tmp) == d  # round-trips
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_list_drafts() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        lab_drafts.save_draft("a-test", {"subject": "alpha"}, tmp)
        lab_drafts.save_draft("b-test", {"subject": "beta"}, tmp)
        names = {d["name"] for d in lab_drafts.list_drafts(tmp)}
        assert names == {"a-test", "b-test"}
        subjects = {d["subject"] for d in lab_drafts.list_drafts(tmp)}
        assert subjects == {"alpha", "beta"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_guards() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        assert lab_drafts.load_draft("nope", tmp) is None  # absent
        assert lab_drafts.draft_rel_path("../etc") is None  # traversal -> no path
        raised = False
        try:
            lab_drafts.save_draft("../etc", {"subject": "x"}, tmp)
        except ValueError:
            raised = True
        assert raised, "a traversal name must be refused"
        assert lab_drafts.list_drafts(tmp) == []  # nothing valid written
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_defaults_are_safe() -> None:
    # a minimal draft still has the full shape (so the UI can prefill predictably)
    tmp = Path(tempfile.mkdtemp())
    try:
        d = lab_drafts.save_draft("min", {}, tmp)
        assert d["source"] == "serial" and d["rate_s"] == 1.0
        assert set(d["notes"]) == {"hypothesis", "method", "findings", "conclusion"}
        assert d["labels"] == {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_save_load_roundtrip,
        test_list_drafts,
        test_guards,
        test_defaults_are_safe,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
