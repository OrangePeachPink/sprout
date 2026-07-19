#!/usr/bin/env python3
"""#1161 voice-guard — keep the retired register from migrating back in.

The v0.7.3 wash (PR #1099) retired a register from user-facing copy: the
noun-frames, the "…is truth" formulas, the judgment hooks aimed at other
products, and the "Sprout is a plant" copula (the #1138 register rule:
first-person voice personifies freely; third-person definitional copy says
what Sprout *is* — an app, an assistant — never "a plant"). The maintainer's
concern at ship: without a guard, the old register migrates back one PR at a
time.

This guard scans **changed lines only** (staged diff by default) for the
high-signal retired patterns and **warns** — advisory, a teacher not a wall
(exit 0 unless ``--strict``; promotion to blocking is a later maintainer
call). Deliberately NOT flagged: adjectival ``honest``/``honestly`` (the wash
kept engineering-descriptive uses), the canonical exceptions (``source of
truth``, ``ground truth`` — no pattern matches them), and code identifiers
like ``honesty_gates`` (word boundaries stop at ``_``).

Modes:
    --check                 staged diff (the pre-commit hook; default)
    --diff-range A..B       a git range (e.g. origin/main...HEAD for a PR)
    --all                   full-tree sweep (the RELEASE_CUT backstop recipe)
    --strict                exit non-zero on findings (reserved for promotion)

Suppress a deliberate mention with an inline marker: ``voice-guard: allow``.
Run standalone: ``python tools/dx/voice_guard.py --check``.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# High-signal retired-register patterns (#1099 digest = the spec of retired vs
# kept). Tuned for near-zero false positives; anything softer stays a human
# judgment at the release sweep.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "noun-frame",
        re.compile(r"\bhonesty\b|\bhonest data\b|\bdishonest|\bmoraliz\w*", re.I),
    ),
    (
        "is-truth formula",
        re.compile(r"\braw \+ band (?:is|are) truth\b|\bis truth\b|=\s*truth\b", re.I),
    ),
    (
        "judgment hook",
        re.compile(
            r"\brefuses? to lie\b|\bfake %|\bfake percent|\bmade-?up number", re.I
        ),
    ),
    (
        "copula (#1138)",
        re.compile(
            # (?![\w-]) spares plant-care/plant-first/plants; the noun list
            # spares descriptors like "the plant monitor on your sill".
            r"\bSprout is (?:a|the) plant"
            r"(?![\w-])"
            r"(?!\s+(?:monitor|assistant|companion|voice|app|care))",
            re.I,
        ),
    ),
]

ALLOW_MARKER = "voice-guard: allow"

# Historical record and fixtures stay out of scope: evidence trees, archives,
# the changelog, ADRs (they record the rename), and this guard's own files.
SKIP_PARTS = ("docs/evidence/", "docs/archive/", "_archive/", ".git/")
SKIP_NAMES = ("CHANGELOG.md", "voice_guard.py", "test_voice_guard.py")
SKIP_DIR_PARTS = ("docs/adr/",)

_REPO = Path(__file__).resolve().parents[2]

# Text surfaces worth scanning in --all mode (diff modes scan whatever changed).
_TREE_GLOBS = ("*.md", "*.html", "*.json", "*.py", "*.js", "*.yml", "*.yaml")


def _skipped(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/")
    if any(part in norm for part in SKIP_PARTS + SKIP_DIR_PARTS):
        return True
    return norm.rsplit("/", 1)[-1] in SKIP_NAMES


def scan_line(text: str) -> list[str]:
    """Names of every retired-register pattern present on one line."""
    if ALLOW_MARKER in text:
        return []
    return [name for name, pat in PATTERNS if pat.search(text)]


def _added_lines(diff_text: str):
    """(path, lineno, text) for every added line in a unified diff (-U0)."""
    path, lineno = None, 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            lineno = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            if path is not None and not _skipped(path):
                yield path, lineno, raw[1:]
            lineno += 1


def collect_from_diff(diff_args: list[str]) -> list[tuple[str, int, str, list[str]]]:
    out = subprocess.run(
        ["git", "diff", "--no-color", "-U0", *diff_args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=_REPO,
    )
    hits = []
    for path, lineno, text in _added_lines(out.stdout):
        names = scan_line(text)
        if names:
            hits.append((path, lineno, text.strip(), names))
    return hits


def collect_from_tree(root: Path = _REPO) -> list[tuple[str, int, str, list[str]]]:
    hits = []
    for glob in _TREE_GLOBS:
        for path in sorted(root.rglob(glob)):
            rel = str(path.relative_to(root))
            if _skipped(rel) or "node_modules" in rel:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                names = scan_line(line)
                if names:
                    hits.append((rel, lineno, line.strip(), names))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true", help="scan the staged diff (default)"
    )
    ap.add_argument("--diff-range", metavar="A..B", help="scan a git diff range")
    ap.add_argument(
        "--all", action="store_true", help="full-tree sweep (release backstop)"
    )
    ap.add_argument("--strict", action="store_true", help="exit non-zero on findings")
    args = ap.parse_args()

    if args.all:
        hits = collect_from_tree()
    elif args.diff_range:
        hits = collect_from_diff([args.diff_range])
    else:
        hits = collect_from_diff(["--cached"])

    if not hits:
        return 0

    print(
        "voice-guard (#1161): retired-register language in these lines --",
        file=sys.stderr,
    )
    for path, lineno, text, names in hits:
        shown = text if len(text) <= 96 else text[:93] + "..."
        print(f"  {path}:{lineno}  [{', '.join(names)}]  {shown}", file=sys.stderr)
    print(
        "\nThe register moved on (PR #1099's wash; the #1138 rule): describe\n"
        "what the reading IS (raw + band), keep self-candor as a voice trait,\n"
        "and say what Sprout is (an app, an assistant) -- never 'a plant'.\n"
        "Deliberate mention? add 'voice-guard: allow' inline. Advisory for\n"
        "now -- this message is the enforcement.",
        file=sys.stderr,
    )
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
