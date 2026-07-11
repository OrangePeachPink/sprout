"""#976 — out-of-order /data.json responses must never paint the wrong chart.

Two /data.json requests are routinely in flight at once (the operator's range switch
AND the live-poll timer). Before the fix, whichever finished last painted last — a
stale-range response landing after a newer request briefly rendered the wrong chart.

This drives the REAL ``refresh()`` extracted from the template through node, with a
controllable fetch, and proves the request-generation guard: only the newest request's
payload can reach DASH / renderAll, regardless of arrival order.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_TPL = (_HERE / "dashboard_template.html").read_text(encoding="utf-8")


def _extract_refresh() -> str:
    """The real ``let __reqGen`` + ``async function refresh(){...}`` block, verbatim."""
    start = _TPL.index("let __reqGen = 0;")
    end = _TPL.index("/* ---- time-range selector", start)
    block = _TPL[start:end].strip()
    assert "async function refresh()" in block
    return block


_HARNESS = """
'use strict';
// ---- stubbed globals the extracted refresh() closes over ----
let LIVE = true, curRange = '24h', activeChannels = null;
let DASH = null, connOk = true, lastOkMs = 0;
const painted = [];   // every renderAll() records the DASH tag it painted
function liveChannelIds() { return []; }
function renderAll() { painted.push(DASH && DASH.tag); }
function renderFreshness() {}
function flash() {}
const _btn = { classList: { add() {}, remove() {} }, disabled: false };
const document = { getElementById: () => _btn };
// controllable fetch: each call parks its resolver so the test drives arrival ORDER
const _resolvers = [];
function fetch(_url) { return new Promise((res) => { _resolvers.push(res); }); }
function _resp(payload, ok = true) { return { ok, json: async () => payload }; }
const _tick = () => new Promise((r) => setTimeout(r, 0));

__REFRESH__

async function scenario_stale_lands_last() {
  DASH = null; painted.length = 0; connOk = true; _resolvers.length = 0;
  const p1 = refresh();            // generation 1 (the operator's first range)
  const p2 = refresh();            // generation 2 (the switch/poll that supersedes it)
  await _tick();
  _resolvers[1](_resp({ tag: 'B' }));   // the NEWER request answers first...
  await _tick();
  _resolvers[0](_resp({ tag: 'A' }));   // ...the STALE one lands last (the bug trigger)
  await Promise.allSettled([p1, p2]);
  return { painted: [...painted], finalDASH: DASH && DASH.tag };
}

async function scenario_superseded_failure_is_not_live_state() {
  DASH = null; painted.length = 0; connOk = true; _resolvers.length = 0;
  const p1 = refresh();            // generation 1 — will FAIL, but is superseded
  const p2 = refresh();            // generation 2 — succeeds
  await _tick();
  _resolvers[1](_resp({ tag: 'B' }));   // newest succeeds
  await _tick();
  _resolvers[0](_resp(null, false));    // stale fails AFTER — must not flip connOk
  await Promise.allSettled([p1, p2]);
  return { finalDASH: DASH && DASH.tag, connOk };
}

(async () => {
  const out = {
    stale_last: await scenario_stale_lands_last(),
    superseded_fail: await scenario_superseded_failure_is_not_live_state(),
  };
  console.log(JSON.stringify(out));
})();
"""


def _run_node(js: str) -> dict:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - CI has node (it runs `node --check`)
        pytest.skip("node not available")
    r = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_a_stale_response_landing_last_never_paints() -> None:
    out = _run_node(_HARNESS.replace("__REFRESH__", _extract_refresh()))
    stale = out["stale_last"]
    # only the NEWEST payload (B) painted; the stale A that arrived last was dropped
    assert stale["painted"] == ["B"], stale
    assert stale["finalDASH"] == "B", stale
    assert "A" not in stale["painted"]  # the wrong chart is never rendered


def test_a_superseded_requests_failure_does_not_flip_the_live_state() -> None:
    out = _run_node(_HARNESS.replace("__REFRESH__", _extract_refresh()))
    sf = out["superseded_fail"]
    assert sf["finalDASH"] == "B", sf
    assert sf["connOk"] is True, sf  # a stale fetch's late failure isn't the live state
