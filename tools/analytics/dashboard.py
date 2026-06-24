"""4-channel soil-moisture dashboard generator (backlog E7).

Reads schema-v1 logs via ``parse_v1`` (E6) and renders a single self-contained
HTML dashboard styled with the Sprout design system (``docs/design/``). It
injects a JSON context + the inlined Sprout tokens into
``dashboard_template.html``.

Honesty rules baked in:

* **raw + band are the truth.** The legacy moist% ``value`` column is never
  plotted (B2/C2).
* **bands are proposed, not validated.** The 7-band boundaries are the
  un-reconciled spec (A2); the UI labels them as such.
* **no fabricated light cycle.** Day/night shading needs the real light
  schedule, which is not in the data, so it is omitted; overall drying slope
  is shown instead.

Usage::

    python tools/analytics/dashboard.py                 # all logs/ -> reports/
    python tools/analytics/dashboard.py logs/ -o out.html
    python tools/analytics/dashboard.py docs/sample_log.csv
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from forecast import fit_line, forecast_payload  # noqa: E402
from parse_v1 import (  # noqa: E402  (needs _HERE on sys.path first)
    DEFAULT_CAL_BOUNDS,
    LogData,
    parse_files,
)

_REPO = _HERE.parents[1]
TOKENS_CSS = _REPO / "docs" / "design" / "sprout-tokens.css"
TEMPLATE = _HERE / "dashboard_template.html"
DEFAULT_OUT = _REPO / "reports" / "plants_dashboard.html"
# Vendored Chart.js -> inlined for a self-contained, offline dashboard. Falls
# back to CDN only if the vendored copy is missing.
VENDOR_CHARTJS = _HERE / "vendor" / "chart.umd.min.js"
CDN_CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"

# firmware band -> (Sprout UI band name, token color, mood label). Mood is band-
# derived (Sprout principle); full personality copy lives in the .dc.html source.
BAND_UI: dict[str, tuple[str, str, str]] = {
    "submerged": ("Saturated", "#0E7A86", "Drowning"),
    "overwatered": ("Wet", "#17B6C4", "Soggy"),
    "well watered": ("Moist", "#34A853", "Thriving"),
    "OK": ("Ideal", "#8BD24F", "Content"),
    "needs water": ("Drying", "#F5A623", "Thirsty"),
    "DRY": ("Dry", "#E8703A", "Parched"),
    "air-dry": ("Parched", "#E0483D", "Critical"),
}
BAND_NAMES_DRY_TO_WET = [
    "air-dry",
    "DRY",
    "needs water",
    "OK",
    "well watered",
    "overwatered",
    "submerged",
]

# series colors - saturated/distinct so lines pop over pastel band shading and
# are not confused with the band palette.
SENSOR_COLORS = ["#1E40AF", "#7C5CFF", "#0E7A86", "#B91C1C", "#0F766E", "#9333EA"]

QUALITY_COLOR = {
    "OK": "#34A853",
    "SUSPECT": "#F5A623",
    "SATURATED": "#17B6C4",
    "NO_SIGNAL": "#9A8480",
    "ERROR": "#E0483D",
    "WARMING": "#F5A623",
    "BASELINE_LEARNING": "#F5A623",
    "ESTIMATED": "#9A8480",
}
QUALITY_SEVERITY = {
    "OK": 0,
    "ESTIMATED": 1,
    "WARMING": 1,
    "BASELINE_LEARNING": 1,
    "SUSPECT": 2,
    "SATURATED": 3,
    "NO_SIGNAL": 4,
    "ERROR": 5,
}
QUALITY_COLS = 72  # heat-strip resolution


# --------------------------------------------------------------------------- #
# small numeric helpers
# --------------------------------------------------------------------------- #
def _slope_per_hour(pairs: list[tuple[float, float]]) -> float | None:
    """Least-squares slope of raw vs hours (counts/hour); None if < 2 points."""
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    var = sum((p[0] - mx) ** 2 for p in pairs)
    if var == 0:
        return 0.0
    cov = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return cov / var


def _hours_since(ts: datetime, start: datetime) -> float:
    return (ts - start).total_seconds() / 3600.0


def _band_ranges(bounds: list[int], lo: int, hi: int) -> list[dict[str, object]]:
    """7 band ranges (dry->wet) from descending boundaries + outer limits."""
    edges = [hi, *bounds, lo]
    out: list[dict[str, object]] = []
    for i, name in enumerate(BAND_NAMES_DRY_TO_WET):
        ui, color, mood = BAND_UI[name]
        out.append(
            {
                "fw": name,
                "ui": ui,
                "color": color,
                "mood": mood,
                "lo": edges[i + 1],
                "hi": edges[i],
            }
        )
    return out


# --------------------------------------------------------------------------- #
# context build
# --------------------------------------------------------------------------- #
def build_context(data: LogData) -> dict:
    soil = [
        r
        for r in data.readings
        if r.record_type.startswith("plants.soil")
        and r.raw_value is not None
        and r.timestamp_utc is not None
    ]
    soil.sort(key=lambda r: r.timestamp_utc)
    if not soil:
        raise ValueError("no plants.soil readings with raw_value + timestamp")

    start = soil[0].timestamp_utc

    seg = next((s for s in reversed(data.segments) if s.cal_bounds), None)
    bounds = list(seg.cal_bounds) if seg else list(DEFAULT_CAL_BOUNDS)
    mrange = seg.moist_range if seg and seg.moist_range else (900, 3400)
    bands = _band_ranges(bounds, mrange[0], mrange[1])

    by_sensor: dict[str, list] = {}
    for r in soil:
        by_sensor.setdefault(r.sensor_id, []).append(r)
    sensor_ids = sorted(by_sensor)
    colors = {
        sid: SENSOR_COLORS[i % len(SENSOR_COLORS)] for i, sid in enumerate(sensor_ids)
    }

    sensors = []
    trajectory_sets = []
    for sid in sensor_ids:
        rs = by_sensor[sid]
        raws = [r.raw_value for r in rs]
        pairs = [(_hours_since(r.timestamp_utc, start), r.raw_value) for r in rs]
        points = [{"x": round(h, 4), "y": v} for h, v in pairs]
        locals_ = [
            r.timestamp_local.strftime("%m-%d %H:%M:%S") if r.timestamp_local else ""
            for r in rs
        ]
        last = rs[-1]
        ui = BAND_UI.get(last.band or "", ("?", "#9A8480", "Unknown"))
        sensors.append(
            {
                "id": sid,
                "gpio": last.gpio,
                "channel": last.channel,
                "color": colors[sid],
                "n": len(rs),
                "raw_min": min(raws),
                "raw_max": max(raws),
                "raw_mean": round(statistics.fmean(raws), 1),
                "raw_median": int(statistics.median(raws)),
                "raw_last": last.raw_value,
                "band_fw": last.band,
                "band_ui": ui[0],
                "band_color": ui[1],
                "mood": ui[2],
                "spread_last": last.spread,
                "quality_last": last.quality_flag,
                "slope_per_hr": _round_opt(_slope_per_hour(pairs), 2),
                "forecast": forecast_payload(sid, rs, bounds),
            }
        )
        _fit = fit_line(pairs)
        trend = None
        if _fit and len(pairs) >= 3:
            x0, x1 = pairs[0][0], pairs[-1][0]
            trend = {
                "x0": round(x0, 4),
                "y0": round(_fit.intercept + _fit.slope * x0, 1),
                "x1": round(x1, 4),
                "y1": round(_fit.intercept + _fit.slope * x1, 1),
                "slope": round(_fit.slope, 2),
            }
        trajectory_sets.append(
            {
                "id": sid,
                "color": colors[sid],
                "points": points,
                "local": locals_,
                "trend": trend,
            }
        )

    sweeps = [
        sw
        for sw in data.sweeps()
        if any(r.raw_value is not None for r in sw.by_sensor.values())
    ]
    spread_points = []
    spreads = []
    for sw in sweeps:
        vals = [r.raw_value for r in sw.by_sensor.values() if r.raw_value is not None]
        if len(vals) < 2 or sw.timestamp_utc is None:
            continue
        sp = max(vals) - min(vals)
        spreads.append(sp)
        spread_points.append(
            {"x": round(_hours_since(sw.timestamp_utc, start), 4), "y": sp}
        )

    sessions = _sessions(soil)
    distribution = _distribution(by_sensor, sensor_ids, colors)
    quality = _quality_strips(by_sensor, sensor_ids, soil, start)
    integrity = _integrity(soil, sweeps, by_sensor, sensor_ids, sessions)

    last_seg = data.segments[-1] if data.segments else None
    total_h = _hours_since(soil[-1].timestamp_utc, start)
    meta = {
        "device_id": getattr(last_seg, "device_id", None),
        "fw": getattr(last_seg, "firmware_version", None),
        "git": getattr(last_seg, "git", None),
        "run": getattr(last_seg, "run", None),
        "schema_version": getattr(last_seg, "schema_version", None),
        "tz_offset": getattr(last_seg, "tz_offset", None),
        "parser": "tools/analytics/parse_v1.py (E6)",
        "sources": data.sources,
        "generated_local": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "start_local": (
            soil[0].timestamp_local.strftime("%Y-%m-%d %H:%M:%S")
            if soil[0].timestamp_local
            else ""
        ),
        "total_hours": round(total_h, 2),
    }

    return {
        "meta": meta,
        "cal": {"bounds": bounds, "moist_range": list(mrange), "bands": bands},
        "sensors": sensors,
        "trajectory": {
            "start_local": meta["start_local"],
            "datasets": trajectory_sets,
        },
        "spread": {
            "points": spread_points,
            "mean": round(statistics.fmean(spreads), 1) if spreads else None,
            "median": int(statistics.median(spreads)) if spreads else None,
            "current": spreads[-1] if spreads else None,
            "max": max(spreads) if spreads else None,
        },
        "distribution": distribution,
        "quality": quality,
        "integrity": integrity,
    }


def _round_opt(v: float | None, n: int) -> float | None:
    return None if v is None else round(v, n)


def _sessions(soil: list) -> list[dict]:
    out: list[dict] = []
    for r in soil:
        if not out or out[-1]["session_id"] != r.session_id:
            out.append(
                {
                    "session_id": r.session_id,
                    "start": _loc(r),
                    "end": _loc(r),
                    "n": 0,
                }
            )
        out[-1]["end"] = _loc(r)
        out[-1]["n"] += 1
    return out


def _loc(r) -> str:
    return r.timestamp_local.strftime("%m-%d %H:%M:%S") if r.timestamp_local else ""


def _distribution(by_sensor, sensor_ids, colors, nbins: int = 24) -> dict:
    all_raw = [r.raw_value for sid in sensor_ids for r in by_sensor[sid]]
    lo, hi = min(all_raw), max(all_raw)
    if hi == lo:
        hi = lo + 1
    pad = max(1, int((hi - lo) * 0.05))
    lo, hi = lo - pad, hi + pad
    width = (hi - lo) / nbins
    edges = [round(lo + i * width, 1) for i in range(nbins + 1)]
    centers = [round((edges[i] + edges[i + 1]) / 2, 1) for i in range(nbins)]
    datasets = []
    for sid in sensor_ids:
        counts = [0] * nbins
        for r in by_sensor[sid]:
            idx = int((r.raw_value - lo) / width)
            idx = min(max(idx, 0), nbins - 1)
            counts[idx] += 1
        datasets.append({"id": sid, "color": colors[sid], "counts": counts})
    return {"edges": edges, "centers": centers, "datasets": datasets}


def _quality_strips(by_sensor, sensor_ids, soil, start) -> dict:
    total_h = _hours_since(soil[-1].timestamp_utc, start) or 1.0
    flags: dict[str, int] = {}
    strips = []
    for sid in sensor_ids:
        cells = [None] * QUALITY_COLS
        for r in by_sensor[sid]:
            flags[r.quality_flag] = flags.get(r.quality_flag, 0) + 1
            h = _hours_since(r.timestamp_utc, start)
            col = min(int(h / total_h * QUALITY_COLS), QUALITY_COLS - 1)
            cur = cells[col]
            sev = QUALITY_SEVERITY.get(r.quality_flag, 2)
            if cur is None:
                cells[col] = {"flag": r.quality_flag, "sev": sev, "n": 1}
            else:
                cur["n"] += 1
                if sev > cur["sev"]:
                    cur["flag"], cur["sev"] = r.quality_flag, sev
        out_cells = [
            {
                "flag": c["flag"] if c else None,
                "color": QUALITY_COLOR.get(c["flag"], "#283322") if c else None,
                "n": c["n"] if c else 0,
            }
            for c in cells
        ]
        strips.append({"id": sid, "cells": out_cells})
    return {"cols": QUALITY_COLS, "strips": strips, "flags": flags}


def _integrity(soil, sweeps, by_sensor, sensor_ids, sessions) -> dict:
    counts = {sid: len(by_sensor[sid]) for sid in sensor_ids}
    n_sensors = len(sensor_ids)
    partial = sum(
        1
        for sw in sweeps
        if len([r for r in sw.by_sensor.values() if r.raw_value is not None])
        < n_sensors
    )
    ts = [sw.timestamp_utc for sw in sweeps if sw.timestamp_utc]
    ts.sort()
    deltas = [(ts[i + 1] - ts[i]).total_seconds() for i in range(len(ts) - 1)]
    cadence = round(statistics.median(deltas), 1) if deltas else None
    span_start = soil[0].timestamp_local
    span_end = soil[-1].timestamp_local
    dur = soil[-1].timestamp_utc - soil[0].timestamp_utc
    flags: dict[str, int] = {}
    for r in soil:
        flags[r.quality_flag] = flags.get(r.quality_flag, 0) + 1
    return {
        "total": len(soil),
        "sweeps": len(sweeps),
        "partial_sweeps": partial,
        "per_sensor": [{"id": sid, "n": counts[sid]} for sid in sensor_ids],
        "count_min": min(counts.values()),
        "count_max": max(counts.values()),
        "count_gap": max(counts.values()) - min(counts.values()),
        "cadence_actual_s": cadence,
        "span_start": span_start.strftime("%m-%d %H:%M:%S") if span_start else "",
        "span_end": span_end.strftime("%m-%d %H:%M:%S") if span_end else "",
        "duration": str(dur).split(".")[0],
        "sessions": sessions,
        "flags": flags,
    }


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def render(ctx: dict) -> str:
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    template = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(ctx, separators=(",", ":"), ensure_ascii=False)
    if VENDOR_CHARTJS.exists():
        lib = VENDOR_CHARTJS.read_text(encoding="utf-8").replace(
            "</script>", "<\\/script>"
        )
        chart_tag = f"<script>\n{lib}\n</script>"
    else:
        chart_tag = f'<script src="{CDN_CHARTJS}"></script>'
    html = template.replace("/*__SPROUT_TOKENS__*/", tokens)
    html = html.replace('"__DASH_JSON__"', blob)
    html = html.replace("<!--__CHARTJS__-->", chart_tag)
    return html


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the 4-channel dashboard.")
    ap.add_argument(
        "inputs",
        nargs="*",
        help="log files / dirs / globs (default: repo logs/)",
    )
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="output HTML path")
    args = ap.parse_args(argv)

    inputs = args.inputs or [str(_REPO / "logs")]
    data = parse_files(inputs)
    if not data.readings:
        print("no readings parsed from:", inputs, file=sys.stderr)
        return 1

    ctx = build_context(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(ctx), encoding="utf-8", newline="\n")

    s = ctx["sensors"]
    print(f"wrote {out}")
    print(
        f"  {ctx['integrity']['total']} readings | "
        f"{ctx['integrity']['sweeps']} sweeps | "
        f"{len(s)} sensors | gap={ctx['integrity']['count_gap']} rows | "
        f"cadence~{ctx['integrity']['cadence_actual_s']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
