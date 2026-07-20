"""#25 — the next-watering predictor: the tier ladder degrades gracefully, the
projection is arithmetically honest, caveats ride along, and abstention is real."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from predictor import (
    MAX_HORIZON_DAYS,
    forecast_fleet,
    median_interval_h,
    personal_threshold,
    predict_fn,
    predict_plant,
)
from segment_history import TierRow

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _rows(spec):
    return [TierRow(T0 + timedelta(minutes=m), float(v), "OK") for m, v in spec]


def _drydown(start_m, start_raw, per_step, n, step_m=30):
    return [(start_m + i * step_m, start_raw + i * per_step) for i in range(n)]


def test_personal_threshold_is_the_raw_she_actually_waters_at() -> None:
    # two waterings, preceded by raw 2000 and 2100 -> median 2050
    rows = _rows([(0, 1500), (30, 2000), (60, 1400), (90, 2100), (120, 1300)])
    waterings = [T0 + timedelta(minutes=45), T0 + timedelta(minutes=105)]
    thr, n = personal_threshold(rows, waterings)
    assert thr == 2050.0 and n == 2
    assert personal_threshold(rows, []) == (None, 0)  # nothing learnable yet


def test_median_interval_is_her_cadence() -> None:
    w = [T0, T0 + timedelta(hours=48), T0 + timedelta(hours=96)]
    assert median_interval_h(w) == (48.0, 2)
    assert median_interval_h([T0]) == (None, 0)  # one event = no interval


def test_rate_tier_projects_her_threshold_along_the_valid_arc() -> None:
    # a watering at raw 2000, then a clean +10 c/h dry-down from 1500
    pre = [(0, 1990), (30, 2000)]
    drop = [(60, 1700), (90, 1500)]  # the transient
    arc = _drydown(120, 1500, 5, 60)  # +5 per 30 min = +10 c/h
    rows = _rows(pre + drop + arc)
    watering = T0 + timedelta(minutes=61)
    now = rows[-1].timestamp_utc
    p = predict_plant(rows, now, [watering])
    assert p["tier"] == "rate"
    assert p["threshold_raw"] == 2000.0
    assert abs(p["rate_c_per_h"] - 10.0) < 0.5
    # raw at arc end ~ 1500 + 5*59 = 1795 -> (2000-1795)/10 ≈ 20.5 h
    assert 15 <= p["due_in_h"] <= 26
    assert p["due_in_days"] == round(p["due_in_h"] / 24, 2)


def test_interval_tier_is_the_cold_start_when_no_arc_is_usable() -> None:
    # freshly watered: the only recent rows are the transient — no valid drying arc
    rows = _rows([(0, 2000), (30, 2005), (60, 1500), (90, 1450)])
    w = [T0 - timedelta(hours=48), T0 + timedelta(minutes=61)]
    p = predict_plant(rows, rows[-1].timestamp_utc, w)
    assert p["tier"] == "interval"
    assert p["due_at"] is not None and p["n_samples"] >= 1
    assert "median interval" in p["reason"]


def test_abstain_is_first_class_not_a_guess() -> None:
    rows = _rows(_drydown(0, 1500, 5, 40))
    none = predict_plant(rows, rows[-1].timestamp_utc, [])
    assert none["tier"] == "none" and none["due_at"] is None
    assert none["due_in_days"] is None  # no invented number
    # exactly one watering and no usable arc -> still honest about the gap
    one = predict_plant(
        _rows([(0, 2000), (30, 1500)]), T0 + timedelta(minutes=30), [T0]
    )
    assert one["due_at"] is None and one["tier"] == "none"


def test_a_crawling_rate_never_promises_past_the_horizon() -> None:
    # +0.02 c/h against a far threshold would project years out
    rows = _rows([(i * 30, 1500 + i * 0.01) for i in range(40)])
    w = [T0 - timedelta(hours=72), T0 - timedelta(hours=24)]
    p = predict_plant(rows, rows[-1].timestamp_utc, w)
    assert p["tier"] != "rate"  # refused the absurd projection
    if p["due_in_days"] is not None:
        assert p["due_in_days"] <= MAX_HORIZON_DAYS * 2  # interval-bounded, sane


def test_caveats_ride_the_forecast_and_the_harness_adapter_matches() -> None:
    rows = _rows(
        [(0, 1990), (30, 2000), (60, 1700), (90, 1500), *_drydown(120, 1500, 5, 60)]
    )
    w = [T0 + timedelta(minutes=61)]
    profiles = {
        "p07": {
            "plant_id": "p07",
            "hydrology": {"probe_reading_caveat": "may-underread-standing-water"},
        }
    }
    fc = forecast_fleet({"p07": rows}, {"p07": w}, profiles=profiles)
    assert fc["p07"]["caveat"] == "may-underread-standing-water"
    # the C4 adapter returns a datetime (or None) with the same decision
    got = predict_fn(rows, rows[-1].timestamp_utc, w)
    assert isinstance(got, datetime)
    assert predict_fn(rows, rows[-1].timestamp_utc, []) is None
