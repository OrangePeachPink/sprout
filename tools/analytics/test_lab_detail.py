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


def test_svg_is_an_instrument() -> None:
    # #325: raw-ADC axis + elapsed-time labels + honest caption (no calibrated %)
    out = lab_detail._svg(
        [{"color": "#ff0000", "points": [{"x": 0.0, "y": 1500}, {"x": 0.1, "y": 1560}]}]
    )
    assert "raw ADC" in out  # y-axis title
    assert "1560" in out and "1500" in out  # raw min/max on the y-axis
    assert "s</text>" in out  # elapsed-time x labels (seconds)
    assert "not</b> a calibrated moisture %" in out  # honest-data caption


def test_parse_interventions() -> None:
    ivs = lab_detail._parse_interventions(
        "ran the test\n@t+180s shade removed\nnoise\n@90 lamp on\n@t+300 done"
    )
    assert {"t_s": 180, "label": "shade removed"} in ivs
    assert {"t_s": 90, "label": "lamp on"} in ivs
    assert {"t_s": 300, "label": "done"} in ivs
    assert len(ivs) == 3
    # an @-marker with no label still records, with a default
    assert lab_detail._parse_interventions("@t+5s") == [
        {"t_s": 5, "label": "intervention"}
    ]
    assert lab_detail._parse_interventions("") == []
    assert lab_detail._parse_interventions(None) == []


def test_svg_renders_markers_in_range_only() -> None:
    ds = [{"color": "#f00", "points": [{"x": 0.0, "y": 1500}, {"x": 1.0, "y": 1600}]}]
    # 1800s = 0.5h -> in [0,1]h window -> drawn; 7200s = 2h -> outside -> not drawn
    out = lab_detail._svg(
        ds, [{"t_s": 1800, "label": "shade off"}, {"t_s": 7200, "label": "later"}]
    )
    assert "ivmark" in out and "shade off" in out
    assert "later" not in out  # out-of-window marker would mislead -> omitted


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
        assert "Lab notes" in out and "Save notes" in out  # notes editor (#158)
        assert "not saved yet" in out  # fresh capture has no notes yet
        assert "__SVG__" not in out and "__CARDS__" not in out  # placeholders filled
        assert "__HYP__" not in out and "__SAVED__" not in out  # notes placeholders too
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_guards,
        test_svg_helper,
        test_svg_is_an_instrument,
        test_parse_interventions,
        test_svg_renders_markers_in_range_only,
        test_render_real_capture,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
