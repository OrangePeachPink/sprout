"""#719 masthead versions — firmware (value or honest mix) + one app==server
product version + a 'behind latest / restart needed' cue.

Veronica's 0.7.0 launch-UX retro: "I'm constantly having to ask if I am running
the latest firmware or the latest server, or do I need to restart / force-reload."
So the three versions must all resolve, and a behind/restart cue must show.
"""

from __future__ import annotations

from tools.analytics import card_context, provenance
from tools.analytics.dashboard import (
    _fw_masthead,
    _ver_tuple,
    _versions_block,
)


def _dev(name: str, fw: str | None, retired: bool = False) -> dict:
    return {"device_id": name, "name": name, "fw": fw, "retired": retired}


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
# #856: retired devices are excluded from the fw set — the ghost 0.8.0 fix
# --------------------------------------------------------------------------- #
def test_retired_device_fw_excluded_from_the_cue() -> None:
    # the retired S3 rig's historical 0.8.0 (immutable raw, never ages out) must not
    # leak into the live fw-mixed cue — same exclusion the #683 fleet count applies.
    v = _versions_block(
        [_dev("live", "0.7.0"), _dev("s3-rig", "0.8.0", retired=True)],
        {"version": "0.7.0"},
    )
    assert v["firmware"]["value"] == "0.7.0"  # single LIVE value, not a mix
    assert v["firmware"]["mixed"] is False
    assert "0.8.0" not in v["firmware"]["all"]  # the ghost is gone
    assert _fw_masthead(v) == "0.7.0"  # not "mixed (0.7.0, 0.8.0)"


def test_retired_device_does_not_trigger_behind(monkeypatch) -> None:
    # a retired board below latest must not raise the restart cue — it's not live fw
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.7.1")
    v = _versions_block(
        [_dev("live", "0.7.1"), _dev("old-rig", "0.6.0", retired=True)],
        {"version": "0.7.1"},
    )
    assert v["firmware"]["behind"] == []
    assert v["restart_needed"] is False


# --------------------------------------------------------------------------- #
# behind-latest + restart cue
# --------------------------------------------------------------------------- #
def test_device_behind_latest_firmware_is_flagged(monkeypatch) -> None:
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.7.1")
    v = _versions_block(
        [_dev("old", "0.7.0"), _dev("current", "0.7.1")], {"version": "0.7.1"}
    )
    assert v["firmware"]["latest"] == "0.7.1"
    behind = {b["device"] for b in v["firmware"]["behind"]}
    assert behind == {"old"}  # only the lower board, and only because it parses
    # #1712: this used to assert restart_needed is True — the defect, written down as
    # an expectation. A board on older firmware is fixed by FLASHING IT; restarting
    # the Monitor cannot help, and saying so trains the operator to ignore the cue.
    assert v["restart_needed"] is False
    assert v["server_stale"] is False


def test_stale_server_sets_restart_needed(monkeypatch) -> None:
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.7.0")
    v = _versions_block([_dev("A", "0.7.0")], {"version": "0.7.0", "stale": True})
    assert v["server_stale"] is True
    assert v["restart_needed"] is True  # a stale server alone triggers the cue


def test_no_false_behind_when_latest_unknown(monkeypatch) -> None:
    # firmware source absent in this checkout -> latest None -> never claim behind
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: None)
    v = _versions_block([_dev("A", "0.1.0")], {"version": "0.7.0", "stale": False})
    assert v["firmware"]["latest"] is None
    assert v["firmware"]["behind"] == []
    assert v["restart_needed"] is False


# --------------------------------------------------------------------------- #
# #1712 — restart_needed means A RESTART HELPS
# --------------------------------------------------------------------------- #
# Observed live 2026-08-20: the masthead showed "newer build - restart the Monitor"
# while app == server == 0.8.1, app_server_match true and server_stale false. The
# working tree, origin/main and the running process were all 98f17f3. Nothing newer
# existed to restart into.


def test_a_behind_board_does_not_ask_for_a_restart(monkeypatch) -> None:
    """THE bug. `restart_needed` was `stale or behind`, conflating two remedies.

    A stale server is fixed by restarting the Monitor. A board on older firmware is
    fixed by flashing the board. Telling the operator to restart for the second one is
    an instruction that cannot work — and a prompt that fires when no restart helps
    trains them to ignore it, which costs exactly when it is real.
    """
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.8.1")
    v = _versions_block(
        [_dev("classic", "0.8.1"), _dev("c5", "0.7.3")],
        {"version": "0.8.1", "stale": False},
    )
    assert v["firmware"]["behind"], "the fixture must actually have a behind board"
    assert v["restart_needed"] is False


def test_the_behind_fact_is_still_published(monkeypatch) -> None:
    """The fix must not silence a true statement — only stop it asking for a restart.

    The masthead's own accurate cue ("N boards on older fw") reads this. It sits in an
    `else if` AFTER restart_needed, so while `behind` fed that flag the correct message
    was unreachable: every behind board rendered the restart prompt instead.
    """
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.8.1")
    v = _versions_block([_dev("c5", "0.7.3")], {"version": "0.8.1", "stale": False})
    assert [b["device"] for b in v["firmware"]["behind"]] == ["c5"]
    assert v["firmware"]["latest"] == "0.8.1"


def test_matching_tree_and_server_render_no_restart_cue(monkeypatch) -> None:
    """AC2: with tree == running build, the banner does not render."""
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.8.1")
    v = _versions_block(
        [_dev("classic", "0.8.1")], {"version": "0.8.1", "stale": False}
    )
    assert v["app"] == v["server"] == "0.8.1"
    assert v["app_server_match"] is True
    assert v["restart_needed"] is False


def test_a_genuinely_newer_checkout_still_triggers_it(monkeypatch) -> None:
    """AC3, the regression that matters: the cue must still fire when it is true."""
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.8.1")
    v = _versions_block([_dev("classic", "0.8.1")], {"version": "0.8.1", "stale": True})
    assert v["restart_needed"] is True


def test_restart_needed_tracks_server_stale_exactly(monkeypatch) -> None:
    """AC1's intent: the flag derives from the versions block's own facts.

    The filing guessed at an mtime-vs-process-start comparison. There is none — the
    flag is one expression, and `behind` was the other half of it. Pinning the
    equivalence keeps a third condition from being folded in later without a cue and a
    remedy of its own.
    """
    monkeypatch.setattr(card_context, "_declared_fw_version", lambda: "0.8.1")
    for stale in (True, False):
        v = _versions_block([_dev("a", "0.7.0")], {"version": "0.8.1", "stale": stale})
        assert v["restart_needed"] is v["server_stale"] is stale
