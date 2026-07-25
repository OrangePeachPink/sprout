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
