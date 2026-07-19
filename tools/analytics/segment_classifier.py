#!/usr/bin/env python3
"""#1244 — C0 TRACER: rule-based segment classifier for one sensor's series.

Classifies a time-ordered (device, sensor) reading series into the #863 taxonomy's
first four kinds — ``watering-transient`` · ``rebound`` · ``steady-drying`` ·
``flagged`` — with deliberately simple, stated rules, and derives the **valid-for-trend
mask** (steady-drying only) that the Workbench trend fit consumes. A drying-rate fitted
through a watering transient or the post-watering rebound is fitting two different
physical processes as one line (the live "+206 c/h *drying* while Soaked" absurdity —
that was the rebound); the mask keeps the fit on the arc that IS drying.

C0's rules (every constant is a first-pass cut for the C1 contract to refine):

- **flagged** — an explicit ROLLUP over the wire's own quality/exception vocabulary
  (#1152 / ADR-0035 §2 owns those kinds; this module consumes, never authors — the
  #1245 containment ruling): today any row whose ``quality_flag`` isn't OK
  (NO_SIGNAL / SENSOR_FAULT / SUSPECT); C1 folds the #1152 ``fault=`` kinds in. The
  name is deliberately NOT "suspect" so wire-SUSPECT stays one concept, one owner.
- **watering-transient** — a sustained wettening run: it STARTS at a single-step raw
  drop >= ``ONSET_DROP_RAW`` (wetter = lower), CONTINUES while raw keeps falling
  (small rises <= ``NOISE_RAW`` don't end it), and is CONFIRMED only if the run's
  total fall >= ``CONFIRM_DROP_RAW`` — else those rows stay unclassified (noise). The
  raw-domain rule intentionally catches gentler waterings than the >=2-band jump
  detector (the Bromeliad case: a ~220-count drink inside one band).
- **rebound** — the ``REBOUND_H`` hours after a confirmed transient ends: water
  redistributing / a wetted probe re-equilibrating. Time-boxed in C0 (rate-based
  refinement is C1); rising raw here is NOT drying evidence.
- **steady-drying** — everything else: the default state between events.

Precedence per row: flagged > watering-transient > rebound > steady-drying.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# ---- C0 first-pass constants (stated cuts; C1 refines) ---------------------- #
ONSET_DROP_RAW = 60  # single-step fall that can start a transient (noise is ~±22)
CONFIRM_DROP_RAW = 150  # total fall a run needs to be a real watering, not noise
NOISE_RAW = 25  # a rise this small doesn't end a falling run
REBOUND_H = 3.0  # post-transient equilibration window (time-boxed in C0)

KINDS = ("watering-transient", "rebound", "steady-drying", "flagged")


@dataclass(frozen=True)
class Segment:
    """One classified run of consecutive same-kind readings."""

    kind: str
    i0: int  # first index into the (sorted) input
    i1: int  # last index, inclusive
    t0: object  # timestamp of i0
    t1: object  # timestamp of i1

    @property
    def n(self) -> int:
        return self.i1 - self.i0 + 1


def _transient_runs(rows) -> list[tuple[int, int]]:
    """Confirmed watering-transient runs as (start, end) index pairs. A run starts at
    an ONSET_DROP_RAW single-step fall, extends while falling (rises <= NOISE_RAW
    tolerated), and confirms only at CONFIRM_DROP_RAW total fall."""
    runs: list[tuple[int, int]] = []
    i = 1
    while i < len(rows):
        prev, cur = rows[i - 1].raw_value, rows[i].raw_value
        if prev is None or cur is None or prev - cur < ONSET_DROP_RAW:
            i += 1
            continue
        start = i - 1  # the last pre-drop reading anchors the run
        peak = prev
        trough = cur
        j = i
        while j + 1 < len(rows):
            nxt = rows[j + 1].raw_value
            # extend while within noise of the RUNNING TROUGH — falls extend it,
            # jitter near the bottom is tolerated, a sustained rise (the rebound
            # starting) breaks out. Anchoring to the previous row instead would let
            # a slow +10/step rebound extend the transient forever.
            if nxt is None or nxt > trough + NOISE_RAW:
                break
            j += 1
            trough = min(trough, nxt)
        if peak - trough >= CONFIRM_DROP_RAW:
            runs.append((start, j))
        i = j + 1
    return runs


def classify(rows) -> list[str]:
    """Per-row kinds for a time-ordered single-sensor series (same length as input).
    Precedence: flagged > watering-transient > rebound > steady-drying."""
    rows = list(rows)
    kinds = ["steady-drying"] * len(rows)
    for start, end in _transient_runs(rows):
        for k in range(start, end + 1):
            kinds[k] = "watering-transient"
        # the rebound window: time-boxed from the transient's last reading
        t_end = rows[end].timestamp_utc
        horizon = t_end + timedelta(hours=REBOUND_H)
        k = end + 1
        while k < len(rows) and rows[k].timestamp_utc <= horizon:
            if kinds[k] == "steady-drying":  # never overwrite a later transient
                kinds[k] = "rebound"
            k += 1
    for k, r in enumerate(rows):
        if r.quality_flag != "OK":
            kinds[k] = "flagged"  # highest precedence — the wire flagged the row
    return kinds


def segments(rows) -> list[Segment]:
    """Consecutive same-kind runs, in order — the golden-fixture surface."""
    rows = list(rows)
    kinds = classify(rows)
    out: list[Segment] = []
    for i, kind in enumerate(kinds):
        if out and out[-1].kind == kind and out[-1].i1 == i - 1:
            last = out.pop()
            out.append(Segment(kind, last.i0, i, last.t0, rows[i].timestamp_utc))
        else:
            t = rows[i].timestamp_utc
            out.append(Segment(kind, i, i, t, t))
    return out


def valid_for_trend(rows) -> list[bool]:
    """The mask the trend fit consumes: True only for steady-drying rows. A fit over
    transient/rebound/flagged rows is fitting a different physical process."""
    return [k == "steady-drying" for k in classify(rows)]
