#!/usr/bin/env python3
"""One operator action = all collection running (#588, ADR-0014's ratification
note). The combined start/stop/status over BOTH collection paths - the serial
monitor (``MonitorController``) and the WiFi fleet (``FleetController``) - with
the graceful degrade the ADR asks for:

* no COM port present   -> the serial path is **skipped with a reason**, not an
  error (a WiFi-only windowsill install is a first-class deployment);
* no registered fleet   -> the fleet path is skipped the same way (a
  tethered-only bench is equally first-class);
* **both** absent       -> an honest error: one action that collected nothing
  must never look like success.

This is lifecycle POLICY, so it lives in the control layer (ADR-0014 §5:
serve.py stays transport/routing/wiring) - serve.py just routes
``/collection/*`` here.

The serial-absence check happens BEFORE spawning: ``plants_logger``'s own run
loop retries a missing port forever (by design - reconnect), which from the
operator plane would read as a phantom "running" monitor on a portless host.
Detecting absence up front keeps the skip honest.
"""

from __future__ import annotations


class CollectionError(RuntimeError):
    """One action, zero collection: both paths were absent/refused."""


def _serial_port_present(port: str | None) -> bool:
    """True when a serial port is available to monitor. An explicit ``port``
    is trusted (the operator named it); otherwise autodetect. Import-guarded:
    no pyserial (or no ports) reads as no serial path."""
    if port:
        return True
    try:
        from tools.logger.plants_logger import autodetect_port

        return autodetect_port() is not None
    except Exception:
        return False


def start_all(
    monitor,
    fleet,
    *,
    port: str | None = None,
    port_present=_serial_port_present,
) -> dict:
    """Start every collection path that exists; skip (with a stated reason)
    each one that doesn't. Raises ``CollectionError`` only when NOTHING could
    start - the one-action promise must not fake success."""
    results: dict = {}

    if not port_present(port):
        results["monitor"] = {
            "state": "skipped",
            "reason": "no serial port present (WiFi-only deployment is fine)",
        }
    else:
        try:
            results["monitor"] = monitor.start(port=port)
        except Exception as e:  # already running / port held - stated, not fatal
            results["monitor"] = {"state": "skipped", "reason": str(e)}

    try:
        results["fleet"] = fleet.start()
    except Exception as e:  # no registered devices / already running
        results["fleet"] = {"state": "skipped", "reason": str(e)}

    collecting = [k for k, v in results.items() if v.get("state") == "running"]
    # "already running" counts as collecting - the operator's intent is met.
    already = [
        k
        for k, v in results.items()
        if v.get("state") == "skipped" and "already running" in v.get("reason", "")
    ]
    if not collecting and not already:
        reasons = "; ".join(
            f"{k}: {v.get('reason', 'unknown')}" for k, v in results.items()
        )
        raise CollectionError(f"nothing to collect from - {reasons}")
    results["collecting"] = True
    return results


def stop_all(monitor, fleet) -> dict:
    """Stop both paths (stopping an already-stopped path is a no-op by each
    controller's own contract)."""
    return {
        "monitor": monitor.stop(),
        "fleet": fleet.stop(),
        "collecting": False,
    }


def status_all(monitor, fleet) -> dict:
    mon, fl = monitor.status(), fleet.status()
    return {
        "monitor": mon,
        "fleet": fl,
        "collecting": mon.get("state") == "running" or fl.get("state") == "running",
    }
