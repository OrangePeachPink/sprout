#!/usr/bin/env python3
"""serve.py-side control of Monitor mode (the always-on logger), mirroring the
experiment ``CaptureController`` (#66/#81). serve.py owns the lifecycle; the spawned
logger owns the serial port and writes the advisory monitor lock (#64/#83). All calls
are localhost-gated by serve.py.

Monitor mode is *continuous* (append-forever to ``logs/``), so unlike a bounded capture
there is no duration / auto-stop - it runs until the operator stops it (or the app does,
during a Monitor->Experiment handoff). The logger flushes every row, so a stop is just a
terminate; the next start's archive step catches up any unbacked-up segments.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_LOGGER_PY = _HERE / "plants_logger.py"

# Spawn the logger as a quiet child of serve.py - no second console window on Windows
# (the Monitor card promises "no terminal"); 0 elsewhere (#183).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# serial_lock (the #64 advisory-lock contract) lives in the capture leaf.
_CAPTURE_DIR = _REPO / "tools" / "capture"
if str(_CAPTURE_DIR) not in sys.path:
    sys.path.insert(0, str(_CAPTURE_DIR))
import serial_lock  # noqa: E402  (sibling leaf)


class MonitorError(RuntimeError):
    """A rejected monitor request (already running, or the port is held)."""


class MonitorController:
    """Start / stop / status for the monitor logger, single-flight."""

    def __init__(
        self,
        *,
        python: str | None = None,
        logger_py: str | Path | None = None,
        logdir: str | Path | None = None,
        lock_dir: str | Path | None = None,
    ) -> None:
        self._python = python or sys.executable
        self._logger_py = Path(logger_py) if logger_py else _LOGGER_PY
        self._logdir = logdir
        self._lock_dir = lock_dir
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._port: str | None = None

    def start(self, *, port: str | None = None) -> dict:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                raise MonitorError("monitor is already running")
            # The serial mutex: refuse to start while ANY live owner holds the port
            # (#330). A stale lock (dead owner) is ignored by current_owner(), so it
            # never blocks a legitimate start — only a truly live holder does.
            owner = serial_lock.current_owner(self._lock_dir)
            if owner:
                raise MonitorError(
                    f"port held by {owner.get('mode')} (pid {owner.get('pid')}) "
                    "- stop it first"
                )
            argv = [self._python, str(self._logger_py)]
            if port:
                argv += ["--port", port]
            if self._logdir:
                argv += ["--logdir", str(self._logdir)]
            self._proc = subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
            )
            self._port = port
            return self._status_locked()

    def stop(self) -> dict:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
                with contextlib.suppress(Exception):
                    self._proc.wait(timeout=5)
            self._proc = None
            self._port = None
            # Clear the monitor's advisory marker (#330). On Windows terminate() is a
            # hard kill, so the logger's own clean-stop release never runs and the
            # marker goes stale. serve.py knows the monitor is stopped, so it clears
            # it here — but ONLY a monitor-owned marker, never an experiment's lock.
            with contextlib.suppress(Exception):
                lock = serial_lock.read_lock(self._lock_dir)
                if lock is not None and lock.get("mode") == "monitor":
                    serial_lock.clear_lock(self._lock_dir)
            return self._status_locked()

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> dict:
        running = self._proc is not None and self._proc.poll() is None
        return {
            "state": "running" if running else "stopped",
            "port": self._port if running else None,
        }
