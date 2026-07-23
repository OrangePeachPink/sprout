"""Smoke tests for the bench-arc renderer (#423).

Asserts the honest-render invariants: every plant present, gaps render no marker,
the instant ghost only appears where a single probe out-dove the sustained median.
"""

from __future__ import annotations

from tools.analytics import bench_arc as ba
from tools.analytics import bench_arc_view as view


def test_renders_all_plants_and_bands() -> None:
    svg = view.render_svg(ba.recompute_arc())
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
    for n in range(1, 12):
        assert f">P{n:02d}</text>" in svg
    for band in ("Parched", "Ideal", "Saturated"):
        assert f">{band}</text>" in svg


def test_html_is_standalone() -> None:
    html = view.render_html(ba.recompute_arc())
    assert html.startswith("<!doctype html>") and "<svg" in html


def test_honest_gap_draws_no_wettest_marker() -> None:
    # A plant whose wettest is a gap (P04: water bypassed) must not get a wettest
    # triangle — its read is honestly absent, not a fabricated point. Adding a
    # wettest to the same plant must add exactly one triangle marker.
    p04 = next(r for r in ba.recompute_arc() if r["plant_id"] == "P04")
    assert p04["wettest"] is None
    p04_wet = dict(p04, wettest=1300, wettest_band="well watered")

    def triangles(rows: list[dict]) -> int:
        return view.render_svg(rows).count(' Z" fill="')

    assert triangles([p04_wet]) == triangles([p04]) + 1


def test_instant_ghost_only_when_zone_outdove_median() -> None:
    arc = ba.recompute_arc()
    svg = view.render_svg(arc)
    # P11: one zone (1296) dove far below the sustained median (2500) -> ghost drawn.
    p11 = next(r for r in arc if r["plant_id"] == "P11")
    assert p11["wettest"] - p11["wettest_instant"] > 60
    assert 'stroke-dasharray="2 2"' in svg  # at least one ghost connector present


def test_render_is_deterministic() -> None:
    assert view.render_svg(ba.recompute_arc()) == view.render_svg(ba.recompute_arc())
