"""#923 — control-surface clarity: one mental model for collection.

The maintainer's screenshot spec was a Monitor card showing 'serial: stopped' beside
'fleet: running (2 of 3 answering)' — two transports, one confusing surface. The
approved collapse: Monitor presents ONE action ('Start collection', both paths); the
serial-only baseline control moves to Diagnostics as an advanced affordance, so a user
never has to know serial vs WiFi to start. (loud-on-stop #813/#941 and honest
configured-vs-answering counts #812 already shipped and are unchanged here.)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import TEMPLATE

_H = TEMPLATE.read_text(encoding="utf-8")
_MON = _H[_H.index('id="monitorCard"') : _H.index('id="captureCard"')]
_DIAG = _H[_H.index('id="diagnostics"') :]


def test_monitor_presents_one_collection_action() -> None:
    assert "▶ Start collection<" in _MON  # the single primary action
    assert 'id="collStart"' in _MON and 'id="collStop"' in _MON
    # the old two-transport labels are gone from Monitor's surface
    assert "Start all collection" not in _MON
    assert "Start logging" not in _MON  # the serial-only button is not on Monitor


def test_serial_baseline_lives_in_diagnostics() -> None:
    # the serial controls relocated (ids unchanged so the wiring binds identically)
    assert 'id="monStart"' in _DIAG and 'id="monPort"' in _DIAG
    assert 'id="monStart"' not in _MON and 'id="monPort"' not in _MON
    assert "Serial baseline" in _DIAG  # labelled, and marked advanced
    assert "advanced" in _DIAG[: _DIAG.index("Reference")]


def test_first_run_launchpad_uses_the_same_vocab() -> None:
    # the NoData first-run launchpad (serve.py) says the same one thing
    serve = (Path(__file__).resolve().parent / "serve.py").read_text(encoding="utf-8")
    assert "Start collection</button>" in serve
    assert "Start all collection" not in serve


def test_adr_0014_records_the_collapse() -> None:
    adr = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "adr"
        / "0014-operator-control-plane.md"
    ).read_text(encoding="utf-8")
    assert "#923" in adr and "advanced affordance in Diagnostics" in adr
