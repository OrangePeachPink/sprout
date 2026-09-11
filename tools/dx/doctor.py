#!/usr/bin/env python3
"""#1553 — `just doctor`: is Sprout correctly installed and ready, on THIS machine.

The onboarding walk (#1541) hit a wall and had nothing to ask. Every failure looked the
same from the outside — a server that starts and then waits forever — because there was
no way to find out which prerequisite was missing without reading the repo. This turns
that wall into a checklist.

**It reports; it never repairs.** A doctor that silently fixes things teaches you
nothing and hides the drift that matters. Each check says what it found, and where a
fix exists it names the command rather than running it.

**It does not import the app.** A doctor whose own checks break when the application is
broken is useless exactly when it is needed, so every check works at the filesystem,
process or subprocess level. `uv sync` failing must not stop this from telling you why.

**Three outcomes, and the difference is load-bearing:**

- ``ok``   — proven on this machine, right now.
- ``warn`` — a real state worth knowing that is *not* a failure: no boards declared yet,
  no serial port, no firmware toolchain. A newcomer with no hardware is not broken, and
  saying so in red would teach them to ignore red.
- ``fail`` — the thing genuinely is not going to work. Only these set a non-zero exit.

The clone-path check is the one nobody expects: Windows' MAX_PATH is 260 and
`path_length_guard` keeps our tracked paths under 200, which budgets **60 characters for
where you cloned**. Blowing that budget produces a checkout that fails or silently lands
incomplete, on a machine that has done nothing wrong — so it is measured here, before it
bites, rather than documented and hoped for (#1559).

    just doctor
    python tools/dx/doctor.py --json     # machine-readable, for the onboarding guard
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORT = 8765

# path_length_guard keeps tracked paths <= 200 of Windows' 260-char MAX_PATH; the
# remainder is the budget for the clone location. Mirrored, not re-derived — the guard
# owns the limit and a test asserts these agree.
MAX_PATH = 260
TRACKED_LIMIT = 200
CLONE_BUDGET = MAX_PATH - TRACKED_LIMIT

OK, WARN, FAIL = "ok", "warn", "fail"
_MARK = {OK: "ok  ", WARN: "warn", FAIL: "FAIL"}


class Check:
    def __init__(self, name: str, status: str, detail: str, fix: str = ""):
        self.name, self.status, self.detail, self.fix = name, status, detail, fix

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "fix": self.fix,
        }


def _run(cmd: list[str], timeout: float = 20) -> tuple[int, str]:
    """Run a command; return (exit code, stdout+stderr). Never raises on a missing
    binary — 'not installed' is a result this tool reports, not an error it dies on."""
    try:
        # Decode explicitly as UTF-8: `text=True` uses the locale encoding, and on a
        # Windows console that renders gh's UTF-8 tick as mojibake ("âœ“"). Same family
        # as #1447 — a tool that reports on your machine must not garble what it read.
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return p.returncode, (p.stdout + p.stderr).strip()
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


def _version(binary: str, args: list[str] | None = None) -> str | None:
    if not shutil.which(binary):
        return None
    code, out = _run([binary, *(args or ["--version"])])
    return out.splitlines()[0].strip() if code == 0 and out else None


# --------------------------------------------------------------------------- checks
def check_git() -> Check:
    v = _version("git")
    if not v:
        return Check(
            "git", FAIL, "not installed", "https://git-scm.com/downloads (see docs)"
        )
    return Check("git", OK, v)


def check_gh_auth() -> Check:
    """#1560's product half. `gh` is OPTIONAL — you can contribute over SSH or HTTPS
    without it — so a missing `gh` is a warn, but an INSTALLED-but-unauthenticated `gh`
    is worth naming: that is the state that fails later, at push time, confusingly."""
    if not shutil.which("gh"):
        return Check(
            "gh (GitHub CLI)", WARN, "not installed — optional (SSH/HTTPS work too)"
        )
    code, out = _run(["gh", "auth", "status"])
    if code == 0:
        who = next(
            (ln.strip() for ln in out.splitlines() if "account" in ln.lower()), ""
        )
        return Check("gh (GitHub CLI)", OK, who or "authenticated")
    return Check(
        "gh (GitHub CLI)", WARN, "installed but not authenticated", "gh auth login"
    )


def check_uv() -> Check:
    v = _version("uv")
    if not v:
        return Check("uv", FAIL, "not installed", "scripts/bootstrap.sh (or .ps1)")
    return Check("uv", OK, v)


def check_just() -> Check:
    v = _version("just")
    if not v:
        return Check("just", FAIL, "not installed", "scripts/bootstrap.sh (or .ps1)")
    return Check("just", OK, v)


def check_env_synced() -> Check:
    """Proven by USE, not by looking for a .venv: a directory can exist and still not
    run. If the locked interpreter answers, the environment is real."""
    if not shutil.which("uv"):
        return Check("locked environment", FAIL, "cannot check — uv is missing")
    code, out = _run(["uv", "run", "--frozen", "python", "--version"], timeout=180)
    if code == 0:
        return Check("locked environment", OK, out.splitlines()[0].strip())
    return Check(
        "locked environment",
        FAIL,
        (out.splitlines()[-1][:120] if out else f"uv run exited {code}"),
        "uv sync",
    )


def check_clone_path() -> Check:
    """The budget nobody is told about (#1559). Only Windows enforces MAX_PATH, but the
    repo must stay clonable there, so the measurement is reported everywhere and only
    graded where it bites."""
    n = len(str(REPO_ROOT))
    head = CLONE_BUDGET - n
    where = f"{n} chars: {REPO_ROOT}"
    if os.name != "nt":
        return Check(
            "clone path length", OK, f"{where} (MAX_PATH is Windows-only; FYI here)"
        )
    if head < 0:
        return Check(
            "clone path length",
            FAIL,
            f"{where} — over the {CLONE_BUDGET}-char budget by {-head}; "
            "a deep tracked path may fail to check out",
            "re-clone somewhere shorter, e.g. C:\\dev\\sprout",
        )
    if head < 15:
        return Check(
            "clone path length",
            WARN,
            f"{where} — only {head} chars of the {CLONE_BUDGET}-char budget left",
            "consider re-cloning shorter, e.g. C:\\dev\\sprout",
        )
    return Check("clone path length", OK, f"{where} ({head} chars of headroom)")


def check_port() -> Check:
    """A busy port is not automatically a problem: Sprout being ALREADY RUNNING is the
    single most likely reason, and calling that a failure would be a lie."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        busy = s.connect_ex(("127.0.0.1", PORT)) == 0
    if not busy:
        return Check(f"port {PORT}", OK, "free")
    return Check(
        f"port {PORT}",
        WARN,
        "something is already listening — probably Sprout itself",
        "just processes   (then `just restart` to take it over)",
    )


def check_boards_declared() -> Check:
    """The #1541 wall, named. No registry = nothing can ever report, which is exactly
    the state that used to present as 'waiting for the first reading' forever."""
    local = REPO_ROOT / "config" / "devices.local.json"
    if not local.exists():
        return Check(
            "boards declared",
            WARN,
            "no config/devices.local.json — nothing is registered yet, so no readings "
            "can arrive",
            "add a board in the app (or copy config/devices.example.json)",
        )
    try:
        doc = json.loads(local.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return Check(
            "boards declared",
            FAIL,
            f"config/devices.local.json is unreadable: {str(e)[:80]}",
            "fix the JSON, or start from config/devices.example.json",
        )
    devices = doc.get("devices") or []
    if not devices:
        return Check(
            "boards declared", WARN, "config/devices.local.json declares no devices"
        )
    return Check("boards declared", OK, f"{len(devices)} device(s) declared")


def main_worktree() -> Path | None:
    """The checkout the app actually runs from, per git itself.

    #1688: `git worktree list` names the main worktree on its first line. This is why
    the drift below needs no env var and no marker file — git already maintains the
    coupling that a canonical-root scheme would have to invent.
    """
    out = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=REPO_ROOT,
    )
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree ") :].strip())
    return None


# Gitignored operator state. Each is resolved by its module RELATIVE TO THAT MODULE'S
# OWN checkout, so every worktree carries a private copy that diverges the moment
# anyone edits one.
#
# EXACT suffixes, not `*.local.json*`. The loose glob also matches the operator's
# backups — devices.local.json.bak-20260706_200920 and eight siblings — which live only
# in the main checkout by design. Listing twelve files, nine of them noise, produces a
# warning people skim, and a warning people skim is not a warning.
LOCAL_CONFIG_SUFFIXES = (".local.json", ".local.jsonl")


def _local_configs(checkout: Path) -> dict[str, Path]:
    d = checkout / "config"
    if not d.is_dir():
        return {}
    return {
        p.name: p
        for p in d.iterdir()
        if p.is_file() and p.name.endswith(LOCAL_CONFIG_SUFFIXES)
    }


def check_local_config_drift() -> Check:
    """#1688 — a worktree can silently read a registry the running app never sees.

    Measured when this was filed: the root checkout had `hydrology` on 11/11 plants,
    a worktree had 7/11. The first verification of #1644's write ran with the worktree
    on `sys.path`, read that stale copy, and reported a field missing on data that had
    just been written correctly to the file the app actually reads.

    **The dangerous case is the opposite one.** A test asserting profile-dependent
    behaviour, run in a worktree, is asserting against a registry nobody runs — it can
    pass while the product is broken, or fail while the product is fine, and the failure
    is invisible because both files legitimately exist.

    This announces the drift rather than resolving it. Redirecting reads to one
    canonical root is a behaviour change in another lane's modules, and #1688 filed it
    as options rather than a decision.
    """
    root = main_worktree()
    if root is None:
        return Check("local config", WARN, "cannot ask git for the main worktree")
    here = REPO_ROOT.resolve()
    if root.resolve() == here:
        return Check(
            "local config", OK, "this IS the main checkout — no drift possible"
        )

    mine = _local_configs(here)
    theirs = _local_configs(root)
    names = sorted(set(mine) | set(theirs))
    if not names:
        return Check("local config", OK, "no local operator config in either checkout")

    drifted: list[str] = []
    for n in names:
        a, b = mine.get(n), theirs.get(n)
        if a is None:
            drifted.append(f"{n} (missing here, present in the main checkout)")
        elif b is None:
            drifted.append(f"{n} (present here, missing from the main checkout)")
        else:
            try:
                if a.read_bytes() != b.read_bytes():
                    drifted.append(n)
            except OSError:
                drifted.append(f"{n} (unreadable)")
    if not drifted:
        return Check(
            "local config", OK, f"{len(names)} local file(s) match the main checkout"
        )
    return Check(
        "local config",
        WARN,
        f"DIFFERS from the main checkout ({root}): {', '.join(drifted)}. Anything you "
        "read here is not what the running app reads (#1688)",
        "copy from the main checkout, or run profile-dependent work from there — a "
        "test that reads this file is asserting against a registry nobody runs",
    )


# #1718: how stale the records lane may get before the doctor says so. Seven days is
# a week of collection — long enough not to nag over a laptop that was shut for the
# weekend, short enough that the ten-week silence this check exists to prevent would
# have been caught on day eight.
RECORDS_STALE_DAYS = 7
_DATA_WORKTREE = REPO_ROOT / ".data-worktree"


def check_records_lane() -> Check:
    """Are the telemetry records actually OFF this machine? (#1718)

    Measured against **origin/data**, never against the local branch. "Committed" was
    precisely the state that hid a ten-week gap: the archive lane staged every segment,
    failed its commit on a hook that could never pass, and reported "retry next run" to
    a log nobody reads. A check that asked "is the worktree clean?" would have said yes
    to a working tree holding 236 unlanded files, and a check that asked "are there
    local commits?" would have said no.

    So this asks the only question that means anything about durability: **is there
    anything here that the remote does not have, and how old is it?** Records are
    irreplaceable — a re-run cannot recreate a day of soil readings — so age is the
    severity axis, not count.
    """
    if not _DATA_WORKTREE.is_dir():
        return Check("records lane", OK, "no data worktree on this machine")
    code, _ = _run(
        ["git", "-C", str(_DATA_WORKTREE), "fetch", "--quiet", "origin", "data"]
    )
    fetched = code == 0
    code, out = _run(
        ["git", "-C", str(_DATA_WORKTREE), "rev-list", "--count", "origin/data..data"]
    )
    unpushed = int(out.strip() or 0) if code == 0 and out.strip().isdigit() else 0
    code, out = _run(["git", "-C", str(_DATA_WORKTREE), "status", "--porcelain"])
    pending = len([ln for ln in out.splitlines() if ln.strip()]) if code == 0 else 0

    if not unpushed and not pending:
        note = "everything landed at origin/data"
        return Check("records lane", OK, note if fetched else note + " (offline check)")

    # Age of the oldest thing that is not at the remote — the number that matters.
    oldest_days = _oldest_unlanded_days(unpushed, pending)
    detail = f"{unpushed} unpushed commit(s), {pending} uncommitted file(s)"
    if oldest_days is not None:
        detail += f"; oldest ~{oldest_days}d"
    fix = "python tools/archive/archive_logs.py   (then verify at origin/data)"
    if oldest_days is not None and oldest_days >= RECORDS_STALE_DAYS:
        return Check("records lane", FAIL, detail + " — records exist in ONE copy", fix)
    return Check("records lane", WARN, detail, fix)


def _oldest_unlanded_days(unpushed: int, pending: int) -> int | None:
    """Age in days of the oldest record not yet at the remote, or None if unknowable.

    Two populations, and the older wins: unpushed COMMITS carry their own dates, while
    uncommitted FILES only have an mtime. Both are read rather than assumed — a backlog
    is only alarming in proportion to how long it has been the only copy."""
    oldest = None
    if unpushed:
        code, out = _run(
            [
                "git",
                "-C",
                str(_DATA_WORKTREE),
                "log",
                "--format=%ct",
                "origin/data..data",
            ]
        )
        stamps = [int(s) for s in out.split() if s.isdigit()] if code == 0 else []
        if stamps:
            oldest = min(stamps)
    if pending:
        code, out = _run(["git", "-C", str(_DATA_WORKTREE), "status", "--porcelain"])
        for line in out.splitlines():
            rel = line[3:].strip().strip('"')
            f = _DATA_WORKTREE / rel
            try:
                mt = int(f.stat().st_mtime)
            except OSError:
                continue
            oldest = mt if oldest is None else min(oldest, mt)
    if oldest is None:
        return None
    return max(0, int((time.time() - oldest) / 86400))


# #1710. Two thresholds, and the gap between them is deliberate: a few hours of quiet is
# the normal state of a machine nobody is collecting on right now, and multiple days is
# unrecoverable loss. Readings cannot be re-collected — a day of soil moisture that was
# never sampled is gone — which is the same reason the records lane grades by AGE.
COLLECTION_QUIET_H = 2
COLLECTION_SILENT_DAYS = 2


def _last_reading_epoch(logs_dir: Path) -> tuple[float | None, int]:
    """(newest reading mtime, how many reading files) for a logs directory.

    Filesystem-level on purpose. The doctor does not import the app, and this must keep
    answering when the collector, the server or the environment is broken — which is
    precisely when someone runs it.
    """
    if not logs_dir.is_dir():
        return None, 0
    newest, count = None, 0
    for f in logs_dir.iterdir():
        if not f.is_file() or f.suffix.lower() != ".csv":
            continue
        count += 1
        try:
            m = f.stat().st_mtime
        except OSError:
            continue
        if newest is None or m > newest:
            newest = m
    return newest, count


def _human_age(seconds: float) -> str:
    if seconds < 3600:
        return str(int(seconds // 60)) + "m"
    if seconds < 86400:
        return str(round(seconds / 3600, 1)) + "h"
    return str(round(seconds / 86400, 1)) + "d"


def check_collection_silence(now: float | None = None) -> Check:
    """How long since the last reading landed? (#1710)

    The greenhouse went silent for **6.3 days** and nothing said so — before, during or
    after. A Windows-update restart shut the host down on 08-13 and it never came back
    up until the operator powered it on by hand on 08-20. Both boards' logs stop mid-day
    and no files exist for five days.

    **Six days of silence looked identical to six days of health**, and that is the part
    a check can fix. The dashboard's own gap machinery (``gaps_by_device``) is
    window-scoped, so a six-day hole is not merely unflagged — it is not even *in* a
    "last 24h" view to be flagged.

    Measured at the MAIN worktree, never this checkout: ``logs/`` is gitignored, so a
    worktree has none and would otherwise report a silence that only reflects where the
    agent happens to be standing (#1688, the same lesson one layer down).

    **Grading.** No readings at all is OK — a contributor with no hardware is not
    broken, and that is doctor's standing rule. Hours is a WARN: not collecting right
    now is an ordinary state. Days is a FAIL, because every hour in that window is
    unrecoverable
    and because a WARN buried in a list of WARNs is how the silence stayed invisible in
    the first place.

    This is item 3's minimum bar reached through the surface DX owns. It does NOT
    satisfy "on next launch the app should SAY" — that surface is serve.py, which is
    Data's — and it does nothing about start-on-boot (item 1) or return-to-power
    (item 2), both of which are machine-configuration decisions for the maintainer.
    """
    root = main_worktree() or REPO_ROOT
    logs = root / "logs"
    newest, count = _last_reading_epoch(logs)
    if newest is None:
        return Check(
            "collection",
            OK,
            "no readings collected on this machine yet"
            if count == 0
            else "reading files present but none readable",
        )
    age = max(0.0, (now if now is not None else time.time()) - newest)
    where = "" if root == REPO_ROOT else " (measured at " + str(root) + ")"
    if age < COLLECTION_QUIET_H * 3600:
        return Check(
            "collection", OK, "last reading " + _human_age(age) + " ago" + where
        )
    if age < COLLECTION_SILENT_DAYS * 86400:
        return Check(
            "collection",
            WARN,
            "no reading for "
            + _human_age(age)
            + " — the collector is not running"
            + where,
            "just start   (then press Start logging)",
        )
    return Check(
        "collection",
        FAIL,
        "SILENT for " + _human_age(age) + " — readings in that window are gone and "
        "cannot be re-collected" + where,
        "just start, then check the host came back from its last restart (#1710)",
    )


def check_serial_ports() -> Check:
    """Optional by design: a contributor with no hardware is not broken."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return Check("serial ports", WARN, "pyserial not importable — not checked")
    ports = list(list_ports.comports())
    if not ports:
        return Check(
            "serial ports", WARN, "none visible — fine if no board is plugged in"
        )
    return Check("serial ports", OK, ", ".join(p.device for p in ports[:4]))


def check_firmware_toolchain() -> Check:
    """Optional: `just check` never needs a compiler; only firmware work does."""
    v = _version("pio")
    if not v:
        return Check(
            "firmware toolchain (pio)",
            WARN,
            "not installed — optional; only firmware work needs it",
        )
    return Check("firmware toolchain (pio)", OK, v)


CHECKS = (
    check_git,
    check_gh_auth,
    check_uv,
    check_just,
    check_env_synced,
    check_clone_path,
    check_port,
    check_boards_declared,
    check_local_config_drift,
    check_records_lane,
    check_collection_silence,
    check_serial_ports,
    check_firmware_toolchain,
)


def run_checks() -> list[Check]:
    return [c() for c in CHECKS]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # cp1252 consoles (the #1447 lesson)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="#1553 — is Sprout ready on this machine?")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    results = run_checks()
    if args.json:
        print(json.dumps([r.as_dict() for r in results], indent=2))
    else:
        print("\nSprout doctor — what is true on this machine right now:\n")
        for r in results:
            print(f"  [{_MARK[r.status]}]  {r.name:24} {r.detail}")
            if r.fix and r.status != OK:
                print(f"           {'':24} -> {r.fix}")
        fails = [r for r in results if r.status == FAIL]
        warns = [r for r in results if r.status == WARN]
        print()
        if fails:
            print(f"  {len(fails)} blocking problem(s). Fix those, then re-run.")
        elif warns:
            print("  Ready. The warnings above are states, not faults — see each note.")
        else:
            print("  Ready, everything checked.")
        print("  Next: just start\n")

    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
