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
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_FLEET_PY = _HERE / "fleet_logger.py"
_DEFAULT_LOGDIR = _REPO / "logs"
_ANALYTICS = _REPO / "tools" / "analytics"
if str(_ANALYTICS) not in sys.path:
    sys.path.insert(0, str(_ANALYTICS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))  # sibling fleet_lock

from fleet_lock import REFUSED_EXIT  # noqa: E402  (#1428 — the shared decline code)

# Quiet child - no second console window on Windows (the no-terminal rule); 0
# elsewhere (#183) - same posture as MonitorController.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# A per-device fleet log file: `<device_id>_<YYYYMMDD>_<HHMMSS>.csv` (#582). The
# device_id may itself contain underscores, so match the date/time suffix greedily.
_FLEET_FILE_RE = re.compile(r"^(.+)_\d{8}_\d{6}\.csv$")


def _active_served() -> list:
    """The registered WiFi devices we should actually poll: served (has a base_url)
    AND **active** (#1007) — a retired/paused board is off *by choice* and must never
    be polled or counted as 'not answering' (grill Q2: off-by-choice is not a fault).
    Import-guarded: a broken registry reads as an empty fleet."""
    try:
        from device_registry import load_registry

        return [
            d
            for d in load_registry().served_devices()
            if not getattr(d, "retired", False)
        ]
    except Exception:
        return []


def _served_device_count() -> int:
    """How many ACTIVE served devices exist - the fleet path's existence check and the
    honest ``configured`` total (#1007: excludes retired). 0 = nothing to poll."""
    return len(_active_served())


def _served_map() -> dict:
    """{active served canonical device_id: previous_ids} — the answering matcher (#812),
    active-only (#1007) so a retired board is never counted as not-answering."""
    return {d.device_id: d.previous_ids for d in _active_served()}


def count_answering(
    logdir, served: dict, window_s: float, *, now: float | None = None
) -> int:
    """Distinct SERVED devices that WROTE a fleet log within ``window_s`` — the
    honest **answering** count (#812), vs the configured total. A configured device
    that never responds (the unplugged yellow-C5) has no fresh file and is NOT
    counted, so it stays visible instead of padding a healthy-looking total.
    ``served`` maps each served canonical id -> its ``previous_ids``; a file's
    device-id prefix is matched through that alias, so a renamed board still counts.
    File mtime is the recency signal (light: no re-parse per status poll)."""
    now = now if now is not None else time.time()
    alias: dict[str, str] = {}
    for cid, prevs in served.items():
        alias[cid] = cid
        for p in prevs or ():
            alias.setdefault(p, cid)
    fresh: set[str] = set()
    try:
        files = list(Path(logdir).glob("*.csv"))
    except OSError:
        return 0
    for f in files:
        m = _FLEET_FILE_RE.match(f.name)
        if not m:
            continue
        canon = alias.get(m.group(1))
        if canon is None:
            continue  # not a served device (e.g. a stray/legacy file)
        try:
            if now - f.stat().st_mtime <= window_s:
                fresh.add(canon)
        except OSError:
            continue
    return len(fresh)


class FleetError(RuntimeError):
    """A rejected fleet request (already running, or no registered devices)."""


# #968: the poller's stderr goes to a CAPPED file, never DEVNULL — a crash leaves its
# last words behind. Truncated to the tail when it bloats.
_WORKER_LOG = "fleet_worker.log"
_LOG_CAP_BYTES = 256 * 1024


class FleetController:
    """Start / stop / status for the fleet logger, single-flight, **supervised**.

    #1004's law (the maintainer's, verbatim: "be a damn logger and never stop"): once
    collection is asserted ON, a worker that exits for ANY reason is restarted
    automatically (bounded backoff, loud log, honest status during the gap) — a give-up
    of one collection half never stops the other. Only an explicit Stop, or repeated
    crashes inside the backoff window, ends it — and then it says WHY (#968 parity with
    #941). A double-start on a healthy worker is idempotent: it never restarts it."""

    def __init__(
        self,
        *,
        python: str | None = None,
        fleet_py: str | Path | None = None,
        logdir: str | Path | None = None,
        cadence_s: float | None = None,
        served_count=_served_device_count,
        answering_fn=None,
        max_restarts: int = 5,
        restart_window_s: float = 60.0,
        supervise_interval_s: float = 1.0,
        backoff_s: float = 1.5,
    ) -> None:
        self._python = python or sys.executable
        self._fleet_py = Path(fleet_py) if fleet_py else _FLEET_PY
        self._logdir = logdir
        self._cadence_s = cadence_s
        self._served_count = served_count  # injectable for tests
        # #812: how many configured devices are actually answering; injectable.
        self._answering_fn = answering_fn or self._default_answering
        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._devices = 0
        # #1004 guard 3 supervision state
        self._want_running = False
        self._supervisor: threading.Thread | None = None
        self._give_up_reason: str | None = None
        # #1428: a clean (exit-0) stand-down is a HEALTHY outcome, not a crash — the
        # #493 double-writer refusal is the case. Held separately from give_up_reason
        # so status can read calm ("another logger owns it") instead of a failure.
        self._benign_note: str | None = None
        self._restarts: list[float] = []
        self._log_fh = None
        self._max_restarts = max_restarts
        self._restart_window_s = restart_window_s
        self._supervise_interval_s = supervise_interval_s
        self._backoff_s = backoff_s

    # ------------------------------- spawn + log ------------------------------ #
    def _open_log(self):
        p = Path(self._logdir or _DEFAULT_LOGDIR) / _WORKER_LOG
        with contextlib.suppress(Exception):
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists() and p.stat().st_size > _LOG_CAP_BYTES:
                tail = p.read_bytes()[-(_LOG_CAP_BYTES // 2) :]
                p.write_bytes(b"...[fleet_worker.log truncated]...\n" + tail)
        try:
            return open(p, "ab", buffering=0)
        except OSError:
            return subprocess.DEVNULL

    def _log_hint(self) -> str:
        """#1428: point at the worker log ONLY when it can actually hold the answer.
        The give-up message used to cite ``logs/fleet_worker.log`` unconditionally; on
        the maintainer's machine that file was 0 bytes and ten days stale, so the
        diagnostic confidently named a file structurally incapable of explaining the
        failure. A diagnostic that names an empty file is worse than one that names
        none — it sends the reader somewhere with nothing to find."""
        p = Path(self._logdir or _DEFAULT_LOGDIR) / _WORKER_LOG
        try:
            if p.is_file() and p.stat().st_size > 0:
                return f"see logs/{_WORKER_LOG}"
        except OSError:
            pass
        return (
            f"logs/{_WORKER_LOG} is empty — the worker died before writing; "
            "check the server console"
        )

    def _spawn_locked(self) -> None:
        argv = [self._python, str(self._fleet_py)]
        if self._logdir:
            argv += ["--logdir", str(self._logdir)]
        if self._cadence_s:
            argv += ["--cadence-s", str(self._cadence_s)]
        self._log_fh = self._open_log()
        self._proc = subprocess.Popen(
            argv,
            # #1428: BOTH streams to the capped log. #968 sent only stderr here; the
            # worker's double-writer refusal ("already running (pid N)") prints to
            # STDOUT, so it went to DEVNULL and the give-up message then cited an empty
            # file. Capturing stdout too is why the refusal now survives to be read.
            stdout=self._log_fh,
            stderr=self._log_fh,
            creationflags=_NO_WINDOW,
        )

    # --------------------------------- control -------------------------------- #
    def start(self) -> dict:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                # #1004 guard 1: idempotent — a start on a HEALTHY worker never restarts
                # it (that collision is exactly what killed the worker the maintainer
                # watched). Re-assert intent and return the running status, no-op.
                self._want_running = True
                return self._status_locked()
            n = self._served_count()
            if n == 0:
                raise FleetError(
                    "no registered fleet devices (no base_url in the device "
                    "registry) - nothing to poll"
                )
            self._want_running = True
            self._give_up_reason = None
            self._benign_note = None  # #1428: a fresh start clears the stand-down
            self._restarts.clear()
            self._spawn_locked()
            self._devices = n
            self._ensure_supervisor_locked()
            return self._status_locked()

    def _ensure_supervisor_locked(self) -> None:
        if self._supervisor is not None and self._supervisor.is_alive():
            return
        self._supervisor = threading.Thread(
            target=self._supervise, name="fleet-supervisor", daemon=True
        )
        self._supervisor.start()

    def _supervise(self) -> None:
        """The watchdog (#1004 guard 3). Sleeps OUTSIDE the lock; acquires it only to
        check + respawn, so it never blocks start/stop/status."""
        while True:
            time.sleep(self._supervise_interval_s)
            respawn = False
            with self._lock:
                if not self._want_running:
                    return
                if self._proc is not None and self._proc.poll() is None:
                    continue  # healthy — keep watching
                # #1428: the worker has exited. A REFUSAL is not a crash. fleet_logger
                # returns REFUSED_EXIT when it declined because another poller already
                # owns the archive (#493) — the deliberate, healthy outcome. Restarting
                # it just makes it decline again until the crash budget is spent: the
                # "crashed 5x" loop the maintainer watched against an empty log while
                # logging was in fact live. A refusal stands the supervisor down as
                # HEALTHY, spends no restart budget, and never becomes a give-up. Any
                # other exit (0 or a crash code) keeps #1004's "restart on any exit"
                # law below — only the refusal is special.
                rc = self._proc.returncode if self._proc is not None else None
                if rc == REFUSED_EXIT:
                    self._benign_note = (
                        "fleet worker declined — another logger already owns the "
                        f"archive (its pid is in logs/{_WORKER_LOG}). Not a crash; "
                        "stood down. Logging continues via the existing one."
                    )
                    self._give_up_reason = None
                    _loud(f"fleet supervision: {self._benign_note}")
                    self._want_running = False
                    self._proc = None
                    return
                now = time.monotonic()
                self._restarts = [
                    t for t in self._restarts if now - t <= self._restart_window_s
                ]
                if len(self._restarts) >= self._max_restarts:
                    self._give_up_reason = (
                        f"fleet worker crashed {len(self._restarts)}x in "
                        f"{int(self._restart_window_s)}s — {self._log_hint()}"
                    )
                    _loud(f"fleet supervision: giving up — {self._give_up_reason}")
                    self._want_running = False
                    self._proc = None
                    return
                self._restarts.append(now)
                _loud(
                    f"fleet supervision: worker exited — restarting "
                    f"(#{len(self._restarts)}, be a damn logger)"
                )
                respawn = True
            if respawn:
                time.sleep(self._backoff_s)  # bounded backoff, off the lock
                with self._lock:
                    if not self._want_running:
                        return
                    if self._proc is None or self._proc.poll() is not None:
                        with contextlib.suppress(Exception):
                            self._spawn_locked()

    def stop(self) -> dict:
        with self._lock:
            self._want_running = False  # tell the supervisor to stand down
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()
                with contextlib.suppress(Exception):
                    self._proc.wait(timeout=5)
            self._proc = None
            self._devices = 0
            self._give_up_reason = None
            self._benign_note = None  # #1428
            if self._log_fh not in (None, subprocess.DEVNULL):
                with contextlib.suppress(Exception):
                    self._log_fh.close()
            return self._status_locked()

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def _default_answering(self) -> int:
        # a device answering every `cadence_s` (default 30 s) touches its file well
        # within this window; 3x cadence (>= 90 s) tolerates a slow sweep / one blip.
        window = max(90.0, 3.0 * (self._cadence_s or 30.0))
        return count_answering(self._logdir or _DEFAULT_LOGDIR, _served_map(), window)

    def _status_locked(self) -> dict:
        running = self._proc is not None and self._proc.poll() is None
        configured = self._devices if running else 0
        # #812: report configured vs ANSWERING honestly — a non-responding
        # configured device (unplugged) is visible, never absorbed into the total.
        answering = min(self._answering_fn(), configured) if running else 0
        out = {
            "state": "running" if running else "stopped",
            "configured": configured,
            "answering": answering,
            "devices": configured,  # back-compat alias (was the configured count)
        }
        # #968: a self-stop surfaces WHY (parity with #941's serial give-up), never a
        # bare "stopped" — the fleet half was previously silent on death.
        if not running and self._give_up_reason:
            out["give_up_reason"] = self._give_up_reason
        # #1428: a clean stand-down reads as healthy, never as a crash. It is NOT a
        # give_up_reason (that renders as failure); a separate calm field the Monitor
        # can show as "another logger active" rather than "stopped — crashed".
        if not running and self._benign_note:
            out["benign_note"] = self._benign_note
            out["healthy_standdown"] = True
        return out


def _loud(msg: str) -> None:
    with contextlib.suppress(Exception):
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()
