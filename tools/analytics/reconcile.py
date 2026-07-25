#!/usr/bin/env python3
"""#1548 (A5, the #1541 wall) — reconcile a DECLARED board against what answers.

A1 (#1544) made "a board described before it reports" representable. This is the other
half: when something finally does report, decide — is this the board she declared,
or a stranger? Bind the first; route the second to adoption (#1027). Never two
records for one board.

**Why this is a decision and not a lookup.** A declared board has a provisional id
(``pending-0N``) because ADR-0027 mints the real id ON the board — so the declaration
and the arrival share *no* identifier. There is nothing to join on. All we have is
circumstance: how many boards are pending, how many unknown ids are reporting, and
whether the board class matches what she said.

So the rule is deliberately conservative, and the ambiguous case is a first-class
outcome rather than a guess:

* **exactly one pending declaration + exactly one stranger** → ``bind``. This is day
  one for essentially every user: one board declared, one board plugged in. Binding it
  is what makes the plants she already mapped light up.
* **a class mismatch** (she declared a C5, an ESP32-classic answered) → never an
  automatic bind. The circumstance is contradicted by the one hard fact we have; a
  bind here would attach her wiring and plant mapping to the wrong hardware.
* **more than one candidate on either side** → ``ambiguous``, with the candidates
  named. Two pending boards and one arrival is a coin flip, and a coin flip that
  silently rewrites which plant is on which probe is the kind of wrong this project
  does not ship. The operator picks; the surface has what it needs to ask.
* **nothing pending** → ``adopt``: an unknown board with no declaration waiting for
  it is exactly #1027's case, unchanged.

**This module decides; it does not write.** ``plan()`` is pure. The write happens via
``registry_model.bind_device`` on an explicit control-plane POST — never as a side
effect of a read. The dashboard's ``/registry`` is a GET, and a GET that re-keys the
registry would be a surprise mutation on a refresh (and would race two open tabs).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tools.analytics.parse_v1 import board_class

# The outcomes. `bind` is the only one that mutates anything, and only on an explicit
# operator/flow action.
BIND = "bind"
ADOPT = "adopt"
AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class Plan:
    """What to do about one board that reported and isn't in the registry."""

    action: str  # BIND | ADOPT | AMBIGUOUS
    device_id: str  # the id that reported (the real, board-minted one)
    pending_id: str | None = None  # the declaration to bind it to, when unambiguous
    candidates: tuple[str, ...] = ()  # pending ids it *could* be, when ambiguous
    reason: str = ""  # plain language, for the surface to render verbatim


@dataclass
class Reconciliation:
    """The whole picture: one plan per reporting stranger, plus the declarations still
    waiting. The surface renders both — "3 boards waiting" is as much a state as "a new
    board arrived"."""

    plans: list[Plan] = field(default_factory=list)
    still_pending: list[str] = field(default_factory=list)

    @property
    def binds(self) -> list[Plan]:
        return [p for p in self.plans if p.action == BIND]


def _classes_conflict(declared_board: str | None, seen_board: str | None) -> bool:
    """True only when BOTH sides state a class and they disagree. An absent class on
    either side is not evidence of anything (ADR-0028: absence is honest, never a
    mismatch), so it does not block a bind."""
    if not declared_board or not seen_board:
        return False
    return board_class(declared_board) != board_class(seen_board)


def plan(model, undeclared: list | None = None) -> Reconciliation:
    """Decide what each reporting-but-unregistered board means, given the declarations.

    ``undeclared`` is ``device_discovery.discover_undeclared``'s output (#1027 §5.1) —
    consumed, never re-derived, so "which boards are strangers" has one definition.
    """
    strangers = list(undeclared or [])
    pending = model.pending_devices()
    pending_ids = [d.get("device_id") for d in pending]
    by_id = {d.get("device_id"): d for d in pending}
    out = Reconciliation(still_pending=list(pending_ids))

    for s in strangers:
        did = s.get("device_id")
        if not did:
            continue
        if not pending_ids:
            out.plans.append(
                Plan(
                    ADOPT,
                    did,
                    reason=(
                        "No board is waiting to be matched, so this is a new board — "
                        "adopt it to start using it."
                    ),
                )
            )
            continue

        # Class is the one hard fact we have; use it to rule candidates OUT.
        seen_board = s.get("board")
        fits = [
            pid
            for pid in pending_ids
            if not _classes_conflict(by_id[pid].get("board"), seen_board)
        ]
        if not fits:
            names = ", ".join(
                f"{by_id[p].get('name')} ({by_id[p].get('board')})" for p in pending_ids
            )
            out.plans.append(
                Plan(
                    ADOPT,
                    did,
                    reason=(
                        f"This board reports as {seen_board or 'an unknown class'}, "
                        f"which doesn't match what's waiting ({names}) — so it's a "
                        "different board, not the one you described."
                    ),
                )
            )
            continue
        if len(fits) == 1 and len(strangers) == 1:
            pid = fits[0]
            out.plans.append(
                Plan(
                    BIND,
                    did,
                    pending_id=pid,
                    reason=(
                        f"This is the board you described as "
                        f'"{by_id[pid].get("name")}" — it\'s reporting now.'
                    ),
                )
            )
            continue
        out.plans.append(
            Plan(
                AMBIGUOUS,
                did,
                candidates=tuple(fits),
                reason=(
                    "More than one board could be this one — pick which declaration it "
                    "is, so the plants you mapped go to the right probes."
                ),
            )
        )
    return out


def apply_plan(model, p: Plan, *, now: str | None = None) -> dict | None:
    """Execute one BIND plan. Anything else is a no-op returning None — an ``adopt`` or
    ``ambiguous`` outcome is a question for the operator, and this function refusing to
    act on it is the point."""
    if p.action != BIND or not p.pending_id:
        return None
    return model.bind_device(p.pending_id, p.device_id, now=now)
