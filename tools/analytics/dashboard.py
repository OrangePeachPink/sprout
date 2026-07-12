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
from band_movement import as_dict as _movement_as_dict  # noqa: E402  (#650 substrate)
from band_movement import band_movements  # noqa: E402  (#650 -> #627/#717 view)
from device_registry import Registry, load_registry  # noqa: E402  (#486 attribution)
from forecast import fit_line, forecast_payload  # noqa: E402
from parse_v1 import (  # noqa: E402  (needs _HERE on sys.path first)
    DEFAULT_CAL_BOUNDS,
    LogData,
)
from source_adapter import (  # noqa: E402  (the source-adapter seam, #277)
    TetheredAdapter,
)
from timefmt import (  # noqa: E402  (local-time-first display labels, #328/#840)
    local_first_system,
)

_REPO = _HERE.parents[1]


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
# #977: schema_version at/above which the raw-only value/unit contract (ADR-0030)
# holds. Below it (or version-less) a row predates the contract and may legitimately
# carry the legacy moist% `value` column (B2/C2, not plotted). v2 (experiment_capture)
# and v3 (ADR-0027 firmware) are raw-only; legacy moist% is v1 / version-less. An
# off-contract row at >= this epoch is a real violation; below it, it's history.
_CONTRACT_EPOCH_SCHEMA = 2
# Chart series are capped for responsiveness over long ranges; the stat / rate /
# forecast panels always use the full windowed data, only the plotted points thin.
MAX_TRAJ_POINTS = 2000
# A sample-to-sample gap longer than this is a logging interruption, surfaced (E9).
GAP_THRESHOLD_S = 120
# #683: a device silent for longer than this (relative to the freshest reading in
# the whole fleet - the live edge) auto-demotes to a slim "retired" row so a dead
# pre-launch test rig stops crowding the live glance view. Distinct from staleness
# (#698, minutes): retirement is the hours-scale "this board is gone" demotion. An
# explicit registry `retired` flag retires a board regardless of age. Documented,
# tunable; data is always preserved (still in the logs / Diagnostics).
RETIRE_AFTER_H = 12.0
# #699: over the WiFi fleet each board polls at its OWN cadence, so a per-device
# gap is judged relative to that device's median poll interval, floored at the
# documented GAP_THRESHOLD_S. A gap = a poll-to-poll delta over
# max(GAP_THRESHOLD_S, GAP_CADENCE_MULT x median interval) - so a slow 60 s WiFi
# poller isn't spammed with false gaps and a fast 5 s serial log still surfaces a
# real 2-minute dropout. Same honest-data law as the aggregate: surfaced, never
# bridged.
GAP_CADENCE_MULT = 3
# #839 Fix B: a logging gap this long (default 1.5 days) is a *window boundary*, not
# a dropout. The trajectory PLOTS only the most recent contiguous run, so a stale
# pre-gap pocket - e.g. reconnect-storm data (#712) a coalesced identity legitimately
# inherited (#602) - can't stretch the axis or bury the live signal. Only the plotted
# points clip; stats / forecast / band-history keep the FULL windowed data (#80). Set
# well above any real WiFi/serial dropout so only a genuine multi-day outage triggers.
TRAJ_GAP_BOUNDARY_H = 36.0
# #698: a device with no reading within this window is STALE/offline - its last
# value must not read as the live reading, and it drops out of the online count.
# 180 s = ~6 sweep intervals at the 30 s cadence; the one canonical threshold the
# client also derives against (it mirrors the template's STATE_ONLINE_S so the
# server-side gate and the viewer-clock gate never disagree). Tunable here.
STALE_AFTER_S = 180
# #719: the firmware's own declared version (the "latest firmware" a device SHOULD
# be running), read from the firmware source of truth. Data reads it read-only to
# flag a board that's behind; Firmware owns the value.
FW_CONFIG = _REPO / "firmware" / "include" / "config.h"
# #685: the Diagnostics integrity panel keeps the DOM BOUNDED regardless of dataset
# size - the full per-session dump grew to ~8k rows under the #712 reset storm and
# re-rendered every refresh. We ship a compact summary + the last N sessions + a
# total; the rest is in the log files the locator points at.
SESSIONS_SHOWN = 20
# Time-range windows (E8). None = all history.
RANGE_HOURS: dict[str, float | None] = {
    "1h": 1.0,
    "3h": 3.0,
    "12h": 12.0,
    "24h": 24.0,
    "48h": 48.0,  # #821: between 1 day and 7 days — same windowing as every chip
    "7d": 24.0 * 7,
    "30d": 24.0 * 30,
    "all": None,
}

# firmware band -> (Sprout UI band name, token color). The mood word is NOT
# authored here - it is read 1:1 from the design system's single source of truth,
# mood-band-map.json (see MOOD_BY_BAND below), per the card-chip ruling (#638).
# Binding the chip to the map is what stops the vocabulary drifting toward drama
# again (the #596 finding: submerged/overwatered/air-dry read Drowning/Soggy/
# Critical instead of the map's soaked/refreshed/faint).
BAND_UI: dict[str, tuple[str, str]] = {
    "submerged": ("Saturated", "#0E7A86"),
    "overwatered": ("Wet", "#17B6C4"),
    "well watered": ("Moist", "#34A853"),
    "OK": ("Ideal", "#8BD24F"),
    "needs water": ("Drying", "#F5A623"),
    "DRY": ("Dry", "#E8703A"),
    "air-dry": ("Parched", "#E0483D"),
}

# The canonical chip mood, one word per calibrated band, READ from the design
# system's single source of truth (ADR-0007 §5, ADR-0008; ruling #638). Chips
# never author a mood - if a word isn't in the map, it isn't a chip. Degrades to
# band-only (empty map) if the design doc is absent in a stripped deploy, rather
# than crashing the dashboard.
_MOOD_MAP_PATH = (
    _HERE.parents[1] / "docs" / "design" / "components" / "mood-band-map.json"
)


def _load_mood_map() -> dict[str, str]:
    try:
        data = json.loads(_MOOD_MAP_PATH.read_text(encoding="utf-8"))
        return {b["fwLevel"]: b["mood"] for b in data.get("bands", [])}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


MOOD_BY_BAND: dict[str, str] = _load_mood_map()


# #722: header orientation line, from the voice pool (never hard-coded). Load-once,
# degrade-to-empty like the mood map — a stripped deploy without the doc just omits it.
_VOICE_PATH = _HERE.parents[1] / "docs" / "design" / "components" / "voice-strings.json"


def _load_orientation() -> str:
    try:
        data = json.loads(_VOICE_PATH.read_text(encoding="utf-8"))
        lines = data.get("bySurface", {}).get("orientation", [])
        return lines[0] if lines else ""
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return ""


ORIENTATION: str = _load_orientation()
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
    "SENSOR_FAULT": "#9A8480",  # #739/v4 firmware self-declared fault (#670 wire half)
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
    "SENSOR_FAULT": 5,  # #739/v4 — a self-declared fault is top-severity
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


def _recent_run_start(soil: list, boundary_h: float) -> datetime:
    """The timestamp where the most recent CONTIGUOUS run begins (#839 Fix B). Walk
    back from the newest reading; the first poll-to-poll gap >= ``boundary_h`` ends the
    run, and everything before it is a stale pre-gap pocket that must not stretch or
    bury the live trajectory. Returns ``soil[0]``'s timestamp when there is no such
    multi-day gap, so the common single-run case is unchanged. ``soil`` must be sorted
    ascending by ``timestamp_utc`` (build_context sorts it)."""
    thr = boundary_h * 3600.0
    run_start = soil[0].timestamp_utc
    for i in range(len(soil) - 1, 0, -1):
        if (soil[i].timestamp_utc - soil[i - 1].timestamp_utc).total_seconds() >= thr:
            run_start = soil[i].timestamp_utc
            break
    return run_start


def _age_seconds(ts: datetime | None, now: datetime) -> float | None:
    """Seconds between a reading's UTC stamp and ``now`` (#698); None if absent.
    Both are normalised to aware-UTC so a naive parse stamp never raises."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


# --------------------------------------------------------------------------- #
# version resolution (#719): masthead firmware + app/server version + behind cue
# --------------------------------------------------------------------------- #
def _ver_tuple(v: str | None) -> tuple:
    """Comparable version key from a dotted string. Non-numeric leading parts
    (a git-ish suffix, a `-rc1`) truncate the tuple rather than guess an order,
    so a comparison is only made where it's honest."""
    if not v:
        return ()
    out: list[int] = []
    for part in str(v).strip().lstrip("vV").split("."):
        num = ""
        for ch in part:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            break
        out.append(int(num))
    return tuple(out)


def _declared_fw_version() -> str | None:
    """The firmware's own declared latest version (``PLANTS_FW_VERSION`` in the
    firmware config). Read-only from Data's side (Firmware owns the value); None
    if the firmware source isn't in this checkout."""
    try:
        text = FW_CONFIG.read_text(encoding="utf-8")
    except OSError:
        return None
    for line in text.splitlines():
        s = line.strip()
        if "PLANTS_FW_VERSION" in s and '"' in s:
            return s.split('"')[1] or None
    return None


def _versions_block(device_groups: list, server: dict) -> dict:
    """The masthead version panel (#719): fleet firmware (value or the honest
    mix), the one app==server product version, and a 'behind latest / restart
    needed' cue - so the operator never has to ask which build is running.
    """
    # #856: exclude RETIRED devices from the firmware set — a retired rig's
    # historical fw (immutable raw, correctly never ages out) must not leak into the
    # live fw-mixed cue, exactly as the #683 fleet count already excludes it. Groups
    # without a `retired` key (a bare caller / a test) read as live, so this is
    # back-compatible.
    fw_by_dev = [
        (g.get("name") or g.get("device_id"), g.get("fw"))
        for g in device_groups
        if g.get("fw") and not g.get("retired")
    ]
    distinct = sorted({fw for _n, fw in fw_by_dev}, key=_ver_tuple)
    fw_value = distinct[0] if len(distinct) == 1 else None
    latest = _declared_fw_version()
    # a device is "behind" only when BOTH versions parse and it's strictly lower
    behind = [
        {"device": n, "fw": fw}
        for n, fw in fw_by_dev
        if latest and _ver_tuple(fw) and _ver_tuple(fw) < _ver_tuple(latest)
    ]
    product = server.get("version")
    return {
        # app and server are the same program reading one constant -> equal by
        # construction; surfaced explicitly so the UI can show ONE labelled value.
        "app": product,
        "server": product,
        "app_server_match": True,
        "firmware": {
            "value": fw_value,  # single value when the fleet agrees
            "mixed": len(distinct) > 1,  # honest 'devices differ' state
            "all": distinct,
            "latest": latest,  # firmware's own declared latest (may be None)
            "behind": behind,  # boards strictly below latest
        },
        # running server predates the checked-out code -> a restart shows newer app
        "server_stale": bool(server.get("stale")),
        "restart_needed": bool(server.get("stale")) or bool(behind),
    }


def _fw_masthead(versions: dict) -> str | None:
    """The single firmware string the masthead shows instead of a bare 'fw ?':
    the agreed value, or an explicit mix like ``mixed (0.6.9, 0.7.0)``. None only
    when no device reported any firmware at all."""
    fw = versions["firmware"]
    if fw["value"]:
        return fw["value"]
    if fw["all"]:
        return "mixed (" + ", ".join(fw["all"]) + ")"
    return None


def _band_ranges(bounds: list[int], lo: int, hi: int) -> list[dict[str, object]]:
    """7 band ranges (dry->wet) from descending boundaries + outer limits."""
    edges = [hi, *bounds, lo]
    out: list[dict[str, object]] = []
    for i, name in enumerate(BAND_NAMES_DRY_TO_WET):
        ui, color = BAND_UI[name]
        out.append(
            {
                "fw": name,
                "ui": ui,
                "color": color,
                "mood": MOOD_BY_BAND.get(name, ""),
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


def filter_channels(
    data: LogData, channels: list[str] | None, canonical=None
) -> LogData:
    """Keep only readings for the given sensor ids (None / empty = all) (E10).
    ``canonical`` (#602): an optional device_id -> canonical-id mapping (the
    registry's ``canonical_for``) so device-scoped tokens keep matching a
    board's whole history across renames; None = identity (v1 behavior).

    #583 (the FENCE rule): a token may be a plain sensor id (``s1`` - matches
    that channel on every device, the single-device case unchanged) or a
    device-scoped ``s1@<device_id>`` composite, matching exactly one device's
    channel - two devices' ``s1`` are different plants and must be
    independently toggleable."""
    if not channels:
        return data
    plain = {c for c in channels if "@" not in c}
    scoped = {tuple(c.split("@", 1)) for c in channels if "@" in c}
    # #602: scoped tokens carry the CANONICAL id (the card key), so a row from a
    # prior identity must match through the same coalesce the grouping uses.
    canon = canonical or (lambda d: d)
    kept = [
        r
        for r in data.readings
        if r.sensor_id in plain or (r.sensor_id, canon(r.device_id)) in scoped
    ]
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


def _device_timeline(sweeps: list, canon=None) -> dict:
    """Per-device poll timestamps over the window, in time order (#699).

    A sweep keys on ``session_id``, which is device-owned, so a sweep is normally
    one device's one poll - but we still split defensively by each reading's
    canonical device_id (#602) so a mixed/legacy log divides cleanly. One entry
    per (device, sweep): the sweep IS the poll, regardless of how many probes it
    carried. Returns ``{device_id: [(utc, local), ...]}``.
    """
    canon = canon or (lambda d: d)
    per: dict[str | None, list] = {}
    for sw in sweeps:
        if sw.timestamp_utc is None:
            continue
        seen: set = set()
        for r in sw.by_sensor.values():
            if r.raw_value is None:
                continue
            dev = canon(r.device_id)
            if dev in seen:
                continue
            seen.add(dev)
            per.setdefault(dev, []).append((sw.timestamp_utc, r.timestamp_local))
    for dev in per:
        per[dev].sort(key=lambda t: t[0])
    return per


def _device_gap_threshold_s(series: list) -> float:
    """The adaptive per-device gap threshold in seconds (#699): a floor of
    GAP_THRESHOLD_S, raised to GAP_CADENCE_MULT x this device's median poll
    interval when it polls slower than the floor implies."""
    if len(series) < 2:
        return float(GAP_THRESHOLD_S)
    deltas = [(b[0] - a[0]).total_seconds() for a, b in zip(series, series[1:])]
    med = statistics.median(deltas)
    return max(float(GAP_THRESHOLD_S), GAP_CADENCE_MULT * med)


def _gaps_by_device(sweeps: list, start: datetime, canon=None) -> dict:
    """Per-device logging interruptions - the fleet extension of #373/#374 (#699).

    Each device is judged against its OWN cadence (``_device_gap_threshold_s``),
    so a WiFi board that drops for a stretch and comes back shows an honest gap,
    never a silently-bridged line that reads as continuous. Aggregate ``_gaps``
    is unchanged; this is the fenced, per-device view (#575's identity rule).
    """
    out: dict[str | None, list[dict]] = {}
    for dev, series in _device_timeline(sweeps, canon).items():
        thr = _device_gap_threshold_s(series)
        gaps: list[dict] = []
        for (ua, la), (ub, _lb) in zip(series, series[1:]):
            dt = (ub - ua).total_seconds()
            if dt > thr:
                gaps.append(
                    {
                        "x0": round(_hours_since(ua, start), 4),
                        "x1": round(_hours_since(ub, start), 4),
                        "dur_min": round(dt / 60, 1),
                        "at_local": la.strftime("%m-%d %H:%M:%S") if la else "",
                    }
                )
        out[dev] = gaps
    return out


def _continuity(
    sweeps: list, start: datetime, gaps_by_device: dict, canon=None
) -> dict:
    """Per-device continuity summary so a human can trust a line has no HIDDEN
    holes (#699): coverage over the device's observed span, its longest gap, and
    its most recent gap. ``coverage_pct`` = 100 x (1 - summed gap time / span).
    """
    timeline = _device_timeline(sweeps, canon)
    out: dict[str | None, dict] = {}
    for dev, series in timeline.items():
        gaps = gaps_by_device.get(dev, [])
        if not series:
            out[dev] = {
                "coverage_pct": None,
                "longest_gap_min": None,
                "last_gap_min": None,
                "gap_count": 0,
            }
            continue
        span_h = _hours_since(series[-1][0], start) - _hours_since(series[0][0], start)
        gap_h = sum(g["dur_min"] for g in gaps) / 60.0
        coverage = None
        if span_h > 0:
            coverage = round(100.0 * max(0.0, 1.0 - gap_h / span_h), 1)
        out[dev] = {
            "coverage_pct": coverage,
            "longest_gap_min": max((g["dur_min"] for g in gaps), default=None),
            "last_gap_min": gaps[-1]["dur_min"] if gaps else None,
            "last_gap_at": gaps[-1]["at_local"] if gaps else None,
            "gap_count": len(gaps),
        }
    return out


def _insert_breaks(points: list, local: list) -> tuple[list, list]:
    """Split a trajectory line across a real dropout (#699): insert a null-y break
    where a point-to-point time delta exceeds the series' adaptive gap threshold,
    so the chart never draws a straight line interpolated across a hole. Keeps the
    parallel ``local`` tooltip array aligned. Runs AFTER decimation so the break
    survives thinning. Chart.js renders a null y as a line break (spanGaps=false).
    """
    if len(points) < 3:
        return points, local
    dxs = [
        points[i]["x"] - points[i - 1]["x"]
        for i in range(1, len(points))
        if points[i]["y"] is not None and points[i - 1]["y"] is not None
    ]
    pos = [d for d in dxs if d > 0]
    if not pos:
        return points, local
    thr_h = max(GAP_THRESHOLD_S / 3600.0, GAP_CADENCE_MULT * statistics.median(pos))
    out_p: list = []
    out_l: list = []
    for i, p in enumerate(points):
        if i and (p["x"] - points[i - 1]["x"]) > thr_h:
            out_p.append({"x": round((points[i - 1]["x"] + p["x"]) / 2, 4), "y": None})
            out_l.append("")
        out_p.append(p)
        out_l.append(local[i])
    return out_p, out_l


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
    # #567: opportunistically refresh the rolling current-pressure cache while
    # we're already in the env path's networking window (same try/except
    # posture as the weather fetch above). The fill paths - the logger's
    # ContextFiller and DeviceAdapter - only ever READ that cache; this is the
    # one place that writes it. Offline -> refresh no-ops -> cache ages out ->
    # pressure fills stop, honestly.
    try:
        import weather_pressure

        weather_pressure.refresh_if_stale(location=loc)
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
def _water_position(band, raw, bands, mrange):
    """#715 'water now?' geometry for one reading. Returns
    ``(band_lo, band_hi, band_pos, dryness)``:

    - ``band_lo``/``band_hi`` - the raw bounds of the reading's current band
      (lo = wetter edge, hi = drier edge);
    - ``band_pos`` - 0.0 (wet edge) .. 1.0 (dry edge) WITHIN that band, so two
      plants in the same band differ by where they sit (2,894-in-DRY vs 2,265);
    - ``dryness`` - 0.0 (wettest) .. 1.0 (driest) across the whole moist range, a
      sortable urgency scalar (higher = more urgent; DesignQA orders on it).

    All ``None`` when there is no real banded reading - no invented urgency where
    there's no signal (the #616 honesty line). Cross-board ``dryness`` is subject
    to the C5 compressed scale (#170) until per-board cal; within a board it's exact."""
    if raw is None or not band:
        return None, None, None, None
    wet, dry = mrange  # (wettest raw, driest raw), e.g. (900, 3400)
    span = dry - wet
    dryness = max(0.0, min(1.0, (raw - wet) / span)) if span else None
    br = next((b for b in bands if b["fw"] == band), None)
    band_lo = band_hi = band_pos = None
    if br is not None:
        band_lo, band_hi = br["lo"], br["hi"]
        bspan = band_hi - band_lo
        if bspan:
            band_pos = max(0.0, min(1.0, (raw - band_lo) / bspan))
    return band_lo, band_hi, band_pos, dryness


def _settled_readings(rs: list) -> list:
    """#697: the settled + valid subset a channel's SUMMARY stats (median / range /
    mean / slope) should use - so a freshly-installed probe's stats track its soil
    value, not the insertion transient or fault zeros.

    Drops what isn't real soil moisture: faulted / implausible (#670) and no-signal
    samples (the `median 2` / `range 0-x` case = startup/fault zeros). Then strips
    the LEADING fresh-insertion air-dry run (the probe read air before it settled
    into soil) - but ONLY if the channel later left air-dry, so a genuinely air-dry
    plant (a cactus, an unwatered pot) keeps all its samples. Returns the full
    non-None set if nothing survives, so stats are never empty. The trajectory
    chart still plots the FULL raw history - this trims only the summary window."""
    valid = [
        r
        for r in rs
        if r.raw_value is not None
        and not r.implausible_wet
        and r.quality_flag not in ("NO_SIGNAL", "SENSOR_FAULT")
    ]
    if not valid:
        return [r for r in rs if r.raw_value is not None]
    first_soil = next((i for i, r in enumerate(valid) if r.band != "air-dry"), None)
    return valid[first_soil:] if first_soil is not None else valid


def _band_trend(m) -> dict:
    """Which way an entity is drifting across the bands over the window (#717) —
    net movement from where it started to where it is now, in the honest unit of
    *bands*, never a slope. `dir`: 'drying' (toward "water me"), 'wetting', or
    'steady'. Read off the discrete transition trail, so it's step-truthful."""
    trail = m.transitions
    start = trail[0]["band"] if trail else m.current["band"]
    now_b = m.current["band"]
    si = BAND_NAMES_DRY_TO_WET.index(start) if start in BAND_NAMES_DRY_TO_WET else None
    ni = BAND_NAMES_DRY_TO_WET.index(now_b) if now_b in BAND_NAMES_DRY_TO_WET else None
    if si is None or ni is None or ni == si:
        direction = "steady"
    elif ni < si:  # index: air-dry=0 .. submerged=6, lower = drier
        direction = "drying"
    else:
        direction = "wetting"
    return {
        "dir": direction,
        "from_band": start,
        "to_band": now_b,
        "steps": (ni - si) if (si is not None and ni is not None) else 0,
    }


def _band_history(soil: list, reg: Registry) -> list[dict]:
    """The band-movement view substrate (#627/#717, PRD-0007 slice 3), assembled
    from the merged #650 substrate + registry plant-first identity. Per entity:
    where it sits across the 7 bands now, the touched-band span, the discrete
    movement trail, a detected re-water window (labeled), and a net trend. Honest:
    device-emitted bands only (never re-thresholded), discrete transitions (never
    an interpolated line), per-device fenced (#650 R8), plant-first labels (#717),
    and a plant with no band-bearing reading yields nothing (R7)."""
    out: list[dict] = []
    for m in band_movements(soil, canonical=reg.canonical_for):
        plant = reg.plant_for(m.device_id, m.sensor_id)
        probe = reg.probe_for(m.device_id, m.sensor_id)
        label = (
            (plant.get("plant_name") if plant else None)
            or (plant.get("plant_id") if plant else None)
            or probe
            or m.sensor_id
        )
        d = _movement_as_dict(m)
        d["plant_id"] = plant.get("plant_id") if plant else None
        d["plant_name"] = plant.get("plant_name") if plant else None
        d["label"] = label
        d["trend"] = _band_trend(m)
        d["current_index"] = (
            BAND_NAMES_DRY_TO_WET.index(m.current["band"])
            if m.current["band"] in BAND_NAMES_DRY_TO_WET
            else None
        )
        d["driest_index"] = BAND_NAMES_DRY_TO_WET.index(d["driest"])
        d["wettest_index"] = BAND_NAMES_DRY_TO_WET.index(d["wettest"])
        out.append(d)
    return out


def build_context(
    data: LogData, registry: Registry | None = None, now: datetime | None = None
) -> dict:
    """``registry`` defaults to ``device_registry.load_registry()`` (the local
    fleet config, falling back to the committed example/demo shape, #486) - pass
    one explicitly to test attribution without touching real/example config
    files. ``now`` (default: wall-clock UTC) is the staleness reference (#698),
    injected so live/just-stale/long-offline are deterministically testable."""
    reg = registry if registry is not None else load_registry()
    now = now or datetime.now(timezone.utc)
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
    # #839 Fix B: the trajectory PLOT is clipped to the most recent contiguous run so
    # a stale pre-gap pocket can't dominate the live view; stats keep the full window
    # (#80). No multi-day gap => recent_start == start => every plot is unchanged.
    recent_start = _recent_run_start(soil, TRAJ_GAP_BOUNDARY_H)

    seg = next((s for s in reversed(data.segments) if s.cal_bounds), None)
    bounds = list(seg.cal_bounds) if seg else list(DEFAULT_CAL_BOUNDS)
    mrange = seg.moist_range if seg and seg.moist_range else (900, 3400)
    bands = _band_ranges(bounds, mrange[0], mrange[1])

    # #583 (the FENCE rule): identity is (device_id, sensor_id) - two devices'
    # s1 are different plants and never mix, merge, or roll up. With a single
    # device the key collapses to the bare sensor id, so today's one-Sprout
    # dashboard is byte-identical (the COLLAPSE rule obeyed at the data layer).
    # #602 (identity continuity): a renamed board's prior identities coalesce
    # into its canonical id AT GROUPING TIME - one card, continuous history.
    # Raw rows keep the id they truthfully reported; only the view keys remap.
    _canon = reg.canonical_for
    device_ids_in_data: list[str] = []
    for r in soil:
        did = _canon(r.device_id)
        if did and did not in device_ids_in_data:
            device_ids_in_data.append(did)
    multi = len(device_ids_in_data) > 1

    def _key(r) -> str:
        return f"{r.sensor_id}@{_canon(r.device_id)}" if multi else r.sensor_id

    by_sensor: dict[str, list] = {}
    for r in soil:
        by_sensor.setdefault(_key(r), []).append(r)
    sensor_ids = sorted(by_sensor)
    if multi:
        # enumeration order, not sid digits: two devices' s1 must not share a
        # colour in the one trajectory chart (they're different plants)
        colors = {
            sid: SENSOR_COLORS[i % len(SENSOR_COLORS)]
            for i, sid in enumerate(sensor_ids)
        }
    else:
        colors = {
            sid: SENSOR_COLORS[_channel_idx(sid) % len(SENSOR_COLORS)]
            for sid in sensor_ids
        }

    sensors = []
    trajectory_sets = []
    for sid in sensor_ids:
        rs = by_sensor[sid]
        raws = [r.raw_value for r in rs]
        pairs = [(_hours_since(r.timestamp_utc, start), r.raw_value) for r in rs]
        # #839 Fix B: the PLOT (points + trend + labels) uses only readings in the
        # recent contiguous run; stats below keep the full windowed `rs` (#80). With
        # no multi-day gap, recent_start == start so plot_rs == rs (byte-identical).
        plot_rs = [r for r in rs if r.timestamp_utc >= recent_start]
        plot_pairs = [
            (_hours_since(r.timestamp_utc, start), r.raw_value) for r in plot_rs
        ]
        points = [{"x": round(h, 4), "y": v} for h, v in plot_pairs]
        # #922: per-plant interior-ambient context, time-aligned to the same x as the
        # moisture points (parallel + same length, so one decimation index thins both).
        # The opt-in "context, not cause" overlay's data - the plant's own temp/RH from
        # the ADR-0023 fill; None per point where no context was filled (honest gap).
        env_points = [
            {"x": round(h, 4), "temp_c": r.temp_context_c, "rh_pct": r.rh_context_pct}
            for (h, _v), r in zip(plot_pairs, plot_rs)
        ]
        has_env = any(
            p["temp_c"] is not None or p["rh_pct"] is not None for p in env_points
        )
        # #697: the SUMMARY stats use the settled+valid window (fault zeros + the
        # insertion warmup excluded); the trajectory above keeps the recent-run plot.
        settled = _settled_readings(rs)
        sraws = [r.raw_value for r in settled] or raws
        spairs = [
            (_hours_since(r.timestamp_utc, start), r.raw_value) for r in settled
        ] or pairs
        # #919: the trend + forecast FITS use CLEAN readings only. A fault / sub-rail /
        # OOB row (excluded by the #670/#697 gate) must never pull the least-squares fit
        # — that is the all-window "wetting on a drying plant" inversion. Raw stays on
        # the plot (truth, #575); only the fits drop these rows, and the count is
        # surfaced (`fit_excluded`) so nothing is silently dropped.
        plot_settled = _settled_readings(plot_rs)
        fit_pairs = [
            (_hours_since(r.timestamp_utc, start), r.raw_value) for r in plot_settled
        ]
        fit_excluded = len(plot_rs) - len(plot_settled)
        locals_ = [
            r.timestamp_local.strftime("%m-%d %H:%M:%S") if r.timestamp_local else ""
            for r in plot_rs
        ]
        last = rs[-1]
        # #486: attribute this channel to a plant via the fleet registry - honest
        # None on an unknown device or unassigned channel, never an invented name.
        # (last.sensor_id, not the group key - the key may be device-scoped, #583)
        # #602: attribute via the canonical id - the registry entry lives there
        plant = reg.plant_for(_canon(last.device_id), last.sensor_id)
        # #616 (the #575 HONESTY rule) split into two states after bench feedback
        # (2026-07-04, live QA over WiFi): a REGISTERED channel with no plant
        # assigned is *unassigned*, which is NOT the same as *no signal*.
        #  - no_signal  = the firmware itself reports NO_SIGNAL. There is no valid
        #    reading, so blank it: `—`, no band, no trend.
        #  - unassigned = registered, reporting a real reading, but no plant mapped
        #    yet (bench QA / pre-install). The prior gate blanked this too - reading
        #    a connected probe's valid air-dry ADC as "the probe is dead", which is
        #    a dishonesty in the OTHER direction: raw counts are truth (#575's own
        #    law). So SHOW its raw + quality + stats, but make NO plant-moisture
        #    claim - the prominent band MOOD is the plant-monitoring assertion #616
        #    guards (a floating pin can read a plausible band), so an unassigned
        #    channel presents "No plant", never a mood.
        # Guard unchanged: an UNregistered device (fresh checkout, or a board not
        # yet in the registry) is never gated - we don't claim to know its wiring,
        # so its real reading keeps its band. Net: never hide a real reading,
        # never claim an unmapped plant. Raw rows stay queryable either way.
        regdev = reg.device(_canon(last.device_id))
        registered = regdev is not None
        # #713: `sensor_id`/`channel` is the board PORT (the repurposed s1..s4);
        # `probe` is the physical sensor label the user stuck on the cable (her
        # s1..s8) - surface it as the sensor identity so `sN` in the UI = her
        # sticker, never a channel index. None when the config hasn't mapped it.
        probe = reg.probe_for(_canon(last.device_id), last.sensor_id)
        # #670: a soil raw below the physical wet rail is impossible from moisture -
        # it's a fault (short / water-contamination / disconnected ADC near 0). It
        # takes priority over every other state: a faulted reading is NOT a band,
        # NOT "saturated", and NOT a plant status. Raw stays shown (truth), but the
        # chip reads "sensor fault" so a dead probe can't masquerade as a drowning
        # plant (the live s3-1 board reading 0-7 as "Saturated" is exactly this).
        # #739/v4: honor the firmware's self-declared SENSOR_FAULT (per-board
        # wet_rail_raw, #670 wire half) in addition to the host-derived sub-rail
        # gate - either source means the reading is a fault, never a moisture band.
        sensor_fault = last.implausible_wet or last.quality_flag == "SENSOR_FAULT"
        no_signal = last.quality_flag == "NO_SIGNAL"
        unassigned = registered and plant is None and not no_signal and not sensor_fault
        if sensor_fault:
            band_ui, band_color, mood = "sensor fault", "#9A8480", "Implausible"
        elif no_signal:
            band_ui, band_color, mood = "no signal", "#9A8480", "Unwired"
        elif unassigned:
            band_ui, band_color, mood = "unassigned", "#9A8480", "No plant"
        else:
            band_ui, band_color = BAND_UI.get(last.band or "", ("?", "#9A8480"))
            mood = MOOD_BY_BAND.get(last.band or "", "")
        # #562 (ADR-0023 v2): the last reading's interior-ambient context, only
        # ever value+tag together - a context value never renders untagged.
        ambient = None
        if last.context_source and (
            last.temp_context_c is not None or last.rh_context_pct is not None
        ):
            ambient = {
                "temp_c": last.temp_context_c,
                "rh_pct": last.rh_context_pct,
                "source": last.context_source,
            }
        # #577 (ADR-0023 §3): pressure is the EXTERIOR-family exception - a
        # separate quantity with its own per-quantity tag, kept distinct from
        # the interior ambient block above so the UI can mark it as exterior.
        # Same value+tag-together honesty; honest-empty when the cache ages out
        # (the fill layer #567 writes nothing when stale -> this stays None).
        pressure = None
        if last.pressure_context_source and last.pressure_context_hpa is not None:
            pressure = {
                "hpa": last.pressure_context_hpa,
                "source": last.pressure_context_source,
            }
        # #715: within-band position + a sortable dryness for the "water now?"
        # view; None where there's no real banded reading (honesty, #616).
        band_lo, band_hi, band_pos, dryness = (
            (None, None, None, None)
            if no_signal or unassigned
            else _water_position(last.band, last.raw_value, bands, mrange)
        )
        # #698: how long since THIS channel last reported. A stale card must show
        # its last value labelled "last seen Nh ago", never as the live reading,
        # and drops out of the online count. Deterministic vs the injected `now`.
        age_s = _age_seconds(last.timestamp_utc, now)
        stale = age_s is not None and age_s > STALE_AFTER_S
        sensors.append(
            {
                "id": sid,
                "sensor_id": last.sensor_id,  # the bare channel token (#583)
                "device_id": _canon(last.device_id) or None,  # canonical (#602)
                "stale": stale,  # #698: no reading within STALE_AFTER_S
                "age_s": int(age_s) if age_s is not None else None,  # #698
                "last_seen_utc": (  # #698: the stamp the "last seen" label reads
                    last.timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if last.timestamp_utc
                    else None
                ),
                "no_signal": no_signal,
                "unassigned": unassigned,  # registered, live, no plant yet (#616 bench)
                "sensor_fault": sensor_fault,  # sub-wet-rail impossible reading (#670)
                "plant_id": plant["plant_id"] if plant else None,
                "plant_name": plant["plant_name"] if plant else None,
                "plant_type": plant.get("plant_type") if plant else None,  # #713
                "pot_size": plant.get("pot_size") if plant else None,  # #713
                "probe": probe,  # #713: the physical sensor label (her sN sticker)
                "device_name": getattr(regdev, "name", None),  # #713 friendly board
                "device_side": getattr(regdev, "side", None),  # #713 left/right
                "ambient": ambient,
                "pressure": pressure,
                "gpio": last.gpio,
                "channel": last.channel,
                "color": colors[sid],
                "n": len(rs),
                "raw_min": min(sraws),  # #697: settled window, not the warmup/faults
                "raw_max": max(sraws),
                "raw_mean": round(statistics.fmean(sraws), 1),
                "raw_median": int(statistics.median(sraws)),
                "raw_last": last.raw_value,
                "band_fw": last.band,
                "band_ui": band_ui,
                "band_color": band_color,
                "band_lo": band_lo,  # #715 current band raw bounds (wet..dry edge)
                "band_hi": band_hi,
                "band_pos": band_pos,  # #715 0=wet edge .. 1=dry edge within band
                "dryness": dryness,  # #715 0=wettest .. 1=driest (sortable urgency)
                "mood": mood,
                "spread_last": last.spread,
                "quality_last": last.quality_flag,
                "slope_per_hr": _round_opt(_slope_per_hour(spairs), 2),
                "forecast": forecast_payload(sid, settled, bounds),
                # #919: rows the #670/#697 gate kept off the trend/forecast fits
                # (still plotted as raw) - surfaced so exclusion is never silent.
                "fit_excluded": fit_excluded,
            }
        )
        # #839 Fix B: fit the dashed trend over the recent-run plot, not the full
        # window - a trend that spanned the stale pre-gap pocket (0..180 h) was the
        # one line that still drew across the empty window in the bug report.
        _fit = fit_line(fit_pairs)
        trend = None
        if _fit and len(fit_pairs) >= 3:
            x0, x1 = fit_pairs[0][0], fit_pairs[-1][0]
            trend = {
                "x0": round(x0, 4),
                "y0": round(_fit.intercept + _fit.slope * x0, 1),
                "x1": round(x1, 4),
                "y1": round(_fit.intercept + _fit.slope * x1, 1),
                "slope": round(_fit.slope, 2),
            }
        # #718: a plant-first label for the legend + tooltip - never the machine
        # id or GPIO. Falls back to plant_id -> probe -> the raw sid when a channel
        # has no plant mapped (honest: shows what's known, invents nothing).
        _traj_label = (
            (plant.get("plant_name") if plant else None)
            or (plant.get("plant_id") if plant else None)
            or probe
            or sid
        )
        trajectory_sets.append(
            {
                "id": sid,
                "label": _traj_label,  # #718 plant-first legend/tooltip label
                "color": colors[sid],
                "points": points,
                "local": locals_,
                "trend": trend,
                "env_points": env_points,  # #922 opt-in context overlay (temp/RH)
                "has_env": has_env,  # #922: offer the toggle only when context exists
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
    # Cross-channel spread, FENCED per device (#651 / #575): a sweep's spread is
    # max-min across its CO-LOCATED probes, and each sweep belongs to one device
    # (sweeps key on session_id, which is device-owned). The old code folded every
    # device's per-sweep spread into ONE global series + one mean/max - blending
    # separate pots into a number with no physical meaning. Now each device keeps
    # its own spread series; a lone probe has no peer to spread against (skipped);
    # a single-device install is exactly one series, numerically unchanged.
    spread_by_dev: dict[str | None, dict] = {}
    for sw in sweeps:
        if sw.timestamp_utc is None:
            continue
        per_dev: dict[str | None, list[int]] = {}
        for r in sw.by_sensor.values():
            if r.raw_value is not None:
                per_dev.setdefault(_canon(r.device_id), []).append(r.raw_value)
        x = round(_hours_since(sw.timestamp_utc, start), 4)
        for dev, vals in per_dev.items():
            if len(vals) < 2:
                continue  # no co-located peer -> no meaningful spread
            sp = max(vals) - min(vals)
            d = spread_by_dev.setdefault(dev, {"points": [], "spreads": []})
            d["points"].append({"x": x, "y": sp})
            d["spreads"].append(sp)

    sessions = _sessions(soil)
    gaps = _gaps(sweeps, start)
    # #699: the fenced, per-device continuity view - each board judged on its own
    # cadence, so a WiFi dropout renders as an honest per-device gap (never a
    # silently-bridged line). Aggregate `gaps` above is unchanged.
    gaps_by_device = _gaps_by_device(sweeps, start, _canon)
    continuity = _continuity(sweeps, start, gaps_by_device, _canon)
    distribution = _distribution(by_sensor, sensor_ids, colors)
    quality = _quality_strips(by_sensor, sensor_ids, soil, start)
    integrity = _integrity(soil, sweeps, by_sensor, sensor_ids, sessions)
    # #685: per-DEVICE row counts (fenced by canonical id) + the log-locator, and
    # bound the session list so the Diagnostics panel stays small regardless of
    # dataset size. A reset storm (#712) can mint thousands of sessions; we show
    # the total + the most recent SESSIONS_SHOWN, not an ~8k-row DOM dump.
    _per_dev_counts: dict[str, int] = {}
    for r in soil:
        _d = _canon(r.device_id) or "—"
        _per_dev_counts[_d] = _per_dev_counts.get(_d, 0) + 1
    integrity["per_device"] = [
        {"device_id": d, "n": n}
        for d, n in sorted(_per_dev_counts.items(), key=lambda kv: -kv[1])
    ]
    integrity["locator"] = _locator(data.sources)
    integrity["sessions_total"] = len(integrity["sessions"])
    integrity["sessions"] = integrity["sessions"][-SESSIONS_SHOWN:]

    # E8: thin only the plotted series for long ranges; stats/forecasts above
    # already consumed the full windowed data.
    for ts in trajectory_sets:
        idx = _dec_idx(len(ts["points"]), MAX_TRAJ_POINTS)
        ts["points"] = [ts["points"][i] for i in idx]
        ts["local"] = [ts["local"][i] for i in idx]
        ts["env_points"] = [ts["env_points"][i] for i in idx]  # #922 same thinning
        # #699: break the line across a real dropout (post-decimation) so the
        # chart never interpolates a straight segment over a WiFi hole.
        ts["points"], ts["local"] = _insert_breaks(ts["points"], ts["local"])
    spread_series = []
    for dev, d in spread_by_dev.items():
        pts = [d["points"][i] for i in _dec_idx(len(d["points"]), MAX_TRAJ_POINTS)]
        s = d["spreads"]
        spread_series.append(
            {
                "device_id": dev,
                "points": pts,
                "current": s[-1],
                "mean": round(statistics.fmean(s), 1),
                "median": int(statistics.median(s)),
                "max": max(s),
                "n": len(s),
            }
        )

    last_seg = _latest_segment(data.segments)  # #496: chronological, not file order
    total_h = _hours_since(soil[-1].timestamp_utc, start)
    meta = {
        "device_id": getattr(last_seg, "device_id", None),
        "fw": getattr(last_seg, "firmware_version", None),
        "git": getattr(last_seg, "git", None),
        "run": getattr(last_seg, "run", None),
        "schema_version": getattr(last_seg, "schema_version", None),
        "config_id": getattr(last_seg, "config_id", None),  # #831/ADR-0030 row 5
        "tz_offset": getattr(last_seg, "tz_offset", None),
        # device-reported cadence + its source (nvs|temp|default) from the banner (#322)
        "cadence_ms": getattr(last_seg, "cadence_ms", None),
        "cadence_src": getattr(last_seg, "cadence_src", None),
        "parser": "tools/analytics/parse_v1.py (E6)",
        "all_channels": list(sensor_ids),
        "sources": data.sources,
        "stale_after_s": STALE_AFTER_S,  # #698: one canonical staleness window
        # the staleness reference used for the server-side stale flags (#698), so
        # a static snapshot's baked ages are interpretable; the client prefers its
        # own viewer clock for the live view.
        "as_of_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        # Local-first display labels (#328, #840): the header/date fields + chart
        # axis read in the rig's LOCAL zone (host tz, abbreviated e.g. CDT) with
        # NO UTC secondary — UTC is not a human clock (#720). The *_local fields
        # above stay machine values; the canonical *_utc data is untouched.
        "start_display": (
            local_first_system(soil[0].timestamp_utc, seconds=True, utc_secondary=False)
            if soil[0].timestamp_utc
            else ""
        ),
        "last_display": (
            local_first_system(
                soil[-1].timestamp_utc, seconds=True, utc_secondary=False
            )
            if soil[-1].timestamp_utc
            else ""
        ),
        "generated_display": local_first_system(
            datetime.now(timezone.utc), seconds=True, utc_secondary=False
        ),
    }

    # #324 provenance panel: server/app + device/log + the honest-data contract state.
    # #977 era-aware contract. Maintainer's law: don't cry VIOLATION in red at
    # someone who isn't in violation of anything - a maker collecting dirt data.
    # The raw-only value/unit contract (ADR-0030) holds at schema_version >= the
    # epoch. Rows below it (version-less too) predate it and may carry the legacy
    # moist% `value` column (B2/C2, not plotted) - HISTORY, calm, never an alarm.
    # Alarm bar = "currently true": only a CURRENT-era off-contract row earns red.
    def _off_contract(r) -> bool:
        return r.value is not None or (r.unit or "") != ""

    live_off = any(
        _off_contract(r) and (r.schema_version or 0) >= _CONTRACT_EPOCH_SCHEMA
        for r in soil
    )
    legacy_off = any(
        _off_contract(r) and (r.schema_version or 0) < _CONTRACT_EPOCH_SCHEMA
        for r in soil
    )
    # back-compat flag: True only when fully clean (no legacy, no live off-contract row)
    raw_only_ok = not live_off and not legacy_off
    if live_off:
        contract_state = "violation"
        contract_label = (
            "off-contract: a current row populates value/unit against the contract"
        )
    elif legacy_off:
        contract_state = "legacy"
        contract_label = (
            "includes legacy pre-contract rows — moist% populated, not plotted"
        )
    else:
        contract_state = "clean"
        contract_label = "raw counts + band only (value/unit empty)"
    provenance_block = {
        "server": provenance.server_provenance(),
        "device": {
            "device_id": meta["device_id"],
            "fw": meta["fw"],
            "fw_git": meta["git"],
            "schema_version": meta["schema_version"],
            "config_id": meta["config_id"],  # #831/ADR-0030 row 5
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
            "raw_only": raw_only_ok,  # back-compat flag: True only when fully clean
            "state": contract_state,  # #977: clean | legacy | violation (era-aware)
            "label": contract_label,
        },
        # Always uncalibrated today: raw + band are the truth; per-channel cal is #170.
        "calibration": "uncalibrated (raw + band only; per-channel cal #170)",
    }

    # #583: the per-device groups the template renders (the #575 spec's eight
    # rules). Single device -> one group + the slim ribbon (COLLAPSE).
    device_groups = _device_groups(
        reg, device_ids_in_data, by_sensor, sensors, data.segments, continuity, now
    )

    # #698: the server-side live-fleet count EXCLUDES stale devices, so an offline
    # spare board never inflates "N online". Deterministic vs `now`; the client
    # re-derives the same split live using `stale_after_s` + the viewer's clock.
    stale_devices = sum(1 for g in device_groups if g.get("stale"))
    fleet_health = {
        "devices_total": len(device_groups),
        "devices_online": len(device_groups) - stale_devices,
        "devices_stale": stale_devices,
        "stale_after_s": STALE_AFTER_S,
    }
    # #683: device lifecycle. A board is RETIRED - demoted to a slim row, dropped
    # from the active fleet count - when the registry marks it `retired`, OR when
    # it has been silent for > RETIRE_AFTER_H relative to the freshest reading in
    # the whole fleet (the live edge; deterministic, no wall-clock, so a dead
    # pre-launch test rig auto-demotes without a registry edit). Reversible +
    # honest: raw data is untouched; only the glance view de-emphasizes it.
    # #856: computed BEFORE the version cue below so the fw-mixed set can exclude
    # retired boards, exactly as the fleet count does (the ghost 0.8.0 fix).
    _fleet_edge = soil[-1].timestamp_utc
    _retire_cut = _fleet_edge - timedelta(hours=RETIRE_AFTER_H)
    for g in device_groups:
        _regdev = reg.device(g["device_id"]) if g.get("device_id") else None
        _reg_retired = bool(getattr(_regdev, "retired", False))
        _auto = False
        _ls = g.get("last_seen_utc")
        if _ls:
            try:
                _last = datetime.strptime(_ls, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=_fleet_edge.tzinfo
                )
                _auto = _last < _retire_cut
            except ValueError:
                _auto = False
        g["retired"] = _reg_retired or _auto
        g["retired_reason"] = (
            "archived" if _reg_retired else ("offline" if _auto else None)
        )

    # #719: resolve the three versions for the masthead - fleet firmware (value or
    # the honest mix), the one app==server product version, and a behind/restart
    # cue. `meta["fw"]` becomes the resolved fleet firmware so the masthead never
    # shows a bare "fw ?" (it was the latest SEGMENT's fw, which can be blank).
    # #856: the fw set is drawn from LIVE (non-retired) devices only, so a retired
    # rig's historical firmware (the S3's ghost 0.8.0) never leaks into the cue.
    versions = _versions_block(device_groups, provenance_block["server"])
    meta["fw"] = _fw_masthead(versions) or meta["fw"]

    # #683: the fleet summary counts only ACTIVE (non-retired) devices + their
    # channels, so a demoted test rig never inflates "N devices · N channels".
    _active_ids = {g["device_id"] for g in device_groups if not g["retired"]}
    _active_channels = sum(1 for s in sensors if s.get("device_id") in _active_ids)
    fleet = {
        "devices_active": sum(1 for g in device_groups if not g["retired"]),
        "devices_retired": sum(1 for g in device_groups if g["retired"]),
        "channels_active": _active_channels,
        "retire_after_h": RETIRE_AFTER_H,
    }

    # #807: the Moisture-history chart plots only LIVE channels — a retired rig's
    # channels drop out, so the chart AND its header count agree with the masthead's
    # active count (8), never counting a retired/faulted channel or calling it a
    # "plant". Same active set the fleet subline uses (#683). Legacy single-device
    # logs (device_id None, never retired) are unaffected.
    _sid_to_dev = {s["id"]: s.get("device_id") for s in sensors}
    trajectory_sets = [
        ts for ts in trajectory_sets if _sid_to_dev.get(ts["id"]) in _active_ids
    ]

    # PRD-0002 R3 (#368): join solar + optional weather onto the soil window. Offline-
    # first — {"available": False} when no location config, so the UI just omits it.
    env = build_env_context(start, soil[-1].timestamp_utc)

    return {
        "meta": meta,
        "fleet_health": fleet_health,  # #698 live count excludes stale boards
        "versions": versions,  # #719 masthead: fw + app/server + behind cue
        "provenance": provenance_block,
        "env": env,
        "orientation": ORIENTATION,  # #722: header voice line, read from the voice pool
        "cal": {"bounds": bounds, "moist_range": list(mrange), "bands": bands},
        "sensors": sensors,
        # #679 (ADR-0028): plants present by design but not probed - rendered as
        # first-class "alive, not probed" cards, never as missing/no-signal.
        "sensorless": reg.sensorless_plants(),
        # #627/#717 (PRD-0007 slice 3): the band-movement view substrate - per
        # plant, where it sits across the 7 bands + how it's drifting over the
        # window. Reads from the merged #650 substrate; no new data-plane work.
        "band_history": _band_history(soil, reg),
        "devices": device_groups,
        "fleet": fleet,  # #683: active vs retired counts for the honest subline
        "trajectory": {
            "start_local": meta["start_local"],
            # local-first chart-axis anchor (#328): local + zone, no UTC secondary.
            "start_axis": meta.get("start_display", "").split(" · UTC ")[0]
            or meta["start_local"],
            "datasets": trajectory_sets,
            # #807: live plotted channels — the header count agrees with the chart
            # and the masthead's active count (never the retired-inclusive total).
            "plant_count": len(trajectory_sets),
        },
        "spread": spread_series,  # #651: per-device, fenced - never blended across pots
        "distribution": distribution,
        "quality": quality,
        "integrity": integrity,
        "gaps": gaps,
        # #699: per-device dropouts, keyed by canonical device_id, for the
        # per-device continuity ribbon + fenced chart breaks.
        "gaps_by_device": {(k or ""): v for k, v in gaps_by_device.items()},
    }


def _device_groups(
    reg, device_ids_in_data, by_sensor, sensors, segments, continuity=None, now=None
) -> list:
    """The per-device group headers (#583, the #575 spec's eight rules).

    - ORDER: registry order first (the config's first-seen list), then
      unregistered devices in data-appearance order - state never re-sorts.
    - PER-DEVICE: connection state, time source, and calibration status live
      here, once - never repeated on cards, never averaged into fleet health.
    - STATES: the header exposes ``last_seen_utc`` and the raw ``time_source``;
      the client derives online/offline/syncing (#279 vocabulary) and stamps
      the offline age with the VIEWER's clock, per the spec - never a baked
      server-side age that goes stale in a static snapshot.
    - IDENTITY: friendly name + hostname from the registry (never a MAC); a
      device with no registry entry shows its device_id honestly.
    """
    ordered: list[str] = [
        d.device_id for d in reg.devices if d.device_id in device_ids_in_data
    ]
    ordered += [d for d in device_ids_in_data if d not in ordered]
    if not ordered:
        ordered = [None]  # a legacy log with no device_id column: one group

    groups = []
    for did in ordered:
        if did is None:  # legacy log, no device_id column: every card, one group
            entry_ids = [s["id"] for s in sensors]
        else:
            entry_ids = [s["id"] for s in sensors if s["device_id"] == did]
        rows = [r for k in entry_ids for r in by_sensor[k]]
        if not rows:
            continue
        last = max(rows, key=lambda r: r.timestamp_utc)
        # #602: the identities this board ACTUALLY reported in this window,
        # besides its canonical one - surfaced on the header so the display-
        # time coalesce is visible, never a silent merge (truth has a chain).
        also_reported_as = sorted(
            {r.device_id for r in rows if r.device_id and r.device_id != did}
        )
        regdev = reg.device(did) if did else None
        base_url = getattr(regdev, "base_url", None)
        hostname = None
        if base_url:
            hostname = base_url.split("://", 1)[-1].rstrip("/")
        transport = (
            "wifi"
            if (
                last.payload.get("transport") == "wifi_poll"
                or last.logger_version.startswith("device_adapter")
            )
            else "serial"
        )
        # #617 HONESTY: fail CLOSED - "bench-verified" must be EARNED by positive
        # evidence, never inferred from silence. The tethered serial banner is
        # meaningful: a board that CAN emit "# board cal: PLACEHOLDER" and doesn't
        # is positively asserting cal_verified=true (#436). But that banner never
        # rides WiFi telemetry, so over WiFi its absence proves nothing - reading
        # it as verified is exactly the fail-open that let the newest, LEAST-
        # calibrated boards claim the strongest calibration. So: a WiFi group is
        # provisional until it can state its own cal (Firmware's served-cal-state
        # half, #617b / ADR-0027 rider 3); a serial group's banner still decides.
        has_placeholder = any(
            reg.canonical_for(seg.device_id) == did
            and any("board cal: PLACEHOLDER" in ln for ln in seg.raw_lines)
            for seg in segments
        )
        # #404 host cal-state reader: the served-cal-state half of #617b. A board
        # that POSITIVELY asserts a verified per-channel cal over the wire (a
        # `# cal_ch` line, #507, with confidence calibrated/corroborated) earns
        # not-provisional even over WiFi - opening the #617 fail-closed for a
        # positive assertion, never for silence. So the bench-calibrated classic
        # (#248) stops rendering `cal · provisional` once it emits its cal_ch;
        # the uncalibrated C5 (confidence=provisional) stays provisional. A
        # PLACEHOLDER banner still forces provisional (a stated non-cal wins).
        cal_verified = any(
            reg.canonical_for(seg.device_id) == did
            and any(
                cc.confidence in ("calibrated", "corroborated")
                for cc in seg.per_channel_cal.values()
            )
            for seg in segments
        )
        cal_provisional = has_placeholder or (transport == "wifi" and not cal_verified)
        # #951: three-tier cal honesty (the display half; Firmware's #952 owns the
        # substrate). channel-cal - a per-channel bench cal (cal_verified) - is the TOP
        # state and wears NO label: the absence of a caveat IS the signal. board-cal - a
        # measured board envelope in the header, distinct from the shared factory
        # default (the C5 after #899) - earns a neutral chip, not the "provisional"
        # scarlet letter it wore for merely lacking per-channel cal. uncalibrated -
        # factory defaults, or a stated PLACEHOLDER banner - keeps the caveat. Derived
        # here from the cal signals already on the wire; when #952 lands a formal
        # cal_source the derivation reads it; the tier->label map is unchanged.
        has_board_cal = any(
            reg.canonical_for(seg.device_id) == did
            and seg.cal_bounds_source == "header"
            and list(seg.cal_bounds) != list(DEFAULT_CAL_BOUNDS)
            for seg in segments
        )
        # #952/Firmware wire emission: a WiFi soil row carries `cal_tier=` directly from
        # the resolver (the additive rssi= pattern), so the tier is AUTHORITATIVE on the
        # live fleet - the header signals above are tethered-only, which is exactly why
        # the C5 wore the wrong chip over WiFi. Aggregate the device's per-channel wire
        # tiers to the group's best (channel-cal > board-cal > uncalibrated, matching
        # the any()-precedence above); read it if present, else fall to the derivation.
        _wire = {r.cal_tier for r in rows if r.cal_tier}
        wire_tier = next(
            (t for t in ("channel-cal", "board-cal", "uncalibrated") if t in _wire),
            None,
        )
        if wire_tier is not None:
            cal_tier = wire_tier
        elif cal_verified:
            cal_tier = "channel-cal"
        elif has_board_cal and not has_placeholder:
            cal_tier = "board-cal"
        else:
            cal_tier = "uncalibrated"
        groups.append(
            {
                "device_id": did,
                # the ratified `name` field first; then the legacy `label` (the
                # parse path folds label into name, but a directly-constructed
                # Device may carry label only); an unregistered device stays
                # its own id - never an invented friendly name (#583/#602)
                "name": (
                    getattr(regdev, "name", None)
                    or getattr(regdev, "label", None)
                    or did
                    or "Sprout"
                ),
                "hostname": hostname,
                "side": getattr(regdev, "side", None),  # #713 physical placement
                "transport": transport,
                "board": getattr(regdev, "board", None),
                "fw": last.firmware_version or None,
                "time_source": last.time_source,  # None = host-stamped
                "last_seen_utc": (
                    last.timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if last.timestamp_utc
                    else None
                ),
                "cal_provisional": cal_provisional,
                # #951 three-tier: channel-cal | board-cal | uncalibrated
                "cal_tier": cal_tier,
                # #814: current WiFi signal from this device's latest polled row.
                # Honest-absent (ADR-0028): a serial/tethered row omits rssi -> None,
                # so no chip, never a fabricated 0 dBm. Real dBm + a band, not a %.
                "rssi": last.rssi,
                "rssi_band": _rssi_band(last.rssi),
                "also_reported_as": also_reported_as,  # honest coalesce (#602)
                # #699: this board's own continuity (coverage/longest/last gap),
                # so a WiFi dropout is visible per device - never fleet-averaged.
                "continuity": (continuity or {}).get(
                    did,
                    {
                        "coverage_pct": None,
                        "longest_gap_min": None,
                        "last_gap_min": None,
                        "gap_count": 0,
                    },
                ),
                # #698: server-side staleness (age since last reading vs `now`),
                # the tested contract behind the client's viewer-clock derivation.
                # A stale group is de-emphasized and out of the online count; it
                # restores automatically once age drops back under the window.
                "stale": (
                    _age_seconds(last.timestamp_utc, now) > STALE_AFTER_S
                    if now is not None and last.timestamp_utc is not None
                    else False
                ),
                "age_s": (
                    int(_age_seconds(last.timestamp_utc, now))
                    if now is not None
                    and _age_seconds(last.timestamp_utc, now) is not None
                    else None
                ),
                "sensors": entry_ids,
            }
        )
    return groups


def _locator(sources: list[str]) -> dict:
    """#685: 'your data lives here' - the log dir(s), the active segment file(s),
    and the archive location an operator would hand an agent to dive into the raw
    data. Repo-relative where the file is inside the repo, else the full path;
    forward-slashed for a copy-pasteable, OS-neutral pointer."""
    repo = str(_REPO).replace("\\", "/")
    arch = str(ARCHIVE_DIR).replace("\\", "/")

    def rel(p: str) -> str:
        p2 = str(p).replace("\\", "/")
        return p2[len(repo) + 1 :] if p2.startswith(repo + "/") else p2

    active: list[str] = []
    archived: list[str] = []
    fleet: list[str] = []
    for s in sources:
        s2 = str(s).replace("\\", "/")
        # #965: a fleet-poll source is an HTTP endpoint, not a file. Splitting it as a
        # path minted a meaningless `http:/` log dir and listed the `.local` host as an
        # "active file". Give it its own labeled line: host[:port], with scheme + any
        # /telemetry path stripped, so the "hand these to an agent" promise holds.
        if s2.startswith(("http://", "https://")):
            fleet.append(s2.split("://", 1)[1].split("/", 1)[0])
        elif s2.startswith(arch):
            archived.append(s2)
        else:
            active.append(s2)
    log_dirs = sorted({"/".join(a.split("/")[:-1]) for a in active})
    return {
        "log_dirs": [rel(d) for d in log_dirs] or [rel(str(LOGS_DIR))],
        "active_files": [a.split("/")[-1] for a in active],
        "active_count": len(active),
        "archive_dir": rel(str(ARCHIVE_DIR)),
        "archive_count": len(archived),
        "fleet_sources": sorted(set(fleet)),  # #965: labeled, never file cosplay
    }


def _rssi_band(dbm: int | None) -> str | None:
    """A labeled WiFi-signal band for a dBm reading (#814). ``None`` -> ``None``: a
    serial/tethered row carries no ``rssi=`` (ADR-0028 honest-absent), so there is no
    band to invent - the surface shows absence as absence, never a fabricated 0 dBm.
    The band is the real dBm's honest bucket, NOT a quality percentage (dashboard
    honesty, B2/C2): ``strong`` >= -67, ``fair`` -67..-75, ``weak`` < -75 (the weak
    cue is the operator's placement/dropout signal)."""
    if dbm is None:
        return None
    if dbm >= -67:
        return "strong"
    if dbm >= -75:
        return "fair"
    return "weak"


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
    # #277: reads through the source-adapter seam - TetheredAdapter today, a future
    # device-served adapter (#276) later, with no change to this call site. Inputs
    # are resolved up front (not left to the adapter's own discovery) so the error
    # message below still names exactly which files were checked.
    data = TetheredAdapter().load(inputs)
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
