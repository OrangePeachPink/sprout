"""Tests for Reading.host_monotonic_ms (#9) - the host logger's elapsed
time.monotonic() read-side accessor. Real shape: plants_logger.py appends
``host_monotonic_ms=<ms>`` to the device payload (RotatingCsv.write, #9).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import parse_file

_COLS = "record_type,timestamp_utc,session_id,sensor_id,raw_value,quality_flag,payload"
_HEADER = "# log_start_utc=2026-07-01T00:00:00Z  tz_offset=-05:00\n"


def _write(tmp_path: Path, payload: str) -> Path:
    p = tmp_path / "one.csv"
    row = f"plants.soil,2026-07-01T00:00:30.000Z,sess001,s1,1312,OK,{payload}"
    p.write_text(f"{_HEADER}{_COLS}\n{row}\n", encoding="utf-8")
    return p


def test_reads_host_monotonic_ms(tmp_path: Path) -> None:
    csv = _write(tmp_path, "level=OK;role=diag;spread=8;gpio=34;host_monotonic_ms=1000")
    r = parse_file(csv).readings[0]
    assert r.host_monotonic_ms == 1000


def test_absent_on_a_pre_9_row_is_honest_none(tmp_path: Path) -> None:
    csv = _write(tmp_path, "level=OK;role=diag;spread=8;gpio=34")
    r = parse_file(csv).readings[0]
    assert r.host_monotonic_ms is None
