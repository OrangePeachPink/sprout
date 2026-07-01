"""4-channel soil-moisture dashboard generator (backlog E7).

Reads schema-v1 logs via ``parse_v1`` (E6) and renders a single self-contained
HTML dashboard styled with the Sprout design system (``docs/design/``). It
injects a JSON context + the inlined Sprout tokens into
``dashboard_template.html``.

Honesty rules baked in:

* **raw + band are the truth.** The legacy moist% ``value`` column is never
  plotted (B2/C2).
* **interior bands are proposed, not validated.** The endpoints (saturated +
  air-dry) are firmware-ratified from the common-cup anchors; the interior
  boundaries are the un-reconciled A2 spec, and the UI labels them as such.
* **no fabricated light cycle.** Day/night shading (#198) uses the real,
  computed solar geometry (``env_solar``, #365/#366) - never a guessed
  schedule. Absent entirely with no rig location configured (R9).

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
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import provenance  # noqa: E402  (sibling - server/app provenance for the panel, #324)
from forecast import fit_line, forecast_payload  # noqa: E402
from parse_v1 import (  # noqa: E402  (needs _HERE on sys.path first)
    DEFAULT_CAL_BOUNDS,
    LogData,
    parse_files,
)
from timefmt import local_first  # noqa: E402  (local-time-first display labels, #328)

_REPO = _HERE.parents[1]


def _tz_offset_hours(reading) -> float | None:
    """The rig-local UTC offset (hours) implied by a reading's paired stamps, for
    local-first display (#328); None if either stamp is missing."""
    if reading.timestamp_local is not None and reading.timestamp_utc is not None:
        delta = reading.timestamp_local - reading.timestamp_utc.replace(tzinfo=None)
        return round(delta.total_seconds() / 3600, 2)
    return None


TOKENS_CSS = _REPO / "docs" / "design" / "tokens" / "sprout-tokens.css"
# Brand fonts, base64-embedded (latin subsets, SIL OFL) so the dashboard renders
# in-brand fully offline - no Google-Fonts CDN. Vendored beside Chart.js;
# regenerate via tools/analytics/embed_fonts.py.
FONTS_CSS = _HERE / "vendor" / "sprout-fonts.css"
TEMPLATE = _HERE / "dashboard_template.html"
DEFAULT_OUT = _REPO / "reports" / "plants_dashboard.html"
# Vendored Chart.js -> inlined for a self-contained, offline dashboard. Falls
# back to CDN only if the vendored copy is missing.
VENDOR_CHARTJS = _HERE / "vendor" / "chart.umd.min.js"
CDN_CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"
# B8 gzip archive of closed segments (read for deep history once they leave logs/).
ARCHIVE_DIR = _REPO / ".data-worktree" / "data" / "archive"
LOGS_DIR = _REPO / "logs"
# Chart series are capped for responsiveness over long ranges; the stat / rate /
# forecast panels always use the full windowed data, only the plotted points thin.
MAX_TRAJ_POINTS = 2000
# A sample-to-sample gap longer than this is a logging interruption, surfaced (E9).
GAP_THRESHOLD_S = 120
# Time-range windows (E8). None = all history.
RANGE_HOURS: dict[str, float | None] = {
    "1h": 1.0,
    "3h": 3.0,
    "12h": 12.0,
    "24h": 24.0,
    "7d": 24.0 * 7,
    "30d": 24.0 * 30,
    "all": None,
}

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

# series colors - the sanctioned categorical set drawn from the band ramp, so the
# dashboard reads as one palette (#203 / design review #99 / #156:
# --band-wet/moist/ideal/drying). Hex, not the CSS vars: the canvas chart's hexA()
# needs resolved colors, and the band tokens are theme-stable.
SENSOR_COLORS = ["#17B6C4", "#34A853", "#8BD24F", "#F5A623"]

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
# inputs, windowing, downsampling (E8)
# --------------------------------------------------------------------------- #
def gather_inputs() -> list[str]:
    """Live logs/ + the B8 gz archive, de-duped by segment stem (live wins)."""
    files: dict[str, Path] = {}
    if ARCHIVE_DIR.is_dir():
        for p in ARCHIVE_DIR.glob("*.csv.gz"):
            files[p.name[:-7]] = p  # strip ".csv.gz"
    if LOGS_DIR.is_dir():
        for p in LOGS_DIR.glob("*.csv"):
            files[p.name[:-4]] = p  # ".csv" live copy overrides the archived .gz
    return [str(p) for _, p in sorted(files.items())]  # stem sort = chronological


def filter_since(data: LogData, hours: float | None) -> LogData:
    """Return a LogData windowed to the last `hours` of data (None = unchanged)."""
    if hours is None:
        return data
    times = [r.timestamp_utc for r in data.readings if r.timestamp_utc]
    if not times:
        return data
    cutoff = max(times) - timedelta(hours=hours)
    kept = [r for r in data.readings if r.timestamp_utc and r.timestamp_utc >= cutoff]
    return LogData(readings=kept, segments=data.segments, sources=data.sources)


def filter_channels(data: LogData, channels: list[str] | None) -> LogData:
    """Keep only readings for the given sensor ids (None / empty = all) (E10)."""
    if not channels:
        return data
    keep = set(channels)
    kept = [r for r in data.readings if r.sensor_id in keep]
    return LogData(readings=kept, segments=data.segments, sources=data.sources)


def _channel_idx(sid: str) -> int:
    """Stable colour index from a sensor id ('s2' -> 1), so colours don't shuffle
    when a channel is excluded (E10)."""
    digits = "".join(ch for ch in sid if ch.isdigit())
    return (int(digits) - 1) if digits else 0


def _dec_idx(n: int, cap: int) -> list[int]:
    """Evenly-spaced indices thinning a length-n series down to <= cap."""
    if n <= cap:
        return list(range(n))
    step = n / cap
    return [int(i * step) for i in range(cap)]


def _gaps(sweeps: list, start: datetime) -> list[dict]:
    """Logging interruptions: sweep-to-sweep deltas over GAP_THRESHOLD_S (E9)."""
    ts = []
    for sw in sweeps:
        locs = [r.timestamp_local for r in sw.by_sensor.values() if r.timestamp_local]
        if sw.timestamp_utc and locs:
            ts.append((sw.timestamp_utc, min(locs)))
    ts.sort()
    out = []
    for (ua, la), (ub, _lb) in zip(ts, ts[1:]):
        dt = (ub - ua).total_seconds()
        if dt > GAP_THRESHOLD_S:
            out.append(
                {
                    "x0": round(_hours_since(ua, start), 4),
                    "x1": round(_hours_since(ub, start), 4),
                    "dur_min": round(dt / 60, 1),
                    "at_local": la.strftime("%m-%d %H:%M:%S"),
                }
            )
    return out


# --------------------------------------------------------------------------- #
# environmental join (PRD-0002 R3, #368): align located weather + computed solar
# onto the soil timeline (timestamp UTC + place), so the overlay (#198) and the
# decomposition (#199) can plot soil behaviour against measured conditions.
# --------------------------------------------------------------------------- #
# Standard sunrise/sunset: geometric centre 0.833 deg below the horizon (matches
# env_solar). Below this the sun is down -> a night band.
_HORIZON_DEG = -0.833


def _night_bands(
    solar_pts: list[dict], start: datetime, end_utc: datetime
) -> list[dict]:
    """Night windows as {x0, x1} in hours-since-start, from a 10-min solar series."""
    if not solar_pts:
        return []
    bands: list[dict] = []
    in_night = False
    band_start: datetime | None = None
    for pt in solar_pts:
        t: datetime = pt["t"]
        night = pt["elevation_deg"] <= _HORIZON_DEG
        if night and not in_night:
            in_night, band_start = True, t
        elif not night and in_night:
            in_night = False
            bands.append(
                {
                    "x0": round((band_start - start).total_seconds() / 3600, 4),
                    "x1": round((t - start).total_seconds() / 3600, 4),
                }
            )
    if in_night and band_start is not None:
        bands.append(
            {
                "x0": round((band_start - start).total_seconds() / 3600, 4),
                "x1": round((end_utc - start).total_seconds() / 3600, 4),
            }
        )
    return bands


def _weather_hourly_join(
    hourly: list[dict], start: datetime, end_utc: datetime
) -> list[dict]:
    """Weather windowed to [start, end_utc] as {x, cloud_cover, radiation}.

    The join key is timestamp (UTC): each hourly record is placed on the soil
    timeline by hours-since-start. Open-Meteo returns time_utc as an ISO string
    (no Z); parsed to UTC. Out-of-window hours are dropped (not extrapolated)."""
    out = []
    for h in hourly:
        ts = h.get("time_utc")
        if ts is None:
            continue
        try:
            t = datetime.fromisoformat(str(ts)).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if t < start or t > end_utc:
            continue
        out.append(
            {
                "x": round((t - start).total_seconds() / 3600, 4),
                "cloud_cover": h.get("cloud_cover"),
                "radiation": h.get("shortwave_radiation"),
            }
        )
    return out


def build_env_context(start: datetime, end_utc: datetime) -> dict:
    """Solar + optional weather joined onto the [start, end_utc] soil window (R3).

    Offline-first (R9): returns ``{"available": False}`` when no location config is
    present (so the dashboard simply omits the overlay — never a broken UI), and
    degrades to **solar-only** when the weather cache is absent / a fetch fails.
    Never commits or logs coordinates (R6 / ADR-0013): coords stay in the gitignored
    config and only the *derived* solar/weather series cross into the context."""
    try:
        import env_solar
    except ImportError:
        return {"available": False}

    loc = env_solar.load_location()
    if loc is None:
        return {"available": False}

    lat = float(loc["latitude"])
    lon = float(loc["longitude"])
    tz_off = float(loc.get("tz_offset_hours", 0))

    solar_pts = env_solar.solar_series(lat, lon, start, end_utc, step_min=10)
    night_bands = _night_bands(solar_pts, start, end_utc)
    tz = timezone(timedelta(hours=tz_off))
    start_local_date = start.astimezone(tz).strftime("%Y-%m-%d")
    sun_ev = env_solar.sun_events(lat, lon, start_local_date, tz_off)

    weather_hourly: list[dict] = []
    weather_source: dict | None = None
    try:
        import env_weather

        wd = env_weather.get_weather(
            lat, lon, start.strftime("%Y-%m-%d"), end_utc.strftime("%Y-%m-%d")
        )
        weather_hourly = _weather_hourly_join(wd["hourly"], start, end_utc)
        weather_source = wd.get("source")
    except Exception:
        pass

    return {
        "available": True,
        "night_bands": night_bands,
        "sun_events": sun_ev,
        "weather_hourly": weather_hourly,
        "weather_source": weather_source,  # registry entry (derived/model) or None
        "solar_source": "derived/computed (solar algorithm; not authoritative)",
    }


def _seg_start(seg) -> datetime | None:
    """A segment's honest start time from its header's ``log_start_utc`` (written by
    the real host loggers - plants_logger.py / experiment_capture.py). A
    legacy-converted segment (legacy_log.py) never emits this key, so it is
    ``None`` - which is the point: it can never outrank a real, host-timestamped
    session in recency ordering (#496)."""
    s = getattr(seg, "log_start_utc", None)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_segment(segments: list):
    """The chronologically-latest segment, or ``None`` if there are none.

    #496: ``segments[-1]`` is file-processing order (glob-sorted filenames across
    however many input paths/naming conventions are aggregated), NOT chronological
    order - so a legacy-converted file whose name happens to sort after the live
    file's can silently make a stale identity (old fw/device_id) look current. Pick
    by each segment's real ``log_start_utc`` instead; segments without one (legacy
    conversions) never win. Falls back to list order only if NONE have a parseable
    start (an all-legacy aggregate - an honest degrade, not a crash)."""
    if not segments:
        return None
    timed = [(s, _seg_start(s)) for s in segments]
    with_time = [(s, t) for s, t in timed if t is not None]
    if with_time:
        return max(with_time, key=lambda st: st[1])[0]
    return segments[-1]


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
        sid: SENSOR_COLORS[_channel_idx(sid) % len(SENSOR_COLORS)] for sid in sensor_ids
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

    # plants.env rows (SHT45 / AS7263) share the monitor log with soil in the
    # esp32dev_env build; keep sweeps soil-only so onboard-ambient/NIR counts never
    # pollute the cross-channel spread or the gap detection (#373/#374). The soil
    # trajectory/sensors/integrity already filter to plants.soil above.
    _soil_data = LogData(
        readings=[r for r in data.readings if r.record_type.startswith("plants.soil")],
        segments=data.segments,
        sources=data.sources,
    )
    sweeps = [
        sw
        for sw in _soil_data.sweeps()
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
    gaps = _gaps(sweeps, start)
    distribution = _distribution(by_sensor, sensor_ids, colors)
    quality = _quality_strips(by_sensor, sensor_ids, soil, start)
    integrity = _integrity(soil, sweeps, by_sensor, sensor_ids, sessions)

    # E8: thin only the plotted series for long ranges; stats/forecasts above
    # already consumed the full windowed data.
    for ts in trajectory_sets:
        idx = _dec_idx(len(ts["points"]), MAX_TRAJ_POINTS)
        ts["points"] = [ts["points"][i] for i in idx]
        ts["local"] = [ts["local"][i] for i in idx]
    spread_points = [
        spread_points[i] for i in _dec_idx(len(spread_points), MAX_TRAJ_POINTS)
    ]

    last_seg = _latest_segment(data.segments)  # #496: chronological, not file order
    total_h = _hours_since(soil[-1].timestamp_utc, start)
    _host_off = datetime.now().astimezone().utcoffset()
    _host_off_h = _host_off.total_seconds() / 3600 if _host_off else None
    meta = {
        "device_id": getattr(last_seg, "device_id", None),
        "fw": getattr(last_seg, "firmware_version", None),
        "git": getattr(last_seg, "git", None),
        "run": getattr(last_seg, "run", None),
        "schema_version": getattr(last_seg, "schema_version", None),
        "tz_offset": getattr(last_seg, "tz_offset", None),
        # device-reported cadence + its source (nvs|temp|default) from the banner (#322)
        "cadence_ms": getattr(last_seg, "cadence_ms", None),
        "cadence_src": getattr(last_seg, "cadence_src", None),
        "parser": "tools/analytics/parse_v1.py (E6)",
        "all_channels": list(sensor_ids),
        "sources": data.sources,
        "generated_local": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z"),
        "start_local": (
            soil[0].timestamp_local.strftime("%Y-%m-%d %H:%M:%S")
            if soil[0].timestamp_local
            else ""
        ),
        "total_hours": round(total_h, 2),
        "last_local": (
            soil[-1].timestamp_local.strftime("%Y-%m-%d %H:%M:%S")
            if soil[-1].timestamp_local
            else ""
        ),
        # Local-first display labels (#328): local time + explicit zone + UTC
        # secondary. The *_local fields above stay machine values — start_local
        # anchors the chart axis and last_local is JS-Date-parsed for freshness.
        "start_display": (
            local_first(
                soil[0].timestamp_utc,
                tz_offset_hours=_tz_offset_hours(soil[0]),
                seconds=True,
            )
            if soil[0].timestamp_utc
            else ""
        ),
        "last_display": (
            local_first(
                soil[-1].timestamp_utc,
                tz_offset_hours=_tz_offset_hours(soil[-1]),
                seconds=True,
            )
            if soil[-1].timestamp_utc
            else ""
        ),
        "generated_display": local_first(
            datetime.now(timezone.utc), tz_offset_hours=_host_off_h, seconds=True
        ),
    }

    # #324 provenance panel: server/app + device/log + the honest-data contract state.
    # raw_only is computed from the data itself — if any row carried a value/unit, the
    # contract is violated and we say so (surface gaps, never smooth them).
    raw_only_ok = all(r.value is None and (r.unit or "") == "" for r in soil)
    provenance_block = {
        "server": provenance.server_provenance(),
        "device": {
            "device_id": meta["device_id"],
            "fw": meta["fw"],
            "fw_git": meta["git"],
            "schema_version": meta["schema_version"],
            "logger_version": getattr(last_seg, "logger_version", None),
            "tz_offset": meta["tz_offset"],
            # #496: honest even in the edge case where NO real (host-timestamped)
            # session exists in this view at all, so a legacy-converted capture is
            # the only/latest segment available — never silently pass its identity
            # off as the live device's (ADR-0025 "no placeholder that reads as real").
            "legacy_converted": getattr(last_seg, "logger_version", None)
            == "legacy-convert",
        },
        "contract": {
            "raw_only": raw_only_ok,
            "label": (
                "raw counts + band only (value/unit empty)"
                if raw_only_ok
                else "CONTRACT VIOLATION — a value/unit is populated"
            ),
        },
        # Always uncalibrated today: raw + band are the truth; per-channel cal is #170.
        "calibration": "uncalibrated (raw + band only; per-channel cal #170)",
    }

    # PRD-0002 R3 (#368): join solar + optional weather onto the soil window. Offline-
    # first — {"available": False} when no location config, so the UI just omits it.
    env = build_env_context(start, soil[-1].timestamp_utc)

    return {
        "meta": meta,
        "provenance": provenance_block,
        "env": env,
        "cal": {"bounds": bounds, "moist_range": list(mrange), "bands": bands},
        "sensors": sensors,
        "trajectory": {
            "start_local": meta["start_local"],
            # local-first chart-axis anchor (#328): local + zone, no UTC secondary.
            "start_axis": meta.get("start_display", "").split(" · UTC ")[0]
            or meta["start_local"],
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
        "gaps": gaps,
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
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    template = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(ctx, separators=(",", ":"), ensure_ascii=False)
    if VENDOR_CHARTJS.exists():
        lib = VENDOR_CHARTJS.read_text(encoding="utf-8").replace(
            "</script>", "<\\/script>"
        )
        chart_tag = f"<script>\n{lib}\n</script>"
    else:
        chart_tag = f'<script src="{CDN_CHARTJS}"></script>'
    html = template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)
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

    inputs = args.inputs or gather_inputs()
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
