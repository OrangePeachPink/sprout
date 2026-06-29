"""Experiment-capture control plane (Epic 1, issue #66) — ADR-0011 Option A.

`serve.py` owns the operator control API and **launches a bounded capture
process**; this module is that launch/lifecycle logic, kept out of the HTTP layer
so it is testable on its own. It does **not** touch the serial port or the data —
the capture subprocess does (it owns the port + writes the isolated file).

What this gives the control API:

* **start** — single-flight (one capture at a time), validated/​sanitized inputs,
  then launch `experiment_capture.py` as a child process;
* **stop** — a *cooperative* stop: drop a `.stop` flag the capture process polls,
  so it exits through its own cleanup (closing the port + clearing the lock),
  with an abrupt `terminate()` only as a fallback;
* **status** — poll the child and report `idle / running / done / error`, with the
  finished run's manifest summary.

The **serial source + the port mutual-exclusion pre-check** (`serial_lock.
current_owner()`) land with the #75 serial integration; this slice proves the
seam end-to-end with the device-free synthetic source. The hook is marked below.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_CAPTURE_PY = _HERE / "experiment_capture.py"

# Spawn the capture as a quiet child of serve.py - no extra console window on
# Windows; 0 elsewhere (#183).
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import serial_lock  # noqa: E402  (sibling leaf — the #64 advisory-lock contract)

# A safe path/identifier token — letters, digits, dot, dash, underscore; no "..",
# no slashes. experiment_id / subject become a folder name, so this is the guard
# against path traversal from a control-API request.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SLUG_SUB = re.compile(r"[^A-Za-z0-9._-]+")  # runs of folder-unsafe chars -> "_"
_SOURCES = ("synthetic", "serial")  # serial = real device, gated by the pre-check


class ControlError(ValueError):
    """A rejected control request (bad input, busy, unavailable source)."""


def _safe_token(value: object, field: str) -> str:
    s = str(value).strip()
    if ".." in s or not _TOKEN_RE.match(s):
        raise ControlError(f"invalid {field}: {value!r} (use letters/digits/.-_)")
    return s


def _slugify(value: object, field: str) -> str:
    """Folder/header-safe token from a human subject ('open bench' -> 'open_bench'):
    runs of unsafe chars collapse to '_', leading/trailing separators are trimmed,
    and the result is length-bounded so a long descriptive subject still yields a
    filesystem-safe, reasonable folder name (#336). An already-valid token is
    returned unchanged."""
    slug = _SLUG_SUB.sub("_", str(value).strip()).strip("._-")
    slug = slug[:48].strip("._-")  # bound the folder/id length (#336)
    if not slug or ".." in slug or not _TOKEN_RE.match(slug):
        raise ControlError(f"invalid {field}: {value!r} (need a letter or digit)")
    return slug


def _label_value(value: object, field: str) -> str:
    """A human probe label kept for display ('s1 - recheck, redried') (#336).

    The label *key* stays a safe token (it's the join key); the *value* is for
    humans, so spaces and common punctuation are fine. It must stay CSV/JSON-safe
    (no comma, no control chars) and bounded. Empty falls back to '' (caller may
    default to the sensor id)."""
    s = str(value).strip()
    if "," in s or any(ord(c) < 32 for c in s):
        raise ControlError(f"invalid {field}: {value!r} (no commas or control chars)")
    return s[:48]


def _subject_title(value: object, field: str) -> str:
    """The human-entered title, kept for display - spaces are fine, but it must stay
    CSV/JSON-safe (no comma, no control chars) and bounded."""
    s = str(value).strip()
    if not s:
        raise ControlError(f"{field} must not be empty")
    if "," in s or any(ord(c) < 32 for c in s):
        raise ControlError(f"invalid {field}: {value!r} (no commas or control chars)")
    return s[:80]


def _bounded_float(value: object, lo: float, hi: float, field: str) -> float:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ControlError(f"{field} must be a number, got {value!r}") from exc
    if not (lo <= f <= hi):
        raise ControlError(f"{field} {f} out of range [{lo}, {hi}]")
    return f


def _utc_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


class CaptureController:
    """Single-flight launcher + lifecycle for the experiment capture process."""

    def __init__(
        self,
        *,
        experiments_dir: str | Path | None = None,
        python: str | None = None,
        capture_py: str | Path | None = None,
        lock_dir: str | Path | None = None,
    ) -> None:
        self._experiments_dir = (
            Path(experiments_dir) if experiments_dir else _REPO / "experiments"
        )
        self._python = python or sys.executable
        self._capture_py = Path(capture_py) if capture_py else _CAPTURE_PY
        self._lock_dir = lock_dir  # where the serial port pre-check reads the lock
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._meta: dict | None = None

    # -- queries ----------------------------------------------------------- #
    def status(self) -> dict:
        with self._lock:
            return self._status_locked()

    def _live_rows(self, eid: str) -> int:
        """Data rows written to the capture so far - cheap (bounded captures), and the
        writer flushes every row, so it climbs live. -1 of the non-comment lines drops
        the column header."""
        csv_path = self._experiments_dir / eid / f"{eid}.csv"
        try:
            with csv_path.open("r", encoding="utf-8") as f:
                n = sum(1 for line in f if line and not line.startswith("#"))
        except OSError:
            return 0
        return max(0, n - 1)

    def _status_locked(self) -> dict:
        if self._proc is None or self._meta is None:
            return {"state": "idle"}
        rc = self._proc.poll()
        out = dict(self._meta)
        if rc is None:
            out["state"] = "running"
            out["rows"] = self._live_rows(out["experiment_id"])  # live progress (#162)
            return out
        out["exit_code"] = rc
        out["state"] = "done" if rc == 0 else "error"
        manifest = self._experiments_dir / out["experiment_id"] / "manifest.json"
        if manifest.exists():
            with contextlib.suppress(json.JSONDecodeError, OSError):
                m = json.loads(manifest.read_text(encoding="utf-8"))
                out["stopped_by"] = m.get("stopped_by")
                out["transport"] = m.get("transport")
        return out

    # -- commands ---------------------------------------------------------- #
    def start(
        self,
        *,
        subject: str,
        rate_s: float,
        duration_s: float,
        labels: dict | None = None,
        experiment_id: str | None = None,
        source: str = "synthetic",
        port: str | None = None,
    ) -> dict:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                raise ControlError("a capture is already running (single-flight)")
            if source not in _SOURCES:
                raise ControlError(f"unknown source {source!r}; use one of {_SOURCES}")
            if source == "serial":
                if not port:
                    raise ControlError("serial source needs a 'port' (e.g. COM6)")
                # the serial mutex: refuse rather than open (and reset) a held device.
                # current_owner reads the advisory lock without opening; the OS
                # exclusive open is the hard backstop if a lock is missing.
                owner = serial_lock.current_owner(self._lock_dir)
                if owner:
                    raise ControlError(
                        f"port held by {owner.get('mode')} (pid {owner.get('pid')}) "
                        "— stop the monitor first"
                    )
            # A human subject ('open bench') is accepted: the slug ('open_bench') is the
            # folder/CSV-header-safe token; the title keeps the human form for display.
            subject_slug = _slugify(subject, "subject")
            subject_title = _subject_title(subject, "subject")
            rate_s = _bounded_float(rate_s, 0.05, 3600.0, "rate_s")
            duration_s = _bounded_float(duration_s, 1.0, 86400.0, "duration_s")
            eid = (
                _safe_token(experiment_id, "experiment_id")
                if experiment_id
                else f"{_utc_stamp()}_{subject_slug}"
            )

            exp_dir = self._experiments_dir / eid
            exp_dir.mkdir(parents=True, exist_ok=True)
            stop_file = exp_dir / ".stop"
            with contextlib.suppress(FileNotFoundError):
                stop_file.unlink()  # a fresh run starts un-stopped

            cmd = [
                self._python,
                str(self._capture_py),
                "--source",
                source,
                "--subject",
                subject_slug,
                "--title",
                subject_title,
                "--experiment-id",
                eid,
                "--rate-s",
                str(rate_s),
                "--duration-s",
                str(duration_s),
                "--out-dir",
                str(self._experiments_dir),
                "--stop-file",
                str(stop_file),
            ]
            for key, val in (labels or {}).items():
                k = _safe_token(key, "label key")  # the stable join key (sensor id)
                v = _label_value(val, "label value")  # the human label (#336)
                if v:  # skip empties; the capture defaults an unlabeled probe to its id
                    cmd += ["--label", f"{k}={v}"]
            if port:
                cmd += ["--port", _safe_token(port, "port")]

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_NO_WINDOW,
            )
            self._proc = proc
            self._meta = {
                "experiment_id": eid,
                "subject": subject_slug,
                "title": subject_title,
                "rate_s": rate_s,
                "duration_s": duration_s,
                "source": source,
                "pid": proc.pid,
                "stop_file": str(stop_file),
                "started_utc": _utc_iso(),
            }
            return {**self._meta, "state": "running"}

    def stop(self, *, timeout_s: float = 5.0) -> dict:
        with self._lock:
            if self._proc is None or self._meta is None:
                return self._status_locked()  # nothing started -> just report
            if self._proc.poll() is not None:  # already exited -> nothing to stop
                return self._status_locked()
            proc = self._proc
            Path(self._meta["stop_file"]).write_text("stop", encoding="utf-8")
        try:  # wait for the cooperative stop outside the lock
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            proc.terminate()  # fallback: the process didn't honor the flag
            with contextlib.suppress(subprocess.TimeoutExpired):
                proc.wait(timeout=2.0)
        with self._lock:
            return self._status_locked()
