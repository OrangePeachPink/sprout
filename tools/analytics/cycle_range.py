#!/usr/bin/env python3
"""#822 — the watering-cycle range: auto-bound the window to the last watering
instead of the clock (maintainer ruling: **B + A with the 2 h pad**).

The daily question is *"is it time to water again?"*, and a fixed 48 h chip makes the
operator do the arithmetic. This bounds the window to the **arc that answers it**: from
just before the last watering through now, so the whole dry → water → recover shape is
on screen at once.

The ruling, implemented:

- **B — the fleet chart anchors to the watering PASS**, the *resolved* event (detected
  ⊕ glug), not to a single plant's own event. A pass is the operator's unit of work
  (#1245 §3): she waters the windowsill in one round, so the fleet view's "since last
  watering" means "since that round". Per-plant cycle ranges live on the single-plant
  view, where a plant's own arc is the subject.
- **A — a 2 h lead-in pad** before the anchor, so the pre-watering dry-down edge is
  visible rather than clipped at the boundary. Without it the chart opens *at* the
  drop and the operator can't see what the soil looked like going in.
- **The 75-minute pass gap is adopted, not re-ruled** — it is already ratified and
  calibrated against her four session-truths (#1245 §3).

Absent-safe (ADR-0028): with no watering on record the range resolves to ``None`` and
the caller falls back to its fixed chip — the surface never invents an anchor, and
never silently shows a different window than the one it claims.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.segment_classifier import classify, passes  # noqa: E402

# Ruling A: the lead-in pad — how much pre-watering context rides ahead of the anchor.
LEAD_IN_H = 2.0

# The range labels this module serves. "cycle1" = since the last pass; "cycle2" = since
# the one before it (the "past 2 cycles" ask), so a cadence is comparable at a glance.
CYCLE_RANGES = ("cycle1", "cycle2")


def _soil_onsets(series: dict) -> list[tuple]:
    """Detected watering onsets as pass events ``(ts, "soil", plant_id)`` — the same
    classifier boundary every other surface reads (consume, never re-detect)."""
    events: list[tuple] = []
    for pid, rows in series.items():
        kinds = classify(rows)
        for i in range(1, len(rows)):
            if (
                kinds[i] == "watering-transient"
                and kinds[i - 1] != "watering-transient"
            ):
                events.append((rows[i - 1].timestamp_utc, "soil", pid))
    return events


def fleet_pass_anchors(series: dict, journal_events=()) -> list[datetime]:
    """Pass start-times across the fleet, newest first — the resolved anchor set
    (detected ⊕ glug, clustered at the ratified 75-min gap)."""
    events = _soil_onsets(series) + list(journal_events)
    return [p.t0 for p in sorted(passes(events), key=lambda p: p.t0, reverse=True)]


def cycle_window(
    series: dict,
    journal_events=(),
    which: str = "cycle1",
    now: datetime | None = None,
    lead_in_h: float = LEAD_IN_H,
) -> dict | None:
    """The pass-anchored window: ``{t0, t1, hours, anchor, pad_h, n_passes, label}``,
    or **None** when no watering is on record (the caller keeps its fixed chip).

    ``t0`` is the anchor minus the lead-in pad; ``t1`` is now. ``hours`` is the span
    the caller can hand to an hours-based reader unchanged, so this composes with the
    existing range machinery instead of replacing it."""
    now = now or datetime.now(timezone.utc)
    anchors = fleet_pass_anchors(series, journal_events)
    if not anchors:
        return None  # honest: no anchor exists, so no anchored window is claimed
    idx = 1 if which == "cycle2" else 0
    if idx >= len(anchors):
        # asked for two cycles with only one on record — fall back to the one that
        # EXISTS and say so, rather than silently serving a different range
        idx = len(anchors) - 1
        which_served = f"cycle{idx + 1}"
    else:
        which_served = which
    anchor = anchors[idx]
    t0 = anchor - timedelta(hours=lead_in_h)
    span_h = (now - t0) / timedelta(hours=1)
    return {
        "t0": t0.isoformat(),
        "t1": now.isoformat(),
        "hours": round(span_h, 4),
        "anchor": anchor.isoformat(),
        "pad_h": lead_in_h,
        "n_passes": len(anchors),
        "requested": which,
        "label": which_served,
        "exact": which_served == which,
    }
