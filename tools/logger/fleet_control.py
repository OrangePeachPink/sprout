#!/usr/bin/env python3
"""serve.py-side control of the fleet logger (#588, ADR-0014 ratification note),
mirroring ``MonitorController`` (#128): serve.py owns the lifecycle; the spawned
``fleet_logger`` process polls registered WiFi devices and persists to ``logs/``
(#582/#585). All calls are localhost-gated by serve.py.

Fleet collection is *continuous* like Monitor mode - no duration, no auto-stop;
it runs until the operator stops it (or the app's /quit teardown does). The
fleet logger flushes every row, so a stop is just a terminate; the next start's
archive step catches up any unbacked-up segments.

Unlike the serial monitor there is **no COM port and no serial lock** - the
fleet path is WiFi-only, so the #493 orphaned-process failure mode's worst
half (an invisible process holding the port forever) cannot occur here. The
remaining orphan exposure (a process outliving a hard-killed server) is
reviewed in the #588 PR and bounded the same way Monitor's is: visible +
stoppable from the UI, torn down by /quit, and the systemic fix stays with
the maintainer's #493 strategy call.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_FLEET_PY = _HERE / "fleet_logger.py"
_ANALYTICS = _REPO / "tools" / "analytics"
if str(_ANALYTICS) not in sys.path:
    sys.path.insert(0, str(_ANALYTICS))

# Quiet child - no second console window on Windows (the no-terminal rule); 0
# elsewhere (#183) - same posture as MonitorController.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _served_device_count() -> int:
    """How many registered devices have a base_url - the fleet path's existence
    check. 0 = nothing to poll (an honest skip at the collection layer, a clear
    refusal here). Import-guarded: a broken registry reads as an empty fleet."""
    try:
        from device_registry import load_registry

        return len(load_registry().served_devices())
    except Exception:
        return 0


class FleetError(RuntimeError):
    """A rejected fleet request (already running, or no registered devices)."""


class FleetController:
    """Start / stop / status for the fleet logger, single-flight."""

    def __init__(
        self,
        *,
        python: str | None = None,
        fleet_py: str | Path | None = None,
        logdir: str | Path | None = None,
        cadence_s: float | None = None,
        served_count=_served_device_count,
    ) -> None:
        self._python = python or sys.executable
        self._fleet_py = Path(fleet_py) if fleet_py else _FLEET_PY
        self._logdir = logdir
        self._cadence_s = cadence_s
        self._served_count = served_count  # injectable for tests
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._devices = 0

    def start(self) -> dict:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                raise FleetError("fleet logger is already running")
            n = self._served_count()
            if n == 0:
                raise FleetError(
                    "no registered fleet devices (no base_url in the device "
                    "registry) - nothing to poll"
                )
            argv = [self._python, str(self._fleet_py)]
            if self._logdir:
                argv += ["--logdir", str(self._logdir)]
            if self._cadence_s:
                argv += ["--cadence-s", str(self._cadence_s)]
            self._proc = subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
            )
            self._devices = n
            return self._status_locked()

    def stop(self) -> dict:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
                with contextlib.suppress(Exception):
                    self._proc.wait(timeout=5)
            self._proc = None
            self._devices = 0
            return self._status_locked()

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict:
        running = self._proc is not None and self._proc.poll() is None
        return {
            "state": "running" if running else "stopped",
            "devices": self._devices if running else 0,
        }
