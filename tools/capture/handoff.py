#!/usr/bin/env python3
"""Monitor->Experiment automatic COM6 handoff (#129).

When a **serial** experiment starts while the Monitor logger is running, the operator
must not have to stop logging or juggle the port by hand. This orchestrates it: stop the
monitor (frees COM6), start the experiment, and **resume the monitor when the experiment
ends** (a bounded capture, or an operator stop). Pure orchestration over the two
controllers (``CaptureController`` + ``MonitorController``) so it is unit-testable with
fakes - serve.py just calls ``start_experiment`` for every ``/capture/start``.

Safety rests on the existing serial mutex (#64/#85): the monitor's advisory lock is gone
once it is stopped (a stale lock is ignored by the dead-pid check), and the experiment
clears its own lock on exit, so only one process ever holds COM6 across the handoff.
"""

from __future__ import annotations

import contextlib
import threading
import time


def start_experiment(monitor, capture, *, poll_s: float = 1.0, **start_kwargs) -> dict:
    """Start a capture, doing the Monitor->Experiment handoff when it's a **serial**
    start and the monitor is logging. Returns the capture's start result with an added
    ``handoff`` flag (True if logging was paused for this experiment)."""
    resume_port = None
    if start_kwargs.get("source") == "serial":
        mon = monitor.status()
        if mon.get("state") == "running":
            # remember the logging port, then free COM6 for the experiment.
            resume_port = mon.get("port") or start_kwargs.get("port")
            monitor.stop()
    try:
        result = capture.start(**start_kwargs)
    except Exception:
        # the experiment didn't start - put the logger back rather than leave it down.
        if resume_port is not None:
            with contextlib.suppress(Exception):
                monitor.start(port=resume_port)
        raise
    if resume_port is not None:
        _resume_when_done(monitor, capture, resume_port, poll_s)
    out = dict(result)
    out["handoff"] = resume_port is not None
    return out


def _resume_when_done(monitor, capture, port: str, poll_s: float) -> None:
    """Background watcher: resume logging on ``port`` once the experiment stops."""

    def _watch() -> None:
        while True:
            if capture.status().get("state") != "running":
                with contextlib.suppress(Exception):
                    monitor.start(port=port)
                return
            time.sleep(poll_s)

    threading.Thread(target=_watch, daemon=True).start()
