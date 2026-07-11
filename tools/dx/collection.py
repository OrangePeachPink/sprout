#!/usr/bin/env python3
"""Headless collection lifecycle - start / stop / status without the dashboard (#689).

DX owns the headless stop/reclaim + the `just` recipe surface (Data ack, 2026-07-06);
Data owns the data/session-handling side (#712). The always-on era (v0.7.0 runs 24/7)
made this gap real: if the browser tab closes or a collector orphans, there was no
headless way to *see, stop, or reclaim* it - a reboot was the only recourse (#493 / the
#691 resilience log). Three no-dashboard actions:

* ``status`` - list live Sprout collectors by pid + role. Reuses Data's **report-only**
  ``sprout_processes.list_sprout_processes`` (the identifiability half of #493); this
  module never re-implements discovery, it builds the *reclaim* half on top.

* ``stop`` - gracefully stop every live collector (monitor + fleet), then hard-kill any
  that don't exit in the grace window. **Safe mid-write:** the loggers flush every CSV
  row (``RotatingCsv.write`` -> ``writer.writerow`` + ``fh.flush``), so a file is always
  complete up to its last row; a terminate loses at most the sub-millisecond in-flight
  row, never a truncated one. Graceful first (SIGINT triggers the loggers'
  ``KeyboardInterrupt`` clean-exit on POSIX; ``taskkill /PID`` on Windows), hard-kill
  (SIGKILL / ``taskkill /F``) only for survivors.

* ``start`` - parity with the dashboard's one-action "Start logging" (ADR-0014):
  POST ``/collection/start`` to the running server (needs ``just start`` up first). The
  lifecycle *surface* is DX's, but the start policy lives in Data's
  ``collection_control`` - reached over the same HTTP the dashboard button uses.

Reclaim logic is injectable (``terminate`` / ``still_live`` / ``sleep``) so it is
unit-tested without real processes - the same testable-seam pattern as
``sprout_processes``' injectable ``raw_query``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Reuse Data's report-only discovery (the #493 identifiability half). It lives in
# tools/analytics; add that dir to the path rather than duplicate the OS query here.
_ANALYTICS = Path(__file__).resolve().parents[1] / "analytics"
if str(_ANALYTICS) not in sys.path:
    sys.path.insert(0, str(_ANALYTICS))

from sprout_processes import (  # noqa: E402  (path set above)
    format_collector_line,
    group_launch_trees,
    list_sprout_processes,
)

PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"
GRACE_S = 5.0
ROLES = ("monitor", "fleet", "capture")


def _collectors(role: str = "all") -> list[dict]:
    procs = list_sprout_processes()
    if role != "all":
        procs = [p for p in procs if p["role"] == role]
    return procs


def _terminate(pid: int, *, force: bool) -> None:
    """Stop a foreign pid. Graceful (``force=False``) first, hard-kill (``force=True``)
    for survivors. Cross-platform; never raises on an already-dead pid."""
    try:
        if sys.platform == "win32":
            cmd = ["taskkill", "/PID", str(pid)] + (["/F"] if force else [])
            subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        else:
            import signal

            os.kill(pid, signal.SIGKILL if force else signal.SIGINT)
    except (ProcessLookupError, PermissionError, OSError, subprocess.SubprocessError):
        pass  # gone already, or not ours - reclaim() re-checks liveness regardless


def _still_live(pids: list[int]) -> set[int]:
    """Which of ``pids`` are still live Sprout collectors. Re-queries the same lister
    used for discovery, so liveness is cross-platform with zero extra OS-probe code."""
    live = {p["pid"] for p in list_sprout_processes()}
    return live & set(pids)


def reclaim(
    procs: list[dict],
    *,
    terminate=_terminate,
    still_live=_still_live,
    grace_s: float = GRACE_S,
    sleep=time.sleep,
) -> list[dict]:
    """Stop each collector gracefully, hard-kill any that outlive the grace window.

    ``terminate(pid, force=...)`` and ``still_live(pids) -> set`` are injected (the real
    ones shell out / query the OS; tests pass fakes). Returns
    ``[{pid, role, command, outcome}]`` where ``outcome`` is ``graceful`` | ``forced`` |
    ``failed``."""
    if not procs:
        return []
    pids = [p["pid"] for p in procs]
    for pid in pids:
        terminate(pid, force=False)
    sleep(grace_s)
    survivors = still_live(pids)
    for pid in survivors:
        terminate(pid, force=True)
    if survivors:
        sleep(min(grace_s, 2.0))
    final = still_live(pids)
    out = []
    for p in procs:
        pid = p["pid"]
        if pid in final:
            outcome = "failed"
        elif pid in survivors:
            outcome = "forced"
        else:
            outcome = "graceful"
        out.append({**p, "outcome": outcome})
    return out


def _post_start(port: str | None) -> dict:
    body = json.dumps({"port": port} if port else {}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/collection/start",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode() or "{}")


# --------------------------------------------------------------------------- actions


def cmd_status(args) -> int:
    procs = _collectors(args.role)
    if args.json:
        print(json.dumps(procs))
        return 0
    if not procs:
        print("no live Sprout collectors.")
        return 0
    trees = group_launch_trees(procs)  # 1 logical collector per launch tree (#811)
    print(f"{len(trees)} live Sprout collector(s):")
    for t in trees:
        print(format_collector_line(t))
    print("\nStop them headlessly:  just stop-collection")
    return 0


def cmd_stop(args) -> int:
    procs = _collectors(args.role)
    if not procs:
        print("no live Sprout collectors to stop.")
        return 0
    if args.dry_run:
        print(f"[dry-run] would stop {len(procs)} collector(s):")
        for p in procs:
            print(f"  pid {p['pid']:<8} {p['role']:<8} {p['command']}")
        return 0
    results = reclaim(procs, grace_s=args.grace)
    if args.json:
        print(json.dumps(results))
    else:
        for r in results:
            print(f"  {r['outcome']:<8} pid {r['pid']:<8} {r['role']}")
    failed = [r for r in results if r["outcome"] == "failed"]
    if failed:
        pids = ", ".join(str(r["pid"]) for r in failed)
        print(
            f"\n{len(failed)} did not stop (pid {pids}) - force manually: "
            f'powershell -Command "Stop-Process -Id <pid> -Force"',
            file=sys.stderr,
        )
        return 1
    print(f"\nstopped {len(results)} collector(s).")
    return 0


def cmd_start(args) -> int:
    try:
        result = _post_start(args.port)
    except urllib.error.URLError:
        print(
            "no Sprout server up - run `just start`, then `just collection start`.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result) if args.json else f"collection started: {result}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Headless collection lifecycle (#689).")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="action", required=True)

    s = sub.add_parser("status", help="list live collectors (reuses `just processes`)")
    s.add_argument("--role", choices=("all", *ROLES), default="all")
    s.set_defaults(func=cmd_status)

    st = sub.add_parser(
        "stop", help="stop every live collector - graceful, then hard-kill"
    )
    st.add_argument("--role", choices=("all", *ROLES), default="all")
    st.add_argument(
        "--dry-run", action="store_true", help="show what would stop, kill nothing"
    )
    st.add_argument(
        "--grace", type=float, default=GRACE_S, help="seconds to wait before hard-kill"
    )
    st.set_defaults(func=cmd_stop)

    sr = sub.add_parser(
        "start", help="start all collection via the running server (ADR-0014)"
    )
    sr.add_argument(
        "--port", default=None, help="serial port for the monitor path (optional)"
    )
    sr.set_defaults(func=cmd_start)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
