#!/usr/bin/env python3
"""Tests for the experiment catalog (Lab Notebook #154).

    python tools/analytics/test_experiments_catalog.py
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
import experiments_catalog as cat  # noqa: E402


def _mk(root: Path, name: str, manifest: dict | None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    if manifest is not None:
        (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return d


def test_load_sorts_and_maps() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        _mk(tmp, "20260101_000000_old", {
            "experiment_id": "20260101_000000_old", "subject": "old",
            "started_utc": "2026-01-01T00:00:00Z", "duration_s": 30,
            "sample_rate_s": 1.0, "stopped_by": "duration", "labels": {"s1": "a"},
            "transport": {"rows": 10, "sweeps": 3, "dropped": 0, "crc_fail": 0},
        })
        _mk(tmp, "20260626_120000_new", {
            "experiment_id": "20260626_120000_new", "title": "open bench",
            "subject": "open_bench", "started_utc": "2026-06-26T12:00:00Z",
            "duration_s": 60, "transport": {"rows": 20, "sweeps": 5},
        })
        c = cat.load_catalog(tmp)
        assert len(c) == 2
        assert c[0]["experiment_id"] == "20260626_120000_new"  # newest first
        assert c[0]["title"] == "open bench"  # title preferred over subject
        assert c[1]["title"] == "old"  # falls back to subject when no title
        assert c[0]["sweeps"] == 5 and c[1]["rows"] == 10
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_skips_missing_and_bad() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        _mk(tmp, "no_manifest", None)  # dir without a manifest -> skipped
        bad = _mk(tmp, "bad", {"x": 1})
        (bad / "manifest.json").write_text("{not json", encoding="utf-8")
        _mk(tmp, "partial", {"subject": "p", "started_utc": "2026-06-26T00:00:00Z"})
        c = cat.load_catalog(tmp)
        ids = [e["experiment_id"] for e in c]
        assert "no_manifest" not in ids and "bad" not in ids
        partial = next(e for e in c if e["subject"] == "p")
        assert partial["sweeps"] is None and partial["duration_s"] is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_empty_and_missing_dir() -> None:
    assert cat.load_catalog(Path(tempfile.mkdtemp())) == []
    assert cat.load_catalog(Path(tempfile.mkdtemp()) / "nope") == []


def test_render_smoke() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        _mk(tmp, "20260626_120000_x", {
            "experiment_id": "20260626_120000_x", "title": "my <test>",
            "subject": "x", "started_utc": "2026-06-26T12:00:00Z",
            "duration_s": 60, "transport": {"rows": 20, "sweeps": 5},
        })
        out = cat.render_catalog(cat.load_catalog(tmp))
        assert "__SPROUT_TOKENS__" not in out  # token placeholder filled
        assert "__CARDS__" not in out and "__COUNT__" not in out
        assert "my &lt;test&gt;" in out  # title html-escaped
        assert "1 capture(s)" in out
        assert "No experiments yet" in cat.render_catalog([])  # empty state
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_load_sorts_and_maps,
        test_skips_missing_and_bad,
        test_empty_and_missing_dir,
        test_render_smoke,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
