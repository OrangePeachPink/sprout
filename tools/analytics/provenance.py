"""Server / app provenance for the bench-evidence panel (#324).

A screenshot of the dashboard should carry enough context for another lane to know
*what produced this data*: which app code (git SHA + branch), when the server
started, whether it now predates the checked-out tree, and the honest-data contract
state (raw counts + band only — never a calibrated %).

This module owns only the **server/app** facts (the new ones). Device / firmware /
capture facts already live in the parsed segment + manifest; the surfaces assemble
the full panel from both. Pure stdlib; every git call degrades to a sentinel so a
missing git or a non-repo never breaks the page.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

# Captured once, at import — i.e. when serve.py boots. This is the server start time
# and the app code the server is *running*, regardless of later working-tree edits.
SERVER_START_UTC = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + (
    f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"
)
_NOGIT = "nogit"


def _git(args: list[str]) -> str | None:
    """A git command's stripped stdout, or None if git/repo is unavailable."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_REPO), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.strip() or None


def git_sha() -> str:
    return _git(["rev-parse", "--short", "HEAD"]) or _NOGIT


def git_branch() -> str:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"]) or _NOGIT


def git_dirty() -> bool:
    """True if the working tree differs from HEAD (staged or unstaged)."""
    # `git status --porcelain` prints a line per change; empty => clean.
    out = _git(["status", "--porcelain"])
    return bool(out)


# The SHA the server captured at boot — frozen, so staleness can be detected live.
_BOOT_SHA = git_sha()

# #719: the single product version line (ADR-0009 §1) is pyproject's `version`,
# synced repo-wide each release. App and server are the SAME program, so they read
# THIS one constant - which is exactly why they can never disagree. Read once at
# import; degrades to None (never a guessed number) if pyproject is absent/odd.
_PYPROJECT = _REPO / "pyproject.toml"


def _read_product_version() -> str | None:
    try:
        for line in _PYPROJECT.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("version") and "=" in s:
                # `version = "0.7.0"  # comment` -> 0.7.0
                val = s.split("=", 1)[1].split("#", 1)[0].strip()
                return val.strip("\"'") or None
    except OSError:
        pass
    return None


PRODUCT_VERSION = _read_product_version()


def product_version() -> str | None:
    """The one product version (ADR-0009 §1) both the app and the server report.

    They share this single constant by construction, so "is the app version the
    same as the server version?" is answered structurally: yes, always."""
    return PRODUCT_VERSION


def server_provenance() -> dict:
    """App/server provenance for the panel.

    ``stale`` answers "does the running server predate the checked-out code?": the
    boot SHA (frozen at import) vs the current HEAD. True means someone committed
    after the server started — a screenshot from a stale server is a known trap, so
    we surface it rather than let it mislead."""
    head = git_sha()
    boot = _BOOT_SHA
    # Unknown SHAs can't be compared honestly -> don't claim staleness.
    stale = head != boot and _NOGIT not in (head, boot)
    return {
        "app_git_sha": boot,  # what the server is actually running
        "head_git_sha": head,  # what's checked out now
        "branch": git_branch(),
        "dirty": git_dirty(),
        "start_utc": SERVER_START_UTC,
        "stale": stale,
        "version": PRODUCT_VERSION,  # #719: app==server version, one constant
    }
