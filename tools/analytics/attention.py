"""#1582 (R11) — the attention composer: one state per plant, resolved in one place.

R11's complaint is the reason this module exists: band mood carries *how wet*, the
exceptions lane carries *what's odd*, the forecast carries *when next* — and nothing
composed them into **"does this need me."** Four surfaces each answering that question
their own way is the same complaint one layer up, so the answer is computed here and
rendered everywhere.

The model is ``docs/design/specs/attention-model.md``. This module implements §8's
ratified resolution order and nothing else: it **consumes** already-computed fields and
re-derives none of them (§6 rule 2). If a surface needs a new word, it is raised in the
spec first.

**Two rules easy to lose in an implementation, and both the point of the model:**

- **Replace, not decorate** (§1, Data's sharpening). An instrument condition does not
  outrank the plant's mood — it *replaces* it. People read the big word, not the small
  one, so a confident mood beside a small warning chip is the failure mode. A plant
  whose probe is faulted has **no** attention level: not "fine," not "urgent."
- **Fine is not unknown.** ``CANT_TELL`` sits above everything for that reason, rather
  than folding into ``ALL_CLEAR``. *"Everything is fine"* and *"I cannot see"* are
  opposite claims, and collapsing them is the most misleading thing this surface could
  do (ADR-0028's first-class absence, applied to attention).

``urgency`` on the card is a **sort key** (dryness), never a state — measured live, a
harm-bound *Content* plant sorts below a normally-drying *Parched* one, which is the
exact inversion this model exists to catch (§7).
"""

from __future__ import annotations

from typing import NamedTuple

#: §8 level 5's horizon: how far ahead "nothing needs you" has to hold before the calm
#: signal is an affirmative all-clear rather than a shrug. A named constant because the
#: VALUE is the maintainer's (48h proposed, and eventually a measured answer from
#: ``backtest.py``) while the SHAPE is the model's. The client's G3 signal uses the same
#: number; it is stated once here so the two cannot drift apart.
CALM_HORIZON_H = 48.0

#: At or past the Thirsty entry edge — level 3. Consumed from D3's shipped list rather
#: than re-derived from raws or a fresh ladder read (§6 rule 2, one vocabulary).
DRY_NOW_BANDS = ("thirsty", "parched", "faint")

# The five states, in §8's resolution order. The key is what code branches on; the label
# is what a surface renders. Both live here so a surface cannot invent a fifth word.
CANT_TELL = "cant_tell"
HEADING_FOR_HARM = "heading_for_harm"
NEEDS_YOU_NOW = "needs_you_now"
WATCH = "watch"
ALL_CLEAR = "all_clear"

RESOLUTION_ORDER = (CANT_TELL, HEADING_FOR_HARM, NEEDS_YOU_NOW, WATCH, ALL_CLEAR)

LABELS = {
    CANT_TELL: "Can't tell",
    HEADING_FOR_HARM: "Heading for harm",
    NEEDS_YOU_NOW: "Needs you now",
    WATCH: "Watch",
    ALL_CLEAR: "All clear",
}


class AttentionState(NamedTuple):
    """§8's ratified return: ``(state, reason, evidence)``.

    A NamedTuple so it unpacks exactly as the spec writes it while still being readable
    at the call site. ``reason`` is one honest human clause — what the surface says when
    asked *why* — and ``evidence`` names the fields the decision was made from, so a
    disagreement between two surfaces is traceable to an input rather than to a guess.
    """

    state: str
    reason: str
    evidence: dict

    @property
    def label(self) -> str:
        """The rendered word for this state (§2's vocabulary, never re-minted)."""
        return LABELS[self.state]


def _trajectory_is_harm(traj: dict | None) -> bool:
    """Is this plant on an abnormal trajectory (§8 level 2, G2's signal)?

    The predicate, per #1497's founding case (#1434): a **settled drier level shift** —
    ``direction == "drier"`` and the excursion did NOT rebound. Magnitude is
    deliberately not a gate; the +991 step cleared the host's threshold but sat under
    the firmware's own, and what made it real was that it *settled and stayed*.

    ``rebound is False`` is checked identically, never falsily: a ``None`` rebound means
    *can't tell*, and an unknown must not render as "this one is getting worse." That is
    level 1's job, not level 2's — the same distinction the whole model turns on.

    ``floor_vs_rails`` rides as evidence, never as a condition: #1434's value sat
    ``within`` the rails and was still absurd, so the axis alone proves nothing.
    """
    if not isinstance(traj, dict) or not traj.get("known"):
        return False
    return traj.get("direction") == "drier" and traj.get("rebound") is False


def attention_state(card: dict, *, calm_horizon_h: float = CALM_HORIZON_H):
    """Resolve one plant's attention state. **First match wins**, in §8's order.

    Every input is an already-computed card field. The composer decides what they *mean*
    together; it never recomputes what any of them *are*.

    Returns ``None`` for a plant that is **not probed at all** (ADR-0028's by-design
    absence): it has no attention state, because attention is a claim about a
    measurement and there is no measurement. This is the one case §8's five levels do
    not cover, and neither available answer is honest — *All clear* would claim
    knowledge we do not have (the fine-is-not-unknown failure, from the other
    direction), and *Can't tell* would read as a fault on a plant we deliberately chose
    not to probe. So the state is absent rather than guessed; the surface renders the
    absence it already renders, and G7 counts the plant in its **unavailable** bucket.
    Deliberately NOT a sixth word — §6 rule 2 sends a new word to the spec first.
    """
    frame = card.get("frame") or {}
    if frame.get("state") == "sensorless":
        return None
    exception = card.get("exception") or {}
    next_need = card.get("next_need") or {}
    traj = card.get("trajectory")

    # 1. Can't tell — the measurement is untrustworthy, so it REPLACES the mood rather
    #    than sitting beside it. An untrustworthy reading predicts nothing.
    if exception.get("is"):
        return AttentionState(
            CANT_TELL,
            exception.get("reason") or "the reading can't be trusted",
            {"exception_kind": exception.get("kind")},
        )
    health = (card.get("sensor_health") or {}).get("status")
    if health == "inspect":
        return AttentionState(
            CANT_TELL,
            "this sensor needs a look before I'd trust the reading",
            {"sensor_health": health},
        )

    # 2. Heading for harm — a trajectory, not a position (§2). Above needs-you-now
    #    because a thirsty plant recovers from a late watering and one on an abnormal
    #    trajectory may not: #410's asymmetric-failure principle, silent-irreversible
    #    over noisy-recoverable. Unreachable-but-correct until #1584's field lands.
    if _trajectory_is_harm(traj):
        return AttentionState(
            HEADING_FOR_HARM,
            "this one is getting worse faster than a normal dry-down",
            {
                "kind": traj.get("kind"),
                "direction": traj.get("direction"),
                "rebound": traj.get("rebound"),
                "floor_vs_rails": traj.get("floor_vs_rails"),
                "since": traj.get("since"),
            },
        )

    # 3. Needs you now — at or past the Thirsty entry edge, D3's shipped rule.
    band = (frame.get("band") or "").strip().lower()
    if band in DRY_NOW_BANDS:
        return AttentionState(NEEDS_YOU_NOW, "water now", {"band": frame.get("band")})

    # 4. Watch — a reachable ETA inside the calm horizon. It consumes BOTH of its
    #    sources: the horizon says *when*, R3's vocabulary says *how sure* (#1598's
    #    shared home, read as a field rather than re-derived from the span).
    hours = next_need.get("hours") if next_need.get("known") else None
    if hours is not None and hours <= calm_horizon_h:
        return AttentionState(
            WATCH,
            f"needs you in about {_humanize_horizon(hours)}",
            {
                "hours": hours,
                "confidence_word": next_need.get("confidence_word"),
                "horizon_h": calm_horizon_h,
            },
        )

    # 5. All clear — affirmative, and carrying its horizon (§3: the all-clear is a claim
    #    with a shelf life, not the absence of alarm). `hours` beyond the horizon states
    #    when; no forecast states the horizon it is quiet through.
    if hours is not None:
        return AttentionState(
            ALL_CLEAR,
            f"nothing needed for about {_humanize_horizon(hours)}",
            {"hours": hours, "horizon_h": calm_horizon_h},
        )
    return AttentionState(
        ALL_CLEAR,
        "nothing needs you right now",
        {"hours": None, "horizon_h": calm_horizon_h},
    )


def _humanize_horizon(hours: float) -> str:
    """Hours as a calm phrase. Floors rather than rounds on the day boundary: 60h is
    "2 days", never "3 days" — an all-clear that rounds UP over-promises calm, which is
    the one direction this phrase must never err in (the G3 fix, kept here so both
    surfaces share the rule)."""
    if hours < 24:
        return f"{max(1, int(hours))}h"
    days = int(hours // 24)
    return "a day" if days == 1 else f"{days} days"
