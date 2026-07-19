#!/usr/bin/env python3
"""Windowed band-movement substrate (#626, PRD-0007 slice 2).

Per (device, channel) entity over a window, three derived facts:

- **where it is now** - the latest band + its raw count + timestamp;
- **the touched-band span** - the wettest and driest bands the entity actually
  reached in the window (not a range of raw counts - a range of *bands*, the
  honest unit); and
- **the discrete transition sequence** - the ordered band changes with their
  timestamps. This is the movement *trail's* data: a step function, never an
  interpolated line, because a band change is a discrete event, not a slope.

All of it is derived and rebuildable - never a source of truth - and computed
entirely off ``Reading.band``, the device-emitted per-row ground truth
(``payload.level``, parse_v1 / ADR-0021). Nothing is re-thresholded here; the raw
count rides along only as the current-position detail.

**Honesty (R7).** A reading with no ground-truth band (``band is None``) or a
``NO_SIGNAL`` quality carries no movement, so it is excluded. An entity with zero
band-bearing readings yields **no aggregation at all** - this layer never invents
a trail for a silent channel. Deciding "is this channel even wired?" stays the
caller's registry gate (#616); here we simply produce nothing from nothing.

**Fencing (R8).** Entities key on ``(device_id, sensor_id)``. An optional
``canonical`` callable (``Registry.canonical_for``) coalesces a renamed board's
prior ids first (#602/#604), so one board's whole history is one entity - exactly
how the dashboard groups it - while the raw rows keep the ids they truthfully
reported.

**The "since last re-water" window - the open question, resolved.** There is no
watering-event stream yet (a logged "I watered p03 at 14:02" is W3 territory), so
"since last re-water" is *detected*, not *logged*: the most recent sharp wettening
- a jump of >= ``REWATER_WET_JUMP`` bands toward wet that lands at ``OK`` or wetter.
It is always surfaced **labeled ``source="detected"``**, so the view can say
"since a detected watering" and never overclaim a record that doesn't exist. When
nothing qualifies, the window is simply unavailable for that entity (honest
absence, not a guessed origin).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from parse_v1 import BANDS_DRY_TO_WET

# Higher index = wetter (air-dry=0 .. submerged=6). The one ordering, from the
# parse boundary (the leaf), so this module never re-defines the band vocabulary.
_BAND_INDEX = {name: i for i, name in enumerate(BANDS_DRY_TO_WET)}

# A detected re-water: the band jumps at least this many steps toward wet AND
# lands at OK-or-wetter. Two steps keeps a small dry-side wiggle from reading as a
# watering; landing wet keeps a dry->less-dry drift from doing so either.
REWATER_WET_JUMP = 2
_OK_INDEX = _BAND_INDEX["OK"]


def _band_bearing(r) -> bool:
    """A reading that actually carries movement: a real device-emitted band and
    not an explicit no-signal (R7 - no invented trail for a silent channel)."""
    return r.band in _BAND_INDEX and r.quality_flag != "NO_SIGNAL"


def _iso(dt) -> str:
    """A datetime -> the canonical UTC string the dashboard emits elsewhere
    (``last_seen_utc``, dashboard.py) - second precision, trailing Z."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class BandMovement:
    """One entity's band movement over a window. ``span`` is in *bands* (the index
    delta wettest-minus-driest), 0 meaning it never left a single band."""

    device_id: str  # canonical (coalesced) identity
    sensor_id: str
    n: int  # band-bearing readings counted
    current: dict  # {"band", "raw", "ts"} - the latest band-bearing reading
    driest: str  # driest band reached in the window
    wettest: str  # wettest band reached in the window
    span: int  # wettest index - driest index (>= 0)
    transitions: list[dict] = field(default_factory=list)  # [{"ts","band"}]
    rewater: dict | None = None  # {"ts","source":"detected"} or None (unavailable)

    @property
    def key(self) -> tuple[str, str]:
        return (self.device_id, self.sensor_id)


def _entity_key(r, canonical) -> tuple[str, str]:
    did = canonical(r.device_id) if canonical else r.device_id
    return (did or "", r.sensor_id or "")


def _detect_rewater(ordered: list):
    """The datetime of the most recent detected re-water in a time-ordered,
    band-bearing run, or None. A re-water is a >= REWATER_WET_JUMP wettening that
    lands at OK-or-wetter. Returns the raw datetime (for windowing); the caller
    formats it for output."""
    latest = None
    prev_i = None
    for r in ordered:
        i = _BAND_INDEX[r.band]
        if prev_i is not None and (i - prev_i) >= REWATER_WET_JUMP and i >= _OK_INDEX:
            latest = r.timestamp_utc
        prev_i = i
    return latest


def segment_start(readings):
    """#1133: the current inter-watering segment's start = the most recent DETECTED
    re-water among ``readings`` (the #875 Q2 seam), or None when none is detected (then
    the whole window is one segment). Trends/forecasts bind to this so a least-squares
    fit never bridges a watering event — a line across the dry-down→rewater→dry-down
    sawtooth averages physically unrelated arcs. A future manual watering-log cuts here
    too (the fail-safe edge). Returns the raw datetime; the caller windows on it."""
    ordered = sorted(
        (r for r in readings if _band_bearing(r)), key=lambda r: r.timestamp_utc
    )
    return _detect_rewater(ordered) if ordered else None


def _movement_for(ordered: list, device_id: str, sensor_id: str) -> BandMovement:
    """Aggregate one entity's time-ordered, band-bearing readings."""
    indices = [_BAND_INDEX[r.band] for r in ordered]
    driest_i, wettest_i = min(indices), max(indices)
    transitions: list[dict] = []
    last_band = None
    for r in ordered:
        if r.band != last_band:  # the first reading + every change = a trail step
            transitions.append({"ts": _iso(r.timestamp_utc), "band": r.band})
            last_band = r.band
    last = ordered[-1]
    rw = _detect_rewater(ordered)
    return BandMovement(
        device_id=device_id,
        sensor_id=sensor_id,
        n=len(ordered),
        current={
            "band": last.band,
            "raw": last.raw_value,
            "ts": _iso(last.timestamp_utc),
        },
        driest=BANDS_DRY_TO_WET[driest_i],
        wettest=BANDS_DRY_TO_WET[wettest_i],
        span=wettest_i - driest_i,
        transitions=transitions,
        rewater={"ts": _iso(rw), "source": "detected"} if rw else None,
    )


def band_movements(
    readings, *, since_rewater: bool = False, canonical=None
) -> list[BandMovement]:
    """Per-entity band movement over the readings given (the caller windows the
    input first - e.g. ``filter_since`` for 15 min / 24 h / 7 d).

    ``since_rewater=True`` restricts *each entity* to the readings at/after its own
    last detected re-water before aggregating - the per-entity fourth window. An
    entity with no detected re-water is omitted (its window is honestly
    unavailable), never silently widened to "all".

    ``canonical`` (``Registry.canonical_for``) coalesces renamed ids first (R8).
    Returns entities sorted by ``(device_id, sensor_id)``; entities with no
    band-bearing reading are absent (R7)."""
    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for r in readings:
        if _band_bearing(r):
            grouped[_entity_key(r, canonical)].append(r)

    out: list[BandMovement] = []
    for (device_id, sensor_id), rs in grouped.items():
        ordered = sorted(rs, key=lambda r: r.timestamp_utc)
        if since_rewater:
            rw = _detect_rewater(ordered)  # the datetime, or None
            if rw is None:
                continue  # honest absence - no detected origin, no window
            ordered = [r for r in ordered if r.timestamp_utc >= rw]
        out.append(_movement_for(ordered, device_id, sensor_id))
    return sorted(out, key=lambda m: m.key)


def as_dict(m: BandMovement) -> dict:
    """JSON-ready shape for the substrate blob (#627 consumes this)."""
    return {
        "device_id": m.device_id,
        "sensor_id": m.sensor_id,
        "n": m.n,
        "current": m.current,
        "driest": m.driest,
        "wettest": m.wettest,
        "span": m.span,
        "transitions": m.transitions,
        "rewater": m.rewater,
    }
