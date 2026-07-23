"""#923 — control-surface clarity: one mental model for collection.

The maintainer's screenshot spec was a Monitor card showing 'serial: stopped' beside
'fleet: running (2 of 3 answering)' — two transports, one confusing surface. The
approved collapse: Monitor presents ONE action ('Start collection', both paths); the
serial-only baseline control moves to Diagnostics as an advanced affordance, so a user
never has to know serial vs WiFi to start. (loud-on-stop #813/#941 and honest
configured-vs-answering counts #812 already shipped and are unchanged here.)
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import TEMPLATE

_H = TEMPLATE.read_text(encoding="utf-8")
_MON = _H[_H.index('id="monitorCard"') : _H.index('id="captureCard"')]
_DIAG = _H[_H.index('id="diagnostics"') :]


def test_monitor_presents_one_collection_action() -> None:
    # #1004 guard 1: the single action starts DISABLED as an unknown-state gate
    # ("checking…"); its "Start logging" primary face is set by collRender once the
    # first status lands, so Start is never offered before the state is known.
    assert 'id="collToggle" type="button" disabled' in _MON  # the gated single action
    assert "⋯ checking…<" in _MON  # the initial unknown-state face
    assert "▶ Start logging" in _H  # the primary Start face, carried by collRender
    # #980 superseded #923's two-button pair with ONE dual-state toggle (Start when
    # stopped, Stop when running) — the button's face IS the state.
    assert 'id="collToggle"' in _MON
    assert 'id="collStart"' not in _MON and 'id="collStop"' not in _MON
    # the old two-transport labels are gone from Monitor's surface
    assert "Start all collection" not in _MON
    assert "Start collection" not in _MON  # the killed verb is gone from Monitor
    assert (
        "Start tethered board only" not in _MON
    )  # the serial-only control is not on Monitor


def test_serial_baseline_lives_in_diagnostics() -> None:
    # the serial controls relocated (ids unchanged so the wiring binds identically)
    assert 'id="monStart"' in _DIAG and 'id="monPort"' in _DIAG
    assert 'id="monStart"' not in _MON and 'id="monPort"' not in _MON
    assert "Serial baseline" in _DIAG  # labelled, and marked advanced
    assert "advanced" in _DIAG[: _DIAG.index("Reference")]


def test_first_run_launchpad_uses_the_same_vocab() -> None:
    # the NoData first-run launchpad (serve.py) says the same one thing
    serve = (Path(__file__).resolve().parent / "serve.py").read_text(encoding="utf-8")
    assert "Start logging</button>" in serve
    assert "Start all collection" not in serve
    assert (
        "Start collection" not in serve
    )  # the killed verb is gone from the launchpad too


def test_adr_0014_records_the_collapse() -> None:
    adr = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "adr"
        / "0014-operator-control-plane.md"
    ).read_text(encoding="utf-8")
    assert "#923" in adr and "advanced affordance in Diagnostics" in adr


def test_status_line_speaks_sensor_counts_not_transports() -> None:
    # #974: the last unswept surface. The served status line aggregates BOTH
    # collection paths into one honest sensor count; the transport-split
    # "serial: ... fleet: ..." render is gone. "serial"/"fleet" survive only as
    # code-level payload keys (st.monitor / st.fleet).
    coll = _H[_H.index("function collDescribe(") : _H.index("function collRender(")]
    assert (
        "bit('serial'" not in coll and "bit('fleet'" not in coll
    )  # the retired split render
    assert "' · '" not in coll  # the transport join is gone
    # the settled #923 vocabulary is what renders now
    assert "logging ${configured} board" in coll
    assert "not answering" in coll
    assert "not logging" in coll
    # #941's loud give-up reason is preserved, not dropped
    assert "give_up_reason" in coll and "stopped — " in coll
