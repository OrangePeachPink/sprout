"""Advisory serial-port ownership lock (ADR-0011 #64 — the port handoff).

A single JSON file (`logs/.serial-owner.json`) lets the control plane answer
*"who holds the port?"* **without opening it** — opening pulses DTR and resets
the ESP32, so we never want to open merely to ask. The **OS exclusive open is the
hard mutex** (a second opener is refused by the OS); this advisory lock only
avoids a needless reset-to-ask and surfaces a *stale* lock left by a crashed
owner. Both the monitor logger and the experiment capture write this same schema
when they open the port (the schema is the cross-lane contract agreed on #64).

It lives in `logs/` by design (shared with the monitor) — it is a control file,
not telemetry: a dotfile `.json`, so the never-stitch gate (`gather_inputs()`
globs `logs/*.csv`) never sees it.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
LOCK_NAME = ".serial-owner.json"


def lock_path(lock_dir: str | Path | None = None) -> Path:
    return (Path(lock_dir) if lock_dir else _REPO / "logs") / LOCK_NAME


def pid_alive(pid: object) -> bool:
    """True if ``pid`` names a currently-running process (cross-platform)."""
    try:
        pid = int(pid)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        synchronize = 0x00100000
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return False
        # non-signaled (WAIT_TIMEOUT 0x102) => running; signaled (0) => exited
        rc = kernel32.WaitForSingleObject(handle, 0)
        kernel32.CloseHandle(handle)
        return rc == 0x102
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def write_lock(
    port: str | None,
    mode: str,
    *,
    lock_dir: str | Path | None = None,
    pid: int | None = None,
) -> dict:
    """Claim the port in the advisory lock; returns the written record."""
    path = lock_path(lock_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
    )
    record = {
        "pid": pid if pid is not None else os.getpid(),
        "mode": mode,
        "port": port,
        "opened_utc": now,
        # #1554: WHICH logger, not just "a logger". At the bench (2026-07-25) an
        # orphaned plants_logger from a DX *worktree* held COM4, and the maintainer had
        # to identify and stop the right process by hand — while deliberately NOT
        # touching the production Wi-Fi fleet logger. Several loggers can exist on this
        # machine at once, so a lock that says only "pid 12345, monitor" cannot answer
        # the one question that matters: is this the one I care about?
        #
        # `origin` is the invoking checkout's directory name (the worktree), which is
        # what distinguishes them in practice — deliberately the BASENAME, not the full
        # path: this string is rendered in-app and lands in screenshots, and a full path
        # carries the home directory (§0.8.1's personal-info fence, same reasoning as
        # A7's USB-id drop).
        "origin": Path.cwd().name,
    }
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def read_lock(lock_dir: str | Path | None = None) -> dict | None:
    """The raw lock record, or None if there's no (readable) lock."""
    path = lock_path(lock_dir)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_lock(lock_dir: str | Path | None = None) -> None:
    """Release the port (best-effort); safe to call when no lock exists."""
    with contextlib.suppress(FileNotFoundError):
        lock_path(lock_dir).unlink()


def current_owner(lock_dir: str | Path | None = None) -> dict | None:
    """The **live** owner of the port, or None.

    None means free *or* a stale lock from a crashed owner (the OS already freed
    the port). The control plane uses this to refuse a start with an honest
    message without ever opening (and resetting) the device.
    """
    lock = read_lock(lock_dir)
    if lock and pid_alive(lock.get("pid")):
        return lock
    return None


def owner_status(lock_dir: str | Path | None = None) -> dict:
    """Full owner status for the UI (#330): present / live / stale + the lock fields.

    - ``present``: a lock file exists.
    - ``live``:    its pid is still running (the port is genuinely held).
    - ``stale``:   a lock exists but its owner is gone (OS freed the port; the
                   marker is just litter a crashed/hard-killed owner left behind).
    """
    lock = read_lock(lock_dir)
    if lock is None:
        return {
            "present": False,
            "live": False,
            "stale": False,
            "explain": "No one is holding the serial port.",
        }
    live = pid_alive(lock.get("pid"))
    return {
        "present": True,
        "live": live,
        "stale": not live,
        "pid": lock.get("pid"),
        "mode": lock.get("mode"),
        "port": lock.get("port"),
        "opened_utc": lock.get("opened_utc"),
        # #1554: a pre-#1554 lock has no origin — honest None, never a guess at which
        # checkout wrote it (ADR-0028). The sentence below degrades with it.
        "origin": lock.get("origin"),
        "explain": explain_owner(lock, live),
    }


def explain_owner(lock: dict, live: bool) -> str:
    """One sentence the surface renders verbatim: who holds the port, and what to do.

    The lock has always known this; it just never said it. "Port busy" sent the
    maintainer to Task Manager to work out *which* of several loggers was hers to stop —
    at her own bench, on a stray worktree process, while a production fleet logger was
    also running and must not be touched."""
    who = f"pid {lock.get('pid')}"
    origin = lock.get("origin")
    if origin:
        who += f", started from {origin}"
    mode = lock.get("mode") or "a logger"
    port = lock.get("port") or "the serial port"
    if not live:
        return (
            f"A leftover marker from {mode} ({who}) — that process is gone, so "
            f"{port} is already free. Safe to clear."
        )
    return (
        f"{mode} ({who}) is using {port} right now. Stop that one to free the port — "
        "clearing the marker would not release it, and another opener would reset the "
        "board."
    )


def clear_if_stale(lock_dir: str | Path | None = None) -> dict:
    """Clear the marker **only if its owner is dead** — never free a live port (#330).

    Returns ``{"cleared": bool, "reason": str}``. Refusing to clear a live lock is
    the safety: a real process still holds the port, so removing the marker would
    invite a second opener (and a device reset)."""
    status = owner_status(lock_dir)
    if not status["present"]:
        return {"cleared": False, "reason": "no lock present"}
    if status["live"]:
        return {
            "cleared": False,
            # #1554: the refusal now NAMES the owner and says what to do instead —
            # this is the message the bench case needed. Refusing stays correct: the
            # port is genuinely held, and clearing the marker would not free it.
            "reason": status.get("explain"),
        }
    clear_lock(lock_dir)
    return {"cleared": True, "reason": "stale lock removed"}
