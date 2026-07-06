"""#566 (ruled B) / #712 — the collector/monitor opens the port WITHOUT asserting
DTR/RTS, so a host reconnect never resets the board (which minted a new session
every ~30 s → the reconnect storm). esptool is a separate path and unaffected.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from serial_open import open_no_reset


class FakeSerial:
    """A pyserial-shaped port that starts with DTR/RTS HIGH (the default that
    resets an ESP32) and records the order of line changes vs open()."""

    def __init__(self) -> None:
        # object.__setattr__ to bypass the recording __setattr__ during init
        object.__setattr__(self, "events", [])
        object.__setattr__(self, "opened", False)
        object.__setattr__(self, "dtr", True)  # HIGH by default — the reset trap
        object.__setattr__(self, "rts", True)
        object.__setattr__(self, "port", None)
        object.__setattr__(self, "baudrate", None)

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        if key in ("dtr", "rts"):
            self.events.append((key, value))

    def open(self):
        # capture the DTR/RTS state AT open — this is what the driver asserts
        self.events.append(("open", (self.dtr, self.rts)))
        object.__setattr__(self, "opened", True)


def test_dtr_rts_are_held_low_before_open() -> None:
    ser = open_no_reset("COM6", 19200, factory=FakeSerial, timeout=2)
    assert ser.opened is True
    assert ser.dtr is False and ser.rts is False  # never asserted
    # and both were set low BEFORE the port opened (order matters — a late set
    # would still pulse the reset on open)
    open_idx = next(i for i, e in enumerate(ser.events) if e[0] == "open")
    dtr_low = ser.events.index(("dtr", False))
    rts_low = ser.events.index(("rts", False))
    assert dtr_low < open_idx and rts_low < open_idx
    # at the moment of open, both lines read low
    assert ser.events[open_idx] == ("open", (False, False))


def test_config_applied_and_port_never_opened_on_construct() -> None:
    ser = open_no_reset("COM7", 9600, factory=FakeSerial, timeout=1, exclusive=True)
    assert ser.port == "COM7" and ser.baudrate == 9600
    assert ser.timeout == 1 and ser.exclusive is True
    # the factory is called with NO port (deferred open) — a FakeSerial that took
    # a port in __init__ would have opened; ours proves the deferred contract by
    # only opening in open_no_reset (opened True, and exactly one 'open' event).
    assert sum(1 for e in ser.events if e[0] == "open") == 1


def test_real_path_uses_pyserial_deferred_open(monkeypatch) -> None:
    # with no factory, it must construct serial.Serial() with NO args (deferred),
    # never serial.Serial(port, baud) (which opens + pulses DTR).
    import serial_open

    calls = {"argc": None}

    class _Rec(FakeSerial):
        def __init__(self, *args):
            calls["argc"] = len(args)  # 0 == deferred (safe); >0 == opens on init
            super().__init__()

    fake_mod = type(sys)("serial")
    fake_mod.Serial = _Rec
    monkeypatch.setitem(sys.modules, "serial", fake_mod)
    ser = serial_open.open_no_reset("COM6", 19200, timeout=2)
    assert calls["argc"] == 0  # deferred construction — never Serial(port, baud)
    assert ser.dtr is False and ser.rts is False and ser.opened is True
