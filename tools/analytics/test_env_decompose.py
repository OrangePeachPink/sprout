"""Tests for the H1/H2 drying-rate decomposition (#199, PRD-0002 R5).

The headline behaviour is the *honest confound check*: when radiation and dryness
move together (the 48 h baseline reality), the decomposition must report the two
hypotheses as NOT separable — never imply a sun-driven effect the data can't show.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_decompose as ed

# 12 h of steady drying: raw climbs +20/h from 1500 (higher raw = drier).
_DRYING = [(float(h), 1500.0 + 20.0 * h) for h in range(13)]


def _weather(rad_by_hour: list[float]) -> list[dict]:
    return [
        {"x": float(h), "radiation": r, "cloud_cover": 50}
        for h, r in enumerate(rad_by_hour)
    ]


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #


def test_slope_detects_drying() -> None:
    assert ed._slope_per_hour([(0.0, 1500.0), (1.0, 1520.0), (2.0, 1540.0)]) == 20.0
    assert ed._slope_per_hour([(0.0, 1500.0)]) is None  # one point -> no slope
    assert ed._slope_per_hour([(0.0, 1500.0), (1.0, 1500.0)]) == 0.0  # flat = no drying


def test_pearson() -> None:
    assert ed._pearson([1, 2, 3], [2, 4, 6]) == 1.0  # perfect positive
    assert round(ed._pearson([1, 2, 3], [3, 2, 1]), 3) == -1.0  # perfect negative
    assert ed._pearson([1, 1, 1], [1, 2, 3]) is None  # flat -> undefined


# --------------------------------------------------------------------------- #
# windowing
# --------------------------------------------------------------------------- #


def test_drying_windows() -> None:
    wins = ed.drying_windows(_DRYING, window_h=3.0)
    assert len(wins) == 4  # 12 h / 3 h
    for w in wins:
        assert abs(w["drying_rate"] - 20.0) < 1e-6  # steady +20/h drying
    # mean dryness climbs window over window (H1's axis)
    means = [w["mean_raw"] for w in wins]
    assert means == sorted(means) and means[0] < means[-1]


# --------------------------------------------------------------------------- #
# the honest confound check (the heart of #199)
# --------------------------------------------------------------------------- #


def test_confounded_set_is_not_separable() -> None:
    # radiation RISES with time, exactly as dryness does -> H1 and H2 confounded
    rad = [100.0 + 30.0 * h for h in range(13)]
    out = ed.decompose(_DRYING, _weather(rad), window_h=3.0)
    c = out["confound"]
    assert c["separable"] is False
    assert c["radiation_dryness_r"] >= 0.7
    assert "CONFOUNDED" in c["note"]
    # every window still carries both drivers paired with the drying rate
    assert all("mean_radiation" in w and "mean_raw" in w for w in out["windows"])


def test_decorrelated_set_is_separable() -> None:
    # radiation alternates high/low so it does NOT track the monotonic dryness
    rad = [300.0 if (h // 3) % 2 == 0 else 80.0 for h in range(13)]
    out = ed.decompose(_DRYING, _weather(rad), window_h=3.0)
    c = out["confound"]
    assert c["separable"] is True
    assert abs(c["radiation_dryness_r"]) < 0.7


def test_no_weather_is_honest_about_h2() -> None:
    out = ed.decompose(_DRYING, weather_hourly=None, window_h=3.0)
    c = out["confound"]
    assert c["separable"] is None and c["n_paired_windows"] == 0
    assert "H1" in c["note"] and "H2" in c["note"]
    # H1 (drying vs dryness) is still computable without weather
    assert out["windows"] and out["windows"][0]["mean_radiation"] is None


def test_empty_points() -> None:
    out = ed.decompose([], [], window_h=3.0)
    assert out["windows"] == [] and out["confound"]["separable"] is None
