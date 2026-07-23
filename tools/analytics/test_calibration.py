#!/usr/bin/env python3
"""Tests for the calibration workbench (Lab Notebook #192).

python tools/analytics/test_calibration.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
from tools.analytics import calibration  # noqa: E402


def _store_with(rows: list[tuple]) -> Path:
    import duckdb

    db = Path(tempfile.mkdtemp()) / "cal.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE readings (experiment_id VARCHAR, band VARCHAR, raw_value INTEGER)"
    )
    con.executemany("INSERT INTO readings VALUES (?,?,?)", rows)
    con.close()
    return db


def test_propose_and_export() -> None:
    db = _store_with(
        [
            ("e1", "Wet", 1100),
            ("e1", "Wet", 1150),
            ("e2", "Ideal", 1600),
            ("e2", "Ideal", 1700),
            ("e3", "Dry", 2500),
            ("e3", "Dry", 2600),
        ]
    )
    try:
        p = calibration.propose_boundaries(db)
        assert [b["band"] for b in p["bands"]] == ["Wet", "Ideal", "Dry"]  # wet->dry
        assert len(p["boundaries"]) == 2
        assert p["boundaries"][0]["between"] == ["Wet", "Ideal"]
        assert 1300 < p["boundaries"][0]["raw"] < 1450  # midpoint ~1387
        assert p["bands"][0]["experiments"] == 1

        out = Path(tempfile.mkdtemp()) / "cand.json"
        calibration.export_config(p, out)
        cfg = json.loads(out.read_text())
        bounds = cfg["cal_bounds_dry_to_wet"]
        assert bounds == sorted(bounds, reverse=True) and len(bounds) == 2  # dry>wet
        assert "PROPOSED" in cfg["note"]
        assert cfg["schema"].startswith("plants.calibration")
    finally:
        shutil.rmtree(db.parent, ignore_errors=True)


def test_single_band_no_boundary() -> None:
    db = _store_with([("e1", "Parched", 3100), ("e1", "Parched", 3200)])
    try:
        p = calibration.propose_boundaries(db)
        assert len(p["bands"]) == 1 and p["boundaries"] == []
    finally:
        shutil.rmtree(db.parent, ignore_errors=True)


if __name__ == "__main__":
    for fn in (test_propose_and_export, test_single_band_no_boundary):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
