#!/usr/bin/env python3
"""#1643 — the watering AMOUNT: optional, cup-shaped at the surface, mL on the wire.

The corpus this feeds has been frozen at n=32 since 2026-07-13 because the glug journal
records *that* a plant was watered and never *how much*. Two properties make the field
worth having rather than harmful, and both are pinned behaviourally here:

- **the no-amount watering stays one tap** — if the affordance taxes the plain case,
  the plain case loses and the corpus gains nothing anyway (she stops logging);
- **absent is absent** — a row with no amount must never be indistinguishable from a
  real 0 mL pour, or the corpus gains rows that look like measurements and aren't
  (ADR-0028).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_TPL = Path(__file__).resolve().parent / "home_template.html"
_H = _TPL.read_text(encoding="utf-8")
_JS = _H[_H.index("var CUP_ML") : _H.index("/* #1203: record her ruling")]


def _run(snippet: str) -> dict:
    """Execute the REAL glug JS over a stub DOM + fetch, and report what was posted."""
    node = shutil.which("node")
    if node is None:  # pragma: no cover - CI has node (it runs `node --check`)
        pytest.skip("node not available")
    harness = (
        "var _posts = [];\n"
        "function fetch(url, opt) {\n"
        "  _posts.push({url: url, body: JSON.parse(opt.body)});\n"
        "  return Promise.resolve({ json: function () "
        "{ return Promise.resolve({ ok: true }); } }); }\n"
        "var _glugged = new Set();\n"
        "function refresh() {}\n"
        + _JS
        + "\n"
        + snippet
        + "\nconsole.log(JSON.stringify({posts: _posts}));\n"
    )
    r = subprocess.run(
        [node, "-e", harness], capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def _fake_el(pid: str = "p03", ml: str | None = None) -> str:
    """The minimum of an element glugPost touches: a dataset and a text child."""
    ds = f'{{pid: "{pid}"' + (f', ml: "{ml}"' if ml is not None else "") + "}"
    return (
        "var el = { dataset: " + ds + ", lastChild: { nodeValue: 'Glug glug' } };\n"
        "glugPost(el);\n"
    )


# --------------------------------------------------------------------------- #
# absent is absent — the load-bearing one
# --------------------------------------------------------------------------- #
def test_a_plain_watering_posts_NO_ml_key_at_all() -> None:
    """Not 0, not null, not a default — the key is simply not there. `log_manual` only
    writes the field when it is given one, so an omitted key is the store's own
    honest-absent path rather than a value the corpus has to interpret."""
    out = _run(_fake_el())
    (post,) = out["posts"]
    assert post["body"] == {"plant_id": "p03"}
    assert "ml" not in post["body"]


def test_a_chosen_amount_rides_as_ml() -> None:
    out = _run(_fake_el(ml="118.3"))
    (post,) = out["posts"]
    assert post["body"]["plant_id"] == "p03"
    assert post["body"]["ml"] == 118.3


def test_the_plain_path_is_unchanged_code_not_a_new_branch() -> None:
    """The one-tap AC, checked structurally as well as behaviourally: the amount is an
    additive `if`, so the no-amount case runs the statements it ran before #1643."""
    assert "if (el.dataset.ml) body.ml = parseFloat(el.dataset.ml);" in _JS


# --------------------------------------------------------------------------- #
# cups at the surface, mL on the wire
# --------------------------------------------------------------------------- #
def test_cup_fractions_convert_to_the_right_millilitres() -> None:
    """Every dose in the 32-event corpus was measured in cup fractions, so the chips are
    cups and the conversion happens once, at the boundary."""
    out = _run(
        "var el = { dataset: { pid: 'p11' }, lastChild: { nodeValue: 'x' } };\n"
        "[0.25, 1/3, 0.5, 1, 2].forEach(function (c) {\n"
        "  el.dataset.ml = String(cupsToMl(c)); glugPost(el); delete el.dataset.busy;\n"
        "});\n"
    )
    got = [p["body"]["ml"] for p in out["posts"]]
    assert got == [59.1, 78.9, 118.3, 236.6, 473.2]


def test_a_third_of_a_cup_round_trips_back_to_a_third() -> None:
    """The rounding must not destroy the fraction it came from — 78.9/236.588 has to
    read back as ⅓, or the corpus can't recover how she actually measured."""
    out = _run(
        "var el = { dataset: { pid: 'p07', ml: String(cupsToMl(1/3)) },"
        " lastChild: { nodeValue: 'x' } };\nglugPost(el);\n"
    )
    ml = out["posts"][0]["body"]["ml"]
    assert abs(ml / 236.588 - 1 / 3) < 0.001


# --------------------------------------------------------------------------- #
# opening the picker is not a watering
# --------------------------------------------------------------------------- #
def test_the_chips_carry_every_amount_she_actually_measures_with() -> None:
    for frac in ("⅛", "¼", "⅓", "½", "¾", "1½"):
        assert frac in _JS, frac


def test_the_amount_control_is_separate_from_the_glug_button() -> None:
    """The plain watering must not become a two-step. The opener is its own element
    beside the button, so ignoring it leaves the one-tap path physically untouched."""
    assert 'class="glugmore"' in _H
    assert "glugAmountOpen" in _H
    # and it is keyboard-reachable like every other affordance on this surface
    assert 'role="button"' in _H and "tabindex=" in _H


def test_opening_the_picker_posts_nothing_and_then_a_chip_posts_once() -> None:
    """Two properties in one walk, because they are the interaction: revealing the
    amounts is not a watering (nothing is logged until she picks), and picking one logs
    exactly once with that amount. A stub DOM stands in for the real one."""
    out = _run(
        "var _row = null;\n"
        "function _span() { return { className: '', dataset: {}, _kids: [],"
        " textContent: '', setAttribute: function (k, v) { if (k === 'tabindex')"
        " this.tabindex = v; }, appendChild: function (c) { this._kids.push(c); },"
        " querySelector: function () { return this._kids[0]; },"
        " focus: function () {} }; }\n"
        "var document = { createElement: function () { return _span(); } };\n"
        "var opener = { dataset: { pid: 'p06' },"
        " parentNode: { replaceChild: function (n) { _row = n; } } };\n"
        "glugAmountOpen(opener);\n"
        "if (_posts.length) throw new Error('opening posted something');\n"
        "var chip = _row._kids[3];\n"  # the ½-cup chip
        "chip.lastChild = { nodeValue: chip.textContent };\n"
        "glugPost(chip);\n"
    )
    (post,) = out["posts"]
    assert post["body"] == {"plant_id": "p06", "ml": 118.3}
