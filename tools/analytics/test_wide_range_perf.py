"""#1134 — wide-range build perf: the forecast (a next-watering signal) is bounded to a
recent window for a WIDE corpus only, so a 30d build doesn't fit a meaningless 30d line
over every reading. Narrow ranges are byte-identical (bound inactive). Band-movement is
deliberately NOT bounded — it feeds the detected-rewater cue (#875 Q2), which reaches
back days.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.analytics.dashboard import (
    FORECAST_BOUND_MIN_READINGS,
    FORECAST_INPUT_H,
    build_context,
)
from tools.analytics.parse_v1 import LogData, Reading

_T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _r(sid, ts, raw):
    return Reading(
        "plants.soil",
        ts,
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
        {"level": "OK"},
    )


def _corpus(n_per_sensor, step_min):
    rs = []
    for p in range(4):
        sid = f"s{p + 1}"
        for i in range(n_per_sensor):
            rs.append(_r(sid, _T0 + timedelta(minutes=step_min * i), 1500 + (i % 500)))
    return LogData(readings=rs, segments=[], sources=["s"])


def test_wide_corpus_bounds_the_forecast_input() -> None:
    # > threshold readings, spanning far more than the forecast window -> bounded.
    per = FORECAST_BOUND_MIN_READINGS // 4 + 500  # comfortably over the wide threshold
    ctx = build_context(_corpus(per, step_min=2))  # 2-min cadence -> ~weeks of span
    fc = ctx["sensors"][0]["forecast"]
    # the "all" fit's sample count reveals what the forecast actually processed:
    # only ~the recent window, not all `per` readings.
    max_expected = int(FORECAST_INPUT_H * 60 / 2) + 5  # readings in FORECAST_INPUT_H
    assert fc["rates"]["all"]["n"] <= max_expected < per
    assert fc["raw_now"] is not None  # still anchored to the latest reading


def test_narrow_corpus_is_unbounded_byte_identical() -> None:
    # under the wide threshold -> the bound is inactive, forecast sees every reading.
    per = 800  # 4 sensors * 800 = 3200 « threshold
    ctx = build_context(_corpus(per, step_min=30))
    assert ctx["sensors"][0]["forecast"]["rates"]["all"]["n"] == per  # nothing dropped
