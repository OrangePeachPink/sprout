#!/usr/bin/env python3
"""#1337 tripwire — tracked paths stay short enough to clone on Windows.

Windows' classic ``MAX_PATH`` is **260 characters**, and it applies to the *absolute*
path — your clone location plus the repo-relative path. A 210-character tracked path
therefore leaves only 50 characters for "where the user put the repo", and
``C:\\Users\\<name>\\Documents\\GitHub\\sprout\\`` is already ~40. Past that the failure
is not subtle: `git checkout` cannot create the file, so the clone fails or silently
lands incomplete — on a machine that has done nothing wrong.

The repo carried exactly this: two capture CSVs at 210 characters, in a directory whose
name the filename then repeated in full. Long-path support exists (``core.longpaths``,
the Win10+ registry opt-in) but requires the *contributor* to have configured it, which
makes it a fix we cannot ship. Keeping our own paths short is the fix we can.

The limit is 200, not 260, on purpose: 260 minus 200 leaves 60 characters for the clone
location, which covers a realistic Windows home. It is a budget, not a guess.

    python tools/dx/path_length_guard.py --check
    python tools/dx/path_length_guard.py --check --limit 180   # tighter budget
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_LIMIT = 200
_WINDOWS_MAX_PATH = 260


def tracked_paths(repo: Path = _REPO) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=repo, check=True, capture_output=True
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def over_limit(paths: list[str], limit: int = _LIMIT) -> list[tuple[int, str]]:
    """(length, path) for every path at or over the limit, longest first."""
    return sorted(((len(p), p) for p in paths if len(p) >= limit), key=lambda t: -t[0])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="#1337: tracked paths stay Windows-clonable"
    )
    ap.add_argument(
        "--check", action="store_true", help="report + non-zero on findings"
    )
    ap.add_argument("--limit", type=int, default=_LIMIT, help=f"max chars ({_LIMIT})")
    ap.add_argument("filenames", nargs="*", help="ignored (pre-commit passes files)")
    args = ap.parse_args(argv)

    findings = over_limit(tracked_paths(), args.limit)
    if findings:
        print(
            f"path-length-guard: tracked path(s) at/over {args.limit} chars — a "
            f"Windows clone has only {_WINDOWS_MAX_PATH - args.limit} chars left for "
            "the folder the user clones into, and git cannot create the file past "
            "that (#1337):",
            file=sys.stderr,
        )
        for n, p in findings:
            print(f"  {n} chars  {p}", file=sys.stderr)
        print(
            "  Shorten a path SEGMENT — a filename that repeats its own directory name "
            "is the usual culprit, and dropping the repeat loses nothing.",
            file=sys.stderr,
        )
        return 1 if args.check else 0

    longest = max((len(p) for p in tracked_paths()), default=0)
    print(
        f"path-length-guard: longest tracked path {longest} chars (limit {args.limit})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
