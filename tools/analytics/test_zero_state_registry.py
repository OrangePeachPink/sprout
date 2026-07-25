#!/usr/bin/env python3
"""#1547 (A4, the #1541 wall) — the zero state names the REAL state.

The headline finding of the clean-checkout walk: after `just start`, pressing "Start
logging" flipped to "waiting for the first reading…" and sat there forever, with no
indication anywhere of why. The reason was that a fresh clone has zero registered
devices — nothing would ever report — and the screen had no registry awareness at all,
so three different situations rendered as one sentence, and only one of them was true.

These tests pin the three states apart, and pin the two things a fix must NOT break:
the #644 launchpad for the genuinely-configured case, and the filtered-to-zero message.
"""

from __future__ import annotations

from tools.analytics.registry_model import RegistryModel
from tools.analytics.serve import _empty_state_html, _zero_state


def _declared(name: str = "Windowsill") -> RegistryModel:
    m = RegistryModel()
    m.declare_device(name=name, board="esp32-classic", channels=[32])
    return m


def _bound() -> RegistryModel:
    m = _declared()
    pid = m.pending_devices()[0]["device_id"]
    m.bind_device(pid, "y9d41p")
    return m


# --------------------------------------------------------------------------- #
# the state machine
# --------------------------------------------------------------------------- #
def test_no_devices_is_no_boards_not_waiting() -> None:
    """The wall itself: nothing registered means nothing will EVER report."""
    state, _ = _zero_state(RegistryModel())
    assert state == "no-boards"


def test_a_declared_board_is_waiting_and_carries_its_name() -> None:
    state, facts = _zero_state(_declared("Windowsill"))
    assert state == "waiting"
    assert facts["names"] == ["Windowsill"]


def test_a_bound_board_is_ready_so_the_644_launchpad_stays() -> None:
    """DX's correction: the Start control solved a real chicken-and-egg (#644) and a
    fix must not delete it. A bound board genuinely has something to poll."""
    state, _ = _zero_state(_bound())
    assert state == "ready"


def test_a_broken_registry_degrades_to_ready_never_a_lecture() -> None:
    """A registry that can't be read must not replace the operator's launchpad with a
    message about adding boards — degrade to the pre-#1547 behavior."""

    class Broken:
        @property
        def devices(self):
            raise RuntimeError("unreadable")

        def pending_devices(self):
            raise RuntimeError("unreadable")

    assert _zero_state(Broken())[0] == "ready"


# --------------------------------------------------------------------------- #
# what the operator actually reads
# --------------------------------------------------------------------------- #
def test_the_no_boards_page_names_the_blocker_and_offers_the_next_step() -> None:
    html = _empty_state_html(False, model=RegistryModel())
    assert "No boards yet" in html
    assert "no board set up to send readings" in html  # WHY it would wait forever
    assert "Add a board" in html and "#registry" in html  # where to fix it
    assert "Start logging" not in html  # nothing to poll — don't offer it


def test_the_waiting_page_names_the_board_she_declared() -> None:
    html = _empty_state_html(False, model=_declared("Windowsill"))
    assert "Waiting for Windowsill to report" in html
    assert "Check setup" in html
    assert "No boards yet" not in html


def test_two_declared_boards_are_counted_not_arbitrarily_picked() -> None:
    m = _declared("Windowsill")
    m.declare_device(name="Desk", board="esp32-classic", channels=[33])
    html = _empty_state_html(False, model=m)
    assert "Waiting for 2 boards to report" in html


def test_the_configured_case_still_gets_the_start_launchpad() -> None:
    html = _empty_state_html(False, model=_bound())
    assert "Start logging" in html and 'id="collStart"' in html  # #644 intact
    assert "No boards yet" not in html


def test_the_filtered_to_zero_message_is_untouched() -> None:
    """That branch already has data; it must not gain board advice."""
    html = _empty_state_html(True, model=RegistryModel())
    assert "Clear the filter" in html
    assert "No boards yet" not in html and "Start logging" not in html
