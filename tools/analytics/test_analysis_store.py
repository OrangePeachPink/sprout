#!/usr/bin/env python3
"""Tests for the analysis store (Lab Notebook #155).

python tools/analytics/test_analysis_store.py
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
import analysis_store as store  # noqa: E402

_CAPTURE_PY = _HERE.parents[1] / "tools" / "capture" / "experiment_capture.py"


def _capture(out_dir: Path, subject: str) -> None:
    subprocess.run(
        [
            sys.executable,
            str(_CAPTURE_PY),
            "--source",
            "synthetic",
            "--subject",
            subject,
            "--rate-s",
            "0.2",
            "--duration-s",
            "1",
            "--out-dir",
            str(out_dir),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )


def test_build_and_query() -> None:
    exp = Path(tempfile.mkdtemp())
    db = Path(tempfile.mkdtemp()) / "t.duckdb"
    try:
        _capture(exp, "alpha")
        _capture(exp, "beta")
        s = store.build_store(exp, db)
        assert s["experiments"] == 2, s
        assert s["readings"] > 0 and s["feature_rows"] >= 4

        cal = store.query(
            "SELECT DISTINCT season, is_daylight, month, hour FROM readings", db
        )
        for col in ("season", "is_daylight", "month", "hour"):
            assert col in cal.columns, col

        feat = store.query("SELECT * FROM experiment_features", db)
        for col in (
            "raw_median",
            "raw_min",
            "raw_max",
            "raw_spread",
            "raw_slope_per_hr",
            "n",
            "band",
            "subject",
        ):
            assert col in feat.columns, col
        assert feat["n"].min() >= 1
        # one row per (experiment, probe)
        uniq = feat[["experiment_id", "sensor_id"]].drop_duplicates().shape[0]
        assert len(feat) == uniq
    finally:
        shutil.rmtree(exp, ignore_errors=True)
        shutil.rmtree(db.parent, ignore_errors=True)


def test_empty_dir_rebuilds_clean() -> None:
    db = Path(tempfile.mkdtemp()) / "e.duckdb"
    try:
        s = store.build_store(Path(tempfile.mkdtemp()), db)
        assert s["experiments"] == 0 and s["readings"] == 0
        # the tables still exist + are queryable (the schema is always present)
        assert int(store.query("SELECT count(*) c FROM readings", db)["c"][0]) == 0
        feat_n = store.query("SELECT count(*) c FROM experiment_features", db)["c"][0]
        assert int(feat_n) == 0
    finally:
        shutil.rmtree(db.parent, ignore_errors=True)


if __name__ == "__main__":
    for fn in (test_build_and_query, test_empty_dir_rebuilds_clean):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
