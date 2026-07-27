"""#839 Fix B — a multi-day logging gap is a *window boundary*: the trajectory PLOTS
only the most recent contiguous run, so a stale pre-gap pocket (e.g. reconnect-storm
data a coalesced identity legitimately inherited, #602/#712) can't stretch the axis or
bury the live signal. Stats / forecast / band-history keep the FULL windowed data
(the #80 doctrine — only the plotted points clip). Composes with #841 (now = 0 right).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from tools.analytics.dashboard import (
    TRAJ_GAP_BOUNDARY_H,
    _recent_run_start,
    build_context,
)
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# fw=0.7.0  git=test123  run=gapboundary\n"
    "# device_id=plants_esp32_test  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts: str, sid: str, raw: int, session: str = "sess1") -> str:
    local = ts.replace("Z", "")
    return f"plants.soil,{ts},{local},{session},{sid},{raw},OK,level=OK;gpio=36\n"


def _at(base: datetime, mins: float) -> str:
    return (base + timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _plot_pts(ctx: dict, sid: str = "s1") -> list[dict]:
    ds = next(d for d in ctx["trajectory"]["datasets"] if d["id"] == sid)
    return [p for p in ds["points"] if p.get("y") is not None]


# --------------------------------------------------------------------------- #
# _recent_run_start
# --------------------------------------------------------------------------- #


def _soil(*offsets_h: float) -> list:
    base = datetime(2026, 6, 28, tzinfo=timezone.utc)
    return [SimpleNamespace(timestamp_utc=base + timedelta(hours=h)) for h in offsets_h]


def test_recent_run_start_walks_back_to_the_last_multiday_gap() -> None:
    # a stale pocket at 0/0.01 h, a 48 h gap, then a recent run at 48/48.01/48.02 h
    soil = _soil(0.0, 0.01, 48.0, 48.01, 48.02)
    rs = _recent_run_start(soil, TRAJ_GAP_BOUNDARY_H)
    assert rs == soil[2].timestamp_utc  # first reading AFTER the 48 h gap


def test_recent_run_start_is_the_first_reading_when_contiguous() -> None:
    soil = _soil(0.0, 0.5, 1.0, 1.5)  # no gap >= boundary
    assert _recent_run_start(soil, TRAJ_GAP_BOUNDARY_H) == soil[0].timestamp_utc


def test_recent_run_start_ignores_sub_boundary_gaps() -> None:
    # a 6 h dropout is a normal interruption, NOT a window boundary
    soil = _soil(0.0, 0.5, 6.5, 7.0)
    assert _recent_run_start(soil, TRAJ_GAP_BOUNDARY_H) == soil[0].timestamp_utc


# --------------------------------------------------------------------------- #
# build_context: the plot clips, the stats don't
# --------------------------------------------------------------------------- #


def test_trajectory_plots_only_the_recent_run_after_a_multiday_gap(
    tmp_path: Path,
) -> None:
    base = datetime(2026, 6, 28, tzinfo=timezone.utc)
    stale = [_row(_at(base, m), "s1", 1200 + int(m)) for m in (0, 0.5, 1.0)]
    # 2-day gap, then a 5-point recent run
    recent = [_row(_at(base, 2 * 24 * 60 + m), "s1", 2400 + int(m)) for m in range(5)]
    log = tmp_path / "bimodal.csv"
    log.write_text(_HEADER + _COLS + "".join(stale + recent), encoding="utf-8")
    ctx = build_context(parse_files([str(log)]))

    pts = _plot_pts(ctx)
    assert len(pts) == 5  # only the recent run is plotted; the 3 stale points are gone
    # the recent run sits ~48 h after start (hours-since-start), never at x~0
    assert min(p["x"] for p in pts) > 24.0
    # the dashed trend describes the recent run, not the full 0..48 h span
    ds = next(d for d in ctx["trajectory"]["datasets"] if d["id"] == "s1")
    assert ds["trend"] is not None
    assert ds["trend"]["x0"] > 24.0

    # ...but the STATS keep the full windowed data (#80): all 8 readings counted
    per_dev = ctx["integrity"]["per_device"]
    assert sum(d["n"] for d in per_dev) == 8


def test_contiguous_run_is_unchanged_byte_for_byte(tmp_path: Path) -> None:
    # no multi-day gap -> recent_start == start -> the plot keeps every reading
    base = datetime(2026, 6, 28, tzinfo=timezone.utc)
    rows = [_row(_at(base, m), "s1", 1500 + m) for m in range(6)]
    log = tmp_path / "cont.csv"
    log.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    ctx = build_context(parse_files([str(log)]))

    pts = _plot_pts(ctx)
    assert len(pts) == 6  # nothing clipped
    assert min(p["x"] for p in pts) == 0.0  # still anchored at the true start
