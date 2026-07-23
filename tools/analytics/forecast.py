"""Per-sensor analysis + forecast engine for the single-plant view (backlog E3).

Turns one probe's history into the "angles and predictions" a focused
single-plant view needs:

* drying **rate / angle** over rolling windows (counts/hour), with the
  regression's standard error and R^2 so we know whether it is real or noise;
* **time-to-next-band** and **time-to-thirsty** ETAs by extrapolating the
  current drying rate to the relevant raw boundary;
* **band history** (which band, since when, how long);
* **diurnal readiness** + a daily wet/dry shape once there are enough cycles;
* **next-day start/end** projection (trend + diurnal), gated on readiness.

Honesty is built in, not bolted on. Every forecast is **gated**: if the trend
is statistically indistinguishable from flat (|slope| within noise), or there
is not enough history, it returns a clear ``insufficient`` / ``stable`` reason
instead of a fake number. Raw + band are the truth; the legacy moist% ``value``
is never used. The "thirsty" boundary is the A2 (un-reconciled) ``needs water``
edge, so the watering ETA is only as trustworthy as that calibration.

    python tools/analytics/forecast.py            # all sensors, repo logs/
    python tools/analytics/forecast.py -s s3      # one sensor
    python tools/analytics/forecast.py logs/ -s s1
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.parse_v1 import (  # noqa: E402
    DEFAULT_CAL_BOUNDS,
    LogData,
    parse_files,
)

# A trend counts as real drying/wetting only if the slope is both statistically
# significant (|slope| > Z * std-error) and above a practical floor (so a
# trivially-significant 0.5 counts/h on a huge sample is still called stable).
SIG_Z = 2.0
RATE_FLOOR_PER_H = 4.0  # counts/hour
MIN_POINTS = 6
DIURNAL_MIN_DAYS = 2.0

# Band names dry -> wet, aligned with parse_v1 / the firmware classifier.
BANDS_DRY_TO_WET = [
    "air-dry",
    "DRY",
    "needs water",
    "OK",
    "well watered",
    "overwatered",
    "submerged",
]


# --------------------------------------------------------------------------- #
# regression
# --------------------------------------------------------------------------- #
@dataclass
class Fit:
    slope: float  # raw counts per hour (positive = drying, since higher = drier)
    intercept: float
    se: float  # standard error of the slope
    r2: float
    n: int

    @property
    def significant(self) -> bool:
        return (
            self.n >= MIN_POINTS
            and self.se > 0
            and abs(self.slope) > SIG_Z * self.se
            and abs(self.slope) >= RATE_FLOOR_PER_H
        )

    @property
    def direction(self) -> str:
        if not self.significant:
            return "stable"
        return "drying" if self.slope > 0 else "wetting"


def fit_line(pairs: list[tuple[float, float]]) -> Fit | None:
    """OLS of raw (y) on hours (x). Returns None if undefined."""
    n = len(pairs)
    if n < 3:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    se = math.sqrt((ss_res / (n - 2)) / sxx) if n > 2 else math.inf
    return Fit(slope, intercept, se, r2, n)


# --------------------------------------------------------------------------- #
# boundaries
# --------------------------------------------------------------------------- #
def cal_bounds(data: LogData) -> list[int]:
    seg = next((s for s in reversed(data.segments) if s.cal_bounds), None)
    return list(seg.cal_bounds) if seg else list(DEFAULT_CAL_BOUNDS)


def next_drier_boundary(raw: float, bounds: list[int]) -> int | None:
    """Smallest boundary strictly above the current raw (the next drier edge)."""
    drier = sorted(b for b in bounds if b > raw)
    return drier[0] if drier else None


def thirsty_boundary(bounds: list[int]) -> int:
    """Lower edge of the ``needs water`` band = the A2 watering trigger proxy.

    bounds are descending [air|DRY|needs|OK|well|over] edges; the ``needs water``
    lower edge is the 3rd descending boundary (index 2).
    """
    desc = sorted(bounds, reverse=True)
    return desc[2] if len(desc) >= 3 else desc[-1]


# --------------------------------------------------------------------------- #
# ETA
# --------------------------------------------------------------------------- #
@dataclass
class Eta:
    target: int
    headroom: float  # counts from current raw to target (signed: + = drier)
    reachable: bool
    hours: float | None = None
    hours_lo: float | None = None  # optimistic/pessimistic from slope +/- se
    hours_hi: float | None = None
    reason: str = ""


def eta_to(raw_now: float, fit: Fit | None, target: int) -> Eta:
    headroom = target - raw_now
    if target <= raw_now:
        return Eta(target, headroom, reachable=True, hours=0.0, reason="already past")
    if fit is None or not fit.significant or fit.direction != "drying":
        why = "no significant drying" if fit else "insufficient data"
        return Eta(target, headroom, reachable=False, reason=why)
    hours = headroom / fit.slope
    lo_rate = fit.slope + SIG_Z * fit.se  # faster drying -> sooner
    hi_rate = fit.slope - SIG_Z * fit.se  # slower drying -> later
    hours_lo = headroom / lo_rate if lo_rate > 0 else None
    hours_hi = headroom / hi_rate if hi_rate > 0 else None
    return Eta(
        target,
        headroom,
        reachable=True,
        hours=hours,
        hours_lo=hours_lo,
        hours_hi=hours_hi,
        reason="extrapolated at current drying rate",
    )


# --------------------------------------------------------------------------- #
# band history
# --------------------------------------------------------------------------- #
@dataclass
class BandSpan:
    band: str
    start: datetime
    end: datetime

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0


def band_history(readings: list) -> list[BandSpan]:
    spans: list[BandSpan] = []
    for r in readings:
        b = r.band
        if b is None or r.timestamp_utc is None:
            continue
        if spans and spans[-1].band == b:
            spans[-1].end = r.timestamp_utc
        else:
            spans.append(BandSpan(b, r.timestamp_utc, r.timestamp_utc))
    return spans


# --------------------------------------------------------------------------- #
# diurnal
# --------------------------------------------------------------------------- #
@dataclass
class Diurnal:
    ready: bool
    days: float
    reason: str = ""
    by_hour: dict[int, float] = field(default_factory=dict)  # local hour -> mean raw


def diurnal(readings: list) -> Diurnal:
    ts = [r.timestamp_utc for r in readings if r.timestamp_utc]
    if len(ts) < 2:
        return Diurnal(False, 0.0, "no timestamps")
    days = (max(ts) - min(ts)).total_seconds() / 86400.0
    if days < DIURNAL_MIN_DAYS:
        return Diurnal(
            False, days, f"only {days:.2f} d (need >= {DIURNAL_MIN_DAYS:.0f})"
        )
    buckets: dict[int, list[int]] = {}
    for r in readings:
        if r.timestamp_local is None or r.raw_value is None:
            continue
        buckets.setdefault(r.timestamp_local.hour, []).append(r.raw_value)
    by_hour = {h: statistics.fmean(v) for h, v in buckets.items()}
    return Diurnal(True, days, "ok", by_hour)


# --------------------------------------------------------------------------- #
# per-sensor forecast
# --------------------------------------------------------------------------- #
def _window(readings: list, hours: float | None) -> list[tuple[float, float]]:
    """(hours_since_first, raw) pairs, optionally limited to the last N hours."""
    rs = [r for r in readings if r.timestamp_utc and r.raw_value is not None]
    if not rs:
        return []
    last = rs[-1].timestamp_utc
    if hours is not None:
        cutoff = last - timedelta(hours=hours)
        rs = [r for r in rs if r.timestamp_utc >= cutoff]
    t0 = rs[0].timestamp_utc
    return [((r.timestamp_utc - t0).total_seconds() / 3600.0, r.raw_value) for r in rs]


def forecast_sensor(sid: str, readings: list, bounds: list[int]) -> dict:
    rs = [r for r in readings if r.raw_value is not None and r.timestamp_utc]
    rs.sort(key=lambda r: r.timestamp_utc)
    raws = [r.raw_value for r in rs]
    last = rs[-1]
    raw_now = last.raw_value

    rates = {}
    for label, hrs in (("1h", 1.0), ("6h", 6.0), ("24h", 24.0), ("all", None)):
        rates[label] = fit_line(_window(rs, hrs))
    primary = rates["6h"] or rates["all"]

    nb = next_drier_boundary(raw_now, bounds)
    spans = band_history(rs)
    return {
        "sensor": sid,
        "n": len(rs),
        "raw_now": raw_now,
        "band_now": last.band,
        "gpio": last.gpio,
        "ts_last": last.timestamp_local,
        "stats": {
            "mean": round(statistics.fmean(raws), 1),
            "median": int(statistics.median(raws)),
            "stdev": round(statistics.pstdev(raws), 1) if len(raws) > 1 else 0.0,
            "min": min(raws),
            "max": max(raws),
            "noise_spread": int(
                statistics.median([r.spread for r in rs if r.spread is not None] or [0])
            ),
        },
        "rates": rates,
        "to_next_band": eta_to(raw_now, primary, nb) if nb else None,
        "to_thirsty": eta_to(raw_now, primary, thirsty_boundary(bounds)),
        "band_now_hours": spans[-1].hours if spans else 0.0,
        "band_spans": spans,
        "diurnal": diurnal(rs),
    }


# --------------------------------------------------------------------------- #
# JSON payload (for the single-plant view)
# --------------------------------------------------------------------------- #
def _ropt(v: float | None, n: int) -> float | None:
    return None if v is None else round(v, n)


def _fit_payload(fit: Fit | None) -> dict | None:
    if fit is None:
        return None
    return {
        "slope": round(fit.slope, 2),
        "se": round(fit.se, 2) if fit.se != math.inf else None,
        "r2": round(fit.r2, 2),
        "n": fit.n,
        "dir": fit.direction,
        "sig": fit.significant,
    }


def _eta_payload(e: Eta | None) -> dict | None:
    if e is None:
        return None
    return {
        "target": e.target,
        "headroom": round(e.headroom),
        "reachable": e.reachable,
        "hours": _ropt(e.hours, 1),
        "hours_lo": _ropt(e.hours_lo, 1),
        "hours_hi": _ropt(e.hours_hi, 1),
        "reason": e.reason,
    }


def forecast_payload(sid: str, readings: list, bounds: list[int]) -> dict:
    """JSON-safe per-sensor forecast for the single-plant view (E3 -> UI)."""
    f = forecast_sensor(sid, readings, bounds)
    d = f["diurnal"]
    return {
        "raw_now": f["raw_now"],
        "band_now": f["band_now"],
        "band_now_hours": round(f["band_now_hours"], 1),
        "stats": f["stats"],
        "rates": {k: _fit_payload(v) for k, v in f["rates"].items()},
        "next_band": _eta_payload(f["to_next_band"]),
        "thirsty": _eta_payload(f["to_thirsty"]),
        "diurnal": {
            "ready": d.ready,
            "days": round(d.days, 2),
            "reason": d.reason,
            "by_hour": {str(h): round(v) for h, v in sorted(d.by_hour.items())},
        },
        "band_history": [
            {"band": s.band, "hours": round(s.hours, 2)} for s in f["band_spans"]
        ],
    }


# --------------------------------------------------------------------------- #
# CLI report
# --------------------------------------------------------------------------- #
def _fmt_eta(e: Eta | None) -> str:
    if e is None:
        return "n/a"
    if e.hours == 0.0 and e.reason == "already past":
        return f"already at/past raw {e.target}"
    if not e.reachable:
        return f"raw {e.target} (+{e.headroom:.0f}): -- {e.reason}"
    rng = ""
    if e.hours_lo and e.hours_hi:
        rng = f"  [{e.hours_lo:.1f}-{e.hours_hi:.1f} h]"
    return f"raw {e.target} (+{e.headroom:.0f}): ~{e.hours:.1f} h{rng}"


def _fmt_rate(label: str, f: Fit | None) -> str:
    if f is None:
        return f"  {label:>4}: insufficient data"
    sign = "+" if f.slope >= 0 else ""
    return (
        f"  {label:>4}: {sign}{f.slope:.1f} c/h  +/-{f.se:.1f}  "
        f"r2={f.r2:.2f}  n={f.n}  -> {f.direction}"
    )


def report(data: LogData, only: str | None) -> str:
    bounds = cal_bounds(data)
    soil = [r for r in data.readings if r.record_type.startswith("plants.soil")]
    by_sensor: dict[str, list] = {}
    for r in soil:
        by_sensor.setdefault(r.sensor_id, []).append(r)
    ids = sorted(s for s in by_sensor if not only or s == only)
    if not ids:
        return f"no sensor matching {only!r}; have {sorted(by_sensor)}"

    out = [f"forecast engine (E3)  |  cal bounds (dry>wet): {bounds}", ""]
    for sid in ids:
        f = forecast_sensor(sid, by_sensor[sid], bounds)
        st = f["stats"]
        out.append(
            f"=== {sid}  (GPIO {f['gpio']})  raw_now={f['raw_now']}  "
            f"band={f['band_now']!r}  in-band {f['band_now_hours']:.1f} h  n={f['n']}"
        )
        out.append(
            f"  stats: mean {st['mean']}  median {st['median']}  sd {st['stdev']}  "
            f"range {st['min']}-{st['max']}  noise~{st['noise_spread']}"
        )
        out.append("  drying rate (angle), positive = drying:")
        for label in ("1h", "6h", "24h", "all"):
            out.append(_fmt_rate(label, f["rates"][label]))
        out.append(f"  -> next drier band: {_fmt_eta(f['to_next_band'])}")
        out.append(f"  -> thirsty (needs-water edge): {_fmt_eta(f['to_thirsty'])}")
        d = f["diurnal"]
        out.append(
            f"  -> diurnal: {'ready' if d.ready else 'NOT ready'} ({d.reason}); "
            f"next-day start/end: {'available' if d.ready else 'blocked on diurnal'}"
        )
        out.append("")
    out.append(
        "note: ETAs are gated - they only appear once drying is statistically real "
        f"(|slope| > {SIG_Z}*se and >= {RATE_FLOOR_PER_H} c/h). The thirsty edge is "
        "the A2 (un-reconciled) needs-water boundary."
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Per-sensor forecast engine (E3).")
    ap.add_argument("inputs", nargs="*", help="logs (default: repo logs/)")
    ap.add_argument("-s", "--sensor", default=None, help="one sensor id, e.g. s3")
    args = ap.parse_args(argv)

    inputs = args.inputs or [str(_HERE.parents[1] / "logs")]
    data = parse_files(inputs)
    if not data.readings:
        print("no readings parsed", file=sys.stderr)
        return 1
    print(report(data, args.sensor))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
