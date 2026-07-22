#!/usr/bin/env python3
"""#1455 — the classic chart says when it is showing an old window.

The falsehood (#1429 §3): a 30d switch fetches for tens of seconds, or the client
disconnects mid-response; ``setRange`` has already highlighted the 30d button and set
``curRange``, but no paint arrives, so the chart keeps the 7d data while the selector
asserts 30d — silently. The Monitor-says-"stopped"-while-logging class (#1428).

The fix is a second piece of state: ``renderedRange`` (what the chart is actually
painted with) distinct from ``curRange`` (what the selector says). They diverge exactly
when a switch is unresolved, and ``renderFreshness`` speaks that gap in a calm voice.

**Two layers of proof**, both here:
- *presence* — the wiring exists in the template (a grep the repo already relies on for
  template JS), so a refactor that drops a piece fails;
- *behaviour* — the real ``renderFreshness`` is extracted from the template and driven
  through the state transitions in node, so we test what it *does*, not that it exists.
  (``node --check`` on the whole inline script guards syntax separately.)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"
_HTML = _TEMPLATE.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# presence — the four wiring points the honesty depends on
# --------------------------------------------------------------------------- #
def test_rendered_range_is_tracked_apart_from_the_selector() -> None:
    assert "let renderedRange" in _HTML, "the chart's true window must be its own state"


def test_a_successful_paint_advances_rendered_range() -> None:
    """Set only on a real paint, never optimistically (else it lies like the button)."""
    assert "renderedRange = curRange;  // #1455" in _HTML


def test_a_range_switch_surfaces_the_gap_at_once() -> None:
    """setRange must call renderFreshness immediately, so a slow switch is not silent
    for up to the 15s timer interval."""
    assert "renderFreshness(); refresh();" in _HTML


def test_the_marker_branch_exists_and_is_calm() -> None:
    assert "renderedRange !== curRange" in _HTML
    assert "is still loading" in _HTML  # calm voice: loading, not a fault


# --------------------------------------------------------------------------- #
# behaviour — drive the real renderFreshness through the transitions in node
# --------------------------------------------------------------------------- #
_HARNESS = r"""
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const m = html.match(/function renderFreshness\(\)\{[\s\S]*?\n\}/);
if (!m) { console.error('renderFreshness not found'); process.exit(2); }
let _t = '';
const span = { set textContent(v){ _t = v; },
               get textContent(){ return _t; }, style:{} };
global.document = { getElementById: (id) => id === 'refreshed' ? span : null };
let LIVE = true, connOk = true, curRange = '7d', renderedRange = '7d';
let DASH = { meta: { last_local: null, generated_display: 'now' } };
let lastOkMs = Date.now();
eval(m[0]);
function check(name, cond){ if(!cond){ console.error('FAIL: '+name); process.exit(1);} }

renderedRange = curRange = '7d'; renderFreshness();
check('steady', !/still loading/.test(_t));

curRange = '30d'; renderedRange = '7d'; connOk = true; renderFreshness();
check('mismatch-shown', /showing the 7d window/.test(_t));
check('mismatch-pending', /30d is still loading/.test(_t));
check('mismatch-calm', span.style.color === 'var(--muted)');

renderedRange = '30d'; renderFreshness();
check('clears', !/still loading/.test(_t));

connOk = false; curRange = '30d'; renderedRange = '7d'; renderFreshness();
check('disconnect-outranks', /disconnected/.test(_t));

connOk = true; curRange = 'all'; renderedRange = '7d'; renderFreshness();
check('all-words', /all history is still loading/.test(_t));
console.log('PASS');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_render_freshness_speaks_the_stale_window_and_clears(tmp_path: Path) -> None:
    """The state machine, exercised on the real function extracted from the template:
    steady → switch-in-flight (calm marker) → paint (clears) → disconnect (outranks) →
    the 'all' window renders as words."""
    harness = tmp_path / "h.js"
    harness.write_text(_HARNESS, encoding="utf-8")
    r = subprocess.run(
        ["node", str(harness), str(_TEMPLATE)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"behaviour failed: {r.stderr or r.stdout}"
    assert "PASS" in r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_the_inline_script_is_syntactically_valid(tmp_path: Path) -> None:
    """Silent-parse-death guard: a broken inline script shows zero console errors, so
    node --check is the only thing that catches it before the browser silently dies."""
    import re

    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", _HTML, re.S)
    big = [s for s in scripts if len(s) > 500 and "{{" not in s]
    assert big, "expected a substantial inline script to check"
    for i, s in enumerate(big):
        f = tmp_path / f"s{i}.js"
        f.write_text(s, encoding="utf-8")
        r = subprocess.run(
            ["node", "--check", str(f)], capture_output=True, text=True, timeout=30
        )
        assert r.returncode == 0, f"script block {i} has a syntax error: {r.stderr}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
