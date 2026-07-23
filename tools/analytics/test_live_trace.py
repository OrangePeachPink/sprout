#!/usr/bin/env python3
"""Tests for the capture-panel live trajectory (#161).

python tools/analytics/test_live_trace.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.analytics import serve  # noqa: E402

_CAPTURE_PY = _HERE.parents[1] / "tools" / "capture" / "experiment_capture.py"


def test_guards() -> None:
    assert serve._live_trace(None) == []
    assert serve._live_trace("../etc") == []  # traversal refused
    assert serve._live_trace("bad/slash") == []
    assert serve._live_trace("nope", Path(tempfile.mkdtemp())) == []


def test_trace_from_capture() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            [
                sys.executable,
                str(_CAPTURE_PY),
                "--source",
                "synthetic",
                "--subject",
                "tracetest",
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
        ds = serve._live_trace(eid, tmp)
        assert isinstance(ds, list) and len(ds) >= 1  # per-probe datasets
        assert ds[0].get("points")  # the first dataset has points
        p = ds[0]["points"][0]
        assert "x" in p and "y" in p  # points are {x, y}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (test_guards, test_trace_from_capture):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
