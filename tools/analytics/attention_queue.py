"""#1579 (R2) — the ranked queue: who needs me next, by forecast rather than wetness.

R2's complaint is an **inversion**, not a missing number. Per-plant ETAs, runway bands
and attention states all exist; what nobody composed is the greenhouse-wide answer to
*"who first."* And the ordering that was there is measurably wrong for that question:
Design measured ``card.urgency`` live and it is **dryness only** — Parched ``0.404``
against Thirsty ``0.397`` (all but indistinguishable), while a plant heading for harm at
merely Content reads ``0.28`` and sorts *below both*. The plant on the bad trajectory
goes last. That is the inversion this module exists to correct.

**This is deliberately not a third ranking**, which was the ruled constraint and is also
the honest design. Two rankings already exist and each is authoritative for its own
question, so R2 composes them rather than minting a rival:

1. **The attention model (#1592 §8) gives the level.** Its resolution order is already
   the ratified answer to "how much does this need me," so the queue reuses it verbatim
   as the primary key. Re-deriving a severity here would create a second opinion that
   could disagree with the word printed on the card — the exact failure R11 was raised
   to end, one layer up.
2. **Time-to-need orders within the level** — the forecast, which is what "by forecast
   not current wetness" means.
3. **``urgency`` is the tiebreak, and only that** (§7): a sort key for dryness, never a
   state, used to separate two plants the first two keys could not.

**Why the level outranks the ETA, when R2's own title says "by forecast".** The states
are not degrees of one quantity — they answer different questions, and a smaller ETA
does not make a knowable plant more urgent than an unreadable one. *Can't tell* leads
because an untrustworthy reading has no ETA to compete with and someone has to go look;
*Heading for harm* precedes *Needs you now* on #410's asymmetric-failure principle (a
thirsty plant recovers from a late watering; one on an abnormal trajectory may not).
Sorting purely by hours would bury both under a merely-dry plant with a confident
2-hour forecast. Level first, hours within: the forecast decides the order among plants
whose claims are commensurable.

An unknown ETA sorts **last inside its level**, never first and never dropped. "I don't
know when" is not "needs you soonest", and it is not "doesn't need you" either — the
plant keeps its place in the level the model gave it (ADR-0028, applied to ordering).
"""

from __future__ import annotations

from tools.analytics.attention import RESOLUTION_ORDER, attention_state

#: The primary sort key IS §8's resolution order — same tuple, not a copy, so the queue
#: cannot drift from the word on the card. If the spec adds a level, the queue inherits
#: it; if it reorders, the queue reorders with it.
QUEUE_ORDER = RESOLUTION_ORDER

_RANK = {state: i for i, state in enumerate(QUEUE_ORDER)}


def _eta_hours(card: dict) -> float | None:
    """The forecast ETA this plant is ordered by, or None when it has no answer.

    Read from the already-computed ``next_need`` (§6 rule 2 — consume, never re-derive):
    the forecast is one calculation with one owner, and a queue that recomputed it could
    order plants by a number no surface displays.
    """
    nn = card.get("next_need") or {}
    return nn.get("hours") if nn.get("known") else None


def queue_entry(card: dict) -> dict | None:
    """One plant's place in the queue, carrying *why* it is there.

    Returns ``None`` for a plant with no attention state — a not-probed plant, which the
    model deliberately leaves absent. It is unavailable rather than last: ranking it
    would claim a position in an ordering built from measurements it does not have.

    ``basis`` names the three keys the position was decided from, in the order they were
    applied. A disagreement about the queue is then traceable to an input rather than
    argued about — the same reason the attention state carries its evidence.
    """
    st = attention_state(card)
    if st is None:
        return None
    hours = _eta_hours(card)
    return {
        "plant_id": card.get("plant_id"),
        "name": card.get("name"),
        "state": st.state,
        "label": st.label,
        "reason": st.reason,
        "hours": hours,
        "confidence_word": (card.get("next_need") or {}).get("confidence_word"),
        "urgency": card.get("urgency"),
        "basis": {
            "level": st.state,  # 1. the model's word
            "hours": hours,  # 2. the forecast, within that level
            "urgency": card.get("urgency"),  # 3. dryness, tiebreak only
        },
    }


def _sort_key(e: dict) -> tuple:
    hours = e["hours"]
    urgency = e["urgency"]
    return (
        _RANK[e["state"]],
        # a known ETA leads its level; unknown trails rather than sorting as 0h
        0 if hours is not None else 1,
        hours if hours is not None else 0.0,
        # dryness descending — the tiebreak, so it is negated rather than reversed
        -(urgency if urgency is not None else -1.0),
        # last resort: a stable, reproducible order (two identical plants must not
        # swap places between two renders of the same data)
        str(e.get("name") or ""),
        str(e.get("plant_id") or ""),
    )


def attention_queue(cards: list[dict]) -> dict:
    """The greenhouse ordered by who needs attention next, plus G7's counts.

    ``unavailable`` is a first-class bucket, not a filter: those plants exist and the
    operator still waters them. Hiding them would make the queue quietly answer a
    narrower question ("who of the probed plants") than the one it appears to answer.
    """
    entries, unavailable = [], []
    for card in cards:
        e = queue_entry(card)
        (entries if e is not None else unavailable).append(
            e
            if e is not None
            else {"plant_id": card.get("plant_id"), "name": card.get("name")}
        )
    entries.sort(key=_sort_key)
    for i, e in enumerate(entries, start=1):
        e["rank"] = i
    counts = dict.fromkeys(QUEUE_ORDER, 0)
    for e in entries:
        counts[e["state"]] += 1
    return {
        "queue": entries,
        "unavailable": unavailable,
        "counts": {**counts, "unavailable": len(unavailable)},
        # who to name when one line is all there is room for. None when the greenhouse
        # is entirely all-clear or entirely unprobed — an empty queue has no lead, and
        # naming the calmest plant would read as a summons.
        "lead": next(
            (e for e in entries if e["state"] != "all_clear"),
            None,
        ),
    }
