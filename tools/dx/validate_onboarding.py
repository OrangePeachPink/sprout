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

  1. scripts/bootstrap --check-only, from a TOOLLESS shell
                                - PASS: it runs with uv/just absent from PATH and
                                   reports them missing (#1562). The wall itself:
                                   `command not found: uv` happens one step BEFORE
                                   `uv sync`, which is why this guard missed it
  2. scripts/bootstrap --tools-only
                                - PASS: exit 0. The Quick Start's HEADLINE command
                                   (#1557) — asserted so the guard cannot mirror the
                                   by-hand fallback while the headline rots
  3. uv sync                    - PASS: exit 0
  4. uv run pre-commit install  - PASS: exit 0
  5. Ctrl-C stays clean       - PASS: `serve` traps INT and swallows NOTHING else
                                   (#1552). Guards the MECHANISM, not a simulated
                                   signal: the end-to-end tty behaviour was verified
                                   when #1552 landed; the regression is someone
                                   deleting the trap or reaching for a blanket ignore
  6. port :8765 free            - PASS: nothing already listening (#1337; `just start`
                                   is --serve-or-focus, so a live server would make
                                   this script grade one it did not start)
  7. just start                 - PASS: GET / on :8765 returns HTTP 200 within 30s.
                                   Runs the LITERAL command (#1337), not serve.py
                                   directly; BROWSER=true keeps --open headless
  8. POST /quit                 - PASS: server process exits within 10s
  9. just processes             - PASS: reports zero live Sprout-spawned processes
  10. just check                 - PASS: exit 0 (needs PlatformIO + a C compiler on
                                   PATH - the documented honest-note gap from #512;
                                   this step's failure for THAT reason is a real
                                   result, not a script bug - see CONTRIBUTING.md)
"""

from __future__ import annotations

import contextlib
import os
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


def step_bootstrap_tools() -> StepResult:
    """The README's HEADLINE command must exist and run (#1557).

    The Quick Start now leads with `scripts/bootstrap`, so the guard has to assert that
    and not only the by-hand `uv sync` path below it — a validator that mirrors the
    fallback while the headline rots is how the docs and the product drift apart.
    `--tools-only` is the cheap half: it verifies git/uv/just and exits, so this costs a
    second on a machine that already has them and never re-installs anything.

    (Running it from a genuinely TOOLLESS shell — the wall a new contributor actually
    hits — is #1562's job; this step proves the command is real, not that it bootstraps
    from nothing.)
    """
    script = "bootstrap.ps1" if os.name == "nt" else "bootstrap.sh"
    path = REPO_ROOT / "scripts" / script
    if not path.exists():
        return StepResult(
            f"scripts/{script}", False, "missing — the README promises it"
        )
    cmd = (
        ["pwsh", "-NoProfile", "-File", str(path), "-ToolsOnly"]
        if os.name == "nt"
        else ["sh", str(path), "--tools-only"]
    )
    proc = _run(cmd, timeout_s=180)
    ok = proc.returncode == 0
    detail = "exit 0" if ok else f"exit {proc.returncode}\n{proc.stderr[-800:]}"
    return StepResult(f"scripts/{script} --tools-only", ok, detail)


def step_bootstrap_from_a_toolless_shell() -> StepResult:
    """The wall itself, asserted (#1562): bootstrap must work where uv and just are NOT.

    Every other step here presupposes the tools — which is precisely why this guard
    missed the #1541 report's very first finding. `command not found: uv` happens one
    step *before* `uv sync`, in a shell the validator never simulated.

    Runs `--check-only` with a PATH stripped of everything but the system directories,
    so the script executes in a genuinely toolless environment and has to *detect and
    report* rather than assume. `--check-only` installs nothing on purpose: a guard that
    reaches the network and mutates the machine it is grading is not a guard.

    PASS = it ran, and it correctly said uv and just were missing.
    """
    script = "bootstrap.ps1" if os.name == "nt" else "bootstrap.sh"
    path = REPO_ROOT / "scripts" / script
    if not path.exists():
        return StepResult("toolless bootstrap", False, f"scripts/{script} is missing")

    if os.name == "nt":
        bare = os.environ.get("SYSTEMROOT", r"C:\Windows")
        env = {
            **os.environ,
            "PATH": f"{bare}\\System32;{bare}",
            "PATHEXT": os.environ.get("PATHEXT", ""),
        }
        cmd = ["pwsh", "-NoProfile", "-File", str(path), "-CheckOnly"]
    else:
        env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", "/tmp")}
        cmd = ["sh", str(path), "--check-only"]

    try:
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, env=env
        )
    except (OSError, subprocess.SubprocessError) as e:
        return StepResult("toolless bootstrap", False, f"could not run it: {e}")

    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return StepResult(
            "toolless bootstrap", False, f"exit {proc.returncode}\n{out[-500:]}"
        )
    # It must NOTICE. Reporting everything present from a shell with no PATH would mean
    # the detection is broken and the real run would sail past a missing tool.
    detected = [t for t in ("uv", "just") if f"MISSING  {t}" in out]
    if len(detected) < 2:
        return StepResult(
            "toolless bootstrap",
            False,
            "ran, but did not report uv/just as missing from a stripped PATH — "
            f"its detection is not working:\n{out[-400:]}",
        )
    return StepResult(
        "toolless bootstrap",
        True,
        "ran with no tools on PATH; reported uv + just missing",
    )


def step_ctrl_c_stays_clean() -> StepResult:
    """Ctrl-C is a documented stop, and it must not regress into reading as a crash
    (#1552, #1562).

    **What this proves, and what it doesn't.** The end-to-end behaviour — press Ctrl-C
    at a real terminal, get a clean exit and nothing left running — was verified at a
    tty when #1552 landed, because a terminal signal cannot be faithfully delivered
    from every host this guard runs on. Asserting it here would mean simulating a
    signal and grading the simulation.

    So this guards the *mechanism* instead, which is where the regression
    actually lives: someone deletes the trap, or "fixes" a noisy exit with a
    blanket ignore. Both are one
    careless edit, and both silently restore the failure #1552 removed.

    Two properties, and the second matters more than the first:

    1. `serve` traps INT — the documented stop path is handled at all.
    2. It does NOT swallow everything. A blanket `|| true`, or just's `-` prefix
       (which `logger` legitimately uses, #148), would hide a serve that fails to bind
       or dies on an import error. Tidying one expected keystroke must never cost
       every real crash — that asymmetry is the whole design of the fix.
    """
    justfile = REPO_ROOT / "justfile"
    if not justfile.exists():
        return StepResult("Ctrl-C stays clean", False, "no justfile")
    text = justfile.read_text(encoding="utf-8")
    try:
        recipe = text.split("\nserve *ARGS:", 1)[1].split("\n\n", 1)[0]
    except IndexError:
        return StepResult(
            "Ctrl-C stays clean", False, "the `serve` recipe is gone or was renamed"
        )

    # COMMENTS ONLY EXPLAIN; they never execute. Both checks below run against the
    # comment-stripped body, and that is not fussiness — the recipe's own comment quotes
    # `trap 'exit 0' INT` while explaining it, and quotes `|| true` while explaining why
    # it is NOT used. Scanning raw text makes the trap-check pass on a recipe whose trap
    # was deleted (caught red-proofing this) and makes the blanket-check fail on
    # the very
    # sentence promising not to swallow. A guard fooled by prose about itself is worse
    # than no guard.
    body = [
        ln.strip()
        for ln in recipe.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not any("trap" in ln and "INT" in ln for ln in body):
        return StepResult(
            "Ctrl-C stays clean",
            False,
            "`serve` no longer traps INT — Ctrl-C, the documented stop, will read as a "
            "crash again (#1552)",
        )
    blanket = [
        ln
        for ln in body
        if ln.startswith("-{{py}}") or ln.startswith("-uv ") or "|| true" in ln
    ]
    if blanket:
        return StepResult(
            "Ctrl-C stays clean",
            False,
            f"`serve` swallows ALL failures ({blanket[0]!r}) — a serve that cannot "
            "bind "
            "would go silent. Only SIGINT may be swallowed.",
        )
    return StepResult(
        "Ctrl-C stays clean",
        True,
        "`serve` traps INT and swallows nothing else "
        "(end-to-end proven at a tty, #1552)",
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


def step_preflight_port() -> StepResult:
    """The port must be free BEFORE we test `just start` (#1337).

    `just start` is `--serve-or-focus`: if a server already holds :8765 it focuses
    that one and exits 0 — correct behaviour, but it means the validator would be
    grading a server it did not start. Without this step that shows up as the
    baffling "server exited early (code 0)".

    Rather than adapt around it, this reports the precondition. A port answering
    503 is the specific tell that a previous server accepted /quit and then hung
    without releasing it — worth naming, because it is invisible to
    `just processes`."""
    try:
        with urllib.request.urlopen(BASE_URL, timeout=2) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return StepResult("port :8765 free (clean start)", True, "nothing listening")
    hint = (
        " — a 503 means a previous server accepted /quit but never exited and is "
        "still holding the port; `just processes` does not see it"
        if status == 503
        else ""
    )
    return StepResult(
        "port :8765 free (clean start)",
        False,
        f"something is already serving on :8765 (HTTP {status}){hint}. "
        "Stop it, then re-run — the validator must start the server it grades.",
    )


def step_start_and_check(proc_holder: dict) -> StepResult:
    """Run the LITERAL `just start` a newcomer types, then poll for HTTP 200.

    #1337: this step used to shell out to `uv run python tools/analytics/serve.py`
    while *labelling* itself "just start". That is a validator that cannot fail the
    way a newcomer fails — it skipped `just` entirely, skipped the recipe's
    `@just serve --serve-or-focus --open` indirection, and skipped both flags. A
    broken justfile, a renamed recipe, or a broken single-instance path would all
    have sailed through green while the documented command was dead.

    Headless without lying about the command: `BROWSER` makes Python's `webbrowser`
    resolve to a GenericBrowser running a no-op, so `--open` executes its real code
    path and opens nothing. The command under test stays byte-identical to the
    README's; only what counts as "a browser" changes."""
    env = {**os.environ, "BROWSER": "true"}  # no-op "browser" — see docstring
    server = subprocess.Popen(
        ["just", "start"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
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
        for step in (
            step_bootstrap_from_a_toolless_shell,
            step_bootstrap_tools,
            step_uv_sync,
            step_pre_commit_install,
            step_ctrl_c_stays_clean,
            step_preflight_port,
        ):
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
