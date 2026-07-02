#!/usr/bin/env python3
"""Clean-machine onboarding validation - the machine half of #186.

Scripts the exact sequence the README Quick Start / CONTRIBUTING.md promise, so
"three installs -> it works" is a repeatable check instead of a one-off manual test
(the one behind #512's doc fix). Each step has an explicit pass criterion; the first
failure stops the run and reports which step broke the promise.

Run this from a repo checkout, ideally a genuinely clean one (fresh clone, no prior
uv/pre-commit state) - a real Codespaces or second-machine run is still the maintainer's
call (billable resource), but this script is what that run executes, so the validation
itself isn't ad-hoc or re-derived each time.

    uv run python tools/dx/validate_onboarding.py
    just validate-onboarding

Steps (mirrors the README/CONTRIBUTING Quick Start verbatim, plus a clean-shutdown
check carried over from the #512/#493 manual precedent):

  1. uv sync                    - PASS: exit 0
  2. uv run pre-commit install  - PASS: exit 0
  3. just start (headless)      - PASS: GET / on :8765 returns HTTP 200 within 30s
  4. POST /quit                 - PASS: server process exits within 10s
  5. just processes             - PASS: reports zero live Sprout-spawned processes
  6. just check                 - PASS: exit 0 (needs PlatformIO + a C compiler on
                                   PATH - the documented honest-note gap from #512;
                                   this step's failure for THAT reason is a real
                                   result, not a script bug - see CONTRIBUTING.md)
"""

from __future__ import annotations

import contextlib
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORT = 8765
BASE_URL = f"http://127.0.0.1:{PORT}"


class StepResult:
    def __init__(self, name: str, ok: bool, detail: str):
        self.name = name
        self.ok = ok
        self.detail = detail


def _run(cmd: list[str], timeout_s: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )


def step_uv_sync() -> StepResult:
    proc = _run(["uv", "sync"], timeout_s=300)
    ok = proc.returncode == 0
    detail = "exit 0" if ok else f"exit {proc.returncode}\n{proc.stderr[-800:]}"
    return StepResult("uv sync", ok, detail)


def step_pre_commit_install() -> StepResult:
    proc = _run(["uv", "run", "pre-commit", "install"], timeout_s=120)
    ok = proc.returncode == 0
    detail = "exit 0" if ok else f"exit {proc.returncode}\n{proc.stderr[-800:]}"
    return StepResult("uv run pre-commit install", ok, detail)


def step_start_and_check(proc_holder: dict) -> StepResult:
    """Launch serve.py headless (no --open - a clean/CI machine has no browser to
    open) and poll for HTTP 200, matching #512's manual fresh-clone test."""
    server = subprocess.Popen(
        ["uv", "run", "python", "tools/analytics/serve.py"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    proc_holder["proc"] = server

    deadline = time.monotonic() + 30
    last_error = "never attempted"
    while time.monotonic() < deadline:
        if server.poll() is not None:
            out = server.stdout.read() if server.stdout else ""
            return StepResult(
                "just start (dashboard serves)",
                False,
                f"server exited early (code {server.returncode})\n{out[-800:]}",
            )
        try:
            with urllib.request.urlopen(BASE_URL, timeout=2) as resp:
                if resp.status == 200:
                    return StepResult(
                        "just start (dashboard serves)",
                        True,
                        f"HTTP {resp.status} from {BASE_URL}",
                    )
                last_error = f"HTTP {resp.status}"
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(0.5)

    return StepResult(
        "just start (dashboard serves)",
        False,
        f"no 200 within 30s (last: {last_error})",
    )


def step_quit(proc_holder: dict) -> StepResult:
    server = proc_holder.get("proc")
    if server is None or server.poll() is not None:
        return StepResult(
            "POST /quit (clean shutdown)", False, "no live server to stop"
        )
    # a clean /quit closing the connection before responding is expected
    with contextlib.suppress(urllib.error.URLError, ConnectionError, TimeoutError):
        urllib.request.urlopen(
            urllib.request.Request(f"{BASE_URL}/quit", method="POST"), timeout=5
        )
    try:
        server.wait(timeout=10)
        return StepResult(
            "POST /quit (clean shutdown)", True, "process exited within 10s"
        )
    except subprocess.TimeoutExpired:
        server.kill()
        return StepResult(
            "POST /quit (clean shutdown)",
            False,
            "did not exit within 10s - had to force-kill",
        )


def step_processes() -> StepResult:
    proc = _run(["just", "processes"], timeout_s=30)
    clean = "no live sprout-spawned processes found" in proc.stdout.lower()
    return StepResult(
        "just processes (zero orphans)",
        clean,
        proc.stdout.strip() or proc.stderr.strip(),
    )


def step_check() -> StepResult:
    proc = _run(["just", "check"], timeout_s=900)
    ok = proc.returncode == 0
    tail = (proc.stdout + proc.stderr)[-1500:]
    detail = "exit 0" if ok else f"exit {proc.returncode}\n{tail}"
    return StepResult("just check (the gate)", ok, detail)


def main() -> int:
    results: list[StepResult] = []
    proc_holder: dict = {}

    try:
        for step in (step_uv_sync, step_pre_commit_install):
            result = step()
            results.append(result)
            if not result.ok:
                break
        else:
            result = step_start_and_check(proc_holder)
            results.append(result)
            if result.ok:
                results.append(step_quit(proc_holder))
                results.append(step_processes())
                results.append(step_check())
    finally:
        # Guarantee cleanup regardless of which path above ran or whether step_quit
        # actually stopped the server - never leave an orphan server behind (#493).
        server = proc_holder.get("proc")
        if server and server.poll() is None:
            server.kill()
            server.wait(timeout=10)

    print("\n=== Clean-machine onboarding validation (#186) ===\n")
    all_ok = True
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        all_ok = all_ok and r.ok
        print(f"[{mark}] {r.name}")
        if not r.ok:
            print(f"       {r.detail}")
    print()
    print(
        "RESULT: "
        + (
            "PASS - clean machine, documented installs only, all green."
            if all_ok
            else "FAIL - see the failing step above."
        )
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
