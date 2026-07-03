#!/usr/bin/env python3
"""
plants_logger.py - host-side serial capture for the plants controller (fw v0.5.0+).

Owns the serial port (replacing `pio device monitor --filter log2file`), and per
docs/TELEMETRY_SCHEMA.md:
  * stamps each device row with host UTC + local time and a monotonic sample_id,
    plus the host's own elapsed `time.monotonic()` (host_monotonic_ms, #9) - a
    relative axis immune to a UTC backward jump/DST duplicate hour or an NTP step,
  * reorders to the canonical CSV schema and writes a rotating, self-describing
    CSV file (a new file each UTC day) under <repo>/logs/,
  * renders a terse pretty console for live eyeballing (the B2 file/console split),
  * auto-reconnects if the port drops OR the stream silently stalls (#417), marking
    an honest `# reconnect` seam, and decodes losslessly (latin-1) so a stray byte
    is one recoverable char, never a dropped row.

Usage:
  python plants_logger.py --port COM5
  python plants_logger.py --port /dev/ttyUSB0 --baud 19200 --logdir ../../logs
  python plants_logger.py                       # auto-detect the USB-serial port

Requires: pyserial  (pip install pyserial)
"""

import argparse
import contextlib
import csv
import os
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed.  Run:  pip install pyserial")

# Optional B8 archive step (tools/archive/archive_logs.py). Best-effort: if it is
# missing or git fails, logging continues uninterrupted.
_ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "archive")
sys.path.insert(0, _ARCHIVE_DIR)
try:
    import archive_logs
except Exception:
    archive_logs = None

# Advisory serial-ownership lock (ADR-0011 #64, tools/capture/serial_lock.py).
# Best-effort: lets the experiment control plane learn the monitor holds the port
# *without opening it* (opening pulses DTR and resets the ESP32). The OS exclusive
# open is the real mutex; this dotfile is the courtesy that avoids a reset-to-ask
# and surfaces a stale lock from a crashed owner. Both writers use the same schema.
_CAPTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "capture")
sys.path.insert(0, _CAPTURE_DIR)
try:
    import serial_lock
except Exception:
    serial_lock = None

LOGGER_VERSION = "plants_logger_0_4"

# Canonical file schema (docs/TELEMETRY_SCHEMA.md S2). The host fills timestamp_*,
# sample_id, logger_version; context/event/notes stay empty until those layers land.
CANONICAL_COLS = [
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
# Device serial-line column order (the firmware's "# device_cols:" legend).
DEVICE_COLS = [
    "record_type",
    "session_id",
    "device_id",
    "fw",
    "millis_ms",
    "sensor_model",
    "sensor_id",
    "sensor_position",
    "channel",
    "raw_value",
    "value",
    "unit",
    "quality_flag",
    "payload",
]
KNOWN_RECORD_PREFIXES = ("plants.", "aq.")


def iso_utc(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def iso_local(dt):
    loc = dt.astimezone()
    return loc.strftime("%Y-%m-%d %H:%M:%S.") + f"{loc.microsecond // 1000:03d}"


def tz_offset(dt):
    off = dt.astimezone().utcoffset() or timedelta(0)
    total = int(off.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


def payload_get(payload, key):
    for kv in payload.split(";"):
        if kv.startswith(key + "="):
            return kv[len(key) + 1 :]
    return ""


def is_line_noise(text):
    """True for an idle-line-noise line - mostly non-ASCII bytes (e.g. runs of
    0xFF from false UART frames during the 30 s idle gap), vs a genuinely
    unparseable but printable line. The device only ever emits ASCII."""
    if not text:
        return False
    return sum(ord(c) < 127 for c in text) / len(text) < 0.5


# --- stall watchdog (#417) --------------------------------------------------
# A *silent* stall — the port stays open (no SerialException) but the device stops
# streaming — makes ser.readline() return b"" forever; the plain loop spins on it
# with no data and no reconnect (the 9-minute hole, 2026-06-30). The existing
# reconnect only fires on a SerialException. The watchdog detects "no data row for
# longer than expected", forces a reconnect, and marks an honest seam so the gap is
# queryable, never silently stitched (docs/TELEMETRY_SCHEMA.md).

STALL_MULT = 2.0  # expect >= 1 data row per STALL_MULT x cadence ...
STALL_FLOOR_S = (
    90.0  # ... but never trip below this (safe for 30 s cadence + idle noise)
)
RECONNECT_SLEEP_S = 2.0


class _SerialStall(Exception):
    """Raised in the read loop when the watchdog trips; reuses the reconnect path."""


def cadence_ms_from_header(header_lines):
    """Pull ``cadence_ms`` from the device ``#`` header block; None if absent."""
    for ln in header_lines:
        for tok in ln.replace(",", " ").split():
            if tok.startswith("cadence_ms="):
                with contextlib.suppress(ValueError):
                    return int(tok[len("cadence_ms=") :])
    return None


def stall_timeout_s(cadence_ms, *, mult=STALL_MULT, floor_s=STALL_FLOOR_S):
    """Seconds of no data before forcing a reconnect. Keys off cadence when known,
    with a floor so a slow (30 s) cadence + idle line-noise never false-trips."""
    if cadence_ms and cadence_ms > 0:
        return max(floor_s, mult * (cadence_ms / 1000.0))
    return floor_s


class StallWatchdog:
    """Tracks time since the last data row; ``stalled()`` once it exceeds the timeout.
    Clock-injected so it unit-tests without waiting on a wall clock or hardware."""

    def __init__(self, timeout_s, *, clock=time.monotonic):
        self._timeout_s = timeout_s
        self._clock = clock
        self._last = clock()

    def mark_data(self):
        self._last = self._clock()

    def retune(self, timeout_s):
        self._timeout_s = timeout_s

    def gap_s(self):
        return self._clock() - self._last

    def stalled(self):
        return self.gap_s() >= self._timeout_s


def reconnect_seam_line(gap_s, now, reason):
    """An honest, queryable ``#`` seam written into the CSV on reconnect, so a logging
    hole is never silently stitched."""
    return (
        f"# reconnect  gap_s={gap_s:.1f}  at_utc={iso_utc(now)}  "
        f"reason={reason}  logger={LOGGER_VERSION}"
    )


def autodetect_port():
    ports = list(list_ports.comports())
    for p in ports:  # prefer a known USB-serial bridge
        blob = " ".join(x for x in (p.description, p.manufacturer, p.hwid) if x).lower()
        if any(
            k in blob
            for k in ("cp210", "ch340", "ftdi", "silicon labs", "usb serial", "wch")
        ):
            return p.device
    return ports[0].device if ports else None


def parse_device_line(text):
    """Dict of DEVICE_COLS (+ _crc_ok), or None if not a recoverable record.
    Re-syncs on the first known record_type token, then validates an optional
    NMEA-style '*HH' XOR checksum suffix (None if the line carries no checksum)."""
    idx = -1
    for pre in KNOWN_RECORD_PREFIXES:
        j = text.find(pre)
        if j != -1 and (idx == -1 or j < idx):
            idx = j
    if idx == -1:
        return None
    body = text[idx:].strip()
    crc_ok = None
    star = body.rfind("*")
    if star != -1 and len(body) - star == 3:  # trailing "*HH"
        want = body[star + 1 :]
        body = body[:star]
        calc = 0
        for ch in body:
            calc ^= ord(ch) & 0xFF
        crc_ok = f"{calc:02X}" == want.upper()
    fields = body.split(",")
    if len(fields) != len(DEVICE_COLS):
        return None
    d = dict(zip(DEVICE_COLS, fields))
    d["_crc_ok"] = crc_ok
    return d


def _append_payload(payload, key, value):
    """Append one ``;k=v`` pair to a device payload string (host-side extension,
    same additive convention as #278's device_seq/time_source). Never touches the
    device-emitted keys - only adds to the end."""
    pair = f"{key}={value}"
    return f"{payload};{pair}" if payload else pair


def stamp_row(dev, sample_id, now, logger_version, *, host_monotonic_ms=None):
    """Build one CANONICAL_COLS row dict from a parsed device line, stamped with
    the host's observed-at time + a host sample counter (schema v1 S2: these are
    host-filled, not device-native). Pulled out of RotatingCsv.write() (#277) so a
    non-serial transport (the WiFi DeviceAdapter, source_adapter.py) can produce
    byte-identical row semantics without going through a CSV file at all.

    ``logger_version`` is the caller's own identity (e.g. ``LOGGER_VERSION`` for
    the serial logger, a distinct string for an HTTP-polling adapter) - never
    hardcoded here, so a WiFi-sourced row honestly names what actually stamped it
    rather than falsely claiming the serial logger touched it.

    ``host_monotonic_ms`` is optional (#9): the serial logger has one persistent
    process with a meaningful single start reference; a per-poll adapter usually
    doesn't, so it stays the honest default None rather than a fabricated value."""
    payload = dev["payload"]
    if host_monotonic_ms is not None:
        payload = _append_payload(payload, "host_monotonic_ms", host_monotonic_ms)
    row = dict.fromkeys(CANONICAL_COLS, "")
    row.update(
        {
            "record_type": dev["record_type"],
            "session_id": dev["session_id"],
            "device_id": dev["device_id"],
            "firmware_version": dev["fw"],
            "logger_version": logger_version,
            "millis_ms": dev["millis_ms"],
            "sensor_model": dev["sensor_model"],
            "sensor_id": dev["sensor_id"],
            "sensor_position": dev["sensor_position"],
            "channel": dev["channel"],
            "raw_value": dev["raw_value"],
            "value": dev["value"],
            "unit": dev["unit"],
            "quality_flag": dev["quality_flag"],
            "payload": payload,
            "timestamp_utc": iso_utc(now),
            "timestamp_local": iso_local(now),
            "sample_id": sample_id,
        }
    )
    return row


class RotatingCsv:
    """One CSV file per UTC day, each re-emitting the device header block so every
    segment is independently self-describing.

    Also stamps every row with the host's own **monotonic** elapsed time (#9):
    UTC alone can jump backward or duplicate an hour at a DST transition, or step
    on an NTP correction - a relative axis anchored to ``time.monotonic()`` at
    logger start survives both, for a multi-week run's own internal ordering."""

    def __init__(self, logdir, maxbytes=0, *, monotonic=time.monotonic):
        self.logdir = logdir
        self.maxbytes = maxbytes
        self.device_id = "unknown"
        self.day = None
        self.fh = None
        self.writer = None
        self.header_lines = []
        self.current_path = None
        self._monotonic = monotonic
        self._t0 = monotonic()  # this logger process's own start reference
        os.makedirs(logdir, exist_ok=True)

    def set_header(self, lines):
        self.header_lines = [ln.rstrip("\n") for ln in lines]

    def _roll(self, now):
        day = now.strftime("%Y%m%d")
        need = (self.fh is None) or (day != self.day)
        if not need and self.maxbytes and self.fh.tell() >= self.maxbytes:
            need = True  # size cap: limit any corruption/disk-full to one segment
        if not need:
            return None
        if self.fh:
            self.fh.close()
        self.day = day
        # device_id already starts with "plants_esp32_", so no extra prefix.
        fname = f"{self.device_id}_{day}_{now.strftime('%H%M%S')}.csv"
        path = os.path.join(self.logdir, fname)
        # Long-lived handle - the rotating logger closes it on roll, so a `with`
        # block doesn't apply (SIM115 is a false positive here).
        self.fh = open(path, "a", newline="", encoding="utf-8")  # noqa: SIM115
        self.writer = csv.writer(self.fh)
        self.fh.write(
            f"# log_start_utc={iso_utc(now)}  tz_offset={tz_offset(now)}  "
            f"logger={LOGGER_VERSION}  schema_version=1\n"
        )
        for ln in self.header_lines:
            self.fh.write(ln + "\n")
        self.writer.writerow(CANONICAL_COLS)
        self.fh.flush()
        self.current_path = path
        return path

    def write(self, dev, sample_id, now):
        if self.device_id == "unknown" and dev["device_id"]:
            self.device_id = dev["device_id"]
        new_path = self._roll(now)
        host_monotonic_ms = round((self._monotonic() - self._t0) * 1000)
        row = stamp_row(
            dev, sample_id, now, LOGGER_VERSION, host_monotonic_ms=host_monotonic_ms
        )
        self.writer.writerow([row[c] for c in CANONICAL_COLS])
        self.fh.flush()
        return row, new_path

    def write_comment(self, line):
        """Write a raw ``#`` comment into the current segment (honest seam, #417)."""
        if self.fh is None:
            return None
        self.fh.write(line.rstrip("\n") + "\n")
        self.fh.flush()
        return self.current_path


def console_line(row):
    t = row["timestamp_local"][11:19]  # HH:MM:SS
    # raw + band are the truth; no moisture-% (it was an uncalibrated remap, #38).
    return (
        f"{t}  {row['sensor_id']:<3}  raw={row['raw_value']:<4}  "
        f"{row['quality_flag']:<9}  "
        f"{payload_get(row['payload'], 'level')}"
    )


def _archive_step(logdir, exclude=None, include_all=False):
    """Best-effort B8 archive of closed segments; never disrupts logging."""
    if archive_logs is None:
        return
    try:
        archive_logs.archive(logs_dir=logdir, exclude=exclude, include_all=include_all)
    except Exception as e:
        print(f"[logger] archive step failed (non-fatal): {e}")


def _lock_claim(port):
    """Best-effort advisory claim that the monitor owns ``port`` (ADR-0011 #64).
    Written on the canonical lock path (serial_lock's default <repo>/logs), not
    --logdir, so the control plane always looks in one agreed place. Never blocks
    logging: the OS exclusive open already happened and is the real mutex."""
    if serial_lock is None:
        return
    try:
        serial_lock.write_lock(port, "monitor")
    except Exception as e:
        print(f"[logger] serial-lock claim failed (non-fatal): {e}")


def _lock_release():
    """Best-effort advisory release; safe when no lock exists. Only the clean-stop
    path calls this — a crash leaves a stale lock that current_owner() ignores via
    its pid-alive check, and a transient reconnect intentionally keeps the lock so
    the control plane still sees the (live) monitor as the owner."""
    if serial_lock is None:
        return
    try:
        serial_lock.clear_lock()
    except Exception as e:
        print(f"[logger] serial-lock release failed (non-fatal): {e}")


def run(
    port,
    baud,
    logdir,
    maxbytes,
    *,
    open_fn=None,
    clock=time.monotonic,
    sleep=time.sleep,
):
    csvlog = RotatingCsv(logdir, maxbytes)
    sample_id = 0
    pending_hdr = []
    dropped = 0
    crc_fail = 0
    noise = 0
    if open_fn is None:  # real path; tests inject a fake serial factory

        def open_fn():
            return serial.Serial(port, baud, timeout=2)

    # Floor timeout until the header reveals the real cadence, then retune (#417).
    watchdog = StallWatchdog(stall_timeout_s(None), clock=clock)
    _archive_step(logdir, include_all=False)  # back up closed segments from prior runs
    while True:
        try:
            ser = open_fn()
        except Exception as e:
            print(f"[logger] cannot open {port} ({e}); retrying in 3s")
            sleep(3)
            continue
        print(f"[logger] connected {port} @ {baud}  ->  {logdir}")
        _lock_claim(port)  # advisory: the monitor now owns the port (ADR-0011 #64)
        watchdog.mark_data()  # a fresh connection resets the stall clock
        try:
            while True:
                raw = ser.readline()
                text = raw.decode("latin-1").rstrip("\r\n") if raw else ""
                if not text:
                    # No line this read. A prolonged run of these with no data row is
                    # a silent stall (port open, device quiet) — force a reconnect.
                    if watchdog.stalled():
                        raise _SerialStall(watchdog.gap_s())
                    continue  # normal idle timeout between bursts
                if text.lstrip().startswith("#"):
                    pending_hdr.append(text)
                    print(text)
                    continue
                dev = parse_device_line(text)
                if dev is None:
                    if is_line_noise(text):
                        # Idle-line noise (0xFF false frames during the 30 s gap):
                        # swallow it; surface a count every 10 so a rising trend
                        # stays visible without flooding the console.
                        noise += 1
                        if noise % 10 == 0:
                            print(f"[noise] {noise} idle-line lines suppressed")
                        continue
                    dropped += 1
                    print(f"[drop {dropped}] {text[:80]}")
                    continue
                if dev.get("_crc_ok") is False:
                    crc_fail += 1
                    print(f"[crc {crc_fail}] {text[:80]}")
                    continue
                if pending_hdr:
                    csvlog.set_header(pending_hdr)
                    cad = cadence_ms_from_header(pending_hdr)
                    if cad:
                        watchdog.retune(stall_timeout_s(cad))
                    pending_hdr = []
                sample_id += 1
                now = datetime.now(timezone.utc)
                row, new_path = csvlog.write(dev, sample_id, now)
                watchdog.mark_data()  # a real data row proves the stream is alive
                if new_path:
                    print(f"[logger] -> {new_path}")
                    # new segment opened -> the previous one is closed; back it up
                    _archive_step(logdir, exclude=new_path)
                print(console_line(row))
        except _SerialStall as stall:
            gap = stall.args[0]
            print(
                f"[logger] serial stall {gap:.0f}s (port open, no data) -> reconnecting"
            )
            csvlog.write_comment(
                reconnect_seam_line(gap, datetime.now(timezone.utc), "stall-watchdog")
            )
            with contextlib.suppress(Exception):
                ser.close()
            sleep(RECONNECT_SLEEP_S)
        except serial.SerialException as e:
            print(f"[logger] port dropped ({e}); reconnecting...")
            csvlog.write_comment(
                reconnect_seam_line(
                    watchdog.gap_s(), datetime.now(timezone.utc), "port-dropped"
                )
            )
            with contextlib.suppress(Exception):
                ser.close()
            sleep(RECONNECT_SLEEP_S)
        except KeyboardInterrupt:
            print(
                f"\n[logger] stopped ({sample_id} rows, {dropped} dropped, "
                f"{crc_fail} crc-fail, {noise} idle-noise)"
            )
            with contextlib.suppress(Exception):
                ser.close()
            _lock_release()  # advisory: port released on clean stop (ADR-0011 #64)
            _archive_step(logdir, include_all=True)  # the active segment is now closed
            print("[logger] stopped cleanly - data saved. Safe to close this window.")
            return


def main():
    ap = argparse.ArgumentParser(
        description="Host-side serial logger for the plants controller."
    )
    ap.add_argument(
        "--port", help="serial port (COM5, /dev/ttyUSB0). Auto-detect if omitted."
    )
    ap.add_argument(
        "--baud", type=int, default=19200, help="baud (default 19200, matches firmware)"
    )
    here = os.path.dirname(os.path.abspath(__file__))
    default_logdir = os.path.normpath(os.path.join(here, "..", "..", "logs"))
    ap.add_argument(
        "--logdir", default=default_logdir, help="output dir (default <repo>/logs)"
    )
    ap.add_argument(
        "--maxbytes",
        type=int,
        default=25 * 1024 * 1024,
        help="rotate when a segment exceeds this many bytes "
        "(default 25MB; 0=daily only)",
    )
    args = ap.parse_args()
    port = args.port or autodetect_port()
    if not port:
        sys.exit("No serial port found. Specify --port.")
    run(port, args.baud, args.logdir, args.maxbytes)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Ctrl-C is the normal way to stop the logger. If it lands mid-archive (after
        # the loop's clean-stop handler has run), treat it as the intended stop, not a
        # crash: fall through to a 0 exit so `just` / launchers don't surface a scary
        # "recipe failed" on the expected way to stop (#148).
        print("\n[logger] stopped - data saved. Safe to close this window.")
