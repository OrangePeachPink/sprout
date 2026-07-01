"""Changed-LINES clang-format gate (#352, v2 — supersedes the changed-files v1).

Runs `git-clang-format` against a base ref so only the *lines the diff touched*
are formatted — untouched hand-aligned `=`-columns and trailing-comment columns
survive byte-identical, even in a file you're editing. This closes the residual
that the changed-*files* gate left (AGENTS.md §code-style; bit #376/#348/#376).

Toolchain (ADR-0002 #10, Trellis sign-off on #352):
  - Both `clang-format` and `git-clang-format` come from the pinned
    `clang-format==22.1.5` wheel in the uv dev env (one hash-pinned source in
    uv.lock — provenance >= the old mirror).
  - We bind git-clang-format to the uv-env binary via `--binary` and NEVER let
    it fall back to an ambient clang-format (the "no ambient toolchain"
    principle from #259). Both executables are resolved next to this
    interpreter (the venv), so `uv run` is the only supported entry.

Modes (same logic everywhere — local == CI; only the base ref differs):
  --check   : report-only (`git-clang-format --diff`); non-empty diff -> exit 1.
              Used by CI (base = PR merge-base, the blocking authority) and
              `just lint-fw`.
  (default) : apply to the working tree, then exit 1 if anything changed so the
              contributor re-stages. Used by the pre-commit hook (base = HEAD).

Usage:
  uv run python tools/clang_format_changed_lines.py --base <ref> [--check]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

EXTENSIONS = "c,cpp,h"


def _resolve(name: str) -> str:
    """Find an executable next to this interpreter (the uv venv) — never ambient.

    The clang-format wheel installs both console scripts into the venv's
    Scripts/ (Windows) or bin/ (POSIX) dir, alongside sys.executable.
    """
    bindir = os.path.dirname(os.path.abspath(sys.executable))
    for cand in (name, name + ".exe"):
        path = os.path.join(bindir, cand)
        if os.path.isfile(path):
            return path
    sys.exit(
        f"error: '{name}' not found in the uv env ({bindir}). "
        "Run `uv sync` to install the pinned clang-format dev dependency (#352)."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        required=True,
        help="git ref to diff against (local hook: HEAD; CI: PR merge-base).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report-only diff; do not modify files (CI / just lint-fw).",
    )
    args = parser.parse_args()

    clang_format = _resolve("clang-format")
    git_clang_format = _resolve("git-clang-format")

    base_cmd = [
        git_clang_format,
        args.base,
        "--binary",
        clang_format,
        "--extensions",
        EXTENSIONS,
    ]

    # Exit code is git-clang-format's authority: `--diff` returns 0 when the
    # touched lines are already clean (covering both "no modified files to
    # format" and "did not modify any files") and non-zero when they need
    # formatting. We never string-match status text.
    check = subprocess.run([*base_cmd, "--diff"], capture_output=True, text=True)
    if check.returncode == 0:
        return 0

    # Touched lines need formatting (or git-clang-format errored — either way,
    # surface its output and fail).
    sys.stdout.write(check.stdout)
    sys.stderr.write(check.stderr)

    if args.check:
        sys.stderr.write(
            "\nerror: changed lines need formatting (#352). "
            "Run `just format-fw` to fix, then re-commit.\n"
        )
        return 1

    # Apply mode (pre-commit hook): reformat the touched lines in the working
    # tree, then fail so the commit aborts and the contributor re-stages.
    subprocess.run(base_cmd, check=False)
    sys.stderr.write(
        "\nclang-format reformatted the lines you changed (#352). "
        "Review, `git add` the result, and commit again.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
