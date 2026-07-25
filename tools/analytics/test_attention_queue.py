#!/usr/bin/env python3
"""#1579 (R2) — the queue orders by forecast, and does not invent a second severity.

The test that matters most is the **inversion** one: R2 exists because ordering by
``card.urgency`` puts the plant heading for harm last. Design measured that live (harm
at Content `0.28` sorting below a normally-drying Parched `0.404`), so it is pinned here
against the real numbers rather than against a story about them.

The rest pin the ruled shape: the level comes from the attention model and is not
re-derived, the forecast orders within a level, ``urgency`` only ever breaks a tie, and
a plant with no answer keeps its place instead of leading or vanishing.
"""

from __future__ import annotations

from tools.analytics import attention
from tools.analytics.attention_queue import QUEUE_ORDER, attention_queue, queue_entry


def card(
    name: str,
    *,
    band: str = "content",
    hours: float | None = None,
    urgency: float | None = 0.3,
    harm: bool = False,
    exception: str | None = None,
    sensorless: bool = False,
) -> dict:
    """A card carrying only the fields the composer consumes."""
    frame = {"state": "sensorless" if sensorless else "ok", "band": band}
    c: dict = {
        "plant_id": name,
        "name": name,
        "frame": frame,
        "urgency": urgency,
        "next_need": (
            {"known": True, "hours": hours, "confidence_word": "roughly"}
            if hours is not None
            else {"known": False}
        ),
    }
    if exception:
        c["exception"] = {"is": True, "kind": exception, "reason": "can't trust it"}
    if harm:
        # #1497's settled drier level shift — the founding case's shape
        c["trajectory"] = {
            "known": True,
            "kind": "level_shift",
            "direction": "drier",
            "rebound": False,
        }
    return c


def _names(q: dict) -> list[str]:
    return [e["name"] for e in q["queue"]]


# --------------------------------------------------------------------------- #
# the inversion R2 exists to correct — with Design's measured numbers
# --------------------------------------------------------------------------- #
def test_the_harm_bound_plant_outranks_the_drier_one_that_is_merely_thirsty() -> None:
    """Design measured `urgency` live: harm-at-Content 0.28 sorts BELOW Parched 0.404
    and Thirsty 0.397. Sorted by dryness the plant in trouble goes last; that is the
    whole complaint. Ranked by attention level it leads."""
    parched = card("parched", band="parched", urgency=0.404, hours=1.0)
    thirsty = card("thirsty", band="thirsty", urgency=0.397, hours=2.0)
    harmed = card("harmed", band="content", urgency=0.28, harm=True, hours=40.0)
    q = attention_queue([parched, thirsty, harmed])
    assert _names(q)[0] == "harmed", _names(q)
    # and the dryness sort — the one that shipped — would have put it dead last
    by_urgency = sorted(
        ["parched", "thirsty", "harmed"],
        key=lambda n: {"parched": 0.404, "thirsty": 0.397, "harmed": 0.28}[n],
        reverse=True,
    )
    assert by_urgency[-1] == "harmed"


def test_an_unreadable_plant_leads_even_with_no_eta_at_all() -> None:
    """Can't tell has no forecast to compete with, and someone has to go look. A queue
    sorted purely by hours would drop it to the bottom for having no number."""
    q = attention_queue(
        [card("dry", band="parched", hours=1.0), card("blind", exception="open_adc")]
    )
    assert _names(q) == ["blind", "dry"]


def test_ranking_only_the_display_list_would_drop_the_leader() -> None:
    """The seam rule, pinned: `/cards.json` splits its cards into a normal grid and an
    exceptions lane, and the queue must be built from BOTH. Feeding it the grid alone
    silently removes every plant someone has to go look at — the queue would then be
    calmest exactly when it should be loudest."""
    grid = [card("dry", band="parched", hours=1.0)]
    lane = [card("blind", exception="open_adc")]
    assert _names(attention_queue(grid + lane))[0] == "blind"
    assert _names(attention_queue(grid)) == ["dry"]  # what the wrong wiring produces


# --------------------------------------------------------------------------- #
# not a third ranking
# --------------------------------------------------------------------------- #
def test_the_primary_key_is_the_attention_models_own_order_not_a_copy() -> None:
    """If the spec reorders its levels, the queue must reorder with it. A copied list
    would silently disagree with the word printed on the card."""
    assert QUEUE_ORDER is attention.RESOLUTION_ORDER


def test_the_level_is_read_from_the_model_never_recomputed() -> None:
    e = queue_entry(card("p", band="thirsty", hours=3.0))
    assert e["state"] == attention.attention_state(card("p", band="thirsty")).state
    assert e["label"] == attention.LABELS[e["state"]]


# --------------------------------------------------------------------------- #
# the forecast orders within a level
# --------------------------------------------------------------------------- #
def test_within_one_level_the_sooner_forecast_comes_first() -> None:
    q = attention_queue(
        [
            card("later", band="content", hours=40.0, urgency=0.9),
            card("sooner", band="content", hours=6.0, urgency=0.1),
        ]
    )
    # both are Watch; the ETA decides — and note the dryness ordering is the opposite
    assert _names(q) == ["sooner", "later"]


def test_urgency_only_breaks_a_tie_it_never_overrides_the_forecast() -> None:
    same = [
        card("drier", band="content", hours=10.0, urgency=0.8),
        card("wetter", band="content", hours=10.0, urgency=0.2),
    ]
    assert _names(attention_queue(same)) == ["drier", "wetter"]
    # ...but a sooner ETA beats a drier plant, every time
    q = attention_queue(
        [
            card("drier", band="content", hours=10.0, urgency=0.8),
            card("sooner", band="content", hours=9.0, urgency=0.2),
        ]
    )
    assert _names(q) == ["sooner", "drier"]


# --------------------------------------------------------------------------- #
# honest absence in an ordering
# --------------------------------------------------------------------------- #
def test_an_unknown_eta_trails_its_level_rather_than_leading_or_vanishing() -> None:
    """ "I don't know when" is not "needs you soonest" — and it is not "doesn't need
    you" either. The plant keeps the level the model gave it."""
    q = attention_queue(
        [
            card("noeta", band="parched", hours=None),
            card("soon", band="parched", hours=2.0),
            card("calm", band="content", hours=100.0),
        ]
    )
    assert _names(q) == ["soon", "noeta", "calm"]


def test_a_not_probed_plant_is_unavailable_not_last() -> None:
    """Ranking it would claim a position in an ordering built from measurements it
    doesn't have. It still exists, and the operator still waters it."""
    q = attention_queue(
        [card("probed", band="thirsty", hours=1.0), card("bare", sensorless=True)]
    )
    assert _names(q) == ["probed"]
    assert [u["name"] for u in q["unavailable"]] == ["bare"]
    assert q["counts"]["unavailable"] == 1


# --------------------------------------------------------------------------- #
# what G7 reads
# --------------------------------------------------------------------------- #
def test_counts_cover_every_level_including_the_empty_ones() -> None:
    """A zero must be present, not missing: "no plants need you now" is an answer, and a
    consumer should not have to distinguish it from "that key wasn't computed"."""
    q = attention_queue([card("a", band="thirsty", hours=1.0)])
    assert set(q["counts"]) == set(QUEUE_ORDER) | {"unavailable"}
    assert q["counts"]["needs_you_now"] == 1
    assert q["counts"]["heading_for_harm"] == 0


def test_the_lead_is_the_first_plant_that_actually_needs_something() -> None:
    q = attention_queue(
        [card("dry", band="thirsty", hours=1.0), card("fine", hours=200.0)]
    )
    assert q["lead"]["name"] == "dry"


def test_a_calm_greenhouse_has_no_lead_rather_than_the_calmest_plant() -> None:
    """Naming the least-calm of several all-clear plants would read as a summons."""
    q = attention_queue([card("a", hours=200.0), card("b", hours=300.0)])
    assert q["queue"] and q["lead"] is None


def test_an_empty_greenhouse_answers_without_crashing() -> None:
    q = attention_queue([])
    assert q["queue"] == [] and q["lead"] is None and q["counts"]["unavailable"] == 0


# --------------------------------------------------------------------------- #
# reproducibility
# --------------------------------------------------------------------------- #
def test_two_identical_plants_do_not_swap_places_between_renders() -> None:
    a = card("aaa", band="content", hours=10.0, urgency=0.5)
    b = card("bbb", band="content", hours=10.0, urgency=0.5)
    assert _names(attention_queue([a, b])) == _names(attention_queue([b, a]))


def test_ranks_are_dense_and_start_at_one() -> None:
    q = attention_queue([card("a", band="parched", hours=1.0), card("b", hours=99.0)])
    assert [e["rank"] for e in q["queue"]] == [1, 2]
