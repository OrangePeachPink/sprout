"""#1133 — the dashed trend + forecast/drying-rate windows bind to the CURRENT
inter-watering segment (since the last detected re-water), never across a watering
event. A fit across the dry-down→rewater→dry-down sawtooth averages unrelated arcs.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from band_movement import segment_start
from dashboard import build_context
from parse_v1 import LogData, Reading

_T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _r(minute, raw, level, sid="s1"):
    return Reading(
        "plants.soil",
        _T0 + timedelta(minutes=minute),
        None,
        None,
        "s",
        "dev",
        "0.7.0",
        "x",
        None,
        "UMLIFE_v2_TLC555",
        sid,
        "",
        sid,
        raw,
        None,
        "",
        "OK",
        {"level": level},
    )


def _sawtooth():
    """Dry-down → a sharp re-water (jump toward wet, lands well-watered) → dry-down."""
    rows = []
    m = 0
    # segment 1: drying out, DRY band, high raw
    for i in range(15):
        rows.append(_r(m, 2300 + i * 20, "DRY"))
        m += 30
    # the re-water: a big wettening that lands well-watered (>= 2-band jump -> detected)
    for i in range(12):
        rows.append(_r(m, 1300 + i * 15, "well watered"))
        m += 30
    # segment 2: drying again, well watered -> OK -> needs water
    for i in range(12):
        lvl = "OK" if i < 6 else "needs water"
        rows.append(_r(m, 1500 + i * 40, lvl))
        m += 30
    return rows


def test_segment_start_finds_the_last_rewater() -> None:
    rows = _sawtooth()
    seg = segment_start(rows)
    assert seg is not None
    # the re-water landed at index 15 (first "well watered" reading)
    assert seg == rows[15].timestamp_utc


def test_trend_and_forecast_bind_to_the_current_segment() -> None:
    ctx = build_context(LogData(readings=_sawtooth(), segments=[], sources=["s"]))
    s = ctx["sensors"][0]
    tj = ctx["trajectory"]["datasets"][0]
    # the trend is flagged segment-bound and fits only the post-rewater arc
    assert tj["trend"]["segment_bound"] is True
    # the forecast's "all" fit saw only the segment (24 post-rewater rows), not all 39
    assert s["forecast"]["rates"]["all"]["n"] <= 24
    # but the PLOT keeps every reading (the sawtooth is truth, never clipped)
    assert len(tj["points"]) == 39


def test_no_rewater_is_the_whole_window_byte_identical() -> None:
    # a monotone dry-down, no watering event -> segment is the whole window.
    rows = [
        _r(i * 30, 1500 + i * 20, "OK" if i < 20 else "needs water") for i in range(40)
    ]
    assert segment_start(rows) is None
    ctx = build_context(LogData(readings=rows, segments=[], sources=["s"]))
    tj = ctx["trajectory"]["datasets"][0]
    assert tj["trend"]["segment_bound"] is False
    assert ctx["sensors"][0]["forecast"]["rates"]["all"]["n"] == 40  # full window


def test_segment_x_marks_the_rewater_in_the_plot_coordinate() -> None:
    # #1171: the hero sparkline clips to the segment start, exposed in the SAME x-unit
    # as the plot points (hours since window start) so the render never re-derives it.
    ctx = build_context(LogData(readings=_sawtooth(), segments=[], sources=["s"]))
    tj = ctx["trajectory"]["datasets"][0]
    # the re-water landed at reading index 15; segment_x is that point's own x
    assert tj["segment_x"] == tj["points"][15]["x"]
    assert tj["segment_x"] > 0  # the segment starts partway into the window


def test_trend_fit_consumes_the_c0_mask_end_to_end() -> None:
    # #1244 C0: the served trend excludes watering-transient + rebound rows from the
    # fit — end-to-end through build_context. The sawtooth's post-rewater segment
    # starts with the transient drop + slow-rise rows; the mask drops them and the
    # trend reports how many (the honest "what the line did NOT average" count).
    ctx = build_context(LogData(readings=_sawtooth(), segments=[], sources=["s"]))
    trend = ctx["trajectory"]["datasets"][0]["trend"]
    assert trend is not None and trend["segment_bound"] is True
    assert trend["mask_dropped"] > 0  # the transient/rebound rows were excluded


def test_a_quiet_window_masks_nothing() -> None:
    # a monotone dry-down has no transient/rebound/flagged rows -> nothing dropped.
    rows = [
        _r(i * 30, 1500 + i * 20, "OK" if i < 20 else "needs water") for i in range(40)
    ]
    ctx = build_context(LogData(readings=rows, segments=[], sources=["s"]))
    assert ctx["trajectory"]["datasets"][0]["trend"]["mask_dropped"] == 0


def test_segment_x_is_null_when_no_rewater_so_the_sparkline_goes_calm_empty() -> None:
    # #1171: no detected re-water -> no honest segment -> null, and the render draws the
    # calm-empty caption instead of a fabricated cross-event line.
    rows = [
        _r(i * 30, 1500 + i * 20, "OK" if i < 20 else "needs water") for i in range(40)
    ]
    ctx = build_context(LogData(readings=rows, segments=[], sources=["s"]))
    assert ctx["trajectory"]["datasets"][0]["segment_x"] is None
