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
- **rebound** — post-transient equilibration, RATE-BASED (C1): persists while the
  forward ``REBOUND_WINDOW_M`` slope >= ``REBOUND_RATE_CH`` (+c/h), hard-capped at
  ``REBOUND_MAX_H``. Rising raw here is NOT drying evidence. (C0's fixed 3 h box is
  retired — it truncated slow recoveries and over-held fast settles.)
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
# C1 rate-based rebound (the contract's calibrated defaults, Data-tunable):
REBOUND_RATE_CH = 30.0  # forward slope >= this (+c/h) = still equilibrating
REBOUND_WINDOW_M = 30.0  # the forward slope window (minutes)
REBOUND_MAX_H = 6.0  # hard cap — nothing equilibrates longer than this
# The watering PASS (the #877 retro seam, adopted): fleet-wide gap clustering of
# watering evidence. 75 min reproduces the maintainer's four session-truths 4/4
# (a naive 30 min splits her 07-10 dose session) — a calibrated contract parameter.
PASS_GAP_MIN = 75.0

# #1331: a sampling hole ends a segment. The threshold is the SHIPPED gap rule, not
# a new opinion: the dashboard already defines a logging gap as a delta over
# max(GAP_THRESHOLD_S, GAP_CADENCE_MULT x the series' own median interval) — E9. That
# is cadence-relative on purpose, because a series may be raw 30 s or decimated to
# 30 min and a fixed threshold would either miss every hole or break every row.
# Consume one definition of "a hole"; a second would drift from the shading the
# operator actually sees.
GAP_THRESHOLD_S = 120
GAP_CADENCE_MULT = 3

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
        # C1 rate-based rebound: extend while the FORWARD slope says the probe is
        # still equilibrating (>= REBOUND_RATE_CH over REBOUND_WINDOW_M), sticky on a
        # thin tail (not enough lookahead to claim it settled), hard-capped.
        t_end = rows[end].timestamp_utc
        cap = t_end + timedelta(hours=REBOUND_MAX_H)
        k = end + 1
        j = end + 1
        rebounding = True  # the transient just ended — equilibration is the prior
        while k < len(rows) and rows[k].timestamp_utc <= cap and rebounding:
            if kinds[k] != "steady-drying":  # never overwrite a later transient
                break
            horizon = rows[k].timestamp_utc + timedelta(minutes=REBOUND_WINDOW_M)
            j = max(j, k)
            while j + 1 < len(rows) and rows[j + 1].timestamp_utc <= horizon:
                j += 1
            span_h = (rows[j].timestamp_utc - rows[k].timestamp_utc) / timedelta(
                hours=1
            )
            if span_h >= (REBOUND_WINDOW_M / 60.0) / 3.0:  # enough lookahead to judge
                a, b = rows[k].raw_value, rows[j].raw_value
                rebounding = (
                    a is not None
                    and b is not None
                    and (b - a) / span_h >= REBOUND_RATE_CH
                )
            # else: thin tail — sticky (can't claim it settled without a window)
            if rebounding:
                kinds[k] = "rebound"
                k += 1
    for k, r in enumerate(rows):
        if r.quality_flag != "OK":
            kinds[k] = "flagged"  # highest precedence — the wire flagged the row
    return kinds


def gap_break_seconds(rows) -> float:
    """The hole threshold for THIS series: ``max(GAP_THRESHOLD_S, GAP_CADENCE_MULT x
    median interval)`` — the shipped E9 gap rule, applied to the series' own cadence
    so a raw 30 s stream and a decimated 30 min one are both judged fairly."""
    rows = list(rows)
    if len(rows) < 3:
        return float(GAP_THRESHOLD_S)
    deltas = sorted(
        (rows[i + 1].timestamp_utc - rows[i].timestamp_utc).total_seconds()
        for i in range(len(rows) - 1)
    )
    median = deltas[len(deltas) // 2]
    return max(float(GAP_THRESHOLD_S), GAP_CADENCE_MULT * median)


def segments(rows) -> list[Segment]:
    """Consecutive same-kind runs, in order — the golden-fixture surface.

    **A sampling hole ends a run** (#1331). Same-kind adjacency is not enough: two
    steady arcs either side of a 26-hour outage are not one segment, and treating them
    as one lets a trend fit draw a slope straight through time nobody observed —
    a phantom rate, in the exact column the predictor trains on.

    The break threshold is ``GAP_BREAK_US`` — the store contract §5 dwell cap reused
    deliberately: that cap already encodes "beyond this, an outage is not observed
    time", so a gap that stops counting toward dwell is the same gap that stops a
    segment. One rule, one constant, no second opinion about what a hole is."""
    rows = list(rows)
    kinds = classify(rows)
    break_s = gap_break_seconds(rows)
    out: list[Segment] = []
    for i, kind in enumerate(kinds):
        contiguous = out and out[-1].kind == kind and out[-1].i1 == i - 1
        if contiguous:
            gap_s = (rows[i].timestamp_utc - rows[i - 1].timestamp_utc).total_seconds()
            if gap_s > break_s:
                contiguous = False  # a hole: the previous run ends here
        if contiguous:
            last = out.pop()
            out.append(Segment(kind, last.i0, i, last.t0, rows[i].timestamp_utc))
        else:
            t = rows[i].timestamp_utc
            out.append(Segment(kind, i, i, t, t))
    return out


def valid_trend_runs(rows) -> list[tuple[int, int]]:
    """Contiguous ``steady-drying`` runs as ``(i0, i1)`` index pairs — **the surface a
    trend fit should consume** (#1331).

    ``valid_for_trend`` is a flat per-row mask, and a flat mask cannot express
    discontinuity: the last row before a 26-hour hole and the first row after it are
    BOTH honestly steady-drying, so a consumer pairing consecutive True rows fits a
    slope across time nobody observed — a phantom rate, in the exact column the
    predictor trains on. Marking either row invalid would be a lie about that row;
    the truth is about the JOIN between them, so the runs carry it.

    Each returned run is same-kind AND hole-free, so any fit over one run is a fit
    over continuously observed time."""
    out: list[tuple[int, int]] = []
    for seg in segments(rows):
        if seg.kind == "steady-drying":
            out.append((seg.i0, seg.i1))
    return out


def valid_for_trend(rows) -> list[bool]:
    """The mask the trend fit consumes: True only for steady-drying rows. A fit over
    transient/rebound/flagged rows is fitting a different physical process."""
    return [k == "steady-drying" for k in classify(rows)]


@dataclass(frozen=True)
class Pass:
    """One watering PASS (contract §3): a fleet-wide, gap-clustered group of watering
    evidence with its own identity. The operator's unit of work."""

    pass_id: str  # the cluster's ISO start-minute
    t0: object
    t1: object
    events: tuple  # the clustered (ts, source, ref) evidence, time-ordered

    @property
    def n(self) -> int:
        return len(self.events)


def passes(events, gap_min: float = PASS_GAP_MIN) -> list[Pass]:
    """Cluster watering evidence — (ts, source, ref) tuples, fleet-wide: classifier
    transient onsets ("soil") plus manual glugs ("glug") — into PASSES by time gap
    (contract §3). Derived at read time: the raw tier and the glug journal are never
    touched. 75 min is the calibrated default (the maintainer's four session-truths)."""
    evts = sorted(events, key=lambda e: e[0])
    if not evts:
        return []
    out: list[Pass] = []
    cur = [evts[0]]
    for e in evts[1:]:
        if (e[0] - cur[-1][0]) <= timedelta(minutes=gap_min):
            cur.append(e)
        else:
            out.append(_mk_pass(cur))
            cur = [e]
    out.append(_mk_pass(cur))
    return out


def _mk_pass(evts: list) -> Pass:
    t0, t1 = evts[0][0], evts[-1][0]
    return Pass(t0.strftime("%Y-%m-%dT%H:%M"), t0, t1, tuple(evts))
