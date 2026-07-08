"""#841 — the trajectory x-axis counts back from now=0 at the right edge ("hours
ago"), not forward from the window start. now (the latest reading) is pinned to the
right edge so the live point stops floating each load; the window scales to the
selected range. This is a template-JS change, so it's pinned the same way #821 pinned
the 48h chip: string-assertions against the rendered ``TEMPLATE``.

Scope guard: only the two *trajectory* charts (overview + per-probe detail) flip;
the Diagnostics spread chart intentionally keeps forward "hours since start".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import TEMPLATE

_HTML = TEMPLATE.read_text(encoding="utf-8")


def test_hours_ago_axis_helper_exists() -> None:
    # the anchoring helper that pins now=0 to the right edge and windows to the range
    assert "function hoursAgoX(datasets, xTitle){" in _HTML
    assert "x.max = maxX;" in _HTML  # latest reading = right edge = now
    # left edge = now - selected window (None-range => auto/full)
    assert "x.min = (hrs == null) ? undefined : minX;" in _HTML


def test_tick_labels_read_hours_ago_relative_to_now() -> None:
    # 0 at the right renders "now"; earlier ticks are negative hours-ago (v - this.max),
    # snapped to the half-hour so 1h/3h windows don't fold -0.5h into "now"
    assert "Math.round((v - this.max) * 2) / 2" in _HTML  # relative to now, snapped
    assert "d === 0 ? 'now' : d + 'h'" in _HTML  # 0 => now, else negative hours-ago


def test_ticks_are_anchored_at_now_on_the_right_edge() -> None:
    # afterBuildTicks forces an evenly-spaced set anchored AT maxX (now), so a "now"
    # label lands exactly on the right edge instead of floating with Chart.js defaults
    assert "x.afterBuildTicks = (scale) => {" in _HTML
    assert (
        "for (let v = scale.max; v > lo + 1e-6; v -= step) ticks.push({ value: v });"
        in _HTML
    )
    assert "ticks.push({ value: lo });" in _HTML  # always include the true left edge


def test_both_trajectory_charts_use_the_hours_ago_axis() -> None:
    # overview (renderTraj) + per-probe detail (buildDetailChart) both anchor to now
    assert _HTML.count("hoursAgoX(datasets, 'hours ago  (0 = now, at right)')") == 2


def test_no_forward_hours_since_left_on_a_trajectory_chart() -> None:
    # the old forward "hours since <start>" label must be gone from the trajectory
    # charts (it survives only on the Diagnostics spread chart, asserted below)
    assert "hours since ${DASH.trajectory.start_axis" not in _HTML


def test_diagnostics_spread_chart_is_out_of_scope() -> None:
    # scoping guard: the spread/distribution diagnostic keeps forward hours-since —
    # this fix is deliberately trajectory-only, not a repo-wide axis flip.
    assert "baseScales('hours since start (local)', 'raw spread (counts)')" in _HTML
