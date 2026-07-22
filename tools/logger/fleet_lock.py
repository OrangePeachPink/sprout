"""Cross-process singleton lock for the fleet logger (#493 F2, ADR-0011 kin).

The serial logger cannot be double-started: a COM port opens exactly once, and
the OS refuses a second opener — ``serial_lock.py`` leans on exactly that hard
mutex (its own docstring says so). The **WiFi fleet poller has no such mutex.**
N ``fleet_logger`` processes can each poll the same devices over HTTP and each
write the same rotating CSV per device, interleaving rows into one archive
segment. That is the one genuine data-integrity risk of running collection
unattended overnight: a stale poller left by an earlier session, plus a fresh
start, both writing one file (the exact shape of the #493 orphan incident, but
for the untethered spine, where nothing stops the second writer).

This module supplies the mutex the OS hands serial for free — a real **OS
advisory file lock** on ``logs/.fleet-logger.lock``, taken non-blocking and held
for the process's entire life. A second acquirer is refused, honestly and by
name. The decisive property: **the OS releases the lock automatically when the
holder dies** — clean exit, ``KeyboardInterrupt``, crash, or hard ``kill`` — so a
stale lock file from yesterday's crashed poller is re-acquirable *immediately*.
There is no pid-liveness heuristic and no stale-marker to reap (contrast
serial_lock's ``pid_alive()`` dance, which it needs only because it answers
"who holds the port?" *without* opening it; here holding the lock IS running).

The lock file also carries the holder's pid + start time as plain text at
offset 0, freely readable by another process (the OS lock sits on a sentinel
byte far past EOF, never overlapping the content — Windows byte-range locks are
mandatory, so content and lock must not share bytes). That makes the file both
the mutex and a marker: the #493 identifiability half (``sprout_processes.py``)
and the app's server card can name the live poller from one file.

It lives in ``logs/`` beside ``.serial-owner.json`` — a control dotfile, so the
never-stitch gate (``gather_inputs()`` globs ``logs/*.csv``) never sees it.
"""

from __future__ import annotations

import contextlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
LOCK_NAME = ".fleet-logger.lock"

# Windows byte-range locks are *mandatory* (another process's read of the locked
# region fails), so the OS lock must not sit on any byte the marker occupies.
# Lock a single sentinel byte far past any content the marker will ever write;
# the readable marker lives at offset 0. (POSIX ``flock`` is whole-file advisory,
# so reads never block there — the offset only matters for the Windows path, but
# using it on both keeps the two paths reasoning-identical.)
_LOCK_OFFSET = 1 << 30  # 1 GiB — no marker ever reaches it


def lock_path(lock_dir: str | Path | None = None) -> Path:
    return (Path(lock_dir) if lock_dir else _REPO / "logs") / LOCK_NAME


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _try_os_lock(fd: int) -> bool:
    """Take a non-blocking exclusive OS lock on ``fd``. True if acquired, False
    if another live handle already holds it. Released automatically when the fd
    is closed or the owning process dies — that auto-release is the whole point."""
    if os.name == "nt":
        import msvcrt

        try:
            os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    else:
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False


def _os_unlock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        with contextlib.suppress(OSError):
            os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        with contextlib.suppress(OSError):
            fcntl.flock(fd, fcntl.LOCK_UN)


def _read_marker(fd: int) -> dict | None:
    """The holder's {pid, started_utc} from an already-open fd, or None. Reads at
    offset 0 (never the locked sentinel byte), so it is safe even while another
    process holds the lock — exactly the contention case we need it for."""
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 4096).decode("utf-8").strip()
        return json.loads(raw) if raw else None
    except (OSError, ValueError):
        return None


# #1428: the process exit code a fleet_logger uses when it correctly DECLINED because
# another poller already holds this lock — the deliberate, healthy outcome. Lives here,
# beside the exception that signals it, so the worker (fleet_logger) and its supervisor
# (fleet_control) share one definition instead of two magic numbers. Distinct from 0
# (ran) and from 1 (an unhandled crash), so a decline is legible by exit code alone.
REFUSED_EXIT = 3


class FleetAlreadyRunning(RuntimeError):
    """Raised when a live fleet_logger already holds the singleton lock."""

    def __init__(self, marker: dict | None, path: Path) -> None:
        self.marker = marker or {}
        self.pid = self.marker.get("pid")
        self.started_utc = self.marker.get("started_utc")
        who = f"pid {self.pid}" if self.pid else "an unknown pid"
        since = f" since {self.started_utc}" if self.started_utc else ""
        super().__init__(
            f"a fleet logger is already running ({who}{since}); refusing to start "
            f"a second poller — two writers would interleave one archive (#493). "
            f"Lock: {path}"
        )


class FleetLock:
    """The fleet logger's singleton mutex. Acquire once at process start, hold
    for the whole run, release on exit. ``acquire`` raises ``FleetAlreadyRunning``
    (naming the incumbent's pid) rather than silently letting a second writer in.

    Usable as a context manager or via explicit ``acquire``/``release`` — the
    logger's ``run()`` uses the explicit form so it can turn contention into an
    honest one-line refusal instead of a traceback."""

    def __init__(self, lock_dir: str | Path | None = None) -> None:
        self.path = lock_path(lock_dir)
        self._fd: int | None = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self) -> FleetLock:
        if self._fd is not None:
            return self  # idempotent — already ours
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
        if not _try_os_lock(fd):
            # contended: the incumbent is alive (that is why the lock holds), so
            # its marker at offset 0 is current — read it for an honest message,
            # and DO NOT truncate (leave the incumbent's identity intact).
            marker = _read_marker(fd)
            os.close(fd)
            raise FleetAlreadyRunning(marker, self.path)
        # we own it: stamp our identity at offset 0 for the readers (F1 / the
        # server card / sprout_processes). The sentinel lock byte is untouched.
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(
                fd,
                json.dumps({"pid": os.getpid(), "started_utc": _now_iso()}).encode(
                    "utf-8"
                ),
            )
        except OSError:
            pass  # the mutex is what matters; the marker is a best-effort courtesy
        self._fd = fd
        return self

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        _os_unlock(fd)
        with contextlib.suppress(OSError):
            os.close(fd)
        # best-effort tidy; the OS lock is already released by the close above, so
        # a leftover file is harmless (re-acquirable), never a stale-lock trap.
        with contextlib.suppress(OSError):
            self.path.unlink()

    def __enter__(self) -> FleetLock:
        return self.acquire()

    def __exit__(self, *exc: object) -> None:
        self.release()


def incumbent(lock_dir: str | Path | None = None) -> dict | None:
    """The live fleet logger's {pid, started_utc}, or None if none is running.

    A running holder blocks a probe acquire (so we report it from the marker); a
    free-but-present lock file (stale, owner dead) is re-acquirable, so we take
    and release it and report None. Never resets a device, never opens a port —
    a pure read for the server card / diagnostics."""
    path = lock_path(lock_dir)
    if not path.exists():
        return None
    try:
        fd = os.open(str(path), os.O_RDWR)
    except OSError:
        return None
    try:
        if _try_os_lock(fd):
            _os_unlock(fd)  # it was free (stale) — nobody live is holding it
            return None
        return _read_marker(fd)  # held by a live poller — name it
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)
