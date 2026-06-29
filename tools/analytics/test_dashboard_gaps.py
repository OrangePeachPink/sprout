"""Tests for logging-gap surfacing in the dashboard (#31).

A logging interruption (board reset, logger restart, USB drop) must be obvious,
not interpolated away. build_context() computes the gaps that the three surfaces
consume — the trajectory break, the quality-strip gap marks, and the integrity
"logging gaps" table. This covers that computation end-to-end.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import GAP_THRESHOLD_S, build_context
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.7.0  git=test123  run=gaptest\n"
    "# device_id=plants_esp32_test  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts: str, sid: str, raw: int, session: str = "sess1") -> str:
    local = ts.replace("Z", "")  # _gaps needs a non-null local for its at_local label
    return (
        f"plants.soil,{ts},{local},{session},{sid},{raw},"
        "OK,level=well watered;gpio=36\n"
    )


def _write(path: Path, rows: list[str]) -> None:
    path.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")


def test_no_gap_when_continuous(tmp_path: Path) -> None:
    log = tmp_path / "cont.csv"
    _write(
        log,
        [
            _row("2026-06-28T00:00:30.000Z", "s1", 1500),
            _row("2026-06-28T00:00:30.000Z", "s2", 1550),
            _row("2026-06-28T00:01:00.000Z", "s1", 1505),
            _row("2026-06-28T00:01:00.000Z", "s2", 1555),
            _row("2026-06-28T00:01:30.000Z", "s1", 1510),
            _row("2026-06-28T00:01:30.000Z", "s2", 1560),
        ],
    )
    ctx = build_context(parse_files([str(log)]))
    assert ctx["gaps"] == [], ctx["gaps"]  # 30 s cadence < threshold -> no gap


def test_gap_surfaced_with_duration(tmp_path: Path) -> None:
    # a 6-minute interruption between two sessions must be reported, not interpolated
    log = tmp_path / "gap.csv"
    _write(
        log,
        [
            _row("2026-06-28T00:00:30.000Z", "s1", 1500, "sessA"),
            _row("2026-06-28T00:00:30.000Z", "s2", 1550, "sessA"),
            _row("2026-06-28T00:01:00.000Z", "s1", 1505, "sessA"),
            _row("2026-06-28T00:01:00.000Z", "s2", 1555, "sessA"),
            # --- ~6 min interruption (board reset / USB drop) ---
            _row("2026-06-28T00:07:00.000Z", "s1", 1600, "sessB"),
            _row("2026-06-28T00:07:00.000Z", "s2", 1650, "sessB"),
            _row("2026-06-28T00:07:30.000Z", "s1", 1605, "sessB"),
            _row("2026-06-28T00:07:30.000Z", "s2", 1655, "sessB"),
        ],
    )
    ctx = build_context(parse_files([str(log)]))
    gaps = ctx["gaps"]
    assert len(gaps) == 1, gaps
    g = gaps[0]
    # the ~6-min interruption is stated, not interpolated (exact value tracks the
    # sweep timestamps, so assert a range rather than pinning a brittle number)
    assert 5.5 <= g["dur_min"] <= 7.0, g
    assert g["x1"] > g["x0"], g  # the gap spans a real interval on the trajectory
    assert "at_local" in g, g  # has a start label for the integrity table


def test_threshold_is_the_contract(tmp_path: Path) -> None:
    # the interruption threshold is a documented constant; sub-threshold cadence
    # never raises a phantom gap (the continuous case above proves the no-gap side)
    assert GAP_THRESHOLD_S == 120
    log = tmp_path / "edge.csv"
    _write(
        log,
        [
            _row("2026-06-28T00:00:00.000Z", "s1", 1500),
            _row("2026-06-28T00:00:00.000Z", "s2", 1550),
            _row("2026-06-28T00:00:30.000Z", "s1", 1505),
            _row("2026-06-28T00:00:30.000Z", "s2", 1555),
            _row("2026-06-28T00:01:00.000Z", "s1", 1510),
            _row("2026-06-28T00:01:00.000Z", "s2", 1560),
        ],
    )
    ctx = build_context(parse_files([str(log)]))
    assert ctx["gaps"] == [], ctx["gaps"]  # 30 s cadence, no interruption
