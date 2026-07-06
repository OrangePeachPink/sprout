"""#719 masthead versions — firmware (value or honest mix) + one app==server
product version + a 'behind latest / restart needed' cue.

Veronica's 0.7.0 launch-UX retro: "I'm constantly having to ask if I am running
the latest firmware or the latest server, or do I need to restart / force-reload."
So the three versions must all resolve, and a behind/restart cue must show.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dashboard
import provenance
from dashboard import (
    _fw_masthead,
    _ver_tuple,
    _versions_block,
)


def _dev(name: str, fw: str | None) -> dict:
    return {"device_id": name, "name": name, "fw": fw}


# --------------------------------------------------------------------------- #
# version comparison is honest — only compares where both parse numerically
# --------------------------------------------------------------------------- #
def test_ver_tuple_parses_and_compares() -> None:
    assert _ver_tuple("0.7.0") == (0, 7, 0)
    assert _ver_tuple("v0.7.1") == (0, 7, 1)
    assert _ver_tuple("0.7.0") < _ver_tuple("0.7.1")
    assert _ver_tuple("0.6.9") < _ver_tuple("0.10.0")  # numeric, not lexical
    # a non-numeric/absent value never fabricates an order
    assert _ver_tuple(None) == ()
    assert _ver_tuple("0.7.0-rc1") == (0, 7, 0)  # suffix truncates, doesn't crash


# --------------------------------------------------------------------------- #
# app == server by construction: both read the one product constant
# --------------------------------------------------------------------------- #
def test_product_version_is_read_from_pyproject() -> None:
    # the single product line exists and parses to a dotted version
    assert provenance.product_version() is not None
    assert _ver_tuple(provenance.product_version())  # non-empty -> numeric


def test_app_and_server_are_the_same_constant() -> None:
    server = {"version": "0.7.1", "stale": False}
    v = _versions_block([_dev("A", "0.7.0")], server)
    assert v["app"] == v["server"] == "0.7.1"
    assert v["app_server_match"] is True


# --------------------------------------------------------------------------- #
# fleet firmware — a single agreed value, or the honest mix (never a bare '?')
# --------------------------------------------------------------------------- #
def test_single_firmware_value_when_fleet_agrees() -> None:
    v = _versions_block([_dev("A", "0.7.0"), _dev("B", "0.7.0")], {"version": "0.7.0"})
    assert v["firmware"]["value"] == "0.7.0"
    assert v["firmware"]["mixed"] is False
    assert _fw_masthead(v) == "0.7.0"


def test_mixed_firmware_is_surfaced_not_averaged() -> None:
    v = _versions_block([_dev("A", "0.6.9"), _dev("B", "0.7.0")], {"version": "0.7.0"})
    assert v["firmware"]["value"] is None
    assert v["firmware"]["mixed"] is True
    assert v["firmware"]["all"] == ["0.6.9", "0.7.0"]  # sorted numerically
    assert _fw_masthead(v) == "mixed (0.6.9, 0.7.0)"


def test_no_firmware_reported_gives_none_not_a_guess() -> None:
    v = _versions_block([_dev("A", None)], {"version": "0.7.0"})
    assert _fw_masthead(v) is None


# --------------------------------------------------------------------------- #
# behind-latest + restart cue
# --------------------------------------------------------------------------- #
def test_device_behind_latest_firmware_is_flagged(monkeypatch) -> None:
    monkeypatch.setattr(dashboard, "_declared_fw_version", lambda: "0.7.1")
    v = _versions_block(
        [_dev("old", "0.7.0"), _dev("current", "0.7.1")], {"version": "0.7.1"}
    )
    assert v["firmware"]["latest"] == "0.7.1"
    behind = {b["device"] for b in v["firmware"]["behind"]}
    assert behind == {"old"}  # only the lower board, and only because it parses
    assert v["restart_needed"] is True


def test_stale_server_sets_restart_needed(monkeypatch) -> None:
    monkeypatch.setattr(dashboard, "_declared_fw_version", lambda: "0.7.0")
    v = _versions_block([_dev("A", "0.7.0")], {"version": "0.7.0", "stale": True})
    assert v["server_stale"] is True
    assert v["restart_needed"] is True  # a stale server alone triggers the cue


def test_no_false_behind_when_latest_unknown(monkeypatch) -> None:
    # firmware source absent in this checkout -> latest None -> never claim behind
    monkeypatch.setattr(dashboard, "_declared_fw_version", lambda: None)
    v = _versions_block([_dev("A", "0.1.0")], {"version": "0.7.0", "stale": False})
    assert v["firmware"]["latest"] is None
    assert v["firmware"]["behind"] == []
    assert v["restart_needed"] is False
