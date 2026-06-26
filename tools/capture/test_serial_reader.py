#!/usr/bin/env python3
"""Standalone tests for SerialReader + serial_lock (#65, the serial seam).

    python tools/capture/test_serial_reader.py

The real device isn't here (it needs Firmware #63/#64), so the protocol is
exercised against a FakeSerial that mimics the ADR-0011 contract: a boot banner
on open, ``!cad,<ms>*HH`` validation with ``# ack`` / ``# nak``, then a data
stream. Also covers the advisory lock lifecycle and the slow-cadence auto-stop.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from collections import deque
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import experiment_capture as ec  # noqa: E402
import serial_lock  # noqa: E402

_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
    if not cond:
        _FAILS.append(msg)


def raises(fn, exc, msg: str) -> None:
    try:
        fn()
    except exc:
        check(True, msg)
    except Exception as other:
        check(False, f"{msg} (raised {type(other).__name__} instead)")
    else:
        check(False, f"{msg} (did not raise)")


class FakeSerial:
    """Mimics the ESP32 per ADR-0011: boot banner on open, validates
    ``!cad,<ms>*HH`` (checksum + range), replies ``# ack`` / ``# nak``, then
    streams valid data lines."""

    def __init__(self, *, floor_ms=500, ack=True, banner=True, seed=3) -> None:
        self._floor = floor_ms
        self._ack = ack
        self._q: deque[bytes] = deque()
        self._sweep = 0
        self.closed = False
        if banner:
            self._q.append(b"# boot sprout fw=0.7.0\n")

    def _reply(self, kind, ms, *, err="", prev="") -> None:
        extra = f" err={err}" if err else (f" prev={prev}" if prev else "")
        self._q.append(f"# {kind} cad={ms}{extra} floor={self._floor}\n".encode())

    def write(self, data: bytes) -> int:
        text = data.decode("ascii").strip()
        if text.startswith("!cad,") and "*" in text:
            body, _, cs = text[1:].partition("*")
            calc = 0
            for ch in body:
                calc ^= ord(ch) & 0xFF
            try:
                ms = int(body.split(",")[1])
            except (IndexError, ValueError):
                ms = -1
            if not self._ack:
                return len(data)  # silent -> the client times out
            if f"{calc:02X}" != cs.upper():
                self._reply("nak", ms, err="checksum")
            elif ms < self._floor or ms > 3_600_000:
                self._reply("nak", ms, err="range")
            else:
                self._reply("ack", ms, prev=30000)
        return len(data)

    def readline(self) -> bytes:
        if self._q:
            return self._q.popleft()
        sensor = ec.SOIL_CHANNELS[self._sweep % 4]
        self._sweep += 1
        raw = 1360 + (self._sweep % 7) - 3
        body = (
            f"plants.soil,fake01,plants_esp32_fake,0.7.0,{self._sweep * 100},"
            f"UMLIFE_v2_TLC555,{sensor},origplant,soil_moisture,{raw},77,pct,OK,"
            f"level=well watered;role=disp;spread=12;gpio={ec._GPIO[sensor]}"
        )
        return f"{body}*{ec._nmea_crc(body)}\n".encode()

    def close(self) -> None:
        self.closed = True


def _reader(fake, tmp, **kw):
    return ec.SerialReader("FAKE", 19200, open_fn=lambda: fake, lock_dir=tmp, **kw)


def test_lock() -> None:
    print("serial_lock - write / read / clear / liveness / stale:")
    tmp = Path(tempfile.mkdtemp(prefix="lock_"))
    try:
        rec = serial_lock.write_lock("COM9", "experiment", lock_dir=tmp)
        ok = rec["mode"] == "experiment" and rec["pid"] == os.getpid()
        check(ok, "write_lock records mode + pid")
        check(serial_lock.read_lock(tmp)["port"] == "COM9", "read_lock round-trips")
        check(serial_lock.pid_alive(os.getpid()) is True, "pid_alive: self is alive")
        check(serial_lock.pid_alive(2_000_000_000) is False, "pid_alive: dead pid")
        check(serial_lock.current_owner(tmp) is not None, "current_owner: live lock")
        serial_lock.write_lock("COM9", "monitor", lock_dir=tmp, pid=2_000_000_000)
        check(serial_lock.current_owner(tmp) is None, "current_owner: stale -> None")
        serial_lock.clear_lock(tmp)
        check(serial_lock.read_lock(tmp) is None, "clear_lock removes it")
        serial_lock.clear_lock(tmp)  # idempotent
        check(True, "clear_lock safe when absent")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_serial_lifecycle_and_protocol() -> None:
    print("SerialReader - banner -> lock -> set_cadence ack -> release:")
    tmp = Path(tempfile.mkdtemp(prefix="serlock_"))
    try:
        r = _reader(FakeSerial(), tmp, ack_timeout_s=0.5)
        r.acquire()
        lock = serial_lock.read_lock(tmp)
        check(bool(lock) and lock["mode"] == "experiment", "acquire writes a lock")
        r.set_cadence(1.0)  # 1000 ms >= floor -> ack
        check(True, "set_cadence(1 s) accepted")
        got = next(r.lines())
        check(ec.parse_device_line(got) is not None, "lines() yields a device line")
        r.release()
        check(serial_lock.read_lock(tmp) is None, "release clears the lock")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_serial_errors() -> None:
    print("SerialReader - nak / timeout / no-banner surface as CaptureError:")
    tmp = Path(tempfile.mkdtemp(prefix="sererr_"))
    try:
        r1 = _reader(FakeSerial(), tmp, ack_timeout_s=0.3)
        r1.acquire()
        raises(lambda: r1.set_cadence(0.1), ec.CaptureError, "below floor -> nak")
        r1.release()

        r2 = _reader(FakeSerial(ack=False), tmp, ack_timeout_s=0.1)
        r2.acquire()
        t0 = time.monotonic()
        raises(lambda: r2.set_cadence(1.0), ec.CaptureError, "no ack -> CaptureError")
        check(time.monotonic() - t0 < 1.0, "timeout bounded (retry, not hang)")
        r2.release()

        r3 = _reader(FakeSerial(banner=False), tmp, banner_timeout_s=0.1)
        raises(r3.acquire, ec.CaptureError, "no banner -> CaptureError")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_serial_capture_e2e() -> None:
    print("SerialReader - end-to-end run_capture writes an isolated v2 file:")
    tmp = Path(tempfile.mkdtemp(prefix="sere2e_"))
    lockdir = Path(tempfile.mkdtemp(prefix="sere2elock_"))
    try:
        reader = _reader(FakeSerial(), lockdir, ack_timeout_s=0.5)
        manifest = ec.run_capture(
            reader,
            tmp,
            experiment_id="t_serial",
            subject="fake-bench",
            rate_s=1.0,
            duration_s=0.3,
            labels={"s1": "ctrl"},
        )
        f = tmp / "t_serial" / "t_serial.csv"
        body = f.read_text(encoding="utf-8") if f.exists() else ""
        check("schema_version=2" in body, "serial path writes schema_version=2")
        rows = manifest["transport"]["rows"]
        check(rows > 0, f"rows captured ({rows})")
        check(serial_lock.read_lock(lockdir) is None, "lock cleared after the run")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(lockdir, ignore_errors=True)


def test_slow_cadence_autostop() -> None:
    print("auto-stop is prompt even at a slow cadence (the #72 latent fix):")
    tmp = Path(tempfile.mkdtemp(prefix="slow_"))
    try:
        t0 = time.monotonic()
        ec.run_capture(
            ec.SyntheticReader(seed=2),
            tmp,
            experiment_id="t_slow",
            subject="x",
            rate_s=2.0,
            duration_s=0.4,
            labels={},
        )
        elapsed = time.monotonic() - t0
        check(elapsed < 1.5, f"stopped at ~{elapsed:.2f}s, not the 2 s cadence")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_release_preserves_foreign_lock() -> None:
    print("release() clears ONLY a lock this reader wrote (the #87 mutex tidy-up):")
    tmp = Path(tempfile.mkdtemp(prefix="serforeign_"))
    try:
        # case 1: the monitor holds the port + owns the lock; a 2nd open is refused,
        # so acquire() raises before writing a lock -> release() must not wipe it.
        serial_lock.write_lock("COM6", "monitor", lock_dir=tmp)

        def busy_open():
            raise OSError("COM6 busy (monitor holds it)")

        r1 = ec.SerialReader("COM6", 19200, open_fn=busy_open, lock_dir=tmp)
        raises(r1.acquire, ec.CaptureError, "port-busy open -> CaptureError")
        r1.release()
        owner = serial_lock.current_owner(tmp)
        check(
            owner is not None and owner["mode"] == "monitor",
            "release after a port-busy open left the monitor's lock intact",
        )

        # case 2: open succeeds but no banner -> lock still never written -> a
        # pre-existing foreign lock survives release() too.
        r2 = ec.SerialReader(
            "COM6",
            19200,
            open_fn=lambda: FakeSerial(banner=False),
            lock_dir=tmp,
            banner_timeout_s=0.1,
        )
        raises(r2.acquire, ec.CaptureError, "no-banner open -> CaptureError")
        r2.release()
        owner2 = serial_lock.current_owner(tmp)
        check(
            owner2 is not None and owner2["mode"] == "monitor",
            "release after a no-banner open left the foreign lock intact",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    test_lock()
    test_serial_lifecycle_and_protocol()
    test_serial_errors()
    test_serial_capture_e2e()
    test_slow_cadence_autostop()
    test_release_preserves_foreign_lock()
    print()
    if _FAILS:
        print(f"FAILED ({len(_FAILS)}): " + "; ".join(_FAILS))
        raise SystemExit(1)
    print("All checks passed.")
