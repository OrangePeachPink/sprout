#!/usr/bin/env python3
"""#1550 (A7) — what serial hardware is connected, in ONE place (ADR-0038 §3).

The in-app picker needs the port list, and enumerating it a third time is how the
answers start disagreeing: `plants_logger.autodetect_port` already picks a port by
USB-bridge heuristic, and DX's `doctor` already lists them for the preflight. A picker
that used its own logic could offer a port autodetect would never choose — the operator
picks COM4, the logger opens COM6, and nothing explains why. So the heuristic lives here
and the callers consume it.

**Layer 0 (a leaf): imports pyserial and nothing of ours.**

**The privacy fence, and why this module exists as much for that as for the dedupe.**
`pyserial`'s `hwid` carries the USB instance id — vendor/product ids and, on many
adapters, the adapter's **serial number**. That is squarely in the identifier class this
project keeps out of shared surfaces (the §0.8.1 pre-publish checklist names USB
instance ids alongside MACs and SSIDs), and a picker renders straight into screenshots
and bug reports. So `hwid` is **read for the heuristic and never returned**: the payload
carries the port name, the human description, and a derived boolean. The full string
stays in this process.
"""

from __future__ import annotations

from dataclasses import dataclass

# USB-serial bridge markers. A board on the desk is nearly always behind one of these,
# so their presence is the signal that a port is plausibly Sprout hardware rather than a
# bluetooth modem or a virtual port. Lifted verbatim from plants_logger's autodetect so
# the picker and the logger agree by construction.
_BRIDGE_MARKERS = ("cp210", "ch340", "ftdi", "silicon labs", "usb serial", "wch")


@dataclass(frozen=True)
class SerialPort:
    """One connected port, in the shape a surface may safely render.

    Deliberately NOT a passthrough of pyserial's ListPortInfo: `hwid` (the USB instance
    id, often carrying the adapter's serial number) is read for the heuristic and
    dropped here. A picker's output ends up in screenshots; this is the boundary where
    that stops being our problem."""

    device: str  # "COM6" / "/dev/ttyUSB0" — what the operator picks, the logger opens
    description: str  # the human label the OS reports, e.g. "Silicon Labs CP210x..."
    likely_board: bool  # sits behind a known USB-serial bridge

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "description": self.description,
            "likely_board": self.likely_board,
        }


def _is_bridge(*fields: str | None) -> bool:
    blob = " ".join(f for f in fields if f).lower()
    return any(marker in blob for marker in _BRIDGE_MARKERS)


def list_serial_ports() -> list[SerialPort]:
    """Connected ports, likely-board ones first, then OS order.

    An absent pyserial or an enumeration failure returns `[]` — "no ports visible" is
    legitimate (no board plugged in is not an error, per doctor's own framing), and
    a picker that raised on a machine with no hardware would break the flow for exactly
    the user who most needs it to keep working."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    try:
        raw = list(list_ports.comports())
    except Exception:
        return []
    out = [
        SerialPort(
            device=p.device,
            description=(p.description or "").strip() or "unknown device",
            likely_board=_is_bridge(p.description, p.manufacturer, p.hwid),
        )
        for p in raw
        if getattr(p, "device", None)
    ]
    # stable: likely boards first, otherwise the order the OS gave us
    return sorted(out, key=lambda p: (not p.likely_board,))


def autodetect(ports: list[SerialPort] | None = None) -> str | None:
    """The port the logger would open on its own — a known bridge if one is present,
    else the first port, else None. Exposed so the picker can SHOW that default rather
    than make the operator guess which one it would have chosen."""
    ports = list_serial_ports() if ports is None else ports
    for p in ports:
        if p.likely_board:
            return p.device
    return ports[0].device if ports else None


def ports_payload() -> dict:
    """The picker's payload: the ports, the default, and an honest reason when empty."""
    ports = list_serial_ports()
    return {
        "ports": [p.to_dict() for p in ports],
        "default": autodetect(ports),
        "count": len(ports),
        # ADR-0028: say why there's nothing rather than rendering an empty box
        "reason": ""
        if ports
        else (
            "No serial ports are visible — plug a board in over USB, "
            "or use a WiFi board."
        ),
    }
