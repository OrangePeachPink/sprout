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
import lab_notes


def _dirs() -> tuple[Path, Path, Path]:
    """(root, drafts_dir, docs_dir) - separate, like the real repo layout
    (docs/experiments/drafts/ nested under docs/experiments/), so a draft file
    and its bridged lifecycle record never collide at the same path."""
    root = Path(tempfile.mkdtemp())
    drafts_dir = root / "drafts"
    docs_dir = root / "docs"
    return root, drafts_dir, docs_dir


def test_save_load_roundtrip() -> None:
    root, drafts_dir, docs_dir = _dirs()
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
            drafts_dir,
            docs_dir=docs_dir,
        )
        assert d["subject"] == "s1 shade removal"
        assert d["duration_s"] == 600.0 and d["rate_s"] == 1.0
        assert d["labels"]["s1"] == "under shade"
        # drafts carry the full lab-note plan + the @t+ intervention markers (#326)
        assert d["notes"]["hypothesis"] == "shade off raises ADC"
        assert "@t+180s" in d["notes"]["method"]
        assert lab_drafts.load_draft("shade-recovery", drafts_dir) == d  # round-trips
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_list_drafts() -> None:
    root, drafts_dir, docs_dir = _dirs()
    try:
        lab_drafts.save_draft(
            "a-test", {"subject": "alpha"}, drafts_dir, docs_dir=docs_dir
        )
        lab_drafts.save_draft(
            "b-test", {"subject": "beta"}, drafts_dir, docs_dir=docs_dir
        )
        names = {d["name"] for d in lab_drafts.list_drafts(drafts_dir)}
        assert names == {"a-test", "b-test"}
        subjects = {d["subject"] for d in lab_drafts.list_drafts(drafts_dir)}
        assert subjects == {"alpha", "beta"}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_guards() -> None:
    root, drafts_dir, docs_dir = _dirs()
    try:
        assert lab_drafts.load_draft("nope", drafts_dir) is None  # absent
        assert lab_drafts.draft_rel_path("../etc") is None  # traversal -> no path
        raised = False
        try:
            lab_drafts.save_draft(
                "../etc", {"subject": "x"}, drafts_dir, docs_dir=docs_dir
            )
        except ValueError:
            raised = True
        assert raised, "a traversal name must be refused"
        assert lab_drafts.list_drafts(drafts_dir) == []  # nothing valid written
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_defaults_are_safe() -> None:
    # a minimal draft still has the full shape (so the UI can prefill predictably)
    root, drafts_dir, docs_dir = _dirs()
    try:
        d = lab_drafts.save_draft("min", {}, drafts_dir, docs_dir=docs_dir)
        assert d["source"] == "serial" and d["rate_s"] == 1.0
        assert set(d["notes"]) == {"hypothesis", "method", "findings", "conclusion"}
        assert d["labels"] == {}
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------- #
# draft -> planned lifecycle bridge (#450)
# --------------------------------------------------------------------------- #


def test_save_draft_registers_a_planned_record() -> None:
    root, drafts_dir, docs_dir = _dirs()
    try:
        lab_drafts.save_draft(
            "shade-recovery",
            {
                "subject": "s1 shade removal",
                "notes": {
                    "hypothesis": "shade off raises ADC",
                    "method": "@t+180s remove shade",
                    "findings": "",
                    "conclusion": "",
                },
            },
            drafts_dir,
            docs_dir=docs_dir,
        )
        planned = lab_notes.load_notes("shade-recovery", docs_dir)
        assert planned["status"] == "planned"
        assert planned["hypothesis"] == "shade off raises ADC"
        assert "@t+180s" in planned["method"]
        assert planned["edit_log"][-1]["by"] == "Sage"  # Sage-as-author default
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_save_draft_sync_planned_false_skips_the_bridge() -> None:
    root, drafts_dir, docs_dir = _dirs()
    try:
        lab_drafts.save_draft(
            "no-bridge",
            {"subject": "x"},
            drafts_dir,
            docs_dir=docs_dir,
            sync_planned=False,
        )
        assert (
            lab_notes.load_notes("no-bridge", docs_dir)["status"] is None
        )  # never written
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_resaving_a_draft_updates_the_planned_record_not_duplicates() -> None:
    root, drafts_dir, docs_dir = _dirs()
    try:
        lab_drafts.save_draft(
            "iter",
            {
                "notes": {
                    "hypothesis": "v1",
                    "method": "",
                    "findings": "",
                    "conclusion": "",
                }
            },
            drafts_dir,
            docs_dir=docs_dir,
        )
        lab_drafts.save_draft(
            "iter",
            {
                "notes": {
                    "hypothesis": "v2",
                    "method": "",
                    "findings": "",
                    "conclusion": "",
                }
            },
            drafts_dir,
            docs_dir=docs_dir,
        )
        planned = lab_notes.load_notes("iter", docs_dir)
        assert planned["hypothesis"] == "v2"  # updated, not a second record
        assert planned["version"] == 2  # two saves -> version bumped, edit_log grew
        assert len(planned["edit_log"]) == 2
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_custom_author_is_honored() -> None:
    root, drafts_dir, docs_dir = _dirs()
    try:
        lab_drafts.save_draft(
            "authored", {"subject": "x"}, drafts_dir, docs_dir=docs_dir, author="Data"
        )
        planned = lab_notes.load_notes("authored", docs_dir)
        assert planned["edit_log"][-1]["by"] == "Data"
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_save_load_roundtrip,
        test_list_drafts,
        test_guards,
        test_defaults_are_safe,
        test_save_draft_registers_a_planned_record,
        test_save_draft_sync_planned_false_skips_the_bridge,
        test_resaving_a_draft_updates_the_planned_record_not_duplicates,
        test_custom_author_is_honored,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
