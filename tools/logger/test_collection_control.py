"""#1004 guard 2 — a WiFi-only fleet never sees COM-port vocabulary.

The one-action start (``collection_control.start_all``) auto-detects the serial
transport: it finds a real tethered board when one is present, and on a WiFi-only
windowsill rig (no COM port) it **skips serial with a stated reason** — and that
reason names no COM port. The dashboard's one-button start now passes ``port=None``
(auto-detect) so it takes exactly this path; forcing a stale operator-typed port was
the old leak that made a portless host hunt (and name) a COM device.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collection_control import CollectionError, start_all


class _FleetOk:
    def start(self) -> dict:
        return {"state": "running", "configured": 2, "answering": 2}


class _FleetNone:
    def start(self) -> dict:
        raise RuntimeError("no registered fleet devices - nothing to poll")


class _MonitorBoom:
    """A monitor that would name a COM port if ever asked to start one."""

    def start(self, *, port=None) -> dict:  # pragma: no cover - must NOT be called
        raise AssertionError(f"serial start attempted on a WiFi-only rig (port={port})")


def _no_serial(_port) -> bool:
    return False  # portless host: autodetect finds nothing


def test_wifi_only_start_skips_serial_with_no_com_vocabulary() -> None:
    # the button's new behavior: port=None (auto-detect), WiFi-only rig.
    res = start_all(_MonitorBoom(), _FleetOk(), port=None, port_present=_no_serial)
    assert res["monitor"]["state"] == "skipped"
    assert "WiFi-only" in res["monitor"]["reason"]
    assert res["fleet"]["state"] == "running"
    # guard 2: no COM-port name leaks anywhere in what the operator could see.
    blob = repr(res)
    assert "COM" not in blob


def test_wifi_only_rig_never_attempts_a_serial_start() -> None:
    # _MonitorBoom.start asserts if called; a portless host must never reach it.
    start_all(_MonitorBoom(), _FleetOk(), port=None, port_present=_no_serial)


def test_portless_and_no_fleet_is_an_honest_nothing_not_a_com_error() -> None:
    try:
        start_all(_MonitorBoom(), _FleetNone(), port=None, port_present=_no_serial)
    except CollectionError as e:
        assert "COM" not in str(e)  # the failure blames "nothing", not a phantom port
        assert "WiFi-only" in str(e)
    else:  # pragma: no cover
        raise AssertionError("expected CollectionError when nothing can start")
