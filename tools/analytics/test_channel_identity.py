#!/usr/bin/env python3
"""#1454 — the resolved-identity join, the S1-seam closure.

The seam: a v5 flash leaves v4 ``sN`` rows beside v5 ``chN`` rows in one window, and a
surface keying on the raw token sees one channel as two — doubling (#1432) or dropping
(#1435). This suite pins the one property that cures both: **both token generations
resolve to the same plant/channel identity**, verified on a synthetic mixed window with
one plant on one physical channel.

Native — no store, no server, no wall clock. The fixture is the whole point: an ``s1``
row and a ``ch2`` row for the same port must be indistinguishable to every consumer, so
the test builds exactly that ambiguity and asserts it collapses.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from channel_identity import (
    build_plant_index,
    channel_key,
    resolve_plant,
    resolve_plant_id,
)
from device_registry import Device, Registry

# s1 is the port that emits ch2 (parse_v1.canonical_channel / the 2026-07-01 headers).
# Written out because a fixture that guesses the pairing silently tests nothing.
S1 = "s1"
CH2 = "ch2"


def _registry(*, channel_key_in_registry: str) -> Registry:
    """One board, one plant, keyed by whichever generation the registry happens to
    carry — the axis #1315 turned on (the registry migrated on one side, not the other).
    """
    return Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32-classic",
                label="A",
                channels={
                    channel_key_in_registry: {"plant_id": "p11", "plant_name": "Fern"}
                },
            )
        ]
    )


# --------------------------------------------------------------------------- #
# The key fold — the load-bearing identity
# --------------------------------------------------------------------------- #
def test_both_generations_produce_one_key() -> None:
    """The whole seam in one line: s1 and ch2 on a device are the same join key."""
    assert channel_key("devA", S1) == channel_key("devA", CH2)


def test_an_unknown_token_gets_a_stable_key_that_does_not_collide() -> None:
    """Honest default (ADR-0028): an unrecognised token folds to itself, so it still
    has a key — it simply won't masquerade as a known channel."""
    assert channel_key("devA", "s9") == ("devA", "s9")
    assert channel_key("devA", "s9") != channel_key("devA", CH2)


def test_the_key_is_device_scoped() -> None:
    """The same channel on two boards is two identities — a join key that dropped the
    device would merge unrelated plants."""
    assert channel_key("devA", CH2) != channel_key("devB", CH2)


# --------------------------------------------------------------------------- #
# The index resolves either generation, from a registry keyed either way
# --------------------------------------------------------------------------- #
def test_a_v5_registry_resolves_a_v4_row() -> None:
    """Registry migrated to chN; a legacy sN row still on the wire resolves."""
    index = build_plant_index(_registry(channel_key_in_registry=CH2))
    assert resolve_plant_id(index, "devA", S1) == "p11"
    assert resolve_plant_id(index, "devA", CH2) == "p11"


def test_a_v4_registry_resolves_a_v5_row() -> None:
    """Registry still keyed sN (not migrated); a post-flash chN row resolves. This is
    the direction the raw-token join dropped — pre-flash history stops resolving."""
    index = build_plant_index(_registry(channel_key_in_registry=S1))
    assert resolve_plant_id(index, "devA", CH2) == "p11"
    assert resolve_plant_id(index, "devA", S1) == "p11"


def test_a_half_migrated_registry_is_not_a_source_of_doubles() -> None:
    """A registry carrying BOTH keys for one channel folds to one entry, not two —
    so a mid-migration registry can't itself produce the #1432 double."""
    reg = Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32-classic",
                label="A",
                channels={
                    S1: {"plant_id": "p11", "plant_name": "Fern"},
                    CH2: {"plant_id": "p11", "plant_name": "Fern"},
                },
            )
        ]
    )
    index = build_plant_index(reg)
    assert len(index) == 1
    assert resolve_plant_id(index, "devA", S1) == "p11"


# --------------------------------------------------------------------------- #
# The mixed window — the #1432/#1435 scenario, deduped
# --------------------------------------------------------------------------- #
def test_a_mixed_window_collapses_to_one_identity() -> None:
    """The exact #1432/#1435 fixture: a window of v4 sN rows and v5 chN rows for one
    plant. Grouping the distinct row tokens by their resolved identity yields ONE
    group, not two — the double cured, and the drop (an unresolved generation) ruled
    out because both resolve."""
    index = build_plant_index(_registry(channel_key_in_registry=CH2))
    window_tokens = [S1, S1, CH2, S1, CH2]  # both generations, one physical channel
    identities = {channel_key("devA", tok) for tok in window_tokens}
    plants = {resolve_plant_id(index, "devA", tok) for tok in window_tokens}
    assert len(identities) == 1  # one channel, not two — #1432 cured
    assert plants == {"p11"}  # every row resolves — #1435's drop ruled out


def test_resolve_plant_returns_the_whole_record_for_naming() -> None:
    """A card needs the name, an analysis surface the id — one index serves both."""
    index = build_plant_index(_registry(channel_key_in_registry=CH2))
    plant = resolve_plant(index, "devA", S1)
    assert plant is not None
    assert plant["plant_id"] == "p11" and plant["plant_name"] == "Fern"


def test_an_unregistered_channel_resolves_to_no_plant() -> None:
    """None is a real answer — a guessed plant on an unmapped channel is the failure
    mode this whole seam exists to avoid."""
    index = build_plant_index(_registry(channel_key_in_registry=CH2))
    assert resolve_plant(index, "devA", "s2") is None
    assert resolve_plant_id(index, "devZ", S1) is None  # unknown device
