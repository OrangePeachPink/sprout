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
import csv
import json
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
            time.sleep(self._rate_s)

    def release(self) -> None:
        return None


class SerialReader(Reader):
    """Real serial source — lands with Firmware #63 (set_cadence) + #64 (port
    handoff). Stubbed so the storage/isolation/schema path ships independently."""

    def __init__(self, port: str | None, baud: int) -> None:
        self._port, self._baud = port, baud

    def acquire(self) -> None:
        raise NotImplementedError(
            "Real serial capture lands with #63 (set_cadence) + #64 (port-handoff). "
            "Use --source synthetic until the firmware seam is ready."
        )

    def set_cadence(self, rate_s: float) -> None:  # via the #63 serial command
        raise NotImplementedError

    def lines(self) -> Iterator[str]:
        raise NotImplementedError

    def release(self) -> None:
        return None


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
    ap.add_argument("--experiment-id", help="default: <UTC stamp>_<subject>")
    ap.add_argument("--rate-s", type=float, default=1.0, help="sample cadence, seconds")
    ap.add_argument(
        "--duration-s", type=float, default=20.0, help="auto-stop after N s"
    )
    ap.add_argument(
        "--label", action="append", help="per-probe label, e.g. --label s1=control"
    )
    ap.add_argument(
        "--source", choices=("synthetic", "serial"), default="synthetic",
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
        SyntheticReader() if args.source == "synthetic"
        else SerialReader(args.port, args.baud)
    )

    print(f"experiment '{experiment_id}': {args.subject} @ {args.rate_s}s "
          f"for {args.duration_s}s -> {out_dir / experiment_id} ({args.source})")
    manifest = run_capture(
        reader, out_dir,
        experiment_id=experiment_id, subject=args.subject,
        rate_s=args.rate_s, duration_s=args.duration_s,
        labels=_parse_labels(args.label),
        stop_file=Path(args.stop_file) if args.stop_file else None,
    )
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
