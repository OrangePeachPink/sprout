#!/usr/bin/env python3
"""Tests for lab studies - group captures into a roll-up (Lab Notebook #159).

python tools/analytics/test_lab_studies.py
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.analytics import lab_studies  # noqa: E402


def test_missing_and_guards() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        assert lab_studies.load_study("nope", tmp) is None
        assert lab_studies.list_studies(tmp) == []
        for bad in ("../etc", "a/b"):
            try:
                lab_studies.save_study(bad, {"name": "x"}, tmp)
            except ValueError:
                continue
            raise AssertionError(f"expected ValueError for {bad!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_create_update_and_member_norm() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        s1 = lab_studies.save_study(
            "cup-char",
            {
                "name": "Cup characterization",
                "thesis": "Bracket one cup.",
                "members": "cap_wet, cap_dry\ncap_air",
            },
            tmp,
        )
        assert s1["version"] == 1 and s1["name"] == "Cup characterization"
        assert s1["members"] == ["cap_wet", "cap_dry", "cap_air"]
        # update bumps version; members re-normalize (unique + reject traversal)
        s2 = lab_studies.save_study(
            "cup-char", {"members": ["cap_wet", "cap_wet", "../x", "cap_new"]}, tmp
        )
        assert s2["version"] == 2
        assert s2["members"] == ["cap_wet", "cap_new"]
        assert s2["thesis"] == "Bracket one cup."  # untouched field persists
        assert lab_studies.load_study("cup-char", tmp) == s2  # round-trips
        assert [s["study_id"] for s in lab_studies.list_studies(tmp)] == ["cup-char"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_render_catalog_and_detail() -> None:
    tmp = Path(tempfile.mkdtemp())
    sdir, exp = tmp / "studies", tmp / "exp"
    try:
        lab_studies.save_study(
            "cup-char",
            {
                "name": "Cup characterization",
                "thesis": "Bracket one cup.",
                "conclusion": "Endpoints fixed.",
                "members": "missing_cap",
            },
            sdir,
        )
        cat = lab_studies.render_studies_catalog(lab_studies.list_studies(sdir))
        assert "Cup characterization" in cat and "Create study" in cat
        assert "__CONTENT__" not in cat and "__TITLE__" not in cat
        det = lab_studies.render_study_detail("cup-char", sdir, exp)
        assert det is not None
        assert "Bracket one cup." in det and "Members side-by-side" in det
        assert "capture not found locally" in det  # member absent -> graceful card
        assert lab_studies.render_study_detail("nope", sdir, exp) is None  # 404
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_missing_and_guards,
        test_create_update_and_member_norm,
        test_render_catalog_and_detail,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
