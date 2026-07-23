#!/usr/bin/env python3
"""#1497 / #1434 host slice — the exception taxonomy composes what no single check saw.

The load-bearing case is the recorded #1434 event: a +991 single-step jump, every row
``quality=OK``, that settled ~400 counts DRIER than baseline and held there. The
firmware's ``max_delta_raw=1200`` let it pass and it stayed inside the rails, so neither
a rate check nor an absolute check fired. This suite pins that the COMPOSITION catches
it — a host ``rate_spike`` (past a Data-tunable threshold), going drier, that did NOT
rebound — and that the host never renames or re-judges a kind the firmware itself
declared (#1152: measurement is the wire's axis, analysis is the host's).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.analytics.parse_v1 import Reading
from tools.analytics.segment_classifier import (
    HOST_RATE_SPIKE_RAW,
    ExceptionLabel,
    exception_labels,
    exception_segments,
)

_T0 = datetime(2026, 7, 21, 15, 0, 0, tzinfo=timezone.utc)


def _r(i, raw, quality="OK", step=None, fault=None, secs=30):
    """One soil row at ``i`` steps of ``secs`` (the fleet's real 30 s cadence). ``step``
    and ``fault`` ride the payload exactly as the wire delivers them (#1463 / #670)."""
    payload = {"level": "OK"}
    if step is not None:
        payload["step"] = str(step)
    if fault is not None:
        payload["fault"] = fault
    return Reading(
        "plants.soil",
        _T0 + timedelta(seconds=secs * i),
        None,
        None,
        "sess",
        "8gtt1h",
        "0.8.0",
        "x",
        None,
        "UMLIFE_v2_TLC555",
        "s1",
        "",
        "ch1",
        raw,
        None,
        "",
        quality,
        payload,
    )


def _signed(rows):
    """Stamp each row's payload ``step`` with the signed delta from the prior row —
    the #1463 accepted-sample quantity, approximated as row-to-row for a gap-free
    fixture (0 on the seed)."""
    out = [_r(0, rows[0], step=0)]
    for i in range(1, len(rows)):
        out.append(_r(i, rows[i], step=rows[i] - rows[i - 1]))
    return out


# The verbatim #1434 bench recording (2026-07-21 15:01 UTC): baseline, the +991 spike,
# the settle ~400 drier that HELD. Every row OK on the wire.
_EVENT_1434 = [1628, 2619, 2231, 2096, 2032, 2012, 2029]


def test_the_1434_plus991_event_is_a_host_rate_spike() -> None:
    """AC2: the recorded +991 rows classify correctly. One exception, at the spike:
    a host ``rate_spike``, going drier, that did NOT rebound (held ~400 off)."""
    rows = _signed(_EVENT_1434)
    labels = exception_labels(rows)
    hits = [(k, lab) for k, lab in enumerate(labels) if lab is not None]
    assert len(hits) == 1, f"exactly the +991 step is the exception, got {hits}"
    k, lab = hits[0]
    assert k == 1  # the +991 row, not the settling tail
    assert lab.kind == "rate_spike"
    assert lab.source == "host"  # the firmware passed it (991 < 1200) — host analysis
    assert lab.direction == "drier"  # raw ROSE, moments after water: physically absurd
    assert lab.rebound is False  # settled 401 off baseline and held — a level shift
    assert lab.step == 991


def test_the_rails_axis_alone_would_have_missed_it() -> None:
    """The #1434 third gap: 2029 sits WITHIN a 2742 air rail, so a floor/rails check
    passes — numerically plausible, physically absurd. The axis reports ``within``
    honestly; it is the COMPOSITION (spike + drier + held) that catches it."""
    rows = _signed(_EVENT_1434)
    lab = next(x for x in exception_labels(rows, rails=(810, 2742)) if x is not None)
    assert lab.floor_vs_rails == "within"
    assert (lab.kind, lab.direction, lab.rebound) == ("rate_spike", "drier", False)


def test_a_drier_spike_that_reverts_reads_as_rebounded() -> None:
    """The discriminator: a spike that comes back to baseline is a transient artifact
    (a splash that cleared), not a level shift. Same magnitude, opposite verdict."""
    # +600 spike, then straight back to the 1600 baseline within the window
    rows = _signed([1600, 2200, 1610, 1602, 1600, 1601])
    lab = next(x for x in exception_labels(rows) if x is not None)
    assert lab.kind == "rate_spike" and lab.direction == "drier"
    assert lab.rebound is True  # returned to within noise of baseline — reverted


def test_a_wire_fault_keeps_the_firmwares_kind_verbatim() -> None:
    """#1152/AC3: a row the firmware flagged carries its OWN declared kind. The host
    consumes ``fault=stuck_wet``; it never renames it or re-judges the measurement."""
    rows = [
        _r(0, 1600, step=0),
        _r(1, 20, quality="SENSOR_FAULT", fault="stuck_wet", step=-1580),
        _r(2, 1600, step=1580),
    ]
    lab = exception_labels(rows)[1]
    assert lab is not None
    assert lab.kind == "stuck_wet"  # the firmware's reason, verbatim
    assert lab.source == "wire"  # never "host" — the firmware measured this


def test_a_bare_quality_flag_with_no_fault_reason_uses_the_flag() -> None:
    """A flagged row that carries no specific ``fault=`` falls back to the wire flag
    itself — still the firmware's vocabulary, still ``source="wire"``."""
    rows = [_r(0, 1600, step=0), _r(1, 1600, quality="NO_SIGNAL", step=0)]
    lab = exception_labels(rows)[1]
    assert lab is not None and lab.kind == "NO_SIGNAL" and lab.source == "wire"


def test_the_host_never_flags_a_spike_the_firmware_transient_owns() -> None:
    """A confirmed watering transient is a known wettening the classifier already owns;
    the host overlay must not re-label its steps as anomalies."""
    # a real watering: a sustained wet run (raw falls well past CONFIRM_DROP_RAW)
    rows = _signed([1800, 1180, 1120, 1100, 1090, 1085, 1084])
    labels = exception_labels(rows)
    assert all(x is None for x in labels), "a watering transient is not an exception"


def test_a_sub_threshold_step_is_not_a_spike_but_the_threshold_is_tunable() -> None:
    """AC1: thresholds are Data-tunable. A +400 step is below the 500 default (no
    exception); drop the knob to 300 and the same row fires — the value is a parameter,
    not a buried constant."""
    rows = _signed([1600, 2000, 1998, 1996, 1997])  # +400 drier, holds
    assert all(x is None for x in exception_labels(rows))
    assert HOST_RATE_SPIKE_RAW == 500
    fired = exception_labels(rows, host_spike_raw=300)
    assert fired[1] is not None and fired[1].kind == "rate_spike"


def test_floor_vs_rails_is_honest_absent_without_rails() -> None:
    """No rails supplied → the axis is ``None`` (ADR-0028 honest-absent), never a
    guessed ``within``. The classifier resolves no cal; the caller supplies rails."""
    rows = _signed(_EVENT_1434)
    lab = next(x for x in exception_labels(rows) if x is not None)
    assert lab.floor_vs_rails is None


def test_floor_vs_rails_flags_a_settle_past_a_rail() -> None:
    """A drier spike that settles ABOVE the dry/air rail reads ``above-air`` — an open
    ADC, not soil. (Wet side symmetric: below the wet rail is ``below-floor``.)"""
    rows = _signed([1600, 3200, 3210, 3205, 3208])  # spikes and HOLDS above air
    lab = next(x for x in exception_labels(rows, rails=(810, 2742)) if x is not None)
    assert lab.floor_vs_rails == "above-air"


def test_exception_segments_collapses_the_single_step_spike_to_one_event() -> None:
    """The consumer surface: one labelled event, not a row mask. #1434's spike is a
    one-row segment carrying the ``rate_spike`` label."""
    rows = _signed(_EVENT_1434)
    segs = exception_segments(rows, rails=(810, 2742))
    assert len(segs) == 1
    seg, lab = segs[0]
    assert seg.n == 1 and seg.kind == "exception:rate_spike"
    assert lab.kind == "rate_spike" and lab.direction == "drier"


def test_direction_reads_straight_off_the_signed_step() -> None:
    """The direction axis is exactly the sign of the #1463 wire step — auditable, not
    re-derived: positive (raw rose) = drier, negative = wetter, 0 = neither."""
    from tools.analytics.segment_classifier import _direction

    assert _direction(991) == "drier"
    assert _direction(-300) == "wetter"
    assert _direction(0) is None
    assert _direction(None) is None


def test_the_label_is_a_frozen_dataclass_carrying_all_four_axes() -> None:
    """Shape guard: kind · source + the three context axes + the audit step."""
    rows = _signed(_EVENT_1434)
    lab = next(x for x in exception_labels(rows, rails=(810, 2742)) if x is not None)
    assert isinstance(lab, ExceptionLabel)
    assert {
        lab.kind,
        lab.source,
        lab.direction,
        str(lab.rebound),
        lab.floor_vs_rails,
    } == {"rate_spike", "host", "drier", "False", "within"}
