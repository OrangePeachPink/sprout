#!/usr/bin/env python3
"""
plants_logger.py - host-side serial capture for the plants controller (fw v0.5.0+).

Owns the serial port (replacing `pio device monitor --filter log2file`), and per
docs/TELEMETRY_SCHEMA.md:
  * stamps each device row with host UTC + local time and a monotonic sample_id,
  * reorders to the canonical CSV schema and writes a rotating, self-describing
    CSV file (a new file each UTC day) under <repo>/logs/,
  * renders a terse pretty console for live eyeballing (the B2 file/console split),
  * auto-reconnects if the port drops, and decodes losslessly (latin-1) so a stray
    byte is one recoverable char, never a dropped row.

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


class RotatingCsv:
    """One CSV file per UTC day, each re-emitting the device header block so every
    segment is independently self-describing."""

    def __init__(self, logdir, maxbytes=0):
        self.logdir = logdir
        self.maxbytes = maxbytes
        self.device_id = "unknown"
        self.day = None
        self.fh = None
        self.writer = None
        self.header_lines = []
        self.current_path = None
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
        row = dict.fromkeys(CANONICAL_COLS, "")
        row.update(
            {
                "record_type": dev["record_type"],
                "session_id": dev["session_id"],
                "device_id": dev["device_id"],
                "firmware_version": dev["fw"],
                "logger_version": LOGGER_VERSION,
                "millis_ms": dev["millis_ms"],
                "sensor_model": dev["sensor_model"],
                "sensor_id": dev["sensor_id"],
                "sensor_position": dev["sensor_position"],
                "channel": dev["channel"],
                "raw_value": dev["raw_value"],
                "value": dev["value"],
                "unit": dev["unit"],
                "quality_flag": dev["quality_flag"],
                "payload": dev["payload"],
                "timestamp_utc": iso_utc(now),
                "timestamp_local": iso_local(now),
                "sample_id": sample_id,
            }
        )
        self.writer.writerow([row[c] for c in CANONICAL_COLS])
        self.fh.flush()
        return row, new_path


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


def run(port, baud, logdir, maxbytes):
    csvlog = RotatingCsv(logdir, maxbytes)
    sample_id = 0
    pending_hdr = []
    dropped = 0
    crc_fail = 0
    noise = 0
    _archive_step(logdir, include_all=False)  # back up closed segments from prior runs
    while True:
        try:
            ser = serial.Serial(port, baud, timeout=2)
        except Exception as e:
            print(f"[logger] cannot open {port} ({e}); retrying in 3s")
            time.sleep(3)
            continue
        print(f"[logger] connected {port} @ {baud}  ->  {logdir}")
        _lock_claim(port)  # advisory: the monitor now owns the port (ADR-0011 #64)
        try:
            while True:
                raw = ser.readline()
                if not raw:
                    continue  # idle timeout between 30 s bursts
                text = raw.decode("latin-1").rstrip("\r\n")
                if not text:
                    continue
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
                    pending_hdr = []
                sample_id += 1
                now = datetime.now(timezone.utc)
                row, new_path = csvlog.write(dev, sample_id, now)
                if new_path:
                    print(f"[logger] -> {new_path}")
                    # new segment opened -> the previous one is closed; back it up
                    _archive_step(logdir, exclude=new_path)
                print(console_line(row))
        except serial.SerialException as e:
            print(f"[logger] port dropped ({e}); reconnecting...")
            with contextlib.suppress(Exception):
                ser.close()
            time.sleep(2)
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
