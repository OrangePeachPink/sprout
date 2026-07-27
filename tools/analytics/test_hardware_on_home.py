"""#1556 B6 — hardware health on the default surface, as a roll-up not a repeat."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

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
    # nothing measured -> silent, never "0 fine". #1626 added `unknown` to the tally:
    # a payload of only-unknown sensors is NOT nothing, so it must still render.
    assert (
        "if (!(inspect.length + watch.length + ok + unknown))"
        " { box.hidden = true; return; }" in _HW
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


# --------------------------------------------------------------------------- #
# #1626 — `unknown` is counted, never folded into "fine"
# --------------------------------------------------------------------------- #
def _paint(sensors: list[dict]) -> dict:
    """Run the REAL paintHardware over a stub DOM and return what it rendered.

    A string assertion would pass on a branch that never executes; this pins behaviour,
    which is what the failure mode needs — the bug being prevented is a *count* being
    silently folded into another count.
    """
    node = shutil.which("node")
    if node is None:  # pragma: no cover - CI has node (it runs `node --check`)
        pytest.skip("node not available")
    js = (
        "var _box = { innerHTML: '', hidden: false };\n"
        "var document = { getElementById: function (id) "
        "{ return id === 'hardware' ? _box : null; } };\n"
        "function esc(s) { return String(s); }\n"
        + _HW[: _HW.index("function refreshHardware")]
        + "\npaintHardware("
        + json.dumps(sensors)
        + ");\n"
        "console.log(JSON.stringify({ html: _box.innerHTML, hidden: _box.hidden }));\n"
    )
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_unknown_is_counted_separately_and_never_as_fine() -> None:
    """The live greenhouse after #1626: 8 soil sensors assessed, 3 non-soil instruments
    with no soil readings at all. Folded into `ok` the strip would assert "11 fine" —
    trading "unknown rendered as a mild claim" for "unknown rendered as a clean bill of
    health", which is strictly worse."""
    out = _paint(
        [{"status": "ok", "sensor_id": f"s{i}"} for i in range(8)]
        + [{"status": "unknown", "sensor_id": n} for n in ("as7263", "sht45", "die")]
    )
    assert "8 fine" in out["html"] and "3 unknown" in out["html"]
    assert "11 fine" not in out["html"]
    assert out["hidden"] is False


def test_a_fresh_install_says_unknown_rather_than_zero_fine_or_nothing() -> None:
    """Design's pinned case: on a first run nothing has been assessed yet. "0 fine" is a
    claim and a vanished strip is silence; "2 unknown" is the honest first-run state."""
    out = _paint([{"status": "unknown", "sensor_id": "s1"}, {"status": "unknown"}])
    assert out["hidden"] is False
    assert "2 unknown" in out["html"]
    assert "0 fine" not in out["html"] and "fine" not in out["html"]


def test_no_sensors_at_all_still_hides_the_strip() -> None:
    """Adding `unknown` to the tally must not turn the genuinely-empty case into a
    rendered strip — nothing measured is still silence."""
    assert _paint([])["hidden"] is True


def test_the_absence_is_muted_never_a_warning_colour() -> None:
    """An absence is calm. Colouring it as a warning would recreate the original bug in
    a new costume — three instruments reading as a problem when the truth is that we
    have nothing to say about them (Design's call, #1626)."""
    assert ".hardware .hw-unknown { color: var(--muted); }" in _H
    assert "hw-unknown" in _HW[_HW.index("if (ok) bits.push") :]  # after `fine`
