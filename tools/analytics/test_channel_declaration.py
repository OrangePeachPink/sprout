#!/usr/bin/env python3
"""#1027 — the channel declaration: what a board declares it *has*.

Trellis ruled Option A on #1027: **a channel is a first-class board declaration**, not
an artifact of an assignment — and framed it as a *regression fix*, because ADR-0036 §1
already says so. The firmware declares channels on every telemetry row; a board with
zero plants still emits ``ch0..ch3``. The static registry's ``devices[].channels{}``
got this right and the temporal model dropped it.

**These tests are written against Design-QA's six stated needs**, one section each, so
the contract is checked rather than the implementation admired. The sixth — telling a
default we assumed from a fact she stated — is the one they flagged for review, and it
is the one with no natural failure mode: both produce the same integer, so nothing
breaks visibly when they are conflated. It only shows up later, as a surface that
overclaims or nags.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry_model import (
    Assignment,
    Plant,
    RegistryModel,
    apply_operations,
    load_model,
    save_model,
)

T1 = "2026-07-10T00:00:00Z"
T2 = "2026-07-20T00:00:00Z"


def _adopt(model: RegistryModel, pins=(36, 39, 34, 35), source="stated", now=T1):
    return apply_operations(
        model,
        {
            "devices": {
                "add": [
                    {
                        "device_id": "devA",
                        "base_url": "http://x",
                        "channels": list(pins),
                        "channel_source": source,
                    }
                ]
            }
        },
        now=now,
    )


# --------------------------------------------------------------------------- #
# Need 1 — channel count at adoption (§5.2's gate)
# --------------------------------------------------------------------------- #
def test_n1_the_count_is_whatever_the_board_declares() -> None:
    """*"Could have one sensor, could have 4, could have 6."* The count is not a
    constant of the product; it is a fact about her board."""
    for n in (1, 4, 6):
        m = RegistryModel()
        _adopt(m, pins=tuple(range(n)))
        assert m.declared_channel_count("devA") == n


def test_n1b_a_board_that_declares_nothing_is_not_adoptable() -> None:
    """The ruling: *"no-plants-yet is legitimate; no-pin-config is not an adoptable
    board."* Enforced at the seam, not on the surface — a surface-only check leaves the
    API able to mint exactly the record the ruling forbids."""
    m = RegistryModel()
    r = apply_operations(
        m, {"devices": {"add": [{"device_id": "devA", "base_url": "http://x"}]}}
    )
    assert not r["ok"]
    assert r["errors"][0]["field"] == "channels"
    assert m.devices == []  # rejected whole — no half-adopted board left behind


def test_n1c_an_empty_channel_list_is_rejected_too() -> None:
    """Declaring zero channels is not declaring; it is the same non-config wearing a
    key. Worth its own test because `[]` is falsy and easy to let through."""
    m = RegistryModel()
    r = apply_operations(
        m,
        {"devices": {"add": [{"device_id": "d", "base_url": "u", "channels": []}]}},
    )
    assert not r["ok"] and r["errors"][0]["field"] == "channels"


# --------------------------------------------------------------------------- #
# Need 2 — per-channel pin, readable per channel
# --------------------------------------------------------------------------- #
def test_n2_each_channel_carries_its_own_pin() -> None:
    """Design-QA: the empty-channel state teaches *"connect a sensor to GPIO 34"*, so
    the pin must be readable **per channel**, not only as a total count."""
    m = RegistryModel()
    _adopt(m)
    assert [(d.channel, d.pin) for d in m.declared_channels("devA")] == [
        ("ch0", 36),
        ("ch1", 39),
        ("ch2", 34),
        ("ch3", 35),
    ]


def test_n2b_a_declared_channel_may_have_an_unknown_pin() -> None:
    """Absence stays first-class (ADR-0028): "I have four probes but I'd have to go
    look at the wiring" is a real answer, and better than a guessed pin."""
    m = RegistryModel()
    _adopt(m, pins=(36, None, 34, None))
    assert [d.pin for d in m.declared_channels("devA")] == [36, None, 34, None]
    assert m.declared_channel_count("devA") == 4  # still a known config


# --------------------------------------------------------------------------- #
# Need 3 — the canonical chN token, consumed and never re-minted
# --------------------------------------------------------------------------- #
def test_n3_channels_are_named_in_the_wire_vocabulary() -> None:
    """ADR-0036's token. The wire already emits it; a second naming here would be the
    #1315 shape — two vocabularies for one physical thing."""
    m = RegistryModel()
    _adopt(m, pins=(1, 2, 3))
    assert [d.channel for d in m.declared_channels("devA")] == ["ch0", "ch1", "ch2"]


def test_n3b_the_declaration_joins_the_assignment_on_the_same_token() -> None:
    """The join that makes the whole thing useful: a declared channel and an assigned
    channel must meet. If they did not, "declared but unassigned" would be every
    channel, always."""
    m = RegistryModel(plants=[Plant(plant_id="p01")])
    _adopt(m)
    m.assignments.append(
        Assignment(plant_id="p01", sensor_id="s1", device_id="devA", channel="ch2")
    )
    assert [d.channel for d in m.unassigned_channels("devA")] == ["ch0", "ch1", "ch3"]


# --------------------------------------------------------------------------- #
# Need 4 — declared-but-unassigned is a QUERY, not a template diff
# --------------------------------------------------------------------------- #
def test_n4_the_empty_channel_set_is_queryable() -> None:
    """§5.3's calm-empty set. Design-QA's constraint: if this were only derivable by
    diffing declared-against-assigned in a template, it would be a policy living in a
    template — what ADR-0038 §3 forbids and slice 2 spent its effort removing."""
    m = RegistryModel()
    _adopt(m)
    free = m.unassigned_channels("devA")
    assert len(free) == 4  # a board with no plants yet: legitimate, and renderable
    assert free[0].pin == 36  # with enough detail to teach ("connect one to GPIO 36")


def test_n4b_a_fully_mapped_board_reports_an_empty_set_not_an_error() -> None:
    m = RegistryModel(plants=[Plant(plant_id=f"p0{i}") for i in range(1, 5)])
    _adopt(m)
    for i in range(4):
        m.assignments.append(
            Assignment(
                plant_id=f"p0{i + 1}",
                sensor_id=f"s{i}",
                device_id="devA",
                channel=f"ch{i}",
            )
        )
    assert m.unassigned_channels("devA") == []


# --------------------------------------------------------------------------- #
# Need 5 — versioned: a rewire reads as history, not as a new board
# --------------------------------------------------------------------------- #
def test_n5_a_rewire_closes_the_old_declaration_and_opens_a_new_one() -> None:
    """Her case: *"I took two of the sensors off and moved them to my esp32."* That is
    an edit event on a board that still exists — not a re-adoption."""
    m = RegistryModel()
    _adopt(m)
    r = apply_operations(
        m,
        {"devices": {"rewire": [{"device_id": "devA", "channels": [36, 39]}]}},
        now=T2,
    )
    assert r["ok"] and r["applied"]["rewired"] == 1
    assert m.declared_channel_count("devA") == 2  # two probes left
    assert len(m.devices) == 1  # still ONE board, not a second one


def test_n5b_the_old_wiring_survives_as_history() -> None:
    """The point of versioning: yesterday's readings came off a board wired the old
    way, and that must stay knowable."""
    m = RegistryModel()
    _adopt(m)
    apply_operations(
        m,
        {"devices": {"rewire": [{"device_id": "devA", "channels": [36, 39]}]}},
        now=T2,
    )
    closed = [d for d in m.declaration_history("devA") if not d.is_open]
    assert len(closed) == 4 and all(d.end_ts == T2 for d in closed)


def test_n5c_a_past_instant_gets_the_wiring_in_force_then() -> None:
    """Resolved on the covering interval, like identity. Answering a historical
    question with today's wiring is the #1331 mistake in a different field."""
    m = RegistryModel()
    _adopt(m)
    apply_operations(
        m,
        {"devices": {"rewire": [{"device_id": "devA", "channels": [36, 39]}]}},
        now=T2,
    )
    assert len(m.declared_channels("devA", at_time="2026-07-15T00:00:00Z")) == 4
    assert len(m.declared_channels("devA", at_time="2026-07-25T00:00:00Z")) == 2


def test_n5d_a_rewire_of_an_unknown_board_is_rejected() -> None:
    m = RegistryModel()
    r = apply_operations(
        m, {"devices": {"rewire": [{"device_id": "ghost", "channels": [1]}]}}
    )
    assert not r["ok"] and r["errors"][0]["field"] == "device_id"


# --------------------------------------------------------------------------- #
# Need 6 — a default we assumed vs a fact she stated
# --------------------------------------------------------------------------- #
def test_n6_the_record_distinguishes_recommended_from_stated() -> None:
    """Design-QA's flagged need, and the one with no natural failure mode: both
    produce the same integer, so conflating them breaks nothing visibly. It surfaces
    later as a surface that either overclaims ("your board is wired to GPIO 34") or
    nags (re-asking what she already told us). Same distinction as the cal receipt's
    stored-vs-confirmed."""
    stated, recommended = RegistryModel(), RegistryModel()
    _adopt(stated, source="stated")
    _adopt(recommended, source="recommended")
    assert {d.source for d in stated.declared_channels("devA")} == {"stated"}
    assert {d.source for d in recommended.declared_channels("devA")} == {"recommended"}
    # identical pins — which is exactly why the discriminator has to be its own field
    assert [d.pin for d in stated.declared_channels("devA")] == [
        d.pin for d in recommended.declared_channels("devA")
    ]


def test_n6b_an_unknown_source_is_rejected() -> None:
    m = RegistryModel()
    r = apply_operations(
        m,
        {
            "devices": {
                "add": [
                    {
                        "device_id": "d",
                        "base_url": "u",
                        "channels": [1],
                        "channel_source": "vibes",
                    }
                ]
            }
        },
    )
    assert not r["ok"] and r["errors"][0]["field"] == "channel_source"


# --------------------------------------------------------------------------- #
# Persistence + the read surface slice 4 consumes
# --------------------------------------------------------------------------- #
def test_declarations_survive_a_save_and_reload(tmp_path: Path) -> None:
    """A model fact that does not round-trip is a fact the next process does not have.
    Checked through the real file, not a dict copy."""
    m = RegistryModel()
    _adopt(m)
    path = tmp_path / "devices.json"
    save_model(m, path)
    assert "channel_declarations" in json.loads(path.read_text(encoding="utf-8"))
    back = load_model(path)
    assert [(d.channel, d.pin, d.source) for d in back.declared_channels("devA")] == [
        ("ch0", 36, "stated"),
        ("ch1", 39, "stated"),
        ("ch2", 34, "stated"),
        ("ch3", 35, "stated"),
    ]


def test_the_channel_view_reports_declared_ports_with_no_plant() -> None:
    """The read shape slice 4 renders. Before the declaration existed, a board with no
    assignments had NO ports in this view — §5.3's empty state was not merely unbuilt,
    it was unrepresentable."""
    from registry_model import _channel_view

    m = RegistryModel()
    _adopt(m)
    view = _channel_view(m, {"device_id": "devA"})
    assert [v["channel"] for v in view] == ["ch0", "ch1", "ch2", "ch3"]
    assert all(v["sensor_id"] is None for v in view)  # declared, no plant yet
    assert all(v["declared"] and v["pin_source"] == "stated" for v in view)
    assert view[0]["pin"] == 36


def test_a_grandfathered_port_reads_as_undeclared_rather_than_as_an_error() -> None:
    """A board mapped before declarations existed has assignments and no declaration.
    That is history, not corruption — absence stays first-class (ADR-0028)."""
    from registry_model import _channel_view

    m = RegistryModel(
        plants=[Plant(plant_id="p01")],
        devices=[{"device_id": "old", "base_url": "u"}],
        assignments=[
            Assignment(plant_id="p01", sensor_id="s1", device_id="old", channel="ch0")
        ],
    )
    (port,) = _channel_view(m, {"device_id": "old"})
    assert port["declared"] is False and port["pin"] is None
    assert port["sensor_id"] == "s1"  # the mapping still reads correctly


def test_purging_a_board_takes_its_wiring_history_with_it() -> None:
    """The declaration is the board's own fact, so it cannot outlive the board."""
    m = RegistryModel()
    _adopt(m)
    m.purge(devices={"devA"})
    assert m.channel_declarations == []
