"""Schema-v1 telemetry log reader for the plants project (backlog E6).

Reads the long/tidy ``schema_version=1`` CSV emitted by the host logger
(``tools/logger/plants_logger.py``; contract in ``docs/TELEMETRY_SCHEMA.md``)
and turns it into typed records for analytics and dashboards (E7, E1, E2).

What it handles that the retired single-channel parser could not:

* the per-segment ``#`` provenance header blocks (re-emitted at every
  rotation) and the ``record_type,...`` column-name row that follows each;
* the long/tidy layout - one row per sensor per ~30 s sweep, four sensors
  (``s1..s4``) interleaved;
* ``payload`` (``level=...;role=...;spread=...;gpio=...``) exploded into fields;
* gzip-compressed archive segments (``*.csv.gz``) from the B8 LFS archive;
* future schema bumps - columns are mapped *by name* off each segment's
  header row and ``schema_version`` is surfaced, so an added/reordered column
  does not break the reader.

A note on ``value`` (backlog B2/C2): the CSV ``value``/``unit`` column is the
legacy linear ``moist%`` map ``(3400 - raw) / (3400 - 900)``. It *looks*
authoritative but is not VWC and must not drive analysis. This reader carries
it through unchanged (raw is immutable; nothing is hidden) but exposes
``raw_value`` and the calibrated ``band`` as the trustworthy signals. Build
analytics on ``raw_value`` + ``band``, never on ``value``.

Usage::

    python tools/analytics/parse_v1.py docs/sample_log.csv
    python tools/analytics/parse_v1.py logs/          # all *.csv[.gz] in dir
    python tools/analytics/parse_v1.py                # newest repo log

    from tools.analytics.parse_v1 import parse_files
    data = parse_files(["logs/"])
    df = data.to_dataframe()                          # optional, needs pandas
"""

from __future__ import annotations

import csv
import gzip
import io
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Canonical schema-v1 column order (docs/TELEMETRY_SCHEMA.md section 2). Used
# only as a fallback if a data row is seen before any column-name header row;
# normally the per-segment header row is authoritative.
CANONICAL_COLUMNS = [
    "record_type",
    "timestamp_utc",
    "timestamp_local",
    "sample_id",
    "session_id",
    "device_id",
    "firmware_version",
    "logger_version",
    "millis_ms",
    "sensor_model",
    "sensor_id",
    "sensor_position",
    "channel",
    "raw_value",
    "value",
    "unit",
    "quality_flag",
    "temp_context_c",
    "rh_context_pct",
    "pressure_context_hpa",
    "event_id",
    "payload",
    "notes",
]

# Firmware classifier band names, wettest -> driest, and the as-flashed cal
# boundaries (dry > wet, descending). The boundaries are the *un-reconciled*
# A2 interior bands are proposed; endpoints are firmware-ratified (common-cup #255).
BANDS_WET_TO_DRY = [
    "submerged",
    "overwatered",
    "well watered",
    "OK",
    "needs water",
    "DRY",
    "air-dry",
]
BANDS_DRY_TO_WET = list(reversed(BANDS_WET_TO_DRY))
# Reconciled firmware values (main.cpp:63, #255). Used only when a segment's
# provenance header lacks a "cal bounds" line; prefer header-derived bounds always.
DEFAULT_CAL_BOUNDS = (3050, 2140, 1830, 1520, 1150, 1050)

_KV_RE = re.compile(r"(\w+)=(.*?)(?=\s+\w+=|$)")
_SENSOR_RE = re.compile(r"ch(\d+)=GPIO(\d+)/(\S+)")

# ADR-0022's confidence vocabulary. A header value outside this set is never trusted
# at face value - it degrades to "provisional" (#404) rather than risk an unearned
# "calibrated"/"corroborated" label reaching the runtime corroborated-veto logic.
CONFIDENCE_LEVELS = ("provisional", "calibrated", "corroborated")


@dataclass
class ChannelCal:
    """Per-channel cal-bounds provenance (#404, extends #295's one shared line).

    PROPOSED wire format (awaiting Firmware's emit-format confirmation - see #404):
    ``# cal_ch <sensor_id>: bounds=<d1,...,d6> src=<...> date=<YYYY-MM-DD>
    confidence=<provisional|calibrated|corroborated> scope=<channel|shared>``.
    Parsing here is read-only and additive: a log without any ``cal_ch`` line is
    unaffected (falls through to the existing shared/default cal bounds, #295)."""

    bounds: list[int] = field(default_factory=list)
    src: str | None = None
    date: str | None = None
    confidence: str = "provisional"
    scope: str = "channel"


# --------------------------------------------------------------------------- #
# scalar coercion helpers
# --------------------------------------------------------------------------- #
def _int(s: str | None) -> int | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


def _float(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_local(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.strip())
    except ValueError:
        return None


def parse_payload(s: str | None) -> dict[str, str]:
    """Explode a ``;``-separated ``k=v`` payload into a dict (section 6).

    Values may contain spaces (e.g. ``level=well watered``); the first ``=``
    splits key from value. Empty / missing payload -> empty dict.
    """
    out: dict[str, str] = {}
    if not s:
        return out
    for part in s.split(";"):
        if not part:
            continue
        key, sep, val = part.partition("=")
        if sep:
            out[key.strip()] = val.strip()
    return out


def band_for_raw(
    raw: int | None, bounds: tuple[int, ...] = DEFAULT_CAL_BOUNDS
) -> str | None:
    """Naive band for a raw ADC count using descending (dry>wet) boundaries.

    Pure thresholding - it deliberately ignores the firmware deadband and
    confirm timers, so it will *not* always equal the device-emitted
    ``payload.level`` (which carries hysteresis state). Use the per-row
    ``Reading.band`` for ground truth; use this only for drawing the band
    ladder / shading a chart from the file's own cal bounds.
    """
    if raw is None:
        return None
    for name, edge in zip(BANDS_DRY_TO_WET, bounds):
        if raw >= edge:
            return name
    return BANDS_WET_TO_DRY[0]


# --------------------------------------------------------------------------- #
# data model
# --------------------------------------------------------------------------- #
@dataclass
class SegmentHeader:
    """Provenance for one rotation segment (its ``#`` block + column row)."""

    columns: list[str] = field(default_factory=list)
    schema_version: int | None = None
    log_start_utc: str | None = None
    tz_offset: str | None = None
    logger_version: str | None = None
    firmware_version: str | None = None
    git: str | None = None
    built: str | None = None
    run: str | None = None
    device_id: str | None = None
    mac: str | None = None
    chip: str | None = None
    adc: str | None = None
    session_id: str | None = None
    cadence_ms: int | None = None
    cadence_src: str | None = None  # "nvs" | "temp" | "default" — banner field (#322)
    sensors: dict[str, dict[str, object]] = field(default_factory=dict)
    cal_bounds: list[int] = field(default_factory=list)
    cal_bounds_source: str = ""  # "header" | "default" — set by _parse_header_lines
    per_channel_cal: dict[str, ChannelCal] = field(default_factory=dict)  # #404
    moist_range: tuple[int, int] | None = None
    cfg: dict[str, str] = field(default_factory=dict)
    source: str | None = None
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class Reading:
    """One parsed data row (one sensor, one sweep)."""

    record_type: str
    timestamp_utc: datetime | None
    timestamp_local: datetime | None
    sample_id: int | None
    session_id: str
    device_id: str
    firmware_version: str
    logger_version: str
    millis_ms: int | None
    sensor_model: str
    sensor_id: str
    sensor_position: str
    channel: str
    raw_value: int | None
    value: float | None  # legacy moist% - DO NOT use for analysis (B2/C2)
    unit: str
    quality_flag: str
    payload: dict[str, str]
    event_id: str = ""
    temp_context_c: float | None = None
    rh_context_pct: float | None = None
    pressure_context_hpa: float | None = None
    notes: str = ""
    schema_version: int | None = None
    row: dict[str, str] = field(default_factory=dict)

    @property
    def band(self) -> str | None:
        """Device-emitted band (``payload.level``) - the per-row ground truth."""
        return self.payload.get("level")

    @property
    def role(self) -> str | None:
        return self.payload.get("role")

    @property
    def spread(self) -> int | None:
        return _int(self.payload.get("spread"))

    @property
    def gpio(self) -> int | None:
        return _int(self.payload.get("gpio"))


@dataclass
class Sweep:
    """The set of sensor readings sharing one (session, millis) sample tick."""

    session_id: str
    millis_ms: int | None
    timestamp_utc: datetime | None
    by_sensor: dict[str, Reading]


@dataclass
class LogData:
    """Parsed result: flat readings, plus the segments they came from."""

    readings: list[Reading] = field(default_factory=list)
    segments: list[SegmentHeader] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.readings)

    def sensors(self) -> list[str]:
        seen: dict[str, None] = {}
        for r in self.readings:
            seen.setdefault(r.sensor_id, None)
        return list(seen)

    def sweeps(self) -> list[Sweep]:
        """Group readings into per-tick sweeps, keyed (session_id, millis_ms)."""
        groups: dict[tuple[str, int | None], dict[str, Reading]] = {}
        order: list[tuple[str, int | None]] = []
        for r in self.readings:
            key = (r.session_id, r.millis_ms)
            if key not in groups:
                groups[key] = {}
                order.append(key)
            groups[key][r.sensor_id] = r
        out: list[Sweep] = []
        for key in order:
            members = groups[key]
            ts = min(
                (r.timestamp_utc for r in members.values() if r.timestamp_utc),
                default=None,
            )
            out.append(Sweep(key[0], key[1], ts, members))
        return out

    def to_dataframe(self):  # pandas optional; lazy import keeps E6 dep-free
        """Return a tidy pandas DataFrame (lazy import; pandas optional)."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise ImportError(
                "to_dataframe() needs pandas (pip install pandas)"
            ) from exc
        rows = [
            {
                "timestamp_utc": r.timestamp_utc,
                "timestamp_local": r.timestamp_local,
                "session_id": r.session_id,
                "sample_id": r.sample_id,
                "millis_ms": r.millis_ms,
                "sensor_id": r.sensor_id,
                "channel": r.channel,
                "raw_value": r.raw_value,
                "band": r.band,
                "quality_flag": r.quality_flag,
                "spread": r.spread,
                "gpio": r.gpio,
                "role": r.role,
                # named to discourage misuse - see B2/C2 in the module docstring
                "value_legacy_pct": r.value,
                "record_type": r.record_type,
                "device_id": r.device_id,
                "firmware_version": r.firmware_version,
            }
            for r in self.readings
        ]
        return pd.DataFrame(rows)

    def summary(self) -> str:
        return _summarize(self)


# --------------------------------------------------------------------------- #
# header parsing
# --------------------------------------------------------------------------- #
def _kv(body: str) -> dict[str, str]:
    """Parse whitespace-separated ``k=v`` tokens; values may contain spaces."""
    return {m.group(1): m.group(2).strip() for m in _KV_RE.finditer(body)}


def _looks_structured(body: str) -> bool:
    if body.startswith("plants telemetry"):
        return True
    return bool(re.match(r"\w+=", body))


def _parse_sensors(body: str) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for m in _SENSOR_RE.finditer(body):
        out[f"ch{m.group(1)}"] = {
            "gpio": int(m.group(2)),
            "sensor_id": m.group(3),
        }
    return out


def _parse_cal_channel(body: str) -> tuple[str, ChannelCal] | None:
    """One ``cal_ch <sensor_id>: bounds=... src=... date=... confidence=... scope=...``
    line (#404, PROPOSED). Returns None for a malformed line (no sensor id, or no
    ``:`` separator) - never raises; a bad line just doesn't contribute an override,
    so the channel falls through to the existing shared/default bounds."""
    after = body[len("cal_ch") :].strip()
    if ":" not in after:
        return None
    sid, rest = after.split(":", 1)
    sid = sid.strip()
    if not sid:
        return None
    kv = _kv(rest.strip())
    bounds_str = kv.get("bounds", "")
    try:
        bounds = [int(x) for x in bounds_str.split(",") if x.strip()]
    except ValueError:
        bounds = []
    confidence = kv.get("confidence", "provisional")
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "provisional"  # never invent an unearned confidence level
    return sid, ChannelCal(
        bounds=bounds,
        src=kv.get("src"),
        date=kv.get("date"),
        confidence=confidence,
        scope=kv.get("scope", "channel"),
    )


def cal_bounds_for_channel(seg: SegmentHeader, sensor_id: str) -> tuple[list[int], str]:
    """The cal bounds + confidence label for one channel (#404's honest fallback):
    per-channel provenance (if present and non-empty) -> the shared header line
    (#295) -> the compiled default. The shared/default paths carry "provisional"
    (ADR-0022) since neither is a per-channel calibration claim."""
    ch = seg.per_channel_cal.get(sensor_id)
    if ch and ch.bounds:
        return ch.bounds, ch.confidence
    if seg.cal_bounds_source == "header":
        return seg.cal_bounds, "provisional"
    return list(DEFAULT_CAL_BOUNDS), "provisional"


def _parse_cal(body: str) -> tuple[list[int], tuple[int, int] | None]:
    after = body.split(":", 1)[1] if ":" in body else body
    rng: tuple[int, int] | None = None
    if "[moist%" in after:
        left, right = after.split("[moist%", 1)
        nums = re.findall(r"\d+", right)
        if len(nums) >= 2:
            rng = (int(nums[0]), int(nums[1]))
        after = left
    bounds = [int(x) for x in re.findall(r"\d+", after)]
    return bounds, rng


def _apply_kv(h: SegmentHeader, kv: dict[str, str]) -> None:
    h.log_start_utc = kv.get("log_start_utc", h.log_start_utc)
    h.tz_offset = kv.get("tz_offset", h.tz_offset)
    h.logger_version = kv.get("logger", h.logger_version)
    if "schema_version" in kv:
        h.schema_version = _int(kv["schema_version"])
    h.firmware_version = kv.get("fw", h.firmware_version)
    h.git = kv.get("git", h.git)
    h.built = kv.get("built", h.built)
    h.run = kv.get("run", h.run)
    h.device_id = kv.get("device_id", h.device_id)
    h.mac = kv.get("mac", h.mac)
    h.chip = kv.get("chip", h.chip)
    h.adc = kv.get("adc", h.adc)
    h.session_id = kv.get("session_id", h.session_id)
    if "cadence_ms" in kv:
        h.cadence_ms = _int(kv["cadence_ms"])
    # cadence_src (nvs|temp|default) — the banner field from Firmware #351 (#322), so
    # the dashboard can show whether the live cadence is the persisted default, a
    # session-only experiment override, or the compiled fallback.
    h.cadence_src = kv.get("cadence_src", h.cadence_src)


def _parse_header_lines(
    lines: list[str], columns: list[str], source: str
) -> SegmentHeader:
    h = SegmentHeader(columns=list(columns), source=source, raw_lines=list(lines))
    kv: dict[str, str] = {}
    for line in lines:
        body = line.lstrip("#").strip()
        if body.startswith("sensors:"):
            h.sensors = _parse_sensors(body)
        elif body.startswith("cal bounds"):
            h.cal_bounds, h.moist_range = _parse_cal(body)
        elif body.startswith("cal_ch"):  # #404, PROPOSED - see cal_bounds_for_channel
            parsed = _parse_cal_channel(body)
            if parsed:
                sid, ch_cal = parsed
                h.per_channel_cal[sid] = ch_cal
        elif body.startswith("cfg:"):
            h.cfg = _kv(body[len("cfg:") :])
        elif body.startswith("device_cols:"):
            continue  # the CSV column-name row is authoritative
        elif "=" in body and _looks_structured(body):
            kv.update(_kv(body))
    _apply_kv(h, kv)
    if h.cal_bounds:
        h.cal_bounds_source = "header"
    else:
        h.cal_bounds = list(DEFAULT_CAL_BOUNDS)
        h.cal_bounds_source = "default"
    return h


# --------------------------------------------------------------------------- #
# row parsing
# --------------------------------------------------------------------------- #
def _row_dict(cols: list[str], fields: list[str]) -> dict[str, str]:
    if len(fields) < len(cols):
        fields = fields + [""] * (len(cols) - len(fields))
    return dict(zip(cols, fields))


def _reading_from_row(row: dict[str, str], seg: SegmentHeader) -> Reading:
    return Reading(
        record_type=row.get("record_type", ""),
        timestamp_utc=_parse_utc(row.get("timestamp_utc")),
        timestamp_local=_parse_local(row.get("timestamp_local")),
        sample_id=_int(row.get("sample_id")),
        session_id=row.get("session_id", ""),
        device_id=row.get("device_id", ""),
        firmware_version=row.get("firmware_version", ""),
        logger_version=row.get("logger_version", ""),
        millis_ms=_int(row.get("millis_ms")),
        sensor_model=row.get("sensor_model", ""),
        sensor_id=row.get("sensor_id", ""),
        sensor_position=row.get("sensor_position", ""),
        channel=row.get("channel", ""),
        raw_value=_int(row.get("raw_value")),
        value=_float(row.get("value")),
        unit=row.get("unit", ""),
        quality_flag=row.get("quality_flag", ""),
        payload=parse_payload(row.get("payload", "")),
        event_id=row.get("event_id", ""),
        temp_context_c=_float(row.get("temp_context_c")),
        rh_context_pct=_float(row.get("rh_context_pct")),
        pressure_context_hpa=_float(row.get("pressure_context_hpa")),
        notes=row.get("notes", ""),
        schema_version=seg.schema_version,
        row=row,
    )


# --------------------------------------------------------------------------- #
# file iteration
# --------------------------------------------------------------------------- #
def _open_text(path: Path) -> io.TextIOBase:
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _resolve(paths: list[str | Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        path = Path(p)
        if path.is_dir():
            out.extend(sorted(path.glob("*.csv")))
            out.extend(sorted(path.glob("*.csv.gz")))
        elif any(ch in str(p) for ch in "*?["):
            out.extend(sorted(Path().glob(str(p))))
        else:
            out.append(path)
    return out


def parse_file(path: str | Path, into: LogData | None = None) -> LogData:
    """Parse one log file (``.csv`` or ``.csv.gz``) into a ``LogData``."""
    data = into if into is not None else LogData()
    path = Path(path)
    data.sources.append(str(path))
    header_buf: list[str] = []
    cols: list[str] = list(CANONICAL_COLUMNS)
    current: SegmentHeader | None = None
    with _open_text(path) as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                header_buf.append(line)
                continue
            fields = next(csv.reader([line]))
            if fields and fields[0] == "record_type":
                cols = fields
                current = _parse_header_lines(header_buf, cols, str(path))
                data.segments.append(current)
                header_buf = []
                continue
            if current is None:
                current = _parse_header_lines(header_buf, cols, str(path))
                data.segments.append(current)
                header_buf = []
            data.readings.append(_reading_from_row(_row_dict(cols, fields), current))
    return data


def parse_files(paths: list[str | Path]) -> LogData:
    """Parse many files / dirs / globs into one chronological ``LogData``."""
    data = LogData()
    for path in _resolve(paths):
        parse_file(path, into=data)
    return data


# --------------------------------------------------------------------------- #
# summary / CLI
# --------------------------------------------------------------------------- #
def _fmt_span(readings: list[Reading]) -> str:
    times = [r.timestamp_utc for r in readings if r.timestamp_utc]
    if not times:
        return "no timestamps"
    lo, hi = min(times), max(times)
    dur = hi - lo
    return f"{lo.isoformat()} -> {hi.isoformat()}  ({dur})"


def _summarize(data: LogData) -> str:
    out: list[str] = []
    n = len(data.readings)
    versions = {s.schema_version for s in data.segments if s.schema_version}
    out.append(
        f"schema-v1 log: {n} readings | {len(data.segments)} segment(s) | "
        f"{len(data.sources)} file(s) | schema_version={sorted(versions)}"
    )
    if versions - {1}:
        out.append(f"  !! non-v1 schema seen: {sorted(versions - {1})}")
    out.append(f"  span: {_fmt_span(data.readings)}")
    sessions = {r.session_id for r in data.readings}
    out.append(f"  sessions: {sorted(sessions)}  sweeps: {len(data.sweeps())}")

    qf = Counter(r.quality_flag for r in data.readings)
    out.append(f"  quality_flag: {dict(qf)}")

    out.append("  per sensor (raw min/last/max, band, n):")
    by_sensor: dict[str, list[Reading]] = {}
    for r in data.readings:
        by_sensor.setdefault(r.sensor_id, []).append(r)
    for sid in sorted(by_sensor):
        rs = by_sensor[sid]
        raws = [r.raw_value for r in rs if r.raw_value is not None]
        last = rs[-1]
        gpio = last.gpio
        if raws:
            out.append(
                f"    {sid:>3} (gpio {gpio}): "
                f"{min(raws):>5} / {raws[-1]:>5} / {max(raws):>5}  "
                f"band={last.band!r:<16} n={len(rs)}"
            )
        else:
            out.append(f"    {sid:>3} (gpio {gpio}): no raw  n={len(rs)}")

    if data.segments:
        seg = data.segments[-1]
        out.append(
            f"  latest segment: fw={seg.firmware_version} git={seg.git} run={seg.run}"
        )
        bounds_note = (
            " !! fallback default (no cal bounds in header)"
            if seg.cal_bounds_source == "default"
            else ""
        )
        out.append(
            f"    cal_bounds={seg.cal_bounds} [{seg.cal_bounds_source}]"
            f"{bounds_note} moist_range={seg.moist_range} cadence_ms={seg.cadence_ms}"
        )
        if seg.sensors:
            chmap = " ".join(
                f"{ch}={v['sensor_id']}/gpio{v['gpio']}"
                for ch, v in sorted(seg.sensors.items())
            )
            out.append(f"    channels: {chmap}")
    out.append(
        "  NOTE: 'value' column is the legacy moist% map - analyse on "
        "raw_value + band, not value (B2/C2)."
    )
    return "\n".join(out)


def _default_logs() -> list[str]:
    repo = Path(__file__).resolve().parents[2]
    logs = repo / "logs"
    if not logs.is_dir():
        return []
    files = sorted(logs.glob("*.csv")) + sorted(logs.glob("*.csv.gz"))
    return [str(files[-1])] if files else []


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = _default_logs()
        if not args:
            print("usage: parse_v1.py <log.csv|dir|glob> ...", file=sys.stderr)
            return 2
        print(f"(no args) using newest repo log: {args[0]}")
    data = parse_files(args)
    if not data.readings:
        print("no readings parsed", file=sys.stderr)
        return 1
    print(data.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
