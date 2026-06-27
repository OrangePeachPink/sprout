#!/usr/bin/env python3
"""Tests for the experiment detail view (Lab Notebook #157).

python tools/analytics/test_lab_detail.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import lab_detail  # noqa: E402

_CAPTURE_PY = _HERE.parents[1] / "tools" / "capture" / "experiment_capture.py"


def test_guards() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        assert lab_detail.render_detail("does_not_exist", tmp) is None
        assert lab_detail.render_detail("../etc", tmp) is None  # traversal refused
        assert lab_detail.render_detail("bad/slash", tmp) is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_svg_helper() -> None:
    out = lab_detail._svg(
        [
            {"color": "#ff0000", "points": [{"x": 0.0, "y": 10}, {"x": 1.0, "y": 20}]},
            {"color": "#00ff00", "points": [{"x": 0.0, "y": 5}, {"x": 1.0, "y": 8}]},
        ]
    )
    assert "<svg" in out and out.count("<polyline") == 2
    assert "#ff0000" in out and "#00ff00" in out
    assert lab_detail._svg([]) == '<p class="empty">no trajectory</p>'


def test_render_real_capture() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            [
                sys.executable,
                str(_CAPTURE_PY),
                "--source",
                "synthetic",
                "--subject",
                "testcap",
                "--rate-s",
                "0.2",
                "--duration-s",
                "1",
                "--out-dir",
                str(tmp),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        eid = next(d.name for d in tmp.iterdir() if d.is_dir())
        out = lab_detail.render_detail(eid, tmp)
        assert out is not None
        assert "testcap" in out  # title
        assert "<polyline" in out  # trajectory rendered
        assert "median" in out and "samples" in out  # per-probe stat cards
        assert "__SVG__" not in out and "__CARDS__" not in out  # placeholders filled
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (test_guards, test_svg_helper, test_render_real_capture):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
