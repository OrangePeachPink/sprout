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
import csv
import os
import sys
import time
from datetime import datetime, timezone

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial not installed.  Run:  pip install pyserial")

LOGGER_VERSION = "plants_logger_0_1"

# Canonical file schema (docs/TELEMETRY_SCHEMA.md S2). The host fills timestamp_*,
# sample_id, logger_version; context/event/notes stay empty until those layers land.
CANONICAL_COLS = [
    "record_type", "timestamp_utc", "timestamp_local", "sample_id", "session_id",
    "device_id", "firmware_version", "logger_version", "millis_ms", "sensor_model",
    "sensor_id", "sensor_position", "channel", "raw_value", "value", "unit",
    "quality_flag", "temp_context_c", "rh_context_pct", "pressure_context_hpa",
    "event_id", "payload", "notes",
]
# Device serial-line column order (the firmware's "# device_cols:" legend).
DEVICE_COLS = [
    "record_type", "session_id", "device_id", "fw", "millis_ms", "sensor_model",
    "sensor_id", "sensor_position", "channel", "raw_value", "value", "unit",
    "quality_flag", "payload",
]
KNOWN_RECORD_PREFIXES = ("plants.", "aq.")


def iso_utc(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


def iso_local(dt):
    loc = dt.astimezone()
    return loc.strftime("%Y-%m-%d %H:%M:%S.") + "%03d" % (loc.microsecond // 1000)


def payload_get(payload, key):
    for kv in payload.split(";"):
        if kv.startswith(key + "="):
            return kv[len(key) + 1:]
    return ""


def autodetect_port():
    ports = list(list_ports.comports())
    for p in ports:  # prefer a known USB-serial bridge
        blob = " ".join(x for x in (p.description, p.manufacturer, p.hwid) if x).lower()
        if any(k in blob for k in ("cp210", "ch340", "ftdi", "silicon labs", "usb serial", "wch")):
            return p.device
    return ports[0].device if ports else None


def parse_device_line(text):
    """Dict of DEVICE_COLS, or None if not a recoverable record. Tolerates
    prefix corruption by re-syncing on the first known record_type token."""
    idx = -1
    for pre in KNOWN_RECORD_PREFIXES:
        j = text.find(pre)
        if j != -1 and (idx == -1 or j < idx):
            idx = j
    if idx == -1:
        return None
    fields = text[idx:].strip().split(",")
    if len(fields) != len(DEVICE_COLS):
        return None
    return dict(zip(DEVICE_COLS, fields))


class RotatingCsv:
    """One CSV file per UTC day, each re-emitting the device header block so every
    segment is independently self-describing."""

    def __init__(self, logdir):
        self.logdir = logdir
        self.device_id = "unknown"
        self.day = None
        self.fh = None
        self.writer = None
        self.header_lines = []
        os.makedirs(logdir, exist_ok=True)

    def set_header(self, lines):
        self.header_lines = [ln.rstrip("\n") for ln in lines]

    def _roll(self, now):
        day = now.strftime("%Y%m%d")
        if day == self.day and self.fh:
            return None
        if self.fh:
            self.fh.close()
        self.day = day
        # device_id already starts with "plants_esp32_", so no extra prefix.
        fname = "%s_%s_%s.csv" % (self.device_id, day, now.strftime("%H%M%S"))
        path = os.path.join(self.logdir, fname)
        self.fh = open(path, "a", newline="", encoding="utf-8")
        self.writer = csv.writer(self.fh)
        self.fh.write("# plants log segment  logger=%s  schema_version=1\n" % LOGGER_VERSION)
        for ln in self.header_lines:
            self.fh.write(ln + "\n")
        self.writer.writerow(CANONICAL_COLS)
        self.fh.flush()
        return path

    def write(self, dev, sample_id, now):
        if self.device_id == "unknown" and dev["device_id"]:
            self.device_id = dev["device_id"]
        new_path = self._roll(now)
        row = {c: "" for c in CANONICAL_COLS}
        row.update({
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
        })
        self.writer.writerow([row[c] for c in CANONICAL_COLS])
        self.fh.flush()
        return row, new_path


def console_line(row):
    t = row["timestamp_local"][11:19]  # HH:MM:SS
    return "%s  %-3s  raw=%-4s  %3s%%  %-9s  %s" % (
        t, row["sensor_id"], row["raw_value"], row["value"],
        row["quality_flag"], payload_get(row["payload"], "level"))


def run(port, baud, logdir):
    csvlog = RotatingCsv(logdir)
    sample_id = 0
    pending_hdr = []
    dropped = 0
    while True:
        try:
            ser = serial.Serial(port, baud, timeout=2)
        except Exception as e:
            print("[logger] cannot open %s (%s); retrying in 3s" % (port, e))
            time.sleep(3)
            continue
        print("[logger] connected %s @ %d  ->  %s" % (port, baud, logdir))
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
                    dropped += 1
                    print("[drop %d] %s" % (dropped, text[:80]))
                    continue
                if pending_hdr:
                    csvlog.set_header(pending_hdr)
                    pending_hdr = []
                sample_id += 1
                now = datetime.now(timezone.utc)
                row, new_path = csvlog.write(dev, sample_id, now)
                if new_path:
                    print("[logger] -> %s" % new_path)
                print(console_line(row))
        except serial.SerialException as e:
            print("[logger] port dropped (%s); reconnecting..." % e)
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n[logger] stopped (%d rows written, %d dropped)" % (sample_id, dropped))
            try:
                ser.close()
            except Exception:
                pass
            return


def main():
    ap = argparse.ArgumentParser(description="Host-side serial logger for the plants controller.")
    ap.add_argument("--port", help="serial port (COM5, /dev/ttyUSB0). Auto-detect if omitted.")
    ap.add_argument("--baud", type=int, default=19200, help="baud (default 19200, matches firmware)")
    here = os.path.dirname(os.path.abspath(__file__))
    default_logdir = os.path.normpath(os.path.join(here, "..", "..", "logs"))
    ap.add_argument("--logdir", default=default_logdir, help="output dir (default <repo>/logs)")
    args = ap.parse_args()
    port = args.port or autodetect_port()
    if not port:
        sys.exit("No serial port found. Specify --port.")
    run(port, args.baud, args.logdir)


if __name__ == "__main__":
    main()
