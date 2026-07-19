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
# Case-insensitive map to the canonical band token (#655). Firmware casing has
# drifted - older builds emit `dry` where the canon is `DRY` - and the canon set
# is mixed-case (`DRY`/`OK` upper, the rest lower), so it is not a simple .upper().
# Normalizing the DERIVED band here fixes every case-sensitive consumer at once
# (BAND_UI, the band index, #626) at the single parse boundary (ADR-0021), while
# the raw `payload['level']` stays byte-for-byte untouched.
_CANON_BAND = {name.lower(): name for name in BANDS_WET_TO_DRY}
# The ratified classic in-soil ladder — #995/#1174 (2026-07-19, ADR-0035) with the
# #1236-RATIFIED wet-end re-derive (route B, maintainer production GO): Saturated is a
# thin at-the-rail band (ceiling 1150 = rail+98), Wet/Moist/Ideal re-spaced, the dry
# half unchanged. The host sibling of firmware's MOISTURE_CFG_DEFAULT.boundary, per
# the #1153 host-mirror contract — PAIR-MERGED with Firmware's boundary PR, one motion.
# Descending: the 6 interior edges of the 7 in-soil bands (Soaked..Faint). Faint =
# raw >= [0] (unbounded up), Soaked = raw < [5] (unbounded down); the off-ladder
# air/water anchors live in BOARD_CLASS_ANCHORS below (#1235/#1152). Used only when a
# segment's provenance header lacks a "cal bounds" line; prefer header bounds always.
DEFAULT_CAL_BOUNDS = (2293, 2086, 1879, 1636, 1393, 1150)

# #1235/#1152 — the per-BOARD-CLASS off-ladder anchors: the measured in-soil envelope
# rails (#995/#1174 dry-down, medians of the per-channel cal), the host sibling of
# firmware's board_capability values. ONE definition, two consumers: the pulse envelope
# spans them (#1235) and the #1152 exception layer keys off the SAME rails (dry past
# air = probe-in-air; wet past water = probe-in-water) — never two copies. A profiled
# per-CHANNEL anchor (registry cal chain) beats the class value when present (ADR-0019).
# #1215 (ratified): the #898 cross-board factor is INTERVAL-DEPENDENT — 0.803 on the
# full rail-to-rail envelope (978 cup rail; the probe-in-water exception interval) vs
# 0.850 on the in-soil ladder interval (these 1052/982 wet floors). Both valid for
# their jobs; ADC compression isn't perfectly linear rail-to-rail. Never conflate.
BOARD_CLASS_ANCHORS = {
    "classic": {"air": 3137, "water": 1052},
    "c5": {"air": 2754, "water": 982},
}


def board_class(board: str | None) -> str:
    """Board string -> anchor class. Anything self-describing as a C5 is ``c5``;
    everything else (incl. absent) is ``classic`` — the project's primary/default
    board class, matching DEFAULT_CAL_BOUNDS's own classic-sided default."""
    return "c5" if board and "c5" in board.lower() else "classic"


# A capacitive soil probe cannot read WETTER than fully submerged in water. On the
# classic's scale the physical wet rail is ~900 raw ("wetter than a cup of water");
# a reading below it is not moisture - it is a fault (a short, water-contamination,
# or a disconnected ADC floating near 0). This conservative floor sits well below
# any genuine saturation on either board (classic-in-water ~900; the compressed C5
# ~810, #443), so it catches the observed faults - a dead board reading 0-7, and
# the contaminated P11 s3 that stuck at ~420 - without false-flagging real
# saturated soil. It is DERIVED (a display/analysis gate); the raw value on the
# wire and in the log is never altered. A per-board (cal-derived) floor is the
# robust long-term answer (#670); this fixed floor is the safe interim.
IMPLAUSIBLE_WET_FLOOR = 500

# The schema_version at which `device_id` becomes the stable minted id (ADR-0027
# §1b, Accepted; #618). `>= 3` ⇒ stable id + friendly `name=` in payload; `< 3`
# ⇒ `device_id` is a mutable name (v1 monitor, v2 experiment-capture). Not 2:
# `schema_version=2` is already live-emitted by experiment_capture.py with
# `device_id`=name, so reusing it would misclassify every shipped experiment row.
STABLE_ID_SCHEMA_VERSION = 3

_KV_RE = re.compile(r"(\w+)=(.*?)(?=\s+\w+=|$)")
_SENSOR_RE = re.compile(r"ch(\d+)=GPIO(\d+)/(\S+)")

# ADR-0022's confidence vocabulary. A header value outside this set is never trusted
# at face value - it degrades to "provisional" (#404) rather than risk an unearned
# "calibrated"/"corroborated" label reaching the runtime corroborated-veto logic.
CONFIDENCE_LEVELS = ("provisional", "calibrated", "corroborated")

# ADR-0023 v2's context-source vocabulary: tag -> proximity/family class, so the
# trust class travels deterministically with the value (#562). Interior classes
# (plant_local, room) are the only legal fillers of temp/RH context; "exterior"
# appears solely via the pressure exception (§3). An unknown tag -> None: the
# value stays visible but its class is honestly unresolved, never guessed.
CONTEXT_SOURCE_CLASS = {
    "sht45_onrig": "plant_local",
    "zigbee_room": "room",
    "thread_room": "room",
    "matter_room": "room",
    "ecobee": "room",
    "ha_ambient": "room",
    "weather_openmeteo": "exterior",
}


def context_class(tag: str | None) -> str | None:
    """The ADR-0023 proximity/family class for a ``context_source`` tag, or
    ``None`` when the tag is absent/unknown - a consumer must not invent one."""
    return CONTEXT_SOURCE_CLASS.get(tag) if tag else None


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
    config_id: str | None = None  # #576/v4 — header-authoritative config fingerprint
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
        """Device-emitted band (``payload.level``) - the per-row ground truth,
        normalized to the canonical band token's casing (#655). The raw
        ``payload['level']`` is untouched; only this derived accessor
        canonicalizes casing, so a firmware that emits ``dry`` still renders
        ``DRY`` everywhere (BAND_UI, the band index, #626). An unrecognized value
        passes through unchanged - no invented mapping."""
        raw = self.payload.get("level")
        if raw is None:
            return None
        return _CANON_BAND.get(raw.lower(), raw)

    @property
    def implausible_wet(self) -> bool:
        """True if a soil raw is below the physical wet rail (#670) - a reading no
        capacitive probe can produce from moisture (a short, water-contamination,
        or a disconnected ADC near 0). A derived fault signal; the raw is never
        altered. Only meaningful for soil rows (env readings sit at ~27000, far
        above the floor, so they never trip it)."""
        return (
            self.record_type.startswith("plants.soil")
            and self.raw_value is not None
            and self.raw_value < IMPLAUSIBLE_WET_FLOOR
        )

    @property
    def role(self) -> str | None:
        return self.payload.get("role")

    @property
    def spread(self) -> int | None:
        return _int(self.payload.get("spread"))

    @property
    def gpio(self) -> int | None:
        return _int(self.payload.get("gpio"))

    @property
    def device_seq(self) -> int | None:
        """Device-monotonic row counter (schema v2 §11.2, #278/#300) - the
        device-side half of the dedupe key; survives a store-and-forward
        reconnect/replay, resets only on reboot. None on a v1-only row."""
        return _int(self.payload.get("device_seq"))

    # --- schema v4 (#739 bundle, TELEMETRY_SCHEMA §13) — all payload k=v, so they
    # read None on a v3/v2/v1 row (never stitched): only a >=4 board emits them. ---

    @property
    def config_id(self) -> str | None:
        """Firmware-computed config fingerprint (#576/ADR-0025, schema v4) - an
        8-hex FNV-1a-32 of the active ADC/sampling/cal/cadence snapshot. Same id
        ⇒ rows are directly comparable; a change is a comparability boundary. Read
        from the row's ``payload`` (header-authoritative on the segment); parse_v1
        reads it, never re-derives. None on a pre-v4 row."""
        return self.payload.get("config_id") or None

    @property
    def rssi(self) -> int | None:
        """WiFi signal strength in dBm (#669, schema v4), a negative int.
        Honest-absent (ADR-0028): a serial/tethered or unassociated row omits the
        key entirely - None, never a fake 0. Only dBm ever rides the wire (never
        SSID/BSSID/MAC - the privacy fence)."""
        return _int(self.payload.get("rssi"))

    @property
    def cal_tier(self) -> str | None:
        """The calibration tier this row was resolved at (#952/#957, an additive wire
        token, the ``rssi=`` pattern): channel-cal | board-cal | uncalibrated,
        per soil row, direct from the firmware resolver. Authoritative on the LIVE WiFi
        fleet, where the header-derived signals (cal_bounds_source / cal_ch) don't reach
        - so #951's tier chip is finally true off-tether. An unknown/absent
        value is None (honest-absent, ADR-0028): a serial row that never emits it, or a
        garbled token, falls back to the header derivation rather than passing junk."""
        v = self.payload.get("cal_tier")
        return v if v in ("channel-cal", "board-cal", "uncalibrated") else None

    @property
    def cal_src(self) -> str | None:
        """The resolver's cal-source provenance string (#952, optional companion to
        ``cal_tier``) - e.g. ``board_envelope_20260710`` - for #921's cal-record display
        + a tooltip. None when absent; never invented."""
        return self.payload.get("cal_src") or None

    @property
    def uptime_s(self) -> int | None:
        """Seconds since board boot (#669, schema v4) - a transport-independent
        board diagnostic. None on a pre-v4 row."""
        return _int(self.payload.get("uptime_s"))

    @property
    def heap(self) -> int | None:
        """Free heap bytes (#669, schema v4) - a board health diagnostic. None on
        a pre-v4 row."""
        return _int(self.payload.get("heap"))

    @property
    def fault(self) -> str | None:
        """The specific sensor-fault reason (#670, schema v4): ``stuck_wet`` (short
        / water-contamination) or ``dead_adc``. Present only when the firmware
        self-declares ``quality_flag=SENSOR_FAULT`` (the wire value; the reason
        rides payload so the shared enum stays small). None otherwise."""
        return self.payload.get("fault") or None

    @property
    def time_source(self) -> str | None:
        """Which clock stamped this row (schema v2 §11.1, #278/#300):
        ``device_synced`` (NTP/RTC) or ``device_uptime`` (unsynced, no host
        stamp either) - never trust an unsynced clock as authoritative."""
        return self.payload.get("time_source")

    @property
    def device_timestamp_utc(self) -> datetime | None:
        """The device's own UTC stamp (schema v2 §11.1), if it has one.

        Omitted from the payload entirely when ``time_source=device_uptime``
        (the device honestly doesn't know UTC) - this is that honest ``None``,
        never a guessed value. Use ``timestamp_utc`` (host-stamped, §1) for
        join/forecast/gap-detection; this field is device-provenance only."""
        return _parse_utc(self.payload.get("device_timestamp_utc"))

    @property
    def host_monotonic_ms(self) -> int | None:
        """Elapsed ``time.monotonic()`` (ms) since the host logger started (#9).

        A relative axis that survives a UTC backward jump, a DST-duplicate hour,
        or an NTP step correction - the host-side counterpart to the device's own
        ``millis_ms``. ``None`` on a row from a logger version that predates this
        field (never a guessed value)."""
        return _int(self.payload.get("host_monotonic_ms"))

    @property
    def context_source(self) -> str | None:
        """Which interior-ambient source filled this row's ``temp_context_c`` /
        ``rh_context_pct`` (#562, ADR-0023 v2) - e.g. ``sht45_onrig``. Rides
        payload k=v (the #559 review decision - never a positional column, so
        the companion air-quality project's shared core stays byte-identical).
        ``None`` on any row
        whose interior context was never filled - honest, not a default."""
        return self.payload.get("context_source")

    @property
    def pressure_context_source(self) -> str | None:
        """The per-quantity tag for ``pressure_context_hpa`` (ADR-0023 §3's
        exception: pressure alone may fill from the exterior family, e.g.
        ``weather_openmeteo``). Separate from ``context_source`` because
        mixed-source rows are the common case - the SHT45 has no pressure."""
        return self.payload.get("pressure_context_source")

    @property
    def device_id_is_stable_id(self) -> bool:
        """Version-aware provenance for the ``device_id`` column (#618, ADR-0027).

        The column stays a string; only its *meaning* is version-gated.
        ``schema_version >= 3`` ⇒ ``device_id`` is the stable minted id (a 6-char
        Crockford base32 nonce, ADR-0027 §1b/§6). ``< 3`` (v1 monitor, v2
        experiment-capture) ⇒ it is a mutable friendly name - the legacy epoch
        the #602 map bridges. A row with no schema_version at all is treated as
        legacy (name), never guessed as stable."""
        return (self.schema_version or 0) >= STABLE_ID_SCHEMA_VERSION

    @property
    def device_name(self) -> str | None:
        """The friendly device label (#618, ADR-0027 §1b rider): rides payload
        ``name=`` on every v3 row - both legibility and the pre-mint **degrade
        identifier** (a row emitted before the UUID is minted has no valid
        ``device_id``, and ``name`` is the only identity it carries). ``None``
        on a pre-v3 row, where the friendly name is the ``device_id`` column
        itself."""
        return self.payload.get("name")

    @property
    def device_display_name(self) -> str:
        """The human-facing device name, version-agnostic: the payload ``name``
        when present (v3, or a pre-mint row), else the ``device_id`` column
        (pre-v3, where the id *is* the name). One accessor a consumer can use
        without knowing the row's epoch - the display half of the #587 fence's
        planned ``regdev.name`` swap."""
        return self.device_name or self.device_id


def dedupe_key(r: Reading) -> tuple[str, str, int | None, str, str]:
    """The schema v2 §11.2 row-idempotency key: the tuple that identifies
    *this exact reading* independent of how many times its bytes crossed the
    wire, so a store-and-forward replay can be dropped at ingest rather than
    duplicated. ``device_seq`` is ``None`` for a v1-only row (no dedupe
    signal available - the caller decides how to treat that, this function
    only reports what the row carries)."""
    return (r.device_id, r.session_id, r.device_seq, r.record_type, r.sensor_id)


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
    h.config_id = kv.get("config_id", h.config_id)  # #576/v4 — header-authoritative
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


def reading_from_row(row: dict[str, str], seg: SegmentHeader | None = None) -> Reading:
    """Build one ``Reading`` from a CANONICAL_COLUMNS-shaped row dict, independent
    of file parsing (#277) - the public seam a non-file transport (the WiFi
    ``DeviceAdapter``, ``source_adapter.py``) uses to produce a ``Reading``
    identical in shape to one read from a CSV file. ``seg`` supplies
    ``schema_version`` provenance; omit for a segment-less/synthetic row (an
    empty ``SegmentHeader`` -> ``schema_version=None``, honest, never guessed)."""
    return _reading_from_row(row, seg if seg is not None else SegmentHeader())


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


class _ParseState:
    """The line-by-line parse state threaded through a file (#859): the column
    layout in effect, the current segment, and any header lines buffered before
    their segment commits. Extracted so the whole-file parse and the parse cache's
    byte-offset tail-append share ONE per-line rule (no drift) — the cache seeds a
    fresh state from a file's last segment and resumes from the parsed byte offset."""

    __slots__ = ("cols", "current", "header_buf")

    def __init__(self) -> None:
        self.cols: list[str] = list(CANONICAL_COLUMNS)
        self.current: SegmentHeader | None = None
        self.header_buf: list[str] = []


def _consume_line(line: str, data: LogData, source: str, st: _ParseState) -> None:
    """Fold one newline-stripped ``line`` into ``data``, advancing ``st`` — the one
    per-line rule :func:`parse_file` and the cache tail-append (#859) both use."""
    if not line.strip():
        return
    if line.startswith("#"):
        st.header_buf.append(line)
        return
    fields = next(csv.reader([line]))
    if fields and fields[0] == "record_type":
        st.cols = fields
        st.current = _parse_header_lines(st.header_buf, st.cols, source)
        data.segments.append(st.current)
        st.header_buf = []
        return
    if st.current is None:
        st.current = _parse_header_lines(st.header_buf, st.cols, source)
        data.segments.append(st.current)
        st.header_buf = []
    data.readings.append(_reading_from_row(_row_dict(st.cols, fields), st.current))


def parse_file(path: str | Path, into: LogData | None = None) -> LogData:
    """Parse one log file (``.csv`` or ``.csv.gz``) into a ``LogData``."""
    data = into if into is not None else LogData()
    path = Path(path)
    data.sources.append(str(path))
    st = _ParseState()
    with _open_text(path) as fh:
        for raw_line in fh:
            _consume_line(raw_line.rstrip("\r\n"), data, str(path), st)
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
