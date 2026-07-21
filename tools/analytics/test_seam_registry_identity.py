#!/usr/bin/env python3
"""#1338 seam 1 — temporal registry ↔ tier store ↔ read paths: **one identity, checked
across implementations.**

A *conformance* suite, not a unit suite, and the distinction is the whole point.
``test_identity_projection.py`` checks ``identity.py`` against itself and passes;
``test_interval_join.py`` checks the tier's SQL against its oracle and passes. Both are
green, both are correct, and **together they cannot detect the defect that actually
shipped** — because each verifies one implementation in isolation while the failure
lives *between* implementations.

That failure has a casualty record:

- **#1331** — the tier's join carried no time bounds, so every historical reading
  inherited today's assignment. The SQL and its "independent" oracle agreed with each
  other because both read the same flat map, so the fidelity gate passed while the
  answer was wrong.
- **#1315** — the v5 migration re-keyed the registry to ``chN`` while boards still
  emitted ``sN``. The parse/tier path folded; the Home's own registry join did not, and
  the live Home lost all eight probed plants.

Same root both times: **more than one place answered "who is on this channel", and
nothing compared their answers.** ADR-0038 §3 states the rule this suite enforces —
*identity resolution has exactly one implementation, in any language, on any surface* —
and §4 names ``resolve_plant(device_id, channel, at_time)`` as that implementation.

**How to read a failure here.** A red test in this file does not mean a module is
broken. It means two modules disagree, and the seam is where the bug reaches a user.
Fix by migrating the divergent path onto the projection — never by teaching this suite
to expect the divergence.

**Contract claims under test.** Extracted from prose, per the epic's constraint that
conformance asserts *executable* claims and never parses ADRs as specifications:

- **C1** — every implementation returns the same plant for the same
  ``(device, channel, instant)``.  *(ADR-0038 §3)*
- **C2** — identity resolves on the interval **covering the reading's own instant**,
  never today's open assignment.  *(TIER_STORE_CONTRACT §3, #1331)*
- **C3** — v4 ``sN`` and v5 ``chN`` name the same physical channel; a generation
  mismatch must not resolve in one path and vanish in another.  *(ADR-0036, #1315)*
- **C4** — no identity resolver exists outside the sanctioned surface, **including in
  templates**, which no import graph reaches.  *(ADR-0038 §3)*

**On the strict xfails.** Slice 2 of #1335 migrates the remaining paths onto the
projection. When it lands these stop failing, ``strict=True`` turns the unexpected pass
into a suite failure, and whoever lands it must delete the marker and promote the test
to a live gate. Scaffolding that cannot be forgotten.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from identity import build_projection
from registry_model import Assignment, Plant, RegistryModel
from tier_store import resolve_plant_at

_HERE = Path(__file__).resolve().parent

# The physical pairing, from `parse_v1.canonical_channel` and corroborated by the
# 2026-07-01 capture headers (`ch2=GPIO34/s1`): s1↔ch2, s2↔ch3, s3↔ch0, s4↔ch1.
# Written out because a fixture that guesses this silently tests nothing.
S1_CHANNEL = "ch2"


def _t(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 7, day, hour, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------------------
# the implementations under test — every live answer to "who is on this channel"
# --------------------------------------------------------------------------------------


def _via_projection(model, registry, device_id, channel, at):
    """The reference: ADR-0038 §4's one public function."""
    return build_projection(model, registry).resolve_plant(device_id, channel, at)


def _via_tier_oracle(model, registry, device_id, channel, at):
    """The tier store's per-row linear scan — deliberately not the SQL's shape."""
    rows = [
        (a.device_id, a.channel or a.sensor_id, a.plant_id, a.start_ts, a.end_ts)
        for a in model.assignments
    ]
    return resolve_plant_at(rows, device_id, channel, at)


def _via_static_registry(model, registry, device_id, channel, at):
    """What `dashboard.py:933/:1140`, `multiplant_history.py`, `segment_history.py`
    and `predict_bridge.py`'s fallback all reach for.

    Note the signature: ``plant_for(device_id, channel)`` takes **no instant**. This
    path is not merely wrong about history — it is structurally incapable of answering
    a historical question, which is why C2 cannot be satisfied by fixing its data and
    needs the migration in #1335 slice 2.
    """
    hit = registry.plant_for(device_id, channel)
    return hit["plant_id"] if hit else None


ALL_PATHS = (
    ("projection", _via_projection),
    ("tier-oracle", _via_tier_oracle),
    ("static-registry", _via_static_registry),
)


def _answers(model, registry, device_id, channel, at):
    return {name: fn(model, registry, device_id, channel, at) for name, fn in ALL_PATHS}


# --------------------------------------------------------------------------------------
# fixtures — the same fleet, described to both registries
# --------------------------------------------------------------------------------------


def _fleet(*, static_key: str, plant: str = "p11"):
    """One board, one channel, one plant — described temporally and statically.

    ``static_key`` is the token the STATIC registry is keyed by. That is the axis #1315
    turned on: the migration re-keyed one side and not the other.
    """
    model = RegistryModel(
        plants=[Plant(plant_id=plant), Plant(plant_id="p02")],
        assignments=[
            Assignment(
                plant_id=plant, sensor_id="s1", device_id="d1", channel=S1_CHANNEL
            )
        ],
    )
    registry = Registry(
        devices=[
            Device(
                device_id="d1",
                board="classic",
                label="left",
                channels={static_key: {"plant_id": plant, "plant_name": "Corn"}},
            )
        ]
    )
    return model, registry


def _moved_fleet():
    """A probe that moved from p11 to p02 on the 12th — the #1331 shape."""
    model = RegistryModel(
        plants=[Plant(plant_id="p11"), Plant(plant_id="p02")],
        assignments=[
            Assignment(
                plant_id="p11",
                sensor_id="s1",
                device_id="d1",
                channel=S1_CHANNEL,
                start_ts=None,
                end_ts=_t(12).isoformat(),
            ),
            Assignment(
                plant_id="p02",
                sensor_id="s1",
                device_id="d1",
                channel=S1_CHANNEL,
                start_ts=_t(12).isoformat(),
                end_ts=None,
            ),
        ],
    )
    # a static registry can only hold ONE answer, and it is always today's
    registry = Registry(
        devices=[
            Device(
                device_id="d1",
                board="classic",
                label="left",
                channels={S1_CHANNEL: {"plant_id": "p02", "plant_name": "Fern"}},
            )
        ]
    )
    return model, registry


# --------------------------------------------------------------------------------------
# C1 — every implementation agrees, in the ordinary case
# --------------------------------------------------------------------------------------


def test_c1_all_paths_agree_on_a_stable_binding() -> None:
    """The baseline. If this fails, the seam is broken in the simplest possible case."""
    model, registry = _fleet(static_key=S1_CHANNEL)
    got = _answers(model, registry, "d1", S1_CHANNEL, _t(10))
    assert set(got.values()) == {"p11"}, f"paths disagree on a stable binding: {got}"


def test_c1_absence_agrees_too() -> None:
    """One path inventing a plant where another finds none is the same defect."""
    model, registry = _fleet(static_key=S1_CHANNEL)
    got = _answers(model, registry, "d1", "ch3", _t(10))
    assert set(got.values()) == {None}, f"paths disagree on an unknown channel: {got}"


# --------------------------------------------------------------------------------------
# C2 — the covering interval, never today's answer (#1331)
# --------------------------------------------------------------------------------------


def test_c2_the_temporal_paths_keep_history_with_its_own_plant() -> None:
    model, registry = _moved_fleet()
    assert _via_projection(model, registry, "d1", S1_CHANNEL, _t(10)) == "p11"
    assert _via_tier_oracle(model, registry, "d1", S1_CHANNEL, _t(10)) == "p11"
    # and after the move, both follow it
    assert _via_projection(model, registry, "d1", S1_CHANNEL, _t(14)) == "p02"
    assert _via_tier_oracle(model, registry, "d1", S1_CHANNEL, _t(14)) == "p02"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "#1335 slice 2 — the static path's signature carries no instant, so it answers "
        "every historical question with today's assignment. This is #1331 surviving in "
        "the read paths the user actually looks at. Delete this marker when they "
        "migrate onto the projection."
    ),
)
def test_c2_every_path_including_the_static_one_keeps_history() -> None:
    """The seam, stated as the assertion we want to become true."""
    model, registry = _moved_fleet()
    got = _answers(model, registry, "d1", S1_CHANNEL, _t(10))
    assert set(got.values()) == {"p11"}, f"paths disagree about history: {got}"


# --------------------------------------------------------------------------------------
# C3 — token generation is not identity (#1315)
# --------------------------------------------------------------------------------------


def test_c3_the_projection_folds_both_token_generations() -> None:
    """v4 ``s1`` and v5 ``ch2`` name the same physical channel."""
    model, registry = _fleet(static_key=S1_CHANNEL)
    proj = build_projection(model, registry)
    assert proj.resolve_plant("d1", S1_CHANNEL, _t(10)) == "p11"
    assert proj.resolve_plant("d1", "s1", _t(10)) == "p11"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "#1315 reproduction — the registry is keyed chN while the board still emits "
        "sN. The projection folds the generations; the static registry does a raw dict "
        "lookup and returns None. That asymmetry IS the incident: the Home showed "
        "'Unnamed plant' for all eight probes while the tier path stayed fine. Delete "
        "this marker when the read paths migrate onto the projection."
    ),
)
def test_c3_a_generation_mismatch_never_vanishes_in_one_path_alone() -> None:
    """The live #1315 case: a v4 token against a v5-keyed registry.

    The dangerous shape is not that a path fails — it is that ONE path fails while
    another succeeds, so the system looks healthy from wherever you happen to check.
    """
    model, registry = _fleet(static_key=S1_CHANNEL)
    got = _answers(model, registry, "d1", "s1", _t(10))
    assert len(set(got.values())) == 1, (
        f"a v4 token resolves in some paths and vanishes in others: {got} — "
        "this is the #1315 mechanism"
    )


# --------------------------------------------------------------------------------------
# C4 — one implementation, any surface (ADR-0038 §3)
# --------------------------------------------------------------------------------------

# Every module that answers "who is on this channel" outside the sanctioned surface.
# This is a LEDGER OF DEBT, not a permission list — #1335 slice 2 empties it. A new
# entry means a further identity path was born, which is the rule failing.
#
# Each of these is time-blind by construction: `plant_for` takes no instant. They are
# correct today only because the fleet has recorded zero probe moves (ADR-0037) — the
# same "accidentally right" condition that hid #1331 until it was looked for.
KNOWN_RESOLVERS = {
    # The live read path. Moved out of dashboard.py by the #1336 §5.3 extraction —
    # the same resolver in a new home, not a new one. The ledger neither grew nor
    # shrank here, which is the honest bookkeeping: an extraction relocates a
    # defect, it does not retire it. Retiring it is the identity slice's job (#1335).
    "card_context.py",  # :933, :1140 relative to the moved cluster
    "multiplant_history.py",  # :109, :292 — history attribution
    "segment_history.py",  # :61 — segment attribution
    "predict_bridge.py",  # :120 — STATIC FALLBACK feeding the predictor
    "epoch_sweep.py",  # :76 — presence check, not attribution; benign but counted
}

# The sanctioned surface: the projection, and the static store it legitimately reads.
SANCTIONED = {"identity.py", "device_registry.py"}


def test_c4_no_unregistered_identity_resolver_appears() -> None:
    """ADR-0038 §3, made testable for Python surfaces."""
    pattern = re.compile(r"\.plant_for\s*\(")
    found = {
        p.name
        for p in sorted(_HERE.glob("*.py"))
        if not p.name.startswith("test_")
        and p.name not in SANCTIONED
        and pattern.search(p.read_text(encoding="utf-8", errors="ignore"))
    }

    new = found - KNOWN_RESOLVERS
    assert not new, (
        f"a new identity resolver appeared outside the projection: {sorted(new)}. "
        "ADR-0038 §3 — identity resolution has exactly one implementation, in any "
        "language, on any surface. Resolve through `identity.resolve_plant`; if this "
        "is deliberate, argue it on #1338 before adding it to KNOWN_RESOLVERS."
    )

    gone = KNOWN_RESOLVERS - found
    assert not gone, (
        f"{sorted(gone)} no longer resolves identity independently — good. Remove it "
        "from KNOWN_RESOLVERS so the ledger keeps shrinking and the win is recorded."
    )


# Templates that join identity on a raw wire token. `home_template.html` is the #1315
# site itself, still live: "join like the pulse: plant_id when registered, else the
# card's sensor_id". A template may CONSUME a resolved plant; it must never COMPUTE one.
# #1315's original site. Emptied by the slice-2 migration (#1335): home_template.html
# now consumes the plant the payload already resolved, so the raw-token join is gone.
# The set can only ever SHRINK — an addition means a new template started joining on a
# wire token, which is the #1315 mechanism returning.
KNOWN_TEMPLATE_JOINS: set[str] = set()


def test_c4_templates_are_covered_by_the_rule_too() -> None:
    """#1315 lived in a template, which no import graph reaches — so the rule must too.

    The match is deliberately narrow: an equality comparison between two ``sensor_id``
    values is a join. A template merely *displaying* ``sensor_id``, or indexing a map
    the payload already resolved, is consuming identity and is fine — that distinction
    is the difference between `home_template.html` (a real join) and
    `dashboard_template.html` (which reads `reg.current_mappings`).
    """
    joins_on_token = re.compile(
        r"\.sensor_id\s*===?\s*[\w.]*\.?sensor_id"  # a === b on the raw token
        r"|\[\s*['\"]sensor_id['\"]\s*\]\s*===?\s*"  # or the bracket form
    )
    found = {
        p.name
        for p in _HERE.rglob("*.html")
        if joins_on_token.search(p.read_text(encoding="utf-8", errors="ignore"))
    }

    new = found - KNOWN_TEMPLATE_JOINS
    assert not new, (
        f"a template joins plant identity on a raw wire token: {sorted(new)}. This is "
        "the #1315 mechanism — the template must consume the plant the payload already "
        "resolved, never compute one. ADR-0038 §3."
    )

    gone = KNOWN_TEMPLATE_JOINS - found
    assert not gone, (
        f"{sorted(gone)} no longer joins on a raw token — good. Remove it from "
        "KNOWN_TEMPLATE_JOINS; that is the #1315 site closing."
    )
