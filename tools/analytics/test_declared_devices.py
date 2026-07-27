#!/usr/bin/env python3
"""#1544 (A1, the #1541 wall) — a board can be DESCRIBED before it has ever reported.

The onboarding wall the clean-checkout walk hit: everything shipped assumes a board that
already answered. Adoption (#1027) is reactive. A new user has the inverse — hardware in
hand, nothing flashed, nothing reporting — and for that state there was no entry point
at all, in the model or the surface.

The properties that make declare-before-connect safe, pinned here:

* the declaration is a **real key immediately** — wiring and plant mappings hang off it
  the moment the user describes the board, so their work is saved even if the hardware
  never shows up;
* **binding is its own axis**, not a lifecycle state (lifecycle is the unified
  active|paused|deleted shared with plants and sensors — "pending" is meaningless for a
  plant);
* the **reconcile on first contact re-keys, never duplicates**: the provisional id
  becomes ``previous_ids`` lineage (the shipped #602 fold), so every assignment and
  reading written against it keeps resolving — one board, one record, always.
"""

from __future__ import annotations

from tools.analytics.device_registry import Registry, _device_from_dict
from tools.analytics.registry_model import (
    PENDING_ID_PREFIX,
    Assignment,
    Plant,
    RegistryModel,
    Sensor,
    apply_operations,
    mint_pending_id,
    registry_payload,
)


def _model() -> RegistryModel:
    return RegistryModel(
        plants=[Plant(plant_id="p01", pet_name="Bernie")],
        sensors=[Sensor(sensor_id="s01")],
    )


# --------------------------------------------------------------------------- #
# declaring
# --------------------------------------------------------------------------- #
def test_a_board_can_be_declared_before_it_reports() -> None:
    m = _model()
    d = m.declare_device(name="Windowsill", board="esp32-classic", channels=[32, 33])
    assert d["binding"] == "pending"
    assert d["lifecycle"] == "active"  # declared is NOT paused/deleted
    assert d["name"] == "Windowsill"
    assert d["device_id"].startswith(PENDING_ID_PREFIX)
    assert [c.channel for c in m.declared_channels(d["device_id"])] == ["ch0", "ch1"]
    assert m.is_pending(d["device_id"])
    assert [x["device_id"] for x in m.pending_devices()] == [d["device_id"]]


def test_a_declared_board_needs_a_name() -> None:
    """The name is the only handle on a board that cannot yet identify itself."""
    m = _model()
    try:
        m.declare_device(name="   ")
    except ValueError as exc:
        assert "name" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unnamed declaration must be refused")


def test_the_provisional_id_never_looks_like_a_real_minted_id() -> None:
    """ADR-0027 ids are 6-char base32 minted ON the board. A placeholder that looked
    like one would be indistinguishable in a log line."""
    m = _model()
    did = m.declare_device(name="A")["device_id"]
    assert did.startswith(PENDING_ID_PREFIX) and "-" in did


def test_minted_ids_never_collide_or_reuse_a_retired_number() -> None:
    m = _model()
    a = m.declare_device(name="A")["device_id"]
    b = m.declare_device(name="B")["device_id"]
    assert a != b
    m.bind_device(a, "abc123")  # a's provisional id becomes lineage
    c = mint_pending_id(m)
    assert c not in (a, b)  # the retired provisional is not handed out again


# --------------------------------------------------------------------------- #
# the plant mapping survives the wait (the "work is saved" property)
# --------------------------------------------------------------------------- #
def test_plants_can_be_mapped_onto_a_board_that_has_not_reported() -> None:
    m = _model()
    did = m.declare_device(name="Windowsill", channels=[32])["device_id"]
    m.assignments.append(
        Assignment(plant_id="p01", sensor_id="s01", device_id=did, channel="ch0")
    )
    cur = m.current_for_channel(did, "ch0")
    assert cur is not None and cur.plant_id == "p01"


# --------------------------------------------------------------------------- #
# reconcile on first contact
# --------------------------------------------------------------------------- #
def test_binding_rekeys_the_same_record_and_keeps_the_mapping() -> None:
    """The load-bearing one: bind must NOT create a second record, and the mapping the
    user built at declare-time must be the mapping that goes live."""
    m = _model()
    did = m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])[
        "device_id"
    ]
    m.assignments.append(
        Assignment(plant_id="p01", sensor_id="s01", device_id=did, channel="ch0")
    )

    rec = m.bind_device(did, "y9d41p")

    assert rec is not None
    assert len(m.devices) == 1  # re-keyed, never duplicated
    assert rec["device_id"] == "y9d41p"
    assert rec["binding"] == "bound"
    assert did in rec["previous_ids"]  # #602 lineage — history still resolves
    assert rec["name"] == "Windowsill"  # the human label survives the bind
    # the declare-time mapping is now live on the real board
    assert m.current_for_channel("y9d41p", "ch0").plant_id == "p01"
    assert m.current_for_channel(did, "ch0") is None
    assert [c.channel for c in m.declared_channels("y9d41p")] == ["ch0"]
    assert not m.pending_devices()


def test_the_provisional_id_still_resolves_through_the_shipped_602_fold() -> None:
    """Rows logged against the provisional id (a board that reported mid-declaration)
    must still resolve to the bound board — via `canonical_for`, the EXISTING identity
    fold, not a second mechanism invented for binding."""
    m = _model()
    did = m.declare_device(name="Windowsill", channels=[32])["device_id"]
    m.bind_device(did, "y9d41p")
    reg = Registry(devices=[d for d in map(_device_from_dict, m.devices) if d])
    assert reg.canonical_for(did) == "y9d41p"


def test_binding_is_idempotent_and_refuses_a_live_id() -> None:
    m = _model()
    did = m.declare_device(name="A")["device_id"]
    m.bind_device(did, "y9d41p")
    assert m.bind_device(did, "other1") is None  # already bound — not pending anymore

    other = m.declare_device(name="B")["device_id"]
    try:
        m.bind_device(other, "y9d41p")  # that board is already registered
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("never two records for one board")


def test_binding_an_unknown_id_is_none_never_an_invented_record() -> None:
    m = _model()
    assert m.bind_device("pending-99", "y9d41p") is None
    assert not m.devices


# --------------------------------------------------------------------------- #
# the write path (what A2's flow posts) + the payload (what A4's zero state reads)
# --------------------------------------------------------------------------- #
def test_declare_through_apply_operations_returns_the_minted_id() -> None:
    m = _model()
    r = apply_operations(
        m,
        {
            "devices": {
                "declare": [
                    {
                        "name": "Windowsill",
                        "board": "esp32-classic",
                        "channels": [32, 33],
                    }
                ]
            }
        },
    )
    assert r["ok"]
    assert len(r["applied"]["declared"]) == 1
    did = r["applied"]["declared"][0]
    assert m.is_pending(did)
    assert r["applied"]["channels_declared"] == 2


def test_declare_refuses_a_client_supplied_id_and_a_missing_name() -> None:
    m = _model()
    r = apply_operations(
        m,
        {
            "devices": {
                "declare": [{"name": "A", "device_id": "y9d41p", "channels": [1]}]
            }
        },
    )
    assert not r["ok"] and r["errors"][0]["field"] == "device_id"

    r = apply_operations(m, {"devices": {"declare": [{"channels": [1]}]}})
    assert not r["ok"] and r["errors"][0]["field"] == "name"
    assert not m.devices  # whole-or-nothing


def test_declare_still_requires_the_channel_declaration() -> None:
    """A declaration with no wiring is the same non-adoptable board #1027 forbids —
    reporting or not."""
    m = _model()
    r = apply_operations(m, {"devices": {"declare": [{"name": "A"}]}})
    assert not r["ok"] and r["errors"][0]["field"] == "channels"


def test_the_payload_lets_the_zero_state_tell_the_two_states_apart() -> None:
    """The #1541 wall: the first screen could not distinguish 'no boards registered'
    from 'waiting for a reading', so it said the second forever."""
    m = _model()
    empty = registry_payload(m)
    assert empty["has_any_device"] is False
    assert empty["pending_devices"] == []

    m.declare_device(name="Windowsill", board="esp32-classic", channels=[32, 33])
    doc = registry_payload(m)
    assert doc["has_any_device"] is True
    assert len(doc["pending_devices"]) == 1
    p = doc["pending_devices"][0]
    assert p["name"] == "Windowsill" and p["channels_declared"] == 2
    assert p["declared_ts"]  # when they described it — the wait is datable
