#!/usr/bin/env python3
"""Experiment-mode capture process (Epic 1, issue #65) — the isolated launcher.

Sprout's *Monitor mode* is the always-on baseline logger (``tools/logger``). This is
**Experiment mode**: a short, operator-driven, bounded capture against an arbitrary
subject, written to an **isolated** ``experiments/`` tree that the monitor dashboard
can never auto-discover (the never-stitch guarantee, PRD-0001 R6/R7).

What this module owns (Data lane, device-independent and testable today):

* the bounded capture loop with a **fail-safe auto-stop** — the process stops itself
  at the set duration even if a parent (``serve.py`` / the browser) dies (R3);
* the **schema_version=2** writer — the canonical columns plus the additive,
  filterable shared-core columns ``mode / subject / experiment_id / sample_rate_s /
  label`` (ADR-0012); ``record_type`` stays ``plants.soil`` and ``mode`` discriminates;
* an isolated ``experiments/<experiment_id>/`` folder + a ``manifest.json`` carrying
  the per-cadence transport-error counts (dropped / crc-fail / idle-noise) — the
  error-rate-vs-cadence signal the slow tiers exist to measure (R9);
* a pluggable :class:`Reader` so the **real serial source plugs in behind the seam**
  once Firmware lands the ``set_cadence`` command (#63) and the port-handoff (#64).

The :class:`SerialReader` is a stub until #63/#64; :class:`SyntheticReader` lets the
whole storage / isolation / schema path be built and tested on the host with no
device, and never touches the running baseline.

Usage::

    # synthetic smoke run (no device) — writes an isolated experiment file
    python tools/capture/experiment_capture.py --source synthetic \\
        --subject common-cup --rate-s 0.5 --duration-s 20 \\
        --label s1=control --label s2=treatment

Reuses the monitor logger's validated device-line parsing (incl. the XOR checksum)
so a real device line is parsed identically in both modes; that import pulls in
``pyserial``, which the capture genuinely depends on for its real (serial) source.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import random
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_LOGGER_DIR = _REPO / "tools" / "logger"
if str(_LOGGER_DIR) not in sys.path:
    sys.path.insert(0, str(_LOGGER_DIR))

# Reuse the monitor logger's pure telemetry helpers (one parse_device_line, one
# checksum). A future refactor could extract these into a serial-free shared
# module so neither tool hard-imports pyserial; not needed for this slice.
from plants_logger import (  # noqa: E402  (sibling import after sys.path)
    CANONICAL_COLS,
    is_line_noise,
    iso_local,
    iso_utc,
    parse_device_line,
    tz_offset,
)

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import serial_lock  # noqa: E402  (sibling module)


class CaptureError(RuntimeError):
    """A serial-capture protocol failure (no boot banner, a nak, or no ack)."""


CAPTURE_VERSION = "experiment_capture_0_1"
SCHEMA_VERSION = 2

# schema_version=2 = the canonical monitor columns + additive, *filterable*
# shared-core columns (ADR-0012 §2; not buried in payload, so the never-stitch
# gate can filter on mode / experiment_id). Mapped by name -> v1 readers ignore them.
EXPERIMENT_COLS = [
    *CANONICAL_COLS,
    "mode",
    "subject",
    "experiment_id",
    "sample_rate_s",
    "label",
]
EXPERIMENT_MODE = "experiment"
SOIL_CHANNELS = ("s1", "s2", "s3", "s4")
_GPIO = {"s1": 34, "s2": 35, "s3": 36, "s4": 39}


def _nmea_crc(body: str) -> str:
    """NMEA-style XOR checksum over ``body`` (matches the device + the logger)."""
    calc = 0
    for ch in body:
        calc ^= ord(ch) & 0xFF
    return f"{calc:02X}"


# --------------------------------------------------------------------------- #
# the pluggable source seam (Firmware #63 set_cadence + #64 port-handoff land here)
# --------------------------------------------------------------------------- #
class Reader(ABC):
    """A capture source. ``acquire``/``release`` are the serial-port handoff seam
    (#64); ``set_cadence`` is the firmware command (#63); ``lines`` yields raw
    device lines exactly as the monitor logger would see them."""

    @abstractmethod
    def acquire(self) -> None: ...

    @abstractmethod
    def set_cadence(self, rate_s: float) -> None: ...

    @abstractmethod
    def lines(self) -> Iterator[str]: ...

    @abstractmethod
    def release(self) -> None: ...


class SyntheticReader(Reader):
    """A device-free source: plausible 4-channel sweeps at the set cadence, with a
    sprinkle of idle-noise and a bad-checksum line so the transport-error counters
    (and the error-rate-vs-cadence finding) are actually exercised in tests."""

    def __init__(self, *, seed: int = 0, glitch_every: int = 11) -> None:
        self._rate_s = 1.0
        self._rng = random.Random(seed)
        self._session = f"synth{seed:04x}"
        self._t0 = time.monotonic()
        self._glitch_every = glitch_every
        self._sweep = 0

    def acquire(self) -> None:  # no real port to take
        return None

    def set_cadence(self, rate_s: float) -> None:
        self._rate_s = max(0.01, rate_s)

    def _device_line(self, sensor: str, millis: int) -> str:
        raw = 1360 + self._rng.randint(-8, 8) + (40 if sensor == "s2" else 0)
        value = round((3400 - raw) / 2500 * 100)
        body = (
            f"plants.soil,{self._session},plants_esp32_synthetic,0.7.0,{millis},"
            f"UMLIFE_v2_TLC555,{sensor},origplant,soil_moisture,{raw},{value},pct,OK,"
            f"level=well watered;role=disp;spread={self._rng.randint(8, 22)};"
            f"gpio={_GPIO[sensor]}"
        )
        return f"{body}*{_nmea_crc(body)}"

    def lines(self) -> Iterator[str]:
        while True:
            self._sweep += 1
            millis = int((time.monotonic() - self._t0) * 1000)
            for sensor in SOIL_CHANNELS:
                yield self._device_line(sensor, millis)
            if self._sweep % self._glitch_every == 0:  # idle-noise frame (0xFF run)
                yield "".join(chr(0xFF) for _ in range(12))
            if self._sweep % (self._glitch_every * 2) == 0:  # a corrupted line
                yield "plants.soil,x,x,x,x,x,x,x,x,x,x,x,x,x*00"
            # idle to the next sweep, yielding "" ticks so a bounded capture can
            # auto-stop promptly even at a slow cadence (never block for minutes)
            slept = 0.0
            while slept < self._rate_s:
                step = min(0.5, self._rate_s - slept)
                time.sleep(step)
                slept += step
                yield ""

    def release(self) -> None:
        return None


class SerialReader(Reader):
    """Real serial source implementing the ADR-0011 host contract:

    ``acquire`` = exclusive open (the OS mutex) -> wait for the boot banner ->
    write the advisory lock; ``set_cadence`` = ``!cad,<ms>*HH`` then await
    ``# ack`` / ``# nak``; ``release`` = close + clear the lock.

    The serial open is injectable (``open_fn``) so the whole protocol is
    unit-tested against a fake device; the real device integration needs Firmware
    #63 (the ``!cad`` command) + #64 (reset-on-open + the shared lock)."""

    def __init__(
        self,
        port: str | None,
        baud: int,
        *,
        open_fn=None,
        lock_dir=None,
        ack_timeout_s: float | None = None,
        banner_timeout_s: float = 5.0,
    ) -> None:
        self._port = port
        self._baud = baud
        self._open_fn = open_fn or self._default_open
        self._lock_dir = lock_dir
        self._ack_timeout_s = ack_timeout_s
        self._banner_timeout_s = banner_timeout_s
        self._ser = None
        self._lock_held = False  # set after write_lock; release() gates on it

    def _default_open(self):
        import serial  # real-path only; tests inject open_fn

        kw = {"timeout": 1}
        if os.name != "nt":  # Windows serial is exclusive already; POSIX needs the flag
            kw["exclusive"] = True
        return serial.Serial(self._port, self._baud, **kw)

    def _readline(self) -> str:
        raw = self._ser.readline()
        if not raw:
            return ""
        return raw.decode("latin-1").rstrip("\r\n")

    def acquire(self) -> None:
        try:
            self._ser = self._open_fn()  # OS-exclusive: a 2nd opener is refused
        except Exception as exc:  # surface "port busy" rather than crash
            raise CaptureError(
                f"cannot open {self._port} - monitor still holds it / port busy: {exc}"
            ) from exc
        self._wait_for_banner()  # opening reset the device; wait until it's listening
        serial_lock.write_lock(self._port, "experiment", lock_dir=self._lock_dir)
        self._lock_held = True

    def _wait_for_banner(self) -> None:
        deadline = time.monotonic() + self._banner_timeout_s
        while time.monotonic() < deadline:
            line = self._readline()
            if line.startswith("# boot") and "fw=" in line:
                return
        raise CaptureError("no boot banner after open (device didn't reset / boot?)")

    def set_cadence(self, rate_s: float) -> None:
        ms = max(1, round(rate_s * 1000))
        body = f"cad,{ms}"
        cmd = f"!{body}*{_nmea_crc(body)}\n".encode("ascii")
        timeout = self._ack_timeout_s
        if timeout is None:
            timeout = max(2 * rate_s, 1.5)  # per the contract
        for _ in range(2):  # send + one retry on timeout
            self._ser.write(cmd)
            result = self._await_ack(timeout)
            if result == "ack":
                return
            if result == "nak":
                raise CaptureError(f"device rejected cadence {ms} ms (nak)")
        raise CaptureError(f"device not acking set_cadence {ms} ms")

    def _await_ack(self, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._readline()
            if line.startswith("# ack cad="):
                return "ack"
            if line.startswith("# nak"):
                return "nak"
        return "timeout"

    def lines(self) -> Iterator[str]:
        while True:
            yield self._readline()  # "" on idle -> run_capture ticks the deadline

    def release(self) -> None:
        if self._ser is not None:
            with contextlib.suppress(Exception):  # release must never raise
                self._ser.close()
            self._ser = None
        # Clear ONLY a lock this reader actually wrote. A failed/partial acquire
        # (port busy, or open-but-no-banner) wrote none - don't wipe the monitor's.
        if self._lock_held:
            serial_lock.clear_lock(lock_dir=self._lock_dir)
            self._lock_held = False


# --------------------------------------------------------------------------- #
# the isolated schema_version=2 writer
# --------------------------------------------------------------------------- #
class CaptureWriter:
    """Writes one self-describing schema_version=2 CSV under
    ``experiments/<experiment_id>/`` — never ``logs/``."""

    def __init__(self, out_dir: Path, experiment_id: str, subject: str, rate_s: float):
        self.dir = out_dir / experiment_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / f"{experiment_id}.csv"
        self.experiment_id = experiment_id
        self.subject = subject
        self.rate_s = rate_s
        self._fh = self.path.open("w", encoding="utf-8", newline="")
        self._writer = csv.writer(self._fh, lineterminator="\n")
        self._fh.write(self._header(datetime.now(timezone.utc)))
        self._writer.writerow(EXPERIMENT_COLS)

    def _header(self, now: datetime) -> str:
        return (
            f"# plants telemetry experiment - schema_version={SCHEMA_VERSION} "
            f"mode={EXPERIMENT_MODE} experiment_id={self.experiment_id} "
            f"subject={self.subject} sample_rate_s={self.rate_s} "
            f"logger={CAPTURE_VERSION}\n"
            f"# log_start_utc={iso_utc(now)} tz_offset={tz_offset(now)} "
            f"mode={EXPERIMENT_MODE} - isolated experiment capture; NOT a monitor log "
            f"(never stitch into the baseline)\n"
        )

    def write(self, dev: dict, sample_id: int, label: str, now: datetime) -> None:
        row = dict.fromkeys(EXPERIMENT_COLS, "")
        row.update(
            record_type=dev["record_type"],
            timestamp_utc=iso_utc(now),
            timestamp_local=iso_local(now),
            sample_id=sample_id,
            session_id=dev["session_id"],
            device_id=dev["device_id"],
            firmware_version=dev["fw"],
            logger_version=CAPTURE_VERSION,
            millis_ms=dev["millis_ms"],
            sensor_model=dev["sensor_model"],
            sensor_id=dev["sensor_id"],
            sensor_position=dev["sensor_position"],
            channel=dev["channel"],
            raw_value=dev["raw_value"],
            value=dev["value"],
            unit=dev["unit"],
            quality_flag=dev["quality_flag"],
            payload=dev["payload"],
            mode=EXPERIMENT_MODE,
            subject=self.subject,
            experiment_id=self.experiment_id,
            sample_rate_s=self.rate_s,
            label=label,
        )
        self._writer.writerow([row[c] for c in EXPERIMENT_COLS])
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# --------------------------------------------------------------------------- #
# the bounded capture loop (fail-safe auto-stop)
# --------------------------------------------------------------------------- #
def run_capture(
    reader: Reader,
    out_dir: Path,
    *,
    experiment_id: str,
    subject: str,
    title: str | None = None,
    rate_s: float,
    duration_s: float,
    labels: dict[str, str],
    stop_file: Path | None = None,
) -> dict:
    """Run a bounded capture; returns the manifest dict (also written to disk)."""
    writer = CaptureWriter(out_dir, experiment_id, subject, rate_s)
    counts = {"rows": 0, "sweeps": 0, "dropped": 0, "crc_fail": 0, "noise": 0}
    started = datetime.now(timezone.utc)
    deadline = time.monotonic() + duration_s
    last_sensor: str | None = None
    sample_id = 0
    stopped_by = "duration"
    try:
        reader.acquire()
        reader.set_cadence(rate_s)
        for text in reader.lines():
            if time.monotonic() >= deadline:  # fail-safe auto-stop (R3)
                break
            if stop_file is not None and stop_file.exists():  # operator stop (#66)
                stopped_by = "operator"
                break
            if not text:  # idle tick - lets us check the deadline between bursts
                continue
            dev = parse_device_line(text)
            if dev is None:
                counts["noise" if is_line_noise(text) else "dropped"] += 1
                continue
            if dev.get("_crc_ok") is False:
                counts["crc_fail"] += 1
                continue
            # a sweep = the s1..s4 group; count one when the channel cycle restarts
            if last_sensor is not None and dev["sensor_id"] <= last_sensor:
                counts["sweeps"] += 1
            last_sensor = dev["sensor_id"]
            sample_id += 1
            counts["rows"] += 1
            label = labels.get(dev["sensor_id"], dev["sensor_id"])
            writer.write(dev, sample_id, label, datetime.now(timezone.utc))
    finally:
        reader.release()
        writer.close()
    ended = datetime.now(timezone.utc)

    manifest = {
        "experiment_id": experiment_id,
        "subject": subject,
        "title": title or subject,
        "schema_version": SCHEMA_VERSION,
        "mode": EXPERIMENT_MODE,
        "sample_rate_s": rate_s,
        "duration_s": duration_s,
        "stopped_by": stopped_by,  # "duration" (auto-stop) | "operator" (#66 stop)
        "labels": labels,
        "started_utc": iso_utc(started),
        "ended_utc": iso_utc(ended),
        "capture_version": CAPTURE_VERSION,
        "file": writer.path.name,
        "transport": {  # the error-rate-vs-cadence signal (R9)
            "rows": counts["rows"],
            "sweeps": counts["sweeps"],
            "dropped": counts["dropped"],
            "crc_fail": counts["crc_fail"],
            "idle_noise": counts["noise"],
        },
    }
    (writer.dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _parse_labels(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs or []:
        key, _, val = pair.partition("=")
        if val:
            out[key.strip()] = val.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a bounded Experiment-mode capture.")
    ap.add_argument("--subject", default="unspecified", help="what's being measured")
    ap.add_argument("--title", help="human display title (default: the subject)")
    ap.add_argument("--experiment-id", help="default: <UTC stamp>_<subject>")
    ap.add_argument("--rate-s", type=float, default=1.0, help="sample cadence, seconds")
    ap.add_argument(
        "--duration-s", type=float, default=20.0, help="auto-stop after N s"
    )
    ap.add_argument(
        "--label", action="append", help="per-probe label, e.g. --label s1=control"
    )
    ap.add_argument(
        "--source",
        choices=("synthetic", "serial"),
        default="synthetic",
        help="capture source (serial lands with #63/#64; synthetic = device-free)",
    )
    ap.add_argument("--port", help="serial port (serial source only)")
    ap.add_argument("--baud", type=int, default=19200)
    ap.add_argument(
        "--out-dir", help="experiment root (default <repo>/experiments — never logs/)"
    )
    ap.add_argument(
        "--stop-file", help="cooperative stop: ends cleanly when this file appears"
    )
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else _REPO / "experiments"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    experiment_id = args.experiment_id or f"{stamp}_{args.subject}"
    reader: Reader = (
        SyntheticReader()
        if args.source == "synthetic"
        else SerialReader(args.port, args.baud)
    )

    print(
        f"experiment '{experiment_id}': {args.subject} @ {args.rate_s}s "
        f"for {args.duration_s}s -> {out_dir / experiment_id} ({args.source})"
    )
    try:
        manifest = run_capture(
            reader,
            out_dir,
            experiment_id=experiment_id,
            subject=args.subject,
            title=args.title,
            rate_s=args.rate_s,
            duration_s=args.duration_s,
            labels=_parse_labels(args.label),
            stop_file=Path(args.stop_file) if args.stop_file else None,
        )
    except CaptureError as exc:  # port busy / no banner -> clean exit, no traceback
        print(f"capture failed: {exc}", file=sys.stderr)
        return 1
    t = manifest["transport"]
    print(
        f"done: {t['rows']} rows / {t['sweeps']} sweeps  "
        f"(dropped={t['dropped']} crc_fail={t['crc_fail']} "
        f"idle_noise={t['idle_noise']})"
    )
    print(f"  {out_dir / experiment_id / manifest['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
