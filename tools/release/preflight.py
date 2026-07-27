#!/usr/bin/env python3
"""#1661 `just release-preflight <tag>` — one pass/fail table before §2 closes.

At the v0.8.1 cut these were ~15 separate manual queries spread across an hour, and
**four of them did not exist as checks at all** — they were found by the maintainer
asking questions rather than by a gate.

**Runs BEFORE §2's milestone close**, because that is the last moment corrections are
cheap: after §2 the draft exists, and after §6 the assets are immutable.

The point is not that any check is hard. It is that they lived nowhere, so they were
only as reliable as whoever remembered to ask.

    just release-preflight v0.8.2
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPO = "OrangePeachPink/sprout"
sys.path.insert(0, str(REPO_ROOT))


def _gh_json(args: list[str], default):
    out = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if out.returncode != 0:
        return default
    try:
        return json.loads(out.stdout)
    except ValueError:
        return default


class Row:
    def __init__(self, name: str, ok: bool | None, detail: str):
        self.name, self.ok, self.detail = name, ok, detail

    @property
    def mark(self) -> str:
        return {True: "PASS", False: "FAIL", None: "SKIP"}[self.ok]


def check_version_and_date_sites() -> list[Row]:
    """§1 — delegated to the guard rather than restated.

    Restating them here would be a second implementation of the same rule, and the two
    would drift. The guard already covers five version sites plus both date rows and
    their agreement (#1407/#1633/#1637).
    """
    from tools.dx import version_sync_guard as g

    findings = g.check()
    if not findings:
        return [Row("version + date sites", True, "all declared sites agree")]
    return [Row("version + date sites", False, str(f).strip()) for f in findings]


_SECTION = re.compile(r"(?m)^##\s*\[([^\]]+)\]")


def check_changelog_has_section(tag: str) -> Row:
    """§4 — `[0.8.0]` was missing from CHANGELOG.md entirely at the v0.8.1 cut."""
    version = tag.lstrip("v")
    path = REPO_ROOT / "CHANGELOG.md"
    if not path.exists():
        return Row("CHANGELOG section", False, "CHANGELOG.md is missing")
    found = _SECTION.findall(path.read_text(encoding="utf-8"))
    if version in found:
        return Row("CHANGELOG section", True, f"[{version}] present")
    return Row(
        "CHANGELOG section",
        False,
        f"no [{version}] section — found: {', '.join(found[:4]) or 'none'}",
    )


def check_milestone(tag: str, repo: str) -> list[Row]:
    """§0 + §1.1 — the milestone must be empty of open work, and nothing merged for
    this release may be sitting under a different milestone."""
    rows: list[Row] = []
    open_issues = _gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--milestone",
            tag,
            "--json",
            "number",
            "--limit",
            "200",
        ],
        None,
    )
    if open_issues is None:
        rows.append(Row("milestone open items", None, f"no milestone {tag} on {repo}"))
    elif open_issues:
        nums = ", ".join(f"#{i['number']}" for i in open_issues[:8])
        rows.append(
            Row("milestone open items", False, f"{len(open_issues)} still open: {nums}")
        )
    else:
        rows.append(Row("milestone open items", True, "none open"))

    open_prs = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number,milestone",
            "--limit",
            "200",
        ],
        [],
    )
    on_ms = [p for p in open_prs if (p.get("milestone") or {}).get("title") == tag]
    if on_ms:
        nums = ", ".join(f"#{p['number']}" for p in on_ms[:8])
        rows.append(Row("no open PR on milestone", False, f"{len(on_ms)}: {nums}"))
    else:
        rows.append(Row("no open PR on milestone", True, "none"))
    return rows


def check_contributors(repo: str) -> Row:
    """§1.2 — v0.8.1 shipped a FALSE credit, and the check did not exist.

    Advisory by design: this reports who merged since the previous tag so the operator
    reconciles the record against a query rather than against the week's impression. It
    cannot know who *should* be listed, and pretending otherwise would be a gate that
    fails on a correct release.
    """
    prev = _gh_json(["release", "view", "--repo", repo, "--json", "publishedAt"], {})
    since = prev.get("publishedAt")
    if not since:
        return Row("contributors since last tag", None, "no previous release to bound")
    prs = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "merged",
            "--limit",
            "200",
            "--json",
            "author,mergedAt",
        ],
        [],
    )
    owner = repo.split("/")[0]
    others = sorted(
        {
            p["author"]["login"]
            for p in prs
            if p.get("mergedAt", "") > since
            and p.get("author", {}).get("login")
            and p["author"]["login"] != owner
        }
    )
    if not others:
        return Row("contributors since last tag", True, "no external merges to credit")
    return Row(
        "contributors since last tag",
        None,
        f"reconcile by hand: {', '.join(others)} (§1.2 — a listed contribution that "
        "never merged is a false public claim about someone else's work)",
    )


def preflight(tag: str, repo: str) -> list[Row]:
    rows = list(check_version_and_date_sites())
    rows.append(check_changelog_has_section(tag))
    rows.extend(check_milestone(tag, repo))
    rows.append(check_contributors(repo))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag", help="the release tag being prepared, e.g. v0.8.2")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    a = ap.parse_args(argv)

    rows = preflight(a.tag, a.repo)
    width = max(len(r.name) for r in rows)
    print(f"\nrelease-preflight {a.tag}\n")
    for r in rows:
        print(f"  {r.mark:<4}  {r.name:<{width}}  {r.detail}")

    failed = [r for r in rows if r.ok is False]
    skipped = [r for r in rows if r.ok is None]
    print()
    if skipped:
        print(
            f"  {len(skipped)} check(s) need a human — they are reported, not decided.",
        )
    if failed:
        print(
            f"release-preflight: {len(failed)} FAILURE(S). Fix before closing the "
            "milestone — after §2 the draft exists and after §6 the assets are "
            "immutable.",
            file=sys.stderr,
        )
        return 1
    print("release-preflight: every automated check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
