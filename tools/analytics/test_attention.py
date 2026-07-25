"""#1582 (R11) — the attention composer: §8's resolution order, pinned.

The order is the ratified part of the model (`docs/design/specs/attention-model.md` §8),
so most of these tests are CONFLICT tests rather than single-signal tests: a plant that
qualifies for two levels at once must resolve to the higher one, every time. A composer
that returns the right answer when only one signal is present, and the wrong one when
two are, is the failure this model exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.attention import (
    ALL_CLEAR,
    CALM_HORIZON_H,
    CANT_TELL,
    HEADING_FOR_HARM,
    NEEDS_YOU_NOW,
    RESOLUTION_ORDER,
    WATCH,
    attention_state,
)


def card(
    *, band=None, state="live", exception=None, next_need=None, traj=None, health=None
):
    """A minimal card in the real payload's shape — frame/exception/next_need."""
    exc = exception or {"is": False, "kind": None, "reason": None}
    return {
        "frame": {"band": band, "mood": band, "state": state},
        "exception": exc,
        "next_need": next_need or {"known": False},
        "trajectory": traj,
        "sensor_health": {"status": health} if health else None,
    }


FAULT = {
    "is": True,
    "kind": "fault",
    "reason": "sensor fault — reading can't be trusted",
}
HARM = {"known": True, "kind": "rate_spike", "direction": "drier", "rebound": False}


def test_the_five_levels_in_the_ratified_order() -> None:
    assert RESOLUTION_ORDER == (
        CANT_TELL,
        HEADING_FOR_HARM,
        NEEDS_YOU_NOW,
        WATCH,
        ALL_CLEAR,
    )


def test_each_level_is_reachable_from_its_own_signal() -> None:
    assert attention_state(card(exception=FAULT)).state == CANT_TELL
    assert attention_state(card(traj=HARM)).state == HEADING_FOR_HARM
    assert attention_state(card(band="Thirsty")).state == NEEDS_YOU_NOW
    watch = card(band="Content", next_need={"known": True, "hours": 30})
    assert attention_state(watch).state == WATCH
    assert attention_state(card(band="Moist")).state == ALL_CLEAR


# --------------------------------------------------------------------------- #
# the conflicts — where a wrong order shows up
# --------------------------------------------------------------------------- #
def test_an_untrustworthy_reading_replaces_the_mood_it_does_not_decorate_it() -> None:
    """§1: a plant whose probe is faulted has NO attention level — not "fine," not
    "urgent." A parched-looking faulted plant must not read as a thirsty plant."""
    both = card(band="Parched", exception=FAULT, next_need={"known": True, "hours": 2})
    st = attention_state(both)
    assert st.state == CANT_TELL
    assert st.label == "Can't tell"
    assert "trust" in st.reason


def test_cant_tell_outranks_harm_because_harm_needs_a_trustworthy_reading() -> None:
    assert attention_state(card(exception=FAULT, traj=HARM)).state == CANT_TELL


def test_harm_outranks_needs_you_now() -> None:
    """#410's asymmetric-failure principle: a thirsty plant recovers from a late
    watering; a plant on an abnormal trajectory may not."""
    assert attention_state(card(band="Parched", traj=HARM)).state == HEADING_FOR_HARM


def test_a_merely_content_plant_can_be_heading_for_harm() -> None:
    """G2's whole point: harm is a trajectory, not a position on the mood ladder."""
    assert attention_state(card(band="Content", traj=HARM)).state == HEADING_FOR_HARM


def test_needs_you_now_outranks_watch() -> None:
    already = card(band="Thirsty", next_need={"known": True, "hours": 4})
    assert attention_state(already).state == NEEDS_YOU_NOW


def test_a_sensor_flagged_for_inspection_is_also_cant_tell() -> None:
    assert attention_state(card(band="Moist", health="inspect")).state == CANT_TELL


# --------------------------------------------------------------------------- #
# the honesty rules  (voice-guard: allow)
# --------------------------------------------------------------------------- #
def test_an_unknown_rebound_is_not_a_harm_signal() -> None:
    """`rebound` carries two falsey meanings in the classifier — "it held" and "can't
    tell." Only an explicit False is the #1434 signature; an unknown must never render
    "this one is getting worse," which would be a fabricated claim on no evidence."""
    unknown = dict(HARM, rebound=None)
    assert attention_state(card(band="Content", traj=unknown)).state != HEADING_FOR_HARM
    rebounded = dict(HARM, rebound=True)
    assert (
        attention_state(card(band="Content", traj=rebounded)).state != HEADING_FOR_HARM
    )


def test_magnitude_is_not_the_gate_settling_is() -> None:
    """#1434: +991 cleared the host threshold but sat under the firmware's own, and what
    made it real was that it settled at a new level. A wetter excursion is not harm."""
    wetter = dict(HARM, direction="wetter")
    assert attention_state(card(traj=wetter)).state != HEADING_FOR_HARM
    no_step = {
        "known": True,
        "kind": "rate_spike",
        "direction": "drier",
        "rebound": False,
    }
    assert attention_state(card(traj=no_step)).state == HEADING_FOR_HARM


def test_an_unclassified_trajectory_never_fires_harm() -> None:
    assert attention_state(card(band="Moist", traj={"known": False})).state == ALL_CLEAR
    assert attention_state(card(band="Moist", traj=None)).state == ALL_CLEAR


def test_a_not_probed_plant_has_no_attention_state_at_all() -> None:
    """ADR-0028: neither answer is honest for a plant we chose not to probe — All clear
    claims knowledge we lack, Can't tell reads as a fault. Absence, not a guess."""
    assert attention_state(card(state="sensorless")) is None


def test_watch_is_bounded_by_the_calm_horizon() -> None:
    inside = card(band="Content", next_need={"known": True, "hours": CALM_HORIZON_H})
    assert attention_state(inside).state == WATCH  # inclusive at the boundary
    beyond = card(
        band="Content", next_need={"known": True, "hours": CALM_HORIZON_H + 1}
    )
    assert attention_state(beyond).state == ALL_CLEAR


def test_an_unreachable_forecast_is_not_a_watch() -> None:
    """A forecast that isn't statistically real carries known=False — it is an absence,
    and an absence must not be read as a quiet nearby ETA."""
    unreachable = card(band="Content", next_need={"known": False, "reason": "no fit"})
    assert attention_state(unreachable).state == ALL_CLEAR


def test_the_all_clear_carries_its_horizon_never_a_bare_reassurance() -> None:
    """§3: the calm signal is affirmative and has a shelf life."""
    st = attention_state(card(band="Moist", next_need={"known": True, "hours": 96}))
    assert st.state == ALL_CLEAR
    assert "4 days" in st.reason


def test_the_calm_phrase_floors_it_never_over_promises() -> None:
    """71h is two days, never three: an all-clear that rounds UP over-promises calm,
    the one direction this phrase must not err in.

    71 rather than the obvious 60: at 60 the two agree (60/24 = 2.5, and Python rounds
    half to even, so `round` also yields 2). Verified by regression-testing this pin —
    swapping floor for round left a 60h assertion green. A guard that cannot fail is
    not a guard."""
    st = attention_state(card(band="Moist", next_need={"known": True, "hours": 71}))
    assert "2 days" in st.reason


def test_watch_carries_the_shared_confidence_word_it_does_not_re_derive_it() -> None:
    """#1598: FIRM/ROUGH/HAZY has one home. Watch reads the field."""
    nn = {"known": True, "hours": 30, "confidence_word": "ROUGH"}
    st = attention_state(card(band="Content", next_need=nn))
    assert st.evidence["confidence_word"] == "ROUGH"


def test_the_state_unpacks_as_the_ratified_signature() -> None:
    state, reason, evidence = attention_state(card(band="Thirsty"))
    assert (state, reason) == (NEEDS_YOU_NOW, "water now")
    assert evidence["band"] == "Thirsty"


# --------------------------------------------------------------------------- #
# the surface half — the template CONSUMES the composed state (#1582 §5)
# --------------------------------------------------------------------------- #
_H = (Path(__file__).resolve().parent / "home_template.html").read_text(
    encoding="utf-8"
)
_WATER = _H[_H.index("function waterHTML(") : _H.index("function glugPost(")]


def test_the_card_reads_the_composed_state_and_re_derives_nothing() -> None:
    """The point of the model: each branch consumed the state instead of computing its
    own answer. The old local derivations must be GONE, not merely shadowed — a
    surviving copy is exactly how two surfaces come to disagree (#1534's D1 class)."""
    assert "card.attention" in _WATER
    assert 'att.state === "cant_tell"' in _WATER
    assert 'att.state === "needs_you_now"' in _WATER
    # the retired local re-derivations
    assert "dryNow" not in _H
    assert "card.exception && card.exception.is" not in _WATER


def test_the_harm_level_renders_and_does_not_wear_a_mood_colour() -> None:
    """§6 rule 3: an attention level is not a reading. The harm line takes the state
    channel's act-now token, distinct from --st-fault (the instrument axis, R12) —
    collapsing the two would undo exactly the separation R12 just shipped."""
    assert 'att.state === "heading_for_harm"' in _WATER
    assert "getting worse faster than a normal dry-down" in _WATER
    assert ".water .harm { color: var(--st-due)" in _H
    assert "--band-" not in _WATER


# --------------------------------------------------------------------------- #
# G7 (#1587) — the greenhouse summary counts the levels and mints no words
# --------------------------------------------------------------------------- #
_SUM = _H[
    _H.index("function greenhouseSummary(") : _H.index("function nextNeedSpanHours(")
]


def test_the_summary_counts_the_model_and_defines_nothing_of_its_own() -> None:
    """§5: it AGGREGATES these words. A summary with its own vocabulary is a second
    answer to "which plants need you" — R11's complaint one layer up."""
    assert "c.attention" in _SUM or "list[i].attention" in _SUM
    for level in ("cant_tell", "heading_for_harm", "needs_you_now", "watch"):
        assert level in _SUM
    # it must not re-derive from moods or exceptions the way G3 originally did
    assert "thirsty" not in _SUM.lower()
    assert "exception" not in _SUM


def test_the_calm_signal_became_the_all_clear_case_not_a_second_computation() -> None:
    """G3's affirmative all-clear survives word for word — but as this function's
    everyone-is-fine branch, so calm and the counts cannot disagree."""
    assert "Nothing needs you right now." in _SUM
    assert "Nothing needs you for about " in _SUM
    assert "return greenhouseSummary(cards);" in _H


def test_the_horizon_constant_is_not_duplicated_client_side() -> None:
    """The composer owns the horizon (attention.CALM_HORIZON_H). A client-side copy of a
    tunable constant is the drift #1598 just closed for R3's words."""
    assert "var CALM_HORIZON_H" not in _H


def test_the_summary_claims_a_horizon_only_when_a_forecast_supports_one() -> None:
    """§6 rule 4: never a horizon Sprout cannot support."""
    assert "soonest !== null" in _SUM
    assert "Math.floor(soonest / 24)" in _SUM  # floor: a calm claim must understate
