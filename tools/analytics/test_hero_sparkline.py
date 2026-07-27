"""#1171 — the hero sparkline: the pulse mandate's second element. A per-plant line
of the CURRENT inter-watering segment (#1133), envelope-scaled, Tufte-quiet, and
calm-empty when there is no detected re-water to anchor a segment.

The render lives in the served ``home_template.html`` (client JS); the project idiom
is to read the template and assert the contract is wired. The payload half
(``segment_x`` on the trajectory dataset) is proven in ``test_segment_bound_trends``,
and JS validity by a ``node --check`` in the PR.
"""

from __future__ import annotations

from pathlib import Path

_H = (Path(__file__).resolve().parent / "home_template.html").read_text(
    encoding="utf-8"
)
# drawSparkline is the last function before the close; bound on the LAST </script>.
_SPARK = _H[_H.index("function drawSparkline(") : _H.rindex("</script>")]


def test_the_sparkline_is_wired_into_the_pulse() -> None:
    assert "function drawSparkline(" in _H
    # #1581 (R6): the signature grew a `card` (next_need rides it). The pin FOLLOWS the
    # call rather than being deleted -- it exists so the sparkline cannot be silently
    # unwired. Pinning the argument list also catches a refactor that drops `card`,
    # which would unwire the forecast while the chart still drew.
    assert (
        "drawSparkline(box, ds, lo, hi, inner, tok, card)" in _H
    )  # called from drawPulse


def test_the_forecast_is_drawn_with_a_boundary_not_colour_alone() -> None:
    # #1581 (R6): the predicted curve and its boundary are the point of the slice; pin
    # all THREE cues so none can quietly regress to colour-only.
    assert "next_need" in _SPARK  # the forecast's source reaches the drawing
    # 1. STYLE — pinned per dash pattern, not on a bare "setLineDash": there are TWO
    # dashed elements (the predicted line and the boundary rule), so a substring check
    # passes when either survives. Verified by regression-testing this pin itself:
    # deleting the forecast line's dash left a bare check green. Both are named now.
    assert "setLineDash([10, 8])" in _SPARK  # the predicted curve is dashed
    assert "setLineDash([4, 6])" in _SPARK  # the boundary rule is dashed
    assert "globalAlpha" in _SPARK  # 2. shading — the future region carries a wash
    assert '"now"' in _SPARK and '"predicted"' in _SPARK  # 3. labels


def test_it_clips_to_the_current_segment_never_across_a_watering() -> None:
    # segment-bound (#1133): draw only points at/after the detected re-water
    # (segment_x), never the whole window's cross-event line.
    assert "ds.segment_x" in _SPARK
    assert "p.x >= segX" in _SPARK


def test_y_is_the_in_soil_envelope_not_a_raw_axis() -> None:
    # envelope-scaled (the grill axis ruling): y maps the plant's wet-rail..dry-rail
    # envelope (lo..hi), never 0..5000, and never a raw numeral.
    assert "(p.y - lo) / (hi - lo)" in _SPARK
    assert "5000" not in _SPARK  # no raw-domain axis


def test_empty_segment_is_calm_empty_never_a_fabricated_line() -> None:
    # AC: no re-water (segment_x null) OR too few points -> calm-empty, no line.
    assert "segX === null" in _SPARK
    assert "seg.length < 4" in _SPARK
    assert 'class="calm"' in _SPARK


def test_tufte_quiet_a_ground_and_an_emphasized_now_point() -> None:
    # #1039 item 15: a band-tinted ground + the now-point emphasized; no chrome.
    assert "band-tinted ground" in _SPARK
    assert "arc(" in _SPARK  # the emphasized now-point dot
    assert "LADDER[li].token" in _SPARK  # the ladder's own hues, at ground opacity
