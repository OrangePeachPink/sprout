#!/usr/bin/env python3
"""#1407 tripwire — the product version agrees across every file that declares it.

ADR-0009 §1 declares "a single product version line… synced repo-wide each release
(§3)". Nothing enforced the sync: four files each carried the literal, kept in agreement
by hand. The sharpest consumer is the **citation** — `CITATION.cff` feeds GitHub's "Cite
this repository" widget, and a stale number there is copied verbatim into someone's
paper or dependency note, where it is effectively permanent and looks authoritative.

``pyproject.toml`` is canonical; the rest must match it.

**A declared table, never a grep.** The same literal appears throughout the repo as
*history* — "the v0.7.3 wash (PR #1099)", "standing policy as of v0.7.3", the ADRs'
references to the v0.7.3 plan. Those are correct and must never change: rewriting
them at the next bump would falsify the record (never-stitch, applied to version
strings). A repo-wide search would light up on all of them every release, and the
first thing anyone would do is switch this off. So each site is declared with an
anchored pattern, and a new site is added deliberately.

**Silence is a failure.** A pattern that matches **nothing** means the file was
restructured and the site is no longer watched; a pattern that matches **more than
once** means we cannot say which occurrence we are watching. Both fail loudly rather
than passing — a guard that quietly watches nothing is indistinguishable from one
that passed (the #1327 lesson, and the reason this family exists).

    python tools/dx/version_sync_guard.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

# The canonical source (ADR-0009 §1).
_CANON = ("pyproject.toml", re.compile(r'(?m)^version\s*=\s*"([^"]+)"'))

# Every OTHER file that makes an authoritative version claim. Anchored, one per site.
# Adding a row is a deliberate act; grepping for the literal instead is the anti-pattern
# this guard is built to avoid (see the module docstring).
_SITES = (
    ("CITATION.cff", re.compile(r'(?m)^version:\s*"?([0-9][^"\s]*)"?')),
    (
        "firmware/include/config.h",
        re.compile(r'PLANTS_FW_VERSION\[\]\s*=\s*"([^"]+)"'),
    ),
    # the JSON-LD SoftwareApplication block that feeds search engines
    ("docs/index.html", re.compile(r'(?m)^\s*"version":\s*"([^"]+)"')),
)


class Finding:
    def __init__(self, path: str, detail: str):
        self.path, self.detail = path, detail

    def __str__(self) -> str:
        return f"  {self.path}  {self.detail}"


def _read(repo: Path, rel: str) -> str | None:
    p = repo / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def _line_of(text: str, needle: str) -> int:
    for n, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return n
    return 0


def extract(text: str, pattern: re.Pattern) -> tuple[str | None, str | None]:
    """(version, error). Zero or multiple matches are errors, never a pass."""
    found = pattern.findall(text)
    if not found:
        return None, (
            "pattern matched NOTHING — the file changed shape and this site is no "
            "longer being checked. Fix the pattern; do not delete the row."
        )
    if len(found) > 1:
        return None, (
            f"pattern matched {len(found)} times ({', '.join(found)}) — ambiguous, so "
            "we cannot say which one is being watched. Tighten the anchor."
        )
    return found[0], None


def canonical_version(repo: Path = _REPO) -> tuple[str | None, Finding | None]:
    rel, pat = _CANON
    text = _read(repo, rel)
    if text is None:
        return None, Finding(
            rel, "MISSING — the canonical version source is not there."
        )
    v, err = extract(text, pat)
    return (v, None) if v else (None, Finding(rel, err or "unreadable"))


def check(repo: Path = _REPO) -> list[Finding]:
    canon, bad = canonical_version(repo)
    if bad:
        return [bad]
    findings: list[Finding] = []
    for rel, pat in _SITES:
        text = _read(repo, rel)
        if text is None:
            findings.append(Finding(rel, "MISSING — a declared version site is gone."))
            continue
        v, err = extract(text, pat)
        if err:
            findings.append(Finding(rel, err))
        elif v != canon:
            ln = _line_of(text, v)
            findings.append(
                Finding(f"{rel}:{ln}", f"has {v!r}, canonical is {canon!r}")
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1407: the version agrees everywhere")
    ap.add_argument(
        "--check", action="store_true", help="report + non-zero on findings"
    )
    ap.add_argument("filenames", nargs="*", help="ignored (pre-commit passes files)")
    args = ap.parse_args(argv)

    findings = check()
    if findings:
        print(
            "version-sync-guard: the product version disagrees across the files that "
            "declare it (#1407). pyproject.toml is canonical:",
            file=sys.stderr,
        )
        for f in findings:
            print(str(f), file=sys.stderr)
        print(
            "  A release bumps ALL of them together (ADR-0009 §3). Historical mentions "
            "of an old version in docs/ADRs are correct — never rewrite those.",
            file=sys.stderr,
        )
        return 1 if args.check else 0

    canon, _ = canonical_version()
    print(f"version-sync-guard: {len(_SITES) + 1} declared site(s) agree on {canon}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
