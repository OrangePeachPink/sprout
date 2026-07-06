#!/usr/bin/env python3
"""Source-adapter seam (#277, PRD-0005/Epic #267) — the dashboard reads through an
adapter interface, not ``gather_inputs()``/``parse_files()`` directly, so a future
untethered/device-served transport can plug in without ``dashboard.py`` or
``serve.py`` needing to change their call sites again.

**Scope covered here** (see #277's own acceptance criteria):

* AC "tethered still works via the same interface (degenerate hub)" — done:
  :class:`TetheredAdapter` is a byte-identical wrap of today's serial-logger/host-CSV
  reading path.
* AC "adapter seam is documented for future transports" — done: this module
  *is* that documentation, in code.
* AC "dashboard shows untethered-device data with no serial logger" — done, desk-side:
  :class:`DeviceAdapter` reads a device's ``GET /telemetry`` (#276, PR #541, merged)
  over HTTP. Firmware caches and re-serves the *exact* serial wire bytes (row +
  ``*HH`` checksum, ADR-0018 §4 "one schema, every transport"), so this adapter
  reuses ``plants_logger.parse_device_line()`` and ``stamp_row()`` unchanged — a
  WiFi-sourced ``Reading`` is honest-identical in shape to a tethered one, just
  stamped with *this poll's* host-observed time instead of a live serial line's.
  **Real-hardware bench verification (flash + WiFi + a live browser hit) is a
  separate, physical step this slice cannot claim** — see #276/#277 threads.

:class:`FleetAdapter` (#486) composes N of the above into one ``LogData`` — the
"all plants across all devices, one live view" wiring — deduplicating exact
store-and-forward replays via the existing ``ingest_store.Store`` boundary (#521).

Deliberately dependency-light (only ``parse_v1``/``ingest_store`` +
``plants_logger``): ``TetheredAdapter`` takes its *discovery* callable
(``dashboard.gather_inputs``) as a constructor argument rather than importing
``dashboard`` directly, so there's no import cycle with the modules that will
construct it.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from ingest_store import Store
from parse_v1 import LogData, SegmentHeader, parse_files, reading_from_row

_LOGGER_DIR = Path(__file__).resolve().parent.parent / "logger"
if str(_LOGGER_DIR) not in sys.path:
    sys.path.insert(0, str(_LOGGER_DIR))
from plants_logger import parse_device_line, stamp_row  # noqa: E402

# This adapter's own identity for stamp_row()'s logger_version (#277) - never
# LOGGER_VERSION (plants_logger.py's own identity): a WiFi-polled row was not
# touched by the serial logger, and claiming otherwise would misattribute
# provenance. Bump the trailing version if this adapter's stamping logic changes.
DEVICE_ADAPTER_VERSION = "device_adapter_v1"

# #276's handleTelemetry() default timeout budget for one poll; generous for a
# LAN device but short enough that an unreachable board doesn't hang the dashboard.
_FETCH_TIMEOUT_S = 5.0


class SourceAdapter(Protocol):
    """A pluggable telemetry source.

    ``load(inputs)`` returns parsed data for explicit ``inputs`` (file/dir paths),
    or the adapter's own default discovery when ``inputs`` is ``None`` — so a
    caller never needs to know which transport it's reading from."""

    def load(self, inputs: list[str] | None = None) -> LogData: ...


class TetheredAdapter:
    """The tethered USB serial transport, read via the host logger's written CSV
    files.

    A behavior-preserving wrap — identical output to calling
    ``gather_inputs()``/``parse_files()`` directly today."""

    def __init__(self, discover=None) -> None:
        # `discover` is the caller's own file-discovery function (dashboard.py's
        # gather_inputs); None means "no auto-discovery" — the caller must always
        # pass explicit inputs, which is a valid, testable configuration on its own.
        self._discover = discover

    def load(self, inputs: list[str] | None = None) -> LogData:
        if inputs is not None:
            resolved = inputs
        elif self._discover is not None:
            resolved = self._discover()
        else:
            resolved = []
        return parse_files(resolved)


def _http_get(url: str, timeout: float = _FETCH_TIMEOUT_S) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


class DeviceAdapter:
    """The WiFi-served transport (#276/#277): a device's own ``GET /telemetry``,
    the same wire bytes as serial. ``base_url`` is the device's root, e.g.
    ``http://192.168.1.42`` (no trailing ``/telemetry`` — that's added here).

    ``fetch``/``clock`` are injectable (matching this codebase's existing pattern
    — ``RotatingCsv(monotonic=...)``, ``StallWatchdog(clock=...)``) so this is
    fully unit-testable without a real network call or a live device.

    Honest degrade: an unreachable device, a timeout, or a response with zero
    parseable rows all return an **empty** ``LogData`` — never raise. This is the
    same "no data yet" shape ``serve.py``'s ``NoDataYet`` already renders (#543),
    so a device that's off or still booting shows the same honest empty state a
    fresh checkout does, not a dashboard crash. A row that fails its CRC (garbled
    over the air) is silently dropped, same as the serial logger's own crc-fail
    path — corrupt data is not "no data", but it's also not a value to trust.

    ``pressure_source`` (#567, ADR-0023 §3): a callable -> ``(hpa, tag)`` or
    ``None`` — the same seam ``ContextFiller`` takes on the serial spine. When
    it yields, each polled **soil** row fills ``pressure_context_hpa`` + its
    per-quantity ``pressure_context_source`` payload tag. This path can only
    ever touch the two pressure keys — the untethered spine has no interior
    source (``/telemetry`` serves soil rows only), and weather must never fill
    interior temp/RH, so no interior key is even reachable from here."""

    def __init__(
        self,
        base_url: str,
        *,
        fetch=None,
        clock=None,
        pressure_source=None,
        candidates=None,
        on_resolved=None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        # #676: ordered addresses to try — the mDNS hostname first (stable across
        # DHCP), the configured IP as a fallback. Defaults to the single base_url
        # so existing callers/tests are unchanged. `on_resolved(working_url)` fires
        # when a board answers, for registry self-heal.
        self._candidates = [c.rstrip("/") for c in (candidates or [base_url]) if c]
        self._on_resolved = on_resolved
        self._fetch = fetch if fetch is not None else _http_get
        self._clock = clock if clock is not None else self._utc_now
        self._pressure_source = pressure_source
        self._next_sample_id = 0

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def load(self, inputs: list[str] | None = None) -> LogData:
        # `inputs` isn't meaningful for a single device's own endpoint - this
        # adapter always reads its own discovered address, matching the seam's
        # contract (a caller never needs to know which transport it's reading
        # from, or pass transport-specific args through a generic call site).
        # #676: try each candidate in order (mDNS hostname first, IP fallback) and
        # use the first that ANSWERS - so a board that rebooted to a new DHCP IP is
        # still reached by name, no registry hand-edit.
        text = None
        working = None
        for url in self._candidates:
            try:
                text = self._fetch(f"{url}/telemetry")
                working = url
                break
            except (urllib.error.URLError, OSError, TimeoutError):
                continue  # this address is unreachable - try the next candidate
        if text is None:
            return LogData()  # no candidate reachable - honest empty, not a crash

        now = self._clock()  # one poll, one shared "observed at" moment
        # #567: one pressure read per poll (not per row) - every soil row in
        # this poll shares the same observed-at moment, so one value is honest.
        pressure = self._pressure_source() if self._pressure_source else None
        seg = SegmentHeader(source=working)
        readings = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            dev = parse_device_line(line)
            if dev is None or dev.get("_crc_ok") is False:
                continue  # unparseable or corrupt - never a guessed reading
            context = None
            if pressure is not None and dev["record_type"].startswith("plants.soil"):
                hpa, tag = pressure
                context = {
                    "pressure_context_hpa": str(hpa),
                    "pressure_context_source": tag,
                }
            self._next_sample_id += 1
            row = stamp_row(
                dev, self._next_sample_id, now, DEVICE_ADAPTER_VERSION, context=context
            )
            # reading_from_row()/_int() expects a string-typed row (the CSV-row
            # contract) - stamp_row()'s sample_id is a plain int (RotatingCsv.write()
            # relies on that; csv.writer stringifies it downstream, on that path).
            readings.append(reading_from_row({k: str(v) for k, v in row.items()}, seg))

        if not readings:
            return LogData()
        seg.device_id = readings[0].device_id
        # #676: the board answered at `working` - let the caller self-heal the
        # registry if that's a fresh address (best-effort; never affects the poll).
        if self._on_resolved is not None:
            self._on_resolved(working)
        return LogData(readings=readings, segments=[seg], sources=[working])


class FleetAdapter:
    """N sources, one ``LogData`` (#486 - the "all plants, one live view" wiring).

    Composes any mix of adapters behind the same ``SourceAdapter`` contract -
    today that's one ``TetheredAdapter`` (the host CSV history) plus one
    ``DeviceAdapter`` per fleet-registry device with a ``base_url``. Loads each
    in turn and concatenates; a source that fails or returns nothing simply
    contributes nothing (each adapter already degrades to empty on its own).

    Dedupe rides the existing ingest boundary (``ingest_store.Store``, #521):
    the same physical reading arriving via two transports (a device both
    tethered *and* WiFi-polled) is an exact store-and-forward replay - dropped
    on its schema-v2 ``device_seq`` key. A v1-only row has no dedupe signal and
    is always kept (Store's own honest-degrade rule; a false-positive drop
    would silently lose real data).

    ``inputs`` passes through to the *first* adapter only (by construction the
    tethered/file one - explicit CLI paths mean "read these files", which no
    device endpoint can honor); the rest always use their own discovery."""

    def __init__(self, adapters: list) -> None:
        self._adapters = list(adapters)

    def load(self, inputs: list[str] | None = None) -> LogData:
        store = Store()
        readings, segments, sources = [], [], []
        for i, adapter in enumerate(self._adapters):
            data = adapter.load(inputs if i == 0 else None)
            readings.extend(r for r in data.readings if store.ingest(r))
            segments.extend(data.segments)
            sources.extend(data.sources)
        return LogData(readings=readings, segments=segments, sources=sources)
