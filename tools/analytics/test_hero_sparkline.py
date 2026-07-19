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
    assert "drawSparkline(box, ds, lo, hi, inner, tok)" in _H  # called from drawPulse


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
