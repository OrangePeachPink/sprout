#!/usr/bin/env python3
"""#1550 (A7) — the connected-hardware list: one heuristic, no USB ids in the payload.

Two properties, both of which would be invisible in a screenshot of a working picker:

1. **The picker and the logger agree by construction.** `plants_logger.autodetect_port`
   now consumes this module, so the port the picker shows as the default IS the port the
   logger opens. A picker offering COM4 while the logger opens COM6 — with nothing
   explaining why — is what a second copy of the heuristic would have caused.
2. **`hwid` never leaves the process.** pyserial's `hwid` carries the USB instance id
   and often the adapter's serial number; the pre-publish checklist names USB instance
   ids alongside MACs and SSIDs. A picker renders into screenshots and bug reports,
   so the payload is a deliberate subset and this test is the fence.
"""

from __future__ import annotations

from tools.analytics import serial_ports
from tools.analytics.serial_ports import (
    SerialPort,
    autodetect,
    list_serial_ports,
    ports_payload,
)


class _FakePort:
    """Shaped like pyserial's ListPortInfo, including the field we must not leak."""

    def __init__(self, device, description="", manufacturer="", hwid=""):
        self.device = device
        self.description = description
        self.manufacturer = manufacturer
        self.hwid = hwid


def _patch(monkeypatch, ports):
    import types

    fake = types.SimpleNamespace(comports=lambda: ports)
    mod = types.SimpleNamespace(list_ports=fake)
    monkeypatch.setitem(__import__("sys").modules, "serial.tools", mod)
    monkeypatch.setitem(__import__("sys").modules, "serial.tools.list_ports", fake)


# --------------------------------------------------------------------------- #
# the privacy fence
# --------------------------------------------------------------------------- #
def test_the_usb_instance_id_never_reaches_the_payload(monkeypatch) -> None:
    """hwid carries VID/PID and frequently the adapter's SERIAL NUMBER. It is read for
    the heuristic and dropped — a picker's output ends up in screenshots."""
    secret = "USB VID:PID=10C4:EA60 SER=0001A2B3C4 LOCATION=1-4"
    _patch(
        monkeypatch,
        [_FakePort("COM6", "Silicon Labs CP210x UART Bridge", "Silicon Labs", secret)],
    )
    payload = ports_payload()
    blob = repr(payload)
    assert "0001A2B3C4" not in blob  # the serial number
    assert "10C4:EA60" not in blob  # the VID:PID
    assert "hwid" not in blob
    # ...while still using it: this port IS recognized as a board
    assert payload["ports"][0]["likely_board"] is True


def test_the_payload_shape_is_exactly_three_public_fields(monkeypatch) -> None:
    _patch(monkeypatch, [_FakePort("COM6", "CH340", "wch.cn", "USB VID:PID=1A86:7523")])
    assert set(ports_payload()["ports"][0]) == {
        "device",
        "description",
        "likely_board",
    }


# --------------------------------------------------------------------------- #
# one heuristic, shared
# --------------------------------------------------------------------------- #
def test_a_known_bridge_is_preferred_over_an_earlier_plain_port(monkeypatch) -> None:
    _patch(
        monkeypatch,
        [
            _FakePort("COM1", "Communications Port", "(Standard)", "ACPI\\PNP0501"),
            _FakePort("COM6", "USB Serial Device", "FTDI", "USB VID:PID=0403:6001"),
        ],
    )
    assert autodetect() == "COM6"  # not COM1, though COM1 enumerates first
    assert [p["device"] for p in ports_payload()["ports"]] == ["COM6", "COM1"]


def test_the_logger_and_the_picker_choose_the_same_port(monkeypatch) -> None:
    """The consolidation's whole point (ADR-0038 §3): plants_logger.autodetect_port now
    consumes this module, so the shown default and the opened port cannot diverge."""
    _patch(
        monkeypatch,
        [
            _FakePort("COM1", "Communications Port"),
            _FakePort("COM6", "CP210x", "Silicon Labs", "USB VID:PID=10C4:EA60"),
        ],
    )
    from tools.logger.plants_logger import autodetect_port

    assert autodetect_port() == ports_payload()["default"] == "COM6"


def test_with_no_bridge_the_first_port_is_the_default(monkeypatch) -> None:
    _patch(monkeypatch, [_FakePort("COM1", "Communications Port")])
    assert autodetect() == "COM1"
    assert ports_payload()["ports"][0]["likely_board"] is False


# --------------------------------------------------------------------------- #
# honest absence
# --------------------------------------------------------------------------- #
def test_no_ports_is_a_stated_reason_not_an_empty_box(monkeypatch) -> None:
    _patch(monkeypatch, [])
    p = ports_payload()
    assert p["ports"] == [] and p["count"] == 0 and p["default"] is None
    assert "plug a board in" in p["reason"].lower()


def test_an_enumeration_failure_degrades_and_never_raises(monkeypatch) -> None:
    """No hardware is not an error state, and a picker that raised would break the flow
    for exactly the user who most needs it to keep working."""

    def boom():
        raise OSError("the OS said no")

    import types

    fake = types.SimpleNamespace(comports=boom)
    monkeypatch.setitem(
        __import__("sys").modules,
        "serial.tools",
        types.SimpleNamespace(list_ports=fake),
    )
    monkeypatch.setitem(__import__("sys").modules, "serial.tools.list_ports", fake)
    assert list_serial_ports() == []
    assert autodetect() is None


def test_a_port_with_no_description_still_renders(monkeypatch) -> None:
    _patch(monkeypatch, [_FakePort("COM9", "")])
    assert ports_payload()["ports"][0]["description"] == "unknown device"


def test_the_module_is_a_leaf(monkeypatch) -> None:
    """Layer 0: it may import pyserial and stdlib, nothing of ours."""
    src = __import__("pathlib").Path(serial_ports.__file__).read_text(encoding="utf-8")
    assert "from tools." not in src and "import tools" not in src


def test_autodetect_accepts_a_supplied_list_without_re_enumerating() -> None:
    ports = [
        SerialPort("COM1", "plain", False),
        SerialPort("COM6", "CP210x", True),
    ]
    assert autodetect(ports) == "COM6"
