_DRIFT_ENVELOPE_FRAC = 0.15_FAULT_RATE_PROMPT = 0.05_STUCK_RATE_PROMPT = 0.20_WETTER_RATE_PROMPT = 0.05"""#995 — the sensor health page (grill Q8): a health/QA readout per PHYSICAL sensor.

This extends the SENSOR_QA bench discipline (``docs/SENSOR_QA.md``) into the running
product. It is NOT a life-story of a sensor's plant assignments — it is a QA detail per
physical probe: how often it read out of envelope (wetter-than-water / drier-than-air),
stuck/stale reads (the Issue-3 "returns stale/identical readings" symptom), drift over
time, dropouts, device self-declared faults, and an honest **inspect-for-corrosion
PROMPT** — never a claim. Corrosion runs under soldermask and is an eyes-on check
(SENSOR_QA), so the product prompts the human; it does not diagnose.

Pairs with the cal validation hierarchy (#963): a sensor's health history informs how
far its calibration profile can be trusted. Pure and dependency-free (stdlib only, no
pandas, no server) so it unit-tests directly on ``parse_v1.Reading`` lists.

**Polarity (capacitive):** a higher raw ADC value is DRIER, a lower raw is WETTER. So
the ``air`` anchor is the high/dry rail and ``water`` is the low/wet rail:
``raw > air`` => drier-than-air, ``raw < water`` => wetter-than-water.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime

from parse_v1 import IMPLAUSIBLE_WET_FLOOR

# The device self-declares OK on a healthy read; anything else is a fault it flagged
# (e.g. SENSOR_FAULT). Empty/absent is treated as OK — a missing flag is not a fault.
_OK_FLAGS = {"", "OK", "ok"}

# A run of this many consecutive identical raw values is treated as "stuck" — the
# Issue-3 (ungrounded 1M-ohm resistor) symptom from SENSOR_QA: the sensor responds
# extremely slowly and returns stale/identical readings. Soil moisture drifts
# continuously, so a long exact-repeat run is a real signal, not natural stillness.
STUCK_RUN = 6

# Drift baseline: median of the first/last N soil raws. Enough samples that a single
# outlier can't move the baseline; small enough to work on a short bench log.
DRIFT_WINDOW = 20

# A gap between consecutive reads longer than this multiple of the sensor's own median
# cadence counts as a dropout (data-driven, so it adapts to any polling interval).
DROPOUT_GAP_FACTOR = 4.0

# --- inspect-for-corrosion prompt thresholds (conservative; a prompt, not a verdict) --
_WETTER_RATE_PROMPT = 0.05  # >=5% of reads wetter-than-water => possible water ingress
_STUCK_RATE_PROMPT = 0.20  # >=20% of reads inside a stuck run => stale/failing element
_FAULT_RATE_PROMPT = 0.05  # >=5% device-flagged faults
_DRIFT_ENVELOPE_FRAC = 0.15  # baseline moved >=15% of the air-water span


@dataclass
class SensorHealth:
    """One physical sensor's health readout. Counts + rates are the truth; ``status``
    and ``inspect_for_corrosion`` are a conservative rollup for the UI chip."""

    sensor_id: str
    readings: int  # soil rows with a usable raw_value
    first_utc: str | None
    last_utc: str | None
    span_hours: float | None
    faults: int  # device self-declared quality_flag != OK
    implausible_wet: int  # raw below the physical wet rail (#670): short/contamination
    drier_than_air: int | None  # raw > air anchor (None when uncalibrated)
    wetter_than_water: int | None  # raw < water anchor (None when uncalibrated)
    out_of_envelope_rate: float | None
    longest_stuck_run: int  # longest consecutive-identical raw run
    stuck_rate: float  # fraction of reads inside a run >= STUCK_RUN
    drift_raw: int | None  # last-baseline - first-baseline (None if too few samples)
    dropouts: int | None  # gaps > DROPOUT_GAP_FACTOR x median cadence
    status: str = "ok"  # ok | watch | inspect
    inspect_for_corrosion: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat() if ts else None


def _soil_raws(readings: list) -> list[int]:
    """The usable soil raw values, in reading order (env rows and blanks dropped)."""
    return [
        r.raw_value
        for r in readings
        if r.record_type.startswith("plants.soil") and r.raw_value is not None
    ]


def _longest_and_stuck(raws: list[int]) -> tuple[int, int]:
    """Longest consecutive-identical run, and how many reads sit inside any run that
    reaches ``STUCK_RUN`` (the stale-reading count that feeds ``stuck_rate``)."""
    if not raws:
        return 0, 0
    longest = 1
    run = 1
    stuck_reads = 0
    for prev, cur in zip(raws, raws[1:]):
        run = run + 1 if cur == prev else 1
        longest = max(longest, run)
        # count the whole run once it crosses the threshold (this read + the run so far)
        if run == STUCK_RUN:
            stuck_reads += STUCK_RUN
        elif run > STUCK_RUN:
            stuck_reads += 1
    return longest, stuck_reads


def _drift(raws: list[int]) -> int | None:
    """Baseline shift: median(last window) - median(first window). None until there are
    two non-overlapping windows, so drift is never invented from a handful of reads."""
    if len(raws) < 2 * DRIFT_WINDOW:
        return None
    first = statistics.median(raws[:DRIFT_WINDOW])
    last = statistics.median(raws[-DRIFT_WINDOW:])
    return round(last - first)


def _dropouts(readings: list) -> int | None:
    """Count inter-reading gaps longer than DROPOUT_GAP_FACTOR x the sensor's own median
    cadence. None until there are enough timestamped reads to know the cadence."""
    ts = [r.timestamp_utc for r in readings if r.timestamp_utc is not None]
    ts.sort()
    if len(ts) < 4:
        return None
    gaps = [(b - a).total_seconds() for a, b in zip(ts, ts[1:]) if b > a]
    gaps = [g for g in gaps if g > 0]
    if len(gaps) < 3:
        return None
    cadence = statistics.median(gaps)
    if cadence <= 0:
        return None
    return sum(1 for g in gaps if g > DROPOUT_GAP_FACTOR * cadence)


def sensor_health(
    readings: list,
    *,
    anchors: dict | None = None,
    now: datetime | None = None,
) -> SensorHealth:
    """Health for ONE physical sensor from its reading history. ``readings`` are that
    sensor's ``parse_v1.Reading`` rows (any record type; soil rows carry the moisture
    signal). ``anchors`` is the optional ``{"air": int, "water": int}`` cal envelope —
    absent, the envelope checks report None (honest: uncalibrated, not "zero problems").
    """
    sid = readings[0].sensor_id if readings else ""
    raws = _soil_raws(readings)
    timestamps = sorted(r.timestamp_utc for r in readings if r.timestamp_utc)
    first = timestamps[0] if timestamps else None
    last = timestamps[-1] if timestamps else None
    span_h = (last - first).total_seconds() / 3600.0 if first and last else None

    faults = sum(1 for r in readings if r.quality_flag not in _OK_FLAGS)
    implausible = sum(1 for r in raws if r < IMPLAUSIBLE_WET_FLOOR)

    drier = wetter = ooe_rate = None
    if anchors and anchors.get("air") is not None and anchors.get("water") is not None:
        air, water = int(anchors["air"]), int(anchors["water"])
        drier = sum(1 for v in raws if v > air)
        wetter = sum(1 for v in raws if v < water)
        ooe_rate = (drier + wetter) / len(raws) if raws else 0.0

    longest, stuck_reads = _longest_and_stuck(raws)
    stuck_rate = stuck_reads / len(raws) if raws else 0.0
    drift = _drift(raws)
    dropouts = _dropouts(readings)

    health = SensorHealth(
        sensor_id=sid,
        readings=len(raws),
        first_utc=_iso(first),
        last_utc=_iso(last),
        span_hours=round(span_h, 2) if span_h is not None else None,
        faults=faults,
        implausible_wet=implausible,
        drier_than_air=drier,
        wetter_than_water=wetter,
        out_of_envelope_rate=round(ooe_rate, 4) if ooe_rate is not None else None,
        longest_stuck_run=longest,
        stuck_rate=round(stuck_rate, 4),
        drift_raw=drift,
        dropouts=dropouts,
    )
    _assess(health, raws, anchors)
    return health


def _assess(h: SensorHealth, raws: list[int], anchors: dict | None) -> None:
    """Roll the counts up into a conservative status + corrosion PROMPT. Errs toward
    'watch', reserves 'inspect' (the eyes-on corrosion check) for the strong signals."""
    n = len(raws) or 1
    reasons: list[str] = []
    inspect = False

    if h.implausible_wet:
        inspect = True
        reasons.append(
            f"{h.implausible_wet} read(s) below the physical wet rail "
            f"({IMPLAUSIBLE_WET_FLOOR}) — a short, water ingress, or a disconnected ADC"
        )
    if h.wetter_than_water and h.wetter_than_water / n >= _WETTER_RATE_PROMPT:
        inspect = True
        reasons.append(
            f"{h.wetter_than_water} read(s) wetter-than-water "
            f"({h.wetter_than_water / n:.0%}) - possible wicking / contamination"
        )
    if h.stuck_rate >= _STUCK_RATE_PROMPT:
        inspect = True
        reasons.append(
            f"{h.stuck_rate:.0%} of reads stuck (run ≥ {STUCK_RUN}) — the Issue-3 "
            "stale-reading symptom (ungrounded 1M resistor / failing element)"
        )
    if h.faults and h.faults / n >= _FAULT_RATE_PROMPT:
        inspect = True
        reasons.append(f"{h.faults} device-flagged fault(s) ({h.faults / n:.0%})")
    if h.drift_raw is not None and anchors and anchors.get("air") is not None:
        envelope = abs(int(anchors["air"]) - int(anchors["water"])) or 1
        if abs(h.drift_raw) >= _DRIFT_ENVELOPE_FRAC * envelope:
            inspect = True
            reasons.append(
                f"baseline drifted {h.drift_raw:+d} raw "
                f"({abs(h.drift_raw) / envelope:.0%} of the envelope) over the log"
            )

    # milder signals — a 'watch', not yet an eyes-on inspection
    watch = []
    if not inspect:
        if h.wetter_than_water:
            watch.append("some wetter-than-water reads")
        if h.drier_than_air and h.drier_than_air / n >= 0.20:
            watch.append("frequently drier-than-air (dry soil, or an open sensor)")
        if h.longest_stuck_run >= STUCK_RUN:
            watch.append(f"a stuck run of {h.longest_stuck_run}")
        if h.dropouts:
            watch.append(f"{h.dropouts} dropout(s)")

    h.inspect_for_corrosion = inspect
    h.reasons = reasons if inspect else watch
    h.status = "inspect" if inspect else ("watch" if watch else "ok")


def fleet_health(
    readings: list,
    *,
    anchors_by_sensor: dict | None = None,
    now: datetime | None = None,
) -> list[SensorHealth]:
    """Health for every physical sensor present in a flat reading list, sorted by
    ``sensor_id``. ``anchors_by_sensor`` maps ``sensor_id -> {"air", "water"}`` (each
    optional). One pass groups by ``sensor_id`` preserving order within each sensor."""
    anchors_by_sensor = anchors_by_sensor or {}
    groups: dict[str, list] = {}
    for r in readings:
        groups.setdefault(r.sensor_id, []).append(r)
    out = [
        sensor_health(rs, anchors=anchors_by_sensor.get(sid), now=now)
        for sid, rs in groups.items()
    ]
    out.sort(key=lambda h: h.sensor_id)
    return out
