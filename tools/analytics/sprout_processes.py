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
import re
import subprocess
import sys

_MARKERS = ("plants_logger", "experiment_capture", "fleet_logger")

# #1392: the dashboard server is NOT a spawned child, so it was correctly absent from
# the collector list above - and that correctness read as a false all-clear. DX hit a
# server stuck in the #972 stopping state (port bound, answering 503) and asked the
# documented diagnostic what was live; it answered "no live Sprout-spawned processes
# found", which is true of children and reads as "nothing of Sprout's is running".
#
# Reported through a SEPARATE function rather than by widening the collector list, for
# two reasons. The server is not a collector, and #691's false "4 zombie collectors"
# came from exactly this kind of category blur. And `collection.py` (DX's surface)
# consumes list_sprout_processes() treating every row as a collector - widening it here
# would push a server row into another lane's output as a side effect of a bug fix.
#
# Matched as a path component, never as a substring: this directory holds test_serve.py,
# test_serve_stop.py and six more, so a plain "serve.py" in the command line would
# report a running pytest as the live server.
_SERVER_RE = re.compile(r"(?:^|[\\/\s])serve\.py(?:\s|$)")


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
    BENCH_PREFLIGHT.md's manual recipe uses - {pid, ppid, command} per process."""
    ps = (
        "Get-CimInstance Win32_Process "
        "-Filter \"Name='python.exe' or Name='pythonw.exe'\" | "
        "Select-Object ProcessId, ParentProcessId, CommandLine "
        "| ConvertTo-Json -Compress"
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
        {
            "pid": r.get("ProcessId"),
            "ppid": r.get("ParentProcessId"),
            "command": r.get("CommandLine") or "",
        }
        for r in rows
        if isinstance(r, dict) and r.get("ProcessId") is not None
    ]


def _posix_raw(timeout_s: float = 10.0) -> list[dict]:
    """The live process table on POSIX, via ``ps`` -
    {pid, ppid, command} per process."""
    out = subprocess.run(
        ["ps", "-eo", "pid,ppid,args"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    rows = []
    for line in out.stdout.splitlines()[1:]:  # skip the header row
        parts = line.strip().split(maxsplit=2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        ppid = int(parts[1]) if parts[1].isdigit() else None
        rows.append({"pid": int(parts[0]), "ppid": ppid, "command": parts[2]})
    return rows


def list_sprout_processes(raw_query=None) -> list[dict]:
    """Live Sprout-spawned processes (Monitor logger / Experiment capture).

    Each entry is ``{pid, ppid, role, command}``. ``raw_query`` is injectable
    (a callable returning ``[{"pid": int, "command": str}, ...]``) for tests; it
    defaults to the real platform query (PowerShell CIM on Windows, ``ps`` on
    POSIX). Never raises - an unavailable/failing platform query degrades to an
    empty list, since this is a diagnostic aid, not a safety-critical check."""
    query = raw_query or (_windows_raw if sys.platform == "win32" else _posix_raw)
    try:
        raw = query()
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    found = []
    for row in raw:
        role = _classify(row.get("command") or "")
        if role:
            found.append(
                {
                    "pid": row["pid"],
                    "ppid": row.get("ppid"),
                    "role": role,
                    "command": row["command"],
                }
            )
    return found


def list_sprout_servers(raw_query=None) -> list[dict]:
    """Live dashboard servers - ``{pid, ppid, command}`` each (#1392).

    Deliberately a peer of :func:`list_sprout_processes`, not part of it: a server is
    not a collector, and this list's consumers must not be forced to re-sort the two
    kinds apart. Same never-raises posture - a diagnostic that throws is worse than one
    that under-reports, because the operator is already mid-incident when they run it.
    """
    query = raw_query or (_windows_raw if sys.platform == "win32" else _posix_raw)
    try:
        raw = query()
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    return [
        {"pid": r["pid"], "ppid": r.get("ppid"), "command": r.get("command") or ""}
        for r in raw
        if _SERVER_RE.search(r.get("command") or "")
    ]


def group_launch_trees(procs: list[dict]) -> list[dict]:
    """Collapse launch-tree members into one logical collector each (#811).

    Every Sprout collector runs as a 2-process launch tree - a parent launcher and
    its worker child, and *both* carry the script name in their command line (the
    python-launcher / venv double-process). Reporting each tree member as its own
    row double-counts: one logical fleet reads as "2 fleet", which produced #691's
    false "4 zombie collectors" finding and burned a maintainer-approved live reclaim.

    Groups by parent/child chain among the *matched* processes of the same role: a
    proc whose ``ppid`` is another matched proc (same role) is that proc's child.
    Returns one entry per tree - ``{role, pids, command}`` - with ``pids`` ordered
    root-first (the launcher), so a fleet tree renders ``fleet  pids 39692->24608``.
    When parentage is unavailable (no ``ppid``), each proc stands alone: honest
    degradation that never *merges* unrelated processes."""
    by_pid = {p["pid"]: p for p in procs}
    parent_of: dict = {}
    for p in procs:
        ppid = p.get("ppid")
        parent = by_pid.get(ppid)
        if parent is not None and ppid != p["pid"] and parent["role"] == p["role"]:
            parent_of[p["pid"]] = ppid
    children = set(parent_of)
    trees: list[dict] = []
    for root in procs:
        if root["pid"] in children:
            continue  # reported under its parent
        chain = [root["pid"]]
        frontier = [root["pid"]]
        while frontier:
            cur = frontier.pop()
            for c in procs:
                if parent_of.get(c["pid"]) == cur and c["pid"] not in chain:
                    chain.append(c["pid"])
                    frontier.append(c["pid"])
        trees.append({"role": root["role"], "pids": chain, "command": root["command"]})
    return trees


def format_collector_line(tree: dict) -> str:
    """One honest status line for a logical collector - role + its launch-tree pids.
    Shared by ``_report`` (``just processes``) and ``collection.py`` (``just
    collection status``) so both surfaces render identically."""
    pids = "->".join(str(x) for x in tree["pids"])
    label = "pids" if len(tree["pids"]) > 1 else "pid "
    return f"  {tree['role']:<8} {label} {pids}"


def _report(procs: list[dict], servers: list[dict] | None = None) -> str:
    servers = servers or []
    if not procs and not servers:
        # #1392: the old wording here was "no live Sprout-spawned processes found." -
        # true of children, and read by an operator whose *server* was stuck as "nothing
        # of Sprout's is running". Name what was actually checked, so a clean result
        # can't be mistaken for a clean bill of health it never claimed.
        return "no live Sprout collectors or dashboard servers found."
    lines: list[str] = []
    if servers:
        lines.append(f"{len(servers)} live dashboard server(s):")
        lines.extend(f"  server   pid  {s['pid']}" for s in servers)
        lines.append(
            "  A server that answers 503 accepted Stop but had not exited yet; since "
            "#1392 it force-exits rather than holding the port forever."
        )
        lines.append("")
    if not procs:
        lines.append("no live Sprout collectors found.")
        return "\n".join(lines)
    trees = group_launch_trees(procs)
    header = f"{len(trees)} live Sprout collector(s)"
    if len(procs) != len(trees):
        header += f" ({len(procs)} processes incl. launch-tree children)"
    lines.append(header + ":")  # append, never reassign - the server block is above
    lines.extend(format_collector_line(t) for t in trees)
    lines.append("")
    lines.append(
        "Not one you expect running? Stop it and its tree: powershell -Command "
        '"Stop-Process -Id <pid> -Force"'
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    del argv  # no arguments today; kept for a future --json/--kill
    print(_report(list_sprout_processes(), list_sprout_servers()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
