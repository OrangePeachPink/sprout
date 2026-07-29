"""#1494 ch.3 — the Serial-Plotter promise, guarded offline.

The starter's docs promise a live chart: *"Open the Serial Plotter → a live line. Lift
the probe out of the water cup → watch the line LEAP."* The sketch earns that by
emitting exactly one data line per read (``raw:NNN``) and keeping the voice on separate
lines.

**That rests on an invariant nobody stated as a rule.** The Serial Plotter charts
``label:value`` pairs and skips lines it cannot parse as data — so the voice lines work
*because they contain no digits*. The sketch's own comment says so:

    the Serial Plotter charts label:value lines and skips the voice lines below
    (they carry no digits), so both tools work at once

A future mood string with a number in it — *"Thirsty - 2 days since a drink"* — becomes
a phantom series on someone's chart, silently, and the sketch still compiles and still
reads correctly on the Serial Monitor. This is the on-ramp: the reader is meeting
microcontrollers for the first time and has no way to know the chart is lying.

**What this does NOT do.** It cannot confirm the promise is true on hardware — that is
ch.3's explicit bench requirement (*"the claim must be true, not plausible"*) and it is
not satisfied by any test here. This guards the one property that would break the
promise *between* bench sessions.
"""

from __future__ import annotations

import re
from pathlib import Path

SKETCH = Path(__file__).resolve().parents[2] / "arduino-starter" / "arduino-starter.ino"

# The F("...") strings returned by bandFor() — the mood lines the Plotter must ignore.
_BAND_FN = re.compile(r"bandFor\(int raw\)\s*\{(.*?)\n\}", re.S)
_FSTR = re.compile(r'F\(\s*((?:"(?:[^"\\]|\\.)*"\s*)+)\)', re.S)


def _band_strings() -> list[str]:
    src = SKETCH.read_text(encoding="utf-8")
    m = _BAND_FN.search(src)
    assert m, "bandFor() not found — the sketch changed shape; fix this locator"
    out = []
    for raw in _FSTR.findall(m.group(1)):
        out.append("".join(re.findall(r'"((?:[^"\\]|\\.)*)"', raw)))
    return out


def test_the_sketch_emits_one_parseable_data_line() -> None:
    """`raw:NNN` on its own line is what makes the chart a chart."""
    src = SKETCH.read_text(encoding="utf-8")
    assert 'Serial.print(F("raw:"))' in src
    assert "Serial.println(raw);" in src


def test_the_mood_lines_carry_no_digits() -> None:
    """THE invariant the plotter promise rests on.

    A digit in a mood line is charted as data. The sketch compiles, the Serial Monitor
    reads correctly, and the beginner's chart grows a series that means nothing.
    """
    bands = _band_strings()
    assert len(bands) >= 3, f"expected the three mood lines, found {len(bands)}"
    for b in bands:
        offending = re.findall(r"\d", b)
        assert not offending, (
            f"mood line carries digit(s) {offending}: {b!r}\n"
            "The Serial Plotter charts anything it can parse as data, so this would "
            "appear as a phantom series on the on-ramp's very first chart (#1494 ch.3)."
        )


def test_the_moods_are_the_ratified_ladder_words() -> None:
    """ch.1 shipped the word-mark bands (#1505); this keeps them from drifting back.

    The on-ramp's whole job is seeding the vocabulary a graduating user meets in Sprout
    Full — so the words are the deliverable, not decoration.
    """
    joined = " ".join(_band_strings())
    for word in ("Thirsty", "Soaked", "Content"):
        assert word in joined, f"the ratified ladder word {word!r} is gone"
