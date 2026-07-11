"""#919 — the trend + forecast least-squares fits exclude fault / sub-rail / OOB rows
(the #670/#697 gate), so a fault spike can't invert the trend to "wetting" on a drying
plant. Raw stays plotted (truth, #575); only the FITS drop these rows, and the count is
surfaced (`fit_excluded`) so nothing is silently dropped.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from forecast import fit_line
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.7.0  git=truthgate  run=r\n"
    "# device_id=plants_esp32_test  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_BASE = datetime(2026, 7, 8, tzinfo=timezone.utc)


def _row(mins: float, raw: int) -> str:
    ts = (_BASE + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return f"plants.soil,{ts},{ts[:-1]},sess1,s1,{raw},OK,level=OK\n"


def _sensor(ctx: dict) -> dict:
    return next(s for s in ctx["sensors"] if s["id"] == "s1")


def _trend(ctx: dict) -> dict:
    return next(d for d in ctx["trajectory"]["datasets"] if d["id"] == "s1")["trend"]


def test_fault_rows_excluded_from_the_fits_but_kept_on_the_plot(tmp_path: Path) -> None:
    # 10 clean DRYING rows (raw rises 1500 -> 2400) + 3 sub-rail fault spikes (raw=100,
    # implausible_wet) at the end — the exact shape that inverted the all-window trend.
    clean = [_row(i * 5, 1500 + i * 100) for i in range(10)]
    faults = [_row(m, 100) for m in (50, 52, 54)]
    log = tmp_path / "a.csv"
    log.write_text(_HEADER + _COLS + "".join(clean + faults), encoding="utf-8")
    ctx = build_context(parse_files([str(log)]))
    s = _sensor(ctx)

    # the 3 faults are dropped from the FITS, and the count is surfaced honestly
    assert s["fit_excluded"] == 3
    # the trend now fits the clean drying run -> positive slope (higher raw = drier)
    assert _trend(ctx)["slope"] > 0
    # ...and the forecast fit is on clean data too (drying, not a fault-driven wetting)
    assert s["slope_per_hr"] is not None and s["slope_per_hr"] > 0

    # the fault rows are STILL plotted (display = truth, never silently dropped)
    ds = next(d for d in ctx["trajectory"]["datasets"] if d["id"] == "s1")
    assert 100 in [p["y"] for p in ds["points"] if p.get("y") is not None]


def test_the_gate_actually_changes_the_slope_direction() -> None:
    # demonstrates WHY the gate matters: the same faults, left in, drag the fit down.
    clean_pairs = [(float(i), 1500 + i * 100) for i in range(10)]
    with_faults = [*clean_pairs, (50.0, 100), (52.0, 100), (54.0, 100)]
    assert fit_line(clean_pairs).slope > 0  # clean data: drying
    assert fit_line(with_faults).slope < fit_line(clean_pairs).slope  # faults drag down


def test_no_faults_leaves_the_fit_and_count_unchanged(tmp_path: Path) -> None:
    # a clean channel: nothing excluded, trend unchanged (back-compat)
    rows = [_row(i * 5, 1500 + i * 80) for i in range(8)]
    log = tmp_path / "clean.csv"
    log.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    ctx = build_context(parse_files([str(log)]))
    assert _sensor(ctx)["fit_excluded"] == 0
    assert _trend(ctx)["slope"] > 0
