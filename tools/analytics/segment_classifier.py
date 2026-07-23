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

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent

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


# ---- exception taxonomy (#1497 / #1434 host slice) -------------------------- #
# The host ANALYSIS-layer descriptor for an exception: it COMPOSES the wire's exception
# vocabulary with three context axes the firmware cannot know from a single
# accepted-sample delta — direction, rebound, floor-vs-rails. It never REDEFINES a
# firmware kind (#1152's three axes: measurement = wire fault=/quality_flag, analysis =
# host). Two provenances, kept honest by ``source``: a "wire" label carries the
# firmware's own declared kind verbatim; a "host" label is an analysis detection in the
# SAME vocabulary, at a Data-tunable threshold, and is marked host-derived so it can
# never pose as a wire measurement (the #1428/#1429 falsehood shape).
#
# The #1434 lesson this exists to catch: the maintainer's watering splashed the headers;
# raw jumped +991 in one 30 s step and settled ~400 counts DRIER than baseline, holding
# there — every row ``quality=OK``. The firmware's ``max_delta_raw=1200`` let it pass
# (991 < 1200), and the value stayed inside the physical rails, so no absolute check
# fired either. Only the COMPOSITION catches it: a large single step (rate_spike), the
# wrong way (drier, moments after water), that did NOT rebound (held at a new level).

# The firmware exception-kind vocabulary (#1152 / ADR-0035 §2). The host CONSUMES these
# names; it never authors a parallel one. ``rate_spike`` is the ONLY kind the host can
# also detect itself — a single-step delta past a Data-tunable threshold the firmware's
# on-board ``max_delta_raw`` let pass; every other kind is wire-only (only the firmware
# can know a fault reason or a NO_SIGNAL).
WIRE_EXCEPTION_KINDS = ("rate_spike", "stuck_wet", "dead_adc", "open_adc")

# Data-tunable host rate-spike threshold. The firmware's on-board bound is 1200 (#1434);
# it let the +991 event pass. #1174 measured a FULL watering at ~900 counts across MANY
# 30 s steps, so a SINGLE step this side of that is instrument motion, not soil: 500
# preserves real single-step watering onsets (ONSET_DROP_RAW is 60) while catching +991
# comfortably. Host-only — it never changes what the firmware itself flagged.
HOST_RATE_SPIKE_RAW = 500

# "Rebounded to baseline" tolerance: within this many counts of the pre-excursion level
# counts as reverted (a transient artifact — a splash that came back). 3x the classifier
# noise floor. The +991 event settles 401 counts off baseline — far outside this, so it
# reads (correctly) as HELD, not rebounded: a level shift, i.e. instrument state change.
RECOVER_NOISE_RAW = 3 * NOISE_RAW


@dataclass(frozen=True)
class ExceptionLabel:
    """The host analysis-layer taxonomy for one exception (#1497).

    ``kind`` is ALWAYS a firmware exception-kind (``WIRE_EXCEPTION_KINDS`` or, for a
    wire row with only a bare ``quality_flag``, that flag). ``source`` keeps the two
    layers honest: ``"wire"`` = the firmware self-declared this on this row;
    ``"host"`` = a host analysis detection in the same vocabulary. The three context
    axes are host-derived and honest-absent (ADR-0028) — ``None``, never a faked value,
    when the input can't supply them."""

    # kind: firmware vocabulary — rate_spike | stuck_wet | dead_adc | open_adc | <flag>
    kind: str
    source: str  # "wire" | "host"
    direction: str | None  # "drier" | "wetter" | None (step 0/absent)
    rebound: bool  # True = reverted to baseline (transient); False = held (level shift)
    floor_vs_rails: str | None  # within | below-floor | above-air | None (no rails)
    step: int | None  # the signed wire step that anchors it — the audit trail (#1463)


def _direction(step: int | None) -> str | None:
    """Drier (raw rose, wetter is lower) / wetter / None — straight off the signed
    #1463 wire step, so the axis is auditable against ``step=`` on the row."""
    if step is None or step == 0:
        return None
    return "drier" if step > 0 else "wetter"


def _settled_after(rows, k: int) -> int | None:
    """The raw the series settles to after an excursion at ``k``: the last reading
    within ``REBOUND_MAX_H`` (the same cap the rebound classifier uses). The value the
    #1434 "held ~400 drier" gap is about — a rate check's window has closed by here."""
    cap = rows[k].timestamp_utc + timedelta(hours=REBOUND_MAX_H)
    settled = rows[k].raw_value
    for j in range(k + 1, len(rows)):
        if rows[j].timestamp_utc > cap:
            break
        if rows[j].raw_value is not None:
            settled = rows[j].raw_value
    return settled


def _reverted(rows, k: int) -> bool:
    """Did the excursion at ``k`` come back to within ``RECOVER_NOISE_RAW`` of its
    pre-excursion baseline inside ``REBOUND_MAX_H``? True = a transient artifact (a
    splash that reverted); False = a level shift that held (the #1434 signature)."""
    if k == 0:
        return False
    baseline = rows[k - 1].raw_value
    if baseline is None:
        return False
    cap = rows[k].timestamp_utc + timedelta(hours=REBOUND_MAX_H)
    for j in range(k + 1, len(rows)):
        if rows[j].timestamp_utc > cap:
            break
        rv = rows[j].raw_value
        if rv is not None and abs(rv - baseline) <= RECOVER_NOISE_RAW:
            return True
    return False


def _floor_vs_rails(value: int | None, rails: tuple[int, int] | None) -> str | None:
    """Where ``value`` sits against the channel rails ``(wet_raw, dry_raw)`` — wettest
    (low) and driest (high). ``None`` when no rails are supplied: honest-absent, never a
    guessed "within". The #1434 point is that this axis alone is NOT enough — 2029 sits
    ``within`` a 2742 air rail yet is absurd; it takes the whole composition."""
    if value is None or rails is None:
        return None
    wet_raw, dry_raw = rails
    if value < wet_raw:
        return "below-floor"  # wetter than any probe can read — a short / contamination
    if value > dry_raw:
        return "above-air"  # drier than open air — a disconnected / open ADC
    return "within"


def exception_labels(
    rows,
    *,
    rails: tuple[int, int] | None = None,
    host_spike_raw: int = HOST_RATE_SPIKE_RAW,
) -> list:
    """Per-row exception taxonomy (same length as input; ``None`` where a row is not an
    exception). Composes, per #1152, two provenances:

    - **wire** — any row the firmware flagged (``quality_flag != OK``): the kind is its
      own ``fault=`` reason when present, else the bare ``quality_flag``. Consumed
      verbatim — the host never re-judges what the firmware measured.
    - **host** — a row the firmware passed (``quality_flag == OK``) whose signed #1463
      ``step`` exceeds ``host_spike_raw``. A WETTER step inside a confirmed watering
      transient is suppressed (those falling runs are known wettenings the classifier
      already owns); a DRIER step is never suppressed — a transient is a wettening by
      definition, and the #1434 spike's own decay tail reads as a transient, so guarding
      on membership alone would eat the very spike. Labelled ``rate_spike``, ``source
      ="host"``.

    Every label carries the three context axes (direction · rebound · floor-vs-rails)
    the #1434 event needed and no single check had."""
    rows = list(rows)
    out: list = [None] * len(rows)
    in_transient = [False] * len(rows)
    for start, end in _transient_runs(rows):
        for k in range(start, end + 1):
            in_transient[k] = True
    for k, r in enumerate(rows):
        step = getattr(r, "step", None)
        qf = getattr(r, "quality_flag", "OK")
        if qf != "OK":
            kind = getattr(r, "fault", None) or qf  # firmware's declared kind, verbatim
            out[k] = ExceptionLabel(
                kind=kind,
                source="wire",
                direction=_direction(step),
                rebound=_reverted(rows, k),
                floor_vs_rails=_floor_vs_rails(_settled_after(rows, k), rails),
                step=step,
            )
        elif (
            step is not None
            and abs(step) > host_spike_raw
            and not (in_transient[k] and step < 0)  # a wettening a transient owns
        ):
            out[k] = ExceptionLabel(
                kind="rate_spike",  # firmware vocabulary — consumed, not invented
                source="host",
                direction=_direction(step),
                rebound=_reverted(rows, k),
                floor_vs_rails=_floor_vs_rails(_settled_after(rows, k), rails),
                step=step,
            )
    return out


def exception_segments(
    rows,
    *,
    rails: tuple[int, int] | None = None,
    host_spike_raw: int = HOST_RATE_SPIKE_RAW,
) -> list:
    """Consecutive same-``(kind, source, direction)`` exception rows collapsed into
    ``(Segment, ExceptionLabel)`` pairs — the consumer-facing surface (a card wants one
    labelled event, not a row-by-row mask). A single-step spike like #1434's +991 is a
    one-row segment; a sustained wire fault run is one segment carrying the onset's
    label (its rebound/floor axes look forward from the onset, so they describe the
    whole excursion)."""
    labels = exception_labels(rows, rails=rails, host_spike_raw=host_spike_raw)
    rows = list(rows)
    out: list = []
    i = 0
    while i < len(labels):
        lab = labels[i]
        if lab is None:
            i += 1
            continue
        j = i
        while (
            j + 1 < len(labels)
            and labels[j + 1] is not None
            and (labels[j + 1].kind, labels[j + 1].source, labels[j + 1].direction)
            == (lab.kind, lab.source, lab.direction)
        ):
            j += 1
        seg = Segment(
            f"exception:{lab.kind}",
            i,
            j,
            rows[i].timestamp_utc,
            rows[j].timestamp_utc,
        )
        out.append((seg, lab))
        i = j + 1
    return out


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
