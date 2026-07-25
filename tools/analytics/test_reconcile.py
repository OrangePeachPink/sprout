#!/usr/bin/env python3
"""#1548 (A5) — the declared↔answering reconcile decides, and refuses to guess.

The declaration and the arrival share no identifier (ADR-0027 mints the id on the
board), so this is circumstantial reasoning, not a join. These tests pin the
conservative rule — especially the cases where it must NOT act: a wrong bind attaches
the operator's wiring and plant mapping to wrong hardware, which is worse than asking.
"""

from __future__ import annotations

from tools.analytics.reconcile import ADOPT, AMBIGUOUS, BIND, apply_plan, plan
from tools.analytics.registry_model import Plant, RegistryModel, Sensor


def _model() -> RegistryModel:
    return RegistryModel(
        plants=[Plant(plant_id="p01", pet_name="Bernie")],
        sensors=[Sensor(sensor_id="s01")],
    )


def _stranger(device_id: str, board: str | None = None) -> dict:
    return {"device_id": device_id, "board": board, "channels_seen": ["ch0"]}


def test_one_declaration_one_arrival_binds() -> None:
    """Day one for essentially every user: one board declared, one plugged in."""
    m = _model()
    pid = m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])[
        "device_id"
    ]
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    assert len(r.plans) == 1
    p = r.plans[0]
    assert p.action == BIND and p.pending_id == pid and p.device_id == "y9d41p"
    assert "Windowsill" in p.reason


def test_nothing_pending_is_an_adoption_not_a_bind() -> None:
    """#1027's case, unchanged — an unknown board with no declaration waiting."""
    r = plan(_model(), [_stranger("y9d41p", "esp32-classic")])
    assert r.plans[0].action == ADOPT


def test_a_class_mismatch_never_auto_binds() -> None:
    """She declared a C5; an ESP32-classic answered. The one hard fact we have
    contradicts the circumstance — binding would attach her wiring to wrong hardware."""
    m = _model()
    m.declare_device(name="Windowsill", board="esp32-c5", channels=[1])
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    assert r.plans[0].action == ADOPT
    assert "doesn't match" in r.plans[0].reason


def test_two_pending_boards_is_ambiguous_never_a_coin_flip() -> None:
    m = _model()
    a = m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])[
        "device_id"
    ]
    b = m.declare_device(name="Desk", board="esp32-classic", channels=[33])["device_id"]
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    p = r.plans[0]
    assert p.action == AMBIGUOUS
    assert set(p.candidates) == {a, b}
    assert p.pending_id is None  # nothing chosen — the operator picks


def test_two_arrivals_against_one_declaration_is_ambiguous() -> None:
    """Symmetric: which of the two reporting boards is hers is equally a guess."""
    m = _model()
    m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])
    r = plan(m, [_stranger("aaa111", "esp32-classic"), _stranger("bbb222", None)])
    assert {p.action for p in r.plans} == {AMBIGUOUS}


def test_an_absent_class_does_not_block_a_bind() -> None:
    """ADR-0028: absence is honest, not a mismatch. A board that doesn't state its class
    is not evidence against the one declaration waiting."""
    m = _model()
    pid = m.declare_device(name="Windowsill", channels=[32])["device_id"]
    r = plan(m, [_stranger("y9d41p", None)])
    assert r.plans[0].action == BIND and r.plans[0].pending_id == pid


def test_a_class_only_mismatch_still_binds_the_matching_one() -> None:
    """Two pending, but only one is class-compatible — that is not ambiguity, it is a
    ruled-out candidate."""
    m = _model()
    m.declare_device(name="Desk", board="esp32-c5", channels=[1])
    classic = m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])[
        "device_id"
    ]
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    assert r.plans[0].action == BIND and r.plans[0].pending_id == classic


def test_still_pending_is_reported_even_with_no_arrivals() -> None:
    """ "3 boards waiting" is a state the surface renders, not an empty result."""
    m = _model()
    m.declare_device(name="A", channels=[1])
    m.declare_device(name="B", channels=[2])
    r = plan(m, [])
    assert r.plans == [] and len(r.still_pending) == 2


def test_apply_plan_executes_a_bind_and_refuses_the_rest() -> None:
    m = _model()
    pid = m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])[
        "device_id"
    ]
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    rec = apply_plan(m, r.plans[0])
    assert rec is not None and rec["device_id"] == "y9d41p"
    assert rec["binding"] == "bound" and pid in rec["previous_ids"]
    assert not m.pending_devices()  # the declaration is now a real board
    assert len(m.devices) == 1  # never two records

    # an ambiguous/adopt plan is a question, not an instruction
    m2 = _model()
    m2.declare_device(name="A", channels=[1])
    m2.declare_device(name="B", channels=[2])
    amb = plan(m2, [_stranger("zzz999")]).plans[0]
    assert apply_plan(m2, amb) is None
    assert len(m2.pending_devices()) == 2  # untouched


def test_the_binds_shortcut_selects_only_actionable_plans() -> None:
    m = _model()
    m.declare_device(name="Windowsill", board="esp32-classic", channels=[32])
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    assert len(r.binds) == 1
    r2 = plan(_model(), [_stranger("y9d41p")])
    assert r2.binds == []


# --------------------------------------------------------------------------- #
# the Trellis hold (#1548): identity is not the cal-anchor classifier
# --------------------------------------------------------------------------- #
def test_a_declared_s3_never_auto_binds_to_an_answering_classic() -> None:
    """The regression Trellis caught. `parse_v1.board_class` folds esp32-s3 into
    "classic" (its catch-all cal-anchor arm), so the original check saw NO conflict and
    would auto-bind an S3 declaration to a classic board — pointing her plants at the
    wrong probes, on hardware with a different pin map."""
    m = _model()
    m.declare_device(name="Bench S3", board="esp32-s3", channels=[1, 2])
    r = plan(m, [_stranger("y9d41p", "esp32-classic")])
    assert r.plans[0].action == ADOPT  # NOT a bind
    assert "doesn't match" in r.plans[0].reason


def test_identity_class_keeps_the_three_tokens_distinct_and_absence_none() -> None:
    """Identity must not fold. An unrecognized or absent string is None (honest
    absence), never absorbed into a default that reads as a claim about hardware."""
    from tools.analytics.reconcile import identity_class

    assert identity_class("esp32-classic") == "esp32-classic"
    assert identity_class("esp32-s3") == "esp32-s3"
    assert identity_class("esp32-c5") == "esp32-c5"
    assert (
        len({identity_class(b) for b in ("esp32-classic", "esp32-s3", "esp32-c5")}) == 3
    )
    for absent in (None, "", "   ", "some-future-board"):
        assert identity_class(absent) is None
