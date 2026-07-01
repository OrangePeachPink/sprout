"""Tests for the H1/H2 decomposition render (#199).

Drives real ``env_decompose.decompose`` output through the view. The headline: the
confound verdict is shown honestly — a confounded window set says CONFOUNDED, and a
no-weather set renders H1 only with an explicit "no weather" note on H2.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import env_decompose as ed
import env_decompose_view as view

# 12 h of steady drying: raw climbs +20/h from 1500 (higher raw = drier).
_DRYING = [(float(h), 1500.0 + 20.0 * h) for h in range(13)]


def _weather(rad: list[float]) -> list[dict]:
    return [
        {"x": float(h), "radiation": r, "cloud_cover": 50} for h, r in enumerate(rad)
    ]


def test_confounded_banner() -> None:
    # radiation rises with time exactly as dryness does -> confounded
    svg = view.render_svg(
        ed.decompose(_DRYING, _weather([100.0 + 30.0 * h for h in range(13)]))
    )
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    assert "CONFOUNDED" in svg
    assert "#d9534f" in svg  # the confound (danger) color
    assert "H1 · accelerating" in svg and "H2 · sun-driven" in svg


def test_decorrelated_banner() -> None:
    rad = [300.0 if (h // 3) % 2 == 0 else 80.0 for h in range(13)]
    svg = view.render_svg(ed.decompose(_DRYING, _weather(rad)))
    assert "decorrelated" in svg and "#3b8a3b" in svg  # separable color


def test_no_weather_shows_h2_empty_note() -> None:
    svg = view.render_svg(ed.decompose(_DRYING, weather_hourly=None))
    assert "no weather coverage" in svg  # the H2 panel's honest empty note
    assert "H1 · accelerating" in svg  # H1 still renders


def test_empty_input() -> None:
    svg = view.render_svg(
        {"windows": [], "confound": {"separable": None, "note": "n/a"}}
    )
    assert "no windows" in svg
    assert svg.count("<circle") == 0


def test_a_point_per_window() -> None:
    out = ed.decompose(_DRYING, _weather([100.0 + 30.0 * h for h in range(13)]))
    n = sum(1 for w in out["windows"] if w.get("mean_raw") is not None)
    # H1 + H2 both have weather here -> at least one circle per window per panel
    assert view.render_svg(out).count("<circle") >= n


def test_render_is_deterministic() -> None:
    out = ed.decompose(_DRYING, _weather([120.0] * 13))
    assert view.render_svg(out) == view.render_svg(out)
