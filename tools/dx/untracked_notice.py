#!/usr/bin/env python3
"""#1386 notice — say out loud that `just check` never looked at untracked files.

`just check` runs `pre-commit run --all-files`, and pre-commit only inspects files
git already knows about. A brand-new file you have not `git add`-ed is not in that
set, so every hook — ruff, cspell, the guards — inspects nothing and reports success.
Nothing is broken; the check simply had no opinion, and "no opinion" and "passed" look
identical from the outside.

A newcomer's first contribution very often *is* a new file: they run the documented
command, see green, push, and CI reds on the file the gate never looked at. This makes
the omission audible, the same way the `check` recipe already announces the native C
firmware tests it does not run.

It deliberately does NOT fail the run. Plenty of untracked files are legitimate (scratch
notes, local data), so the goal is to make the omission VISIBLE, never to block on it.

    python tools/dx/untracked_notice.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def untracked_files(repo: Path = _REPO) -> list[str]:
    """Untracked, non-ignored files — exactly what `pre-commit --all-files` skips."""
    out = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    return sorted(p for p in out.decode("utf-8").split("\0") if p)


def main(argv: list[str] | None = None) -> int:
    files = untracked_files()
    if files:
        print("")
        print(
            f"  Heads up: {len(files)} untracked file(s) were NOT checked — "
            "`pre-commit --all-files` only sees files git tracks:"
        )
        for f in files:
            print(f"    {f}")
        print("  `git add` them, then re-run, to have the gate actually check them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
