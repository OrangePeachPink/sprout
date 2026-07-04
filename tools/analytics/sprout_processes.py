#!/usr/bin/env python3
"""Find live Sprout-spawned child processes by command line (#493, identifiability).

`plants_logger.py` (Monitor mode), `experiment_capture.py` (bounded captures), and
`fleet_logger.py` (the untethered WiFi poller, #582) are spawned headless
(``CREATE_NO_WINDOW``) with a generic ``python.exe``/``pythonw.exe`` name (control.py
/ monitor_control.py / fleet_control.py) - by design, so no extra console window
appears. The cost: if a session's window/browser tab is closed without an explicit
"Stop server" click, the child keeps running with **nothing visible in Task
Manager** to identify it as Sprout's without inspecting each process's command-line
arguments - exactly what a live incident needed OS-forensics (``Win32_Process``) to
diagnose (#493). The fleet poller especially: WiFi has no COM port to reveal it, so
before #493 F2 gave it a named lock file, a stray one was fully invisible.

This formalizes that diagnostic into a real, testable command: query the OS process
table for any `python(w).exe` whose command line names `plants_logger`,
`experiment_capture`, or `fleet_logger`, and report each one's PID + role, so "is
anything of mine still running, and what is it" is one command instead of a forensic
investigation.

Scope (see #493's discussion): this is the **identifiability** half of that issue.
It does not stop, kill, or manage anything - it only reports, so the operator (or
BENCH_PREFLIGHT.md's existing `Stop-Process` step) can act on accurate information.
The **auto-shutdown-on-idle** half of #493 is deliberately not built here: it
would conflict with Monitor mode's documented "runs until the operator stops it -
no auto-stop" design (monitor_control.py) - see the PR/issue for that open question.
"""

from __future__ import annotations

import json
import subprocess
import sys

_MARKERS = ("plants_logger", "experiment_capture", "fleet_logger")


def _classify(command: str) -> str | None:
    """Role from a command line, or None if it doesn't name a Sprout child."""
    if "plants_logger" in command:
        return "monitor"
    if "experiment_capture" in command:
        return "capture"
    if "fleet_logger" in command:
        return "fleet"  # the untethered WiFi poller (#582), now discoverable (#493 F1)
    return None


def _windows_raw(timeout_s: float = 10.0) -> list[dict]:
    """The live python(w).exe processes on Windows, via the same CIM query
    BENCH_PREFLIGHT.md's manual recipe uses - {pid, command} per process."""
    ps = (
        "Get-CimInstance Win32_Process "
        "-Filter \"Name='python.exe' or Name='pythonw.exe'\" | "
        "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
    )
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    text = out.stdout.strip()
    if not text:
        return []
    parsed = json.loads(text)
    rows = [parsed] if isinstance(parsed, dict) else parsed
    return [
        {"pid": r.get("ProcessId"), "command": r.get("CommandLine") or ""}
        for r in rows
        if isinstance(r, dict) and r.get("ProcessId") is not None
    ]


def _posix_raw(timeout_s: float = 10.0) -> list[dict]:
    """The live process table on POSIX, via ``ps`` - {pid, command} per process."""
    out = subprocess.run(
        ["ps", "-eo", "pid,args"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    rows = []
    for line in out.stdout.splitlines()[1:]:  # skip the header row
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        rows.append({"pid": int(parts[0]), "command": parts[1]})
    return rows


def list_sprout_processes(raw_query=None) -> list[dict]:
    """Live Sprout-spawned processes (Monitor logger / Experiment capture).

    Each entry is ``{pid, role, command}``. ``raw_query`` is injectable (a callable
    returning ``[{"pid": int, "command": str}, ...]``) for tests; it defaults to the
    real platform query (PowerShell CIM on Windows, ``ps`` on POSIX). Never raises -
    an unavailable/failing platform query degrades to an empty list, since this is a
    diagnostic aid, not a safety-critical check."""
    query = raw_query or (_windows_raw if sys.platform == "win32" else _posix_raw)
    try:
        raw = query()
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    found = []
    for row in raw:
        role = _classify(row.get("command") or "")
        if role:
            found.append({"pid": row["pid"], "role": role, "command": row["command"]})
    return found


def _report(procs: list[dict]) -> str:
    if not procs:
        return "no live Sprout-spawned processes found."
    lines = [f"{len(procs)} live Sprout-spawned process(es):"]
    for p in procs:
        lines.append(f"  pid {p['pid']:<8} {p['role']:<8} {p['command']}")
    lines.append("")
    lines.append(
        "Not one you expect running? Stop it: powershell -Command "
        '"Stop-Process -Id <pid> -Force"'
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    del argv  # no arguments today; kept for a future --json/--kill
    print(_report(list_sprout_processes()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
