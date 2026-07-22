#!/usr/bin/env python3
"""#1027 §5.1 - the calm discovery set, and the safety line it must hold.

The load-bearing property is not "find unregistered boards" - it is that the calm set
NEVER includes a board that is firing #1026's alarm. Design was explicit: building the
calm adopt card on the alarm seam would dress a possible base_url hijack up as a
friendly new board. So the exclusion of the alarm set is a correctness test, not a
nicety, and it gets the sharpest fixture here.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_discovery import discover_undeclared

T0 = datetime(2026, 7, 20, tzinfo=timezone.utc)


class _Row:
    def __init__(self, device_id, sensor_id, minute, board="esp32-classic"):
        self.device_id = device_id
        self.sensor_id = sensor_id
        self.timestamp_utc = T0 + timedelta(minutes=minute)
        self.board = board


def test_an_unregistered_answering_board_is_discovered() -> None:
    rows = [_Row("newbie", "s1", 0), _Row("newbie", "s2", 5)]
    got = discover_undeclared(rows, registered_ids=set())
    assert len(got) == 1
    assert got[0]["device_id"] == "newbie"


def test_a_registered_board_is_never_a_candidate() -> None:
    rows = [_Row("known", "s1", 0)]
    assert discover_undeclared(rows, registered_ids={"known"}) == []


def test_an_alarming_board_is_excluded_by_identity_not_offered_as_calm() -> None:
    """The safety line. A board answering at a registered base_url with an unregistered
    id fires #1026 (alarm). It is unregistered - so it would fall INTO the calm set
    without this exclusion. It must not: a possible hijack is never a friendly guest."""
    rows = [_Row("impostor", "s1", 0), _Row("genuine", "s1", 0)]
    got = discover_undeclared(rows, registered_ids=set(), alarm_ids={"impostor"})
    ids = {e["device_id"] for e in got}
    assert "impostor" not in ids, (
        "an alarming board must never appear as a calm candidate"
    )
    assert "genuine" in ids


def test_the_entry_carries_the_fields_the_adopt_flow_needs() -> None:
    """{device_id, board_class, first_seen, last_seen, channels_seen} - §5.2 defaults
    off board_class, the card shows age off first/last, the declaration starts from the
    real channels_seen."""
    rows = [
        _Row("c5board", "s3", 0, board="esp32-c5-devkitc-1 (official)"),
        _Row("c5board", "s4", 10),
    ]
    (e,) = discover_undeclared(rows, registered_ids=set())
    assert set(e) == {
        "device_id",
        "board",
        "board_class",
        "first_seen",
        "last_seen",
        "channels_seen",
    }
    # the raw display string is preserved verbatim (never machine-read, §6)
    assert e["board"] == "esp32-c5-devkitc-1 (official)"
    # board_class is the LEGACY host token today (the §6 gap, flagged on the issue):
    # firmware does not emit the qualified token on the wire yet.
    assert e["board_class"] == "c5"
    assert e["first_seen"] < e["last_seen"]


def test_channels_seen_are_canonical_and_deduped() -> None:
    """Both token generations for one physical channel fold to one canonical entry -
    the declaration should not see a channel twice under two names (#1454 seam)."""
    rows = [_Row("dev", "s1", 0), _Row("dev", "ch2", 5)]  # s1 == ch2
    (e,) = discover_undeclared(rows, registered_ids=set())
    assert e["channels_seen"] == ["ch2"], "s1 and ch2 are one channel; dedupe them"


def test_newest_activity_first() -> None:
    rows = [_Row("old", "s1", 0), _Row("recent", "s1", 100)]
    got = discover_undeclared(rows, registered_ids=set())
    assert [e["device_id"] for e in got] == ["recent", "old"]


def test_no_telemetry_is_a_calm_empty_not_a_crash() -> None:
    assert discover_undeclared([], registered_ids={"anything"}) == []


def test_the_payload_carries_the_undeclared_key_absent_safe() -> None:
    """registry_payload gains the key; a caller that passes nothing gets []
    (the discovery card's calm-empty), never a KeyError."""
    from registry_model import RegistryModel, registry_payload

    doc = registry_payload(RegistryModel())
    assert doc["undeclared"] == []
    doc2 = registry_payload(RegistryModel(), [{"device_id": "x"}])
    assert doc2["undeclared"] == [{"device_id": "x"}]
