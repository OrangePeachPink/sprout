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
