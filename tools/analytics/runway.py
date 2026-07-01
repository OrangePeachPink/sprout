#!/usr/bin/env python3
"""Basin depletion -> runway in human terms (PRD-0006 R1, #478).

The autonomous-watering vision (PRD-0006) asks for exactly *one* recurring human
action: refill the basin that feeds the pumps - and to be told a refill is coming
*before* it's urgent. R1 is the estimate underneath that promise: from the basin's
capacity + current level (#19) and the pump's throughput x cycle schedule, how much
**runway** is left, expressed the way a person acts on it - *act today* / *a couple
of days* / *good for ~a week* / *plenty*.

Honest-data law (this repo's spine): the runway is a **clearly-labelled derived
value**, never false precision. Until R5 measures the real L/hr on the actual lift
and line, the pump rate is a datasheet *assumption*, so the estimate carries a
``confidence`` of ``"low"`` and a caveat naming what would sharpen it. R4/R5 refine
the inputs; the banding here stays deliberately coarse because coarse-but-honest
beats precise-but-wrong for a "go refill" nudge.

Start simple (PRD-0006 R1): pump-cycle accounting is most of the signal. This module
is input-driven - it takes capacity, level, and either a daily draw or a pump
schedule - so it is testable and demoable without live basin telemetry. Wiring the
current level from the #19 sensor and the measured rate from R5 are later slices.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

# Human-terms bands, in days of remaining runway. Coarse on purpose (see module
# docstring): the point is an actionable nudge, not a countdown timer.
_ACT_TODAY_DAYS = 1.0
_FEW_DAYS_DAYS = 3.0
_ABOUT_WEEK_DAYS = 8.0


@dataclass
class RunwayEstimate:
    """A runway estimate as a labelled derived value (PRD-0006 R1 AC)."""

    band: str  # machine token: act-today | a-couple-days | about-a-week | plenty
    human: str  # the phrase a person acts on
    confidence: str  # "low" until R5 measures the rate; "moderate" once measured
    label: str  # what this value is + what would sharpen it
    days_remaining: float | None
    liters_remaining: float | None
    daily_draw_l: float | None
    caveats: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "band": self.band,
            "human": self.human,
            "confidence": self.confidence,
            "label": self.label,
            "days_remaining": self.days_remaining,
            "liters_remaining": self.liters_remaining,
            "daily_draw_l": self.daily_draw_l,
            "caveats": list(self.caveats),
        }


def daily_draw_from_schedule(
    rate_l_per_hr: float, seconds_per_cycle: float, cycles_per_day: float
) -> float:
    """Litres drawn per day from pump-cycle accounting: rate x on-time x cadence.

    This is the "pump-cycle accounting is most of the signal" path (PRD-0006 R1).
    ``rate_l_per_hr`` is the pump's throughput (assumed from the datasheet until R5
    measures it); ``seconds_per_cycle`` x ``cycles_per_day`` is the daily on-time."""
    if rate_l_per_hr <= 0 or seconds_per_cycle <= 0 or cycles_per_day <= 0:
        return 0.0
    on_hours_per_day = (seconds_per_cycle * cycles_per_day) / 3600.0
    return rate_l_per_hr * on_hours_per_day


def _band(days: float | None) -> tuple[str, str]:
    """Map days-of-runway to a (machine token, human phrase) pair."""
    if days is None:
        return "plenty", "plenty of runway (no measured draw yet)"
    if days < _ACT_TODAY_DAYS:
        return "act-today", "act today"
    if days < _FEW_DAYS_DAYS:
        return "a-couple-days", "a couple of days"
    if days < _ABOUT_WEEK_DAYS:
        return "about-a-week", "good for ~a week"
    return "plenty", "plenty of runway"


def estimate_runway(
    capacity_l: float,
    current_l: float,
    daily_draw_l: float | None,
    *,
    rate_measured: bool = False,
) -> RunwayEstimate:
    """Estimate basin runway in human terms - a labelled, honest derived value.

    ``capacity_l`` bounds the reading; ``current_l`` is the level now (#19);
    ``daily_draw_l`` is the litres/day the pumps pull (from
    :func:`daily_draw_from_schedule` or a measured draw). ``rate_measured`` flags
    that the underlying rate came from R5's real measurement rather than a datasheet
    assumption, which is the only thing that lifts confidence above ``"low"``."""
    caveats: list[str] = []
    level = max(0.0, min(current_l, capacity_l))
    if current_l > capacity_l:
        caveats.append("reported level exceeds capacity; clamped to full")
    if current_l < 0:
        caveats.append("reported level below zero; clamped to empty")

    confidence = "moderate" if rate_measured else "low"
    if rate_measured:
        label = "derived runway estimate - pump-cycle accounting, measured rate (R5)"
    else:
        label = (
            "derived runway estimate - pump-cycle accounting; pump rate assumed from "
            "datasheet (R5 will measure real L/hr; lift/line not yet corrected)"
        )
        caveats.append("pump rate is a datasheet assumption until R5 measures it")

    # No draw (pumps idle / rate unknown): runway is not act-today - say so honestly
    # rather than inventing a number.
    if daily_draw_l is None or daily_draw_l <= 0:
        caveats.append("no positive daily draw supplied; runway is indeterminate")
        return RunwayEstimate(
            band="plenty",
            human="plenty of runway (no measured draw yet)",
            confidence="low",
            label=label,
            days_remaining=None,
            liters_remaining=round(level, 3),
            daily_draw_l=daily_draw_l,
            caveats=caveats,
        )

    days = level / daily_draw_l
    token, human = _band(days)
    if level <= 0:
        token, human = "act-today", "act today - basin empty"
    return RunwayEstimate(
        band=token,
        human=human,
        confidence=confidence,
        label=label,
        days_remaining=round(days, 2),
        liters_remaining=round(level, 3),
        daily_draw_l=round(daily_draw_l, 4),
        caveats=caveats,
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Basin depletion -> runway in human terms (PRD-0006 R1).",
    )
    p.add_argument("--capacity", type=float, required=True, help="basin capacity, L")
    p.add_argument("--level", type=float, required=True, help="current level, L (#19)")
    draw = p.add_mutually_exclusive_group(required=True)
    draw.add_argument("--daily-draw", type=float, help="known litres drawn per day")
    draw.add_argument(
        "--rate",
        type=float,
        help="pump throughput, L/hr (with --cycle-* to derive draw)",
    )
    p.add_argument("--cycle-seconds", type=float, help="pump on-seconds per cycle")
    p.add_argument("--cycles-per-day", type=float, help="pump cycles per day")
    p.add_argument(
        "--rate-measured",
        action="store_true",
        help="the rate came from R5's real measurement (lifts confidence)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.daily_draw is not None:
        daily = args.daily_draw
    else:
        if args.cycle_seconds is None or args.cycles_per_day is None:
            print(
                "error: --rate needs --cycle-seconds and --cycles-per-day",
                file=sys.stderr,
            )
            return 2
        daily = daily_draw_from_schedule(
            args.rate, args.cycle_seconds, args.cycles_per_day
        )
    est = estimate_runway(
        args.capacity, args.level, daily, rate_measured=args.rate_measured
    )
    print(f"runway: {est.human}  [{est.confidence} confidence]")
    if est.days_remaining is not None:
        print(
            f"  ~{est.days_remaining} days  "
            f"({est.liters_remaining} L left, {est.daily_draw_l} L/day)"
        )
    print(f"  {est.label}")
    for c in est.caveats:
        print(f"  - {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
