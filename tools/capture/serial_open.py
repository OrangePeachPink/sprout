"""Open a serial port WITHOUT resetting the board — the #566-ruling-B fix (#712).

## Why this exists

On an ESP32 dev board the USB-serial adapter's **DTR** and **RTS** modem-control
lines are wired to the auto-reset circuit (DTR → EN/reset, RTS → GPIO0/boot).
pyserial's default ``serial.Serial(port, baud)`` **asserts DTR/RTS as it opens**,
which pulses that circuit and **resets the board**. Harmless once — but the
monitor/collector reconnects (a port re-open on every supervisor cycle, a
launcher restart, a transient USB hiccup), and *each* reconnect reset the board,
which minted a **new ``session_id`` every ~30 s** → the reconnect storm (#712,
dozens of 4-row sessions). #566 ruled **B**: fix it host-side by *never asserting
DTR/RTS on open*, rather than changing firmware.

## What it does

Uses pyserial's deferred-open idiom — construct the port object *without* a port
(so it is **not** opened on construction), hold both control lines **low**, then
``open()``. Opening therefore never pulses the auto-reset circuit; the board keeps
running across a host reconnect, so its session_id is stable.

## esptool is UNAFFECTED

esptool (flashing) is a **separate tool** with its **own** serial session and it
*deliberately* asserts DTR/RTS to drive the board into the ROM bootloader. It does
**not** go through this path (the monitor/collector never flashes), so holding
DTR/RTS low here does not touch flashing — you can still `esptool ... write-flash`
exactly as before. This helper is only for the read-only telemetry paths
(``plants_logger`` monitor, ``experiment_capture``).
"""

from __future__ import annotations


def open_no_reset(port: str, baud: int, *, factory=None, **kw):
    """Open ``port`` at ``baud`` without pulsing the ESP32 auto-reset circuit.

    ``factory`` is a zero-arg callable returning an *unopened* pyserial-like port
    (defaults to ``serial.Serial``); injected in tests. Extra ``kw`` (e.g.
    ``timeout=2``, POSIX ``exclusive=True``) are applied as attributes before the
    open, exactly as the constructor would have. Returns the opened port.
    """
    if factory is None:
        import serial  # real path only; lazy so tests need no pyserial

        factory = serial.Serial
    ser = factory()  # NO port arg -> created but NOT opened (pyserial contract)
    ser.port = port
    ser.baudrate = baud
    for key, value in kw.items():
        setattr(ser, key, value)
    # Hold both modem-control lines LOW *before* opening, so the act of opening
    # never asserts them and never pulses DTR->EN / RTS->GPIO0 (the board does not
    # reset on our reconnect). This is the whole fix (#566-B / #712).
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser
