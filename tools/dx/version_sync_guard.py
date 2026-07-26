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
from datetime import date, datetime, timezone
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
    # #1633: the fifth site, and the one that bites hardest. Every routine command
    # runs `uv run --frozen`; a lock that disagrees with pyproject fails with an error
    # that names none of this, and it lands on whoever runs the next command after a
    # bump merges — most likely a new contributor. Anchored to the `sprout` package
    # BLOCK, not to any `version =` in the file: a lockfile is mostly other packages'
    # versions, and a loose pattern here would match hundreds and fail as ambiguous.
    # Fix a finding by REGENERATING (`uv lock`), never by hand-editing: the lockfile is
    # generated state, and a hand-typed version there is a second unverified claim
    # wearing the costume of a fix.
    (
        "uv.lock",
        re.compile(r'(?m)^\[\[package\]\]\nname = "sprout"\nversion = "([^"]+)"'),
    ),
)


class Finding:
    def __init__(self, path: str, detail: str):
        self.path, self.detail = path, detail

    def __str__(self) -> str:
        return f"  {self.path}  {self.detail}"


def _read(repo: Path, rel: str) -> str | None:
    p = repo / rel
    return p.read_text(encoding="utf-8") if p.exists() else None


def _line_of(text: str, pattern: re.Pattern) -> int:
    """Line of the SITE's match, not of the first place the literal happens to appear.

    #1633: uv.lock is mostly other packages' versions, so searching for the bare string
    would point at whichever dependency shares the number — a guard that names the wrong
    line sends the reader to edit the wrong thing, which is worse than naming no line.
    """
    m = pattern.search(text)
    return text.count("\n", 0, m.start(1)) + 1 if m else 0


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


_DATE_RELEASED = re.compile(r'(?m)^date-released:\s*"?(\d{4}-\d{2}-\d{2})"?')


def check_release_date(repo: Path = _REPO, today: date | None = None) -> Finding | None:
    """#1637: the citation must say WHEN the version it claims existed.

    `date-released` is what anchors a citation to a point in time, and GitHub's "Cite
    this repository" widget renders straight from this file. A version with no date
    asserts "Sprout 0.8.1" with nothing saying when that was.

    Two failures are checkable offline, and both have already happened here:

    * **absent** — every release before v0.8.1 shipped without the field at all.
    * **in the future** — the date is written at RELEASE_CUT §1, BEFORE the tag exists,
      so it is a prediction until the publish click. v0.8.1 was set to 2026-07-25 and
      published 2026-07-26T01:20:53Z: a US-evening cut lands on the next UTC day. The
      field was wrong on its very first outing, by exactly that mechanism.

    What is NOT checkable here is "does it match the published release" — that needs
    the API, which a pre-commit hook has no business calling. That check belongs at
    cut time (#1649). This guard catches the two shapes that need no network.
    """
    text = _read(repo, "CITATION.cff")
    if text is None:
        return None  # the MISSING-site check above already owns this
    m = _DATE_RELEASED.search(text)
    if not m:
        return Finding(
            "CITATION.cff",
            "no date-released — the citation claims a version with no date. Add "
            'date-released: "YYYY-MM-DD" (RELEASE_CUT §1, in UTC).',
        )
    try:
        released = date.fromisoformat(m.group(1))
    except ValueError:
        return Finding("CITATION.cff", f"date-released {m.group(1)!r} is not a date.")
    now = today or datetime.now(timezone.utc).date()
    if released > now:
        return Finding(
            f"CITATION.cff:{_line_of(text, _DATE_RELEASED)}",
            f"date-released is {released} — in the FUTURE (today is {now} UTC). The "
            "citation would date the release before it exists.",
        )
    return None


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
            ln = _line_of(text, pat)
            findings.append(
                Finding(f"{rel}:{ln}", f"has {v!r}, canonical is {canon!r}")
            )
    stale_date = check_release_date(repo)
    if stale_date:
        findings.append(stale_date)
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
            "of an old version in docs/ADRs are correct — never rewrite those.\n"
            "  uv.lock is GENERATED: fix it with `uv lock`, never by hand. A "
            "hand-typed version there is a second unverified claim dressed as a "
            "fix (#1633).",
            file=sys.stderr,
        )
        return 1 if args.check else 0

    canon, _ = canonical_version()
    print(f"version-sync-guard: {len(_SITES) + 1} declared site(s) agree on {canon}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
