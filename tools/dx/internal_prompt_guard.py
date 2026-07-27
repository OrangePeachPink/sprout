#!/usr/bin/env python3
"""#1659 — internal lane prompts, runbooks and transcripts stay out of the public repo.

**This is not theoretical.** The #1117/#1129 incident is the standing proof: an external
contributor's coding agent read Sprout's then-public instruction files and faithfully
imitated internal conventions — commits under the maintainer's identity, house-style
messages, an imitated ``Lane:`` trailer — twice, across two PRs, before the
audience-scoped fix landed. **The contributor did nothing wrong.** Every public doc is
executable input for every reader's agent, and theirs did exactly what our files taught
it.

A lane runbook is worse than an instruction file, because it is procedural and
role-shaped: it would recruit some future contributor's agent into *being* the gate —
merging, certifying, signing — with none of the standing context. Sprout has exactly one
gate, and the model breaks with two.

## Two layers, because each catches what the other cannot

**1. Path shape** — the file that is obviously internal and mis-staged. The common
accident.

**2. A sentinel** — an exact string an internal document carries deliberately. This
catches the file that is internal by *content* under an innocuous name, which is the
accident that matters: nobody reviewing a diff titled ``notes.md`` looks twice.

Deliberately **not** a content heuristic. Prose scanning produces false positives on
legitimate process docs — ``docs/process/`` and ``docs/team/OPERATIONS.md`` are
*supposed* to be here — and a guard that cries wolf gets bypassed rather than obeyed.

## Why the path patterns are narrow

The obvious denylist (``*runbook*``, ``*transcript*``, ``*relay*``, ``*lane*``) matches
**five files already tracked in this repo**, every one of them legitimately public:

    docs/bench-procedures/front-door-launch-runbook.md
    docs/bench-procedures/pumps-relays-bringup-run-sheet.md
    docs/flaura-video-transcript.txt
    docs/design/foundations/Sprout Band-Lane Visual Language.dc.html
    docs/design/library/thumbs/band-lane-visual-language.png

A guard that fires on those on day one is a guard someone switches off in week one — so
the patterns below are anchored to *directories and compounds that only internal
material uses*, and there is a test asserting the whole tracked tree passes.

## The known gap, stated rather than hidden

The sentinel only protects documents that carry it, so adding it is part of authoring an
internal doc. A new internal file created without the marker is unprotected. The
counterpart — a check in the *internal* repo flagging its own files that lack the
sentinel — is what keeps the two halves honest, and it does not live here.

    python tools/dx/internal_prompt_guard.py --check
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# The marker an internal document carries deliberately. Assembled at runtime so this
# file — and only this file — does not itself contain the literal it searches for. The
# alternative is a skip-list, which silently stops protecting the guard's own directory.
SENTINEL = "SPROUT-" + "INTERNAL-ONLY"

# Anchored to shapes only internal material uses. Every pattern below was checked
# against the full tracked tree; see test_internal_prompt_guard.py.
PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("internal directory", re.compile(r"(^|/)_?internal/", re.I)),
    ("agent-lane directory", re.compile(r"(^|/)\.agents?/", re.I)),
    ("lane prompt/runbook", re.compile(r"lane[-_](prompt|runbook|brief|relay)", re.I)),
    ("prompt library", re.compile(r"(^|/)(lane[-_])?prompts?/", re.I)),
    ("session transcript", re.compile(r"(^|/)transcripts?/", re.I)),
    (
        "lane-addressed doc",
        # `sprout-workflow-lane.md`, `dx-lane-notes.md` — the lane names are the tell.
        re.compile(
            r"(^|/)[\w.-]*\b(workflow|trellis|dx|design|data|firmware)[-_]lane\b", re.I
        ),
    ),
    ("relay draft", re.compile(r"relay[-_]draft|draft[-_]relay", re.I)),
)


class Finding:
    def __init__(self, path: str, why: str):
        self.path, self.why = path, why

    def __str__(self) -> str:
        return f"  {self.path}\n      {self.why}"


def check_path(rel: str) -> str | None:
    norm = rel.replace("\\", "/")
    for name, pat in PATH_PATTERNS:
        if pat.search(norm):
            return (
                f"path matches an INTERNAL shape ({name}). Internal lane material "
                "lives in the private workspace repo by deliberate placement — every "
                "public doc is executable input for every reader's agent (#1117/#1129)."
            )
    return None


def check_content(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if SENTINEL in text:
        return (
            f"file carries the {SENTINEL} sentinel. It is marked internal by its "
            "author; it does not belong in the public repo."
        )
    return None


def _staged() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=_REPO,
    )
    return [p for p in out.stdout.splitlines() if p.strip()]


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=_REPO,
    )
    return [p for p in out.stdout.splitlines() if p.strip()]


def scan(paths: list[str], root: Path = _REPO) -> list[Finding]:
    findings: list[Finding] = []
    for rel in paths:
        why = check_path(rel)
        if why:
            findings.append(Finding(rel, why))
            continue
        p = root / rel
        if p.is_file():
            why = check_content(p)
            if why:
                findings.append(Finding(rel, why))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="non-zero on findings")
    ap.add_argument("--all", action="store_true", help="scan the whole tracked tree")
    ap.add_argument("filenames", nargs="*", help="pre-commit passes staged files")
    a = ap.parse_args(argv)

    paths = a.filenames or (_tracked() if a.all else _staged())
    findings = scan(paths)
    if findings:
        print(
            "internal-prompt-guard: these look like INTERNAL lane material and must "
            "not enter the public repo (#1659):",
            file=sys.stderr,
        )
        for f in findings:
            print(str(f), file=sys.stderr)
        print(
            "\n  If this is genuinely public, the path shape is the thing to change — "
            "do not weaken the pattern to fit one file.\n"
            f"  If it is internal, move it to the workspace repo. The {SENTINEL} "
            "sentinel is how a doc under an innocuous name declares itself.",
            file=sys.stderr,
        )
        return 1 if a.check else 0
    print(f"internal-prompt-guard: {len(paths)} path(s) clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
