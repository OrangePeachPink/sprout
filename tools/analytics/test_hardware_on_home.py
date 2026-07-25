"""#1556 B6 — hardware health on the default surface, as a roll-up not a repeat."""

from __future__ import annotations

from pathlib import Path

_TPL = Path(__file__).resolve().parent / "home_template.html"
_H = _TPL.read_text(encoding="utf-8")
_HW = _H[_H.index("var HW_NAME_CAP") : _H.index("refresh();\nrefreshHardware();")]


def test_it_reads_the_same_endpoint_classic_reads() -> None:
    """Promoting a surface must not mint a second source able to disagree with the
    first. /sensor/health is the route classic's Diagnostics already reads (#995)."""
    assert '"/sensor/health"' in _HW
    assert 'id="hardware"' in _H


def test_could_not_ask_is_never_rendered_as_everything_is_fine() -> None:
    """ADR-0028: a fetch failure or an older server HIDES the strip. "I could not ask"
    and "all well" are different statements, and the calm one must not stand in for the
    unknown one -- the same rule that keeps Can't tell above All clear."""
    catch = _HW[_HW.index('["catch"]') :]
    assert "hidden = true" in catch
    # nothing measured -> silent, never "0 fine"
    assert (
        "if (!(inspect.length + watch.length + ok)) { box.hidden = true; return; }"
        in _HW
    )


def test_only_the_actionable_class_is_named_and_the_naming_is_capped() -> None:
    """Measured against the live greenhouse: 4 inspect + 7 watch + 0 ok, across soil
    channels AND non-soil sensors. Naming eleven ids in a chrome strip is noise, and a
    permanently-loud strip is one she learns to stop reading. inspect gets names (it is
    actionable); watch gets a count."""
    assert "var HW_NAME_CAP = 4;" in _HW
    assert "inspect.slice(0, HW_NAME_CAP)" in _HW
    assert 'more > 0 ? ", +" + more + " more"' in _HW
    watch_line = _HW[_HW.index("if (watch.length)") : _HW.index("if (ok)")]
    assert "hw-ids" not in watch_line  # counted, not named


def test_worst_first_and_never_a_band_colour() -> None:
    """A probe's condition is not a reading (the colour-roles charter): the strip uses
    the state channel, never the band ramp."""
    assert _HW.index("hw-inspect") < _HW.index("hw-watch")
    assert ".hardware .hw-inspect { color: var(--st-fault)" in _H
    assert "--band-" not in _HW


def test_the_detail_still_lives_on_the_workbench() -> None:
    """A promotion, not a move: the Home carries the roll-up and points at the full
    instrument view (ADR-0033's two surfaces, R12's separation)."""
    assert "/classic#diagnostics" in _HW
