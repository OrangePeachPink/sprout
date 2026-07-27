#!/usr/bin/env python3
"""#1658 — propagate milestones to PRs, by numeric ID, verified after write.

Implements the maintainer's ruling (RELEASE_CUT §1.1): **PRs carry the version
milestone as a rule**, because work is traced through the PR queue and contributors are
credited on PRs. Today that is manual and does not scale — the v0.8.1 cut needed a
77-PR backfill, and the loop hit a two-minute tool timeout partway through.

## Where it runs, and why not at merge

**Queue-entry is the primary moment** (amended). A milestone applied at merge helps the
*record*; the maintainer asked for it while *reviewing* — "I work mostly on a PR queue…
having them link to the milestone is a handy feature." Propagating when a PR enters the
queue delivers it when it is useful. **Merge-time reconciliation is the fallback**,
catching PRs that never passed through the queue: V2 accelerated merges, dependency
bumps.

## The four rules, each of which cost the v0.8.1 cut something

1. **Numeric milestone IDs, never titles.** `gh pr edit --milestone "v0.8.1"` resolves
   by title *only while the milestone is open*, and §1.1's corrections happen **after**
   §2 closes it — so the failing form is the one a releaser reaches for at exactly the
   moment it stops working.
2. **Verify the mutation; never assume it.** GitHub returned 504s on project mutations
   twice during this cut and one write silently did not apply.
3. **Conflicting referenced milestones FAIL for a human.** A PR referencing issues in
   two milestones is a scope question. A helper that silently picks one is a helper that
   quietly decides what shipped.
3b. **A CLOSED milestone is never propagated** — found by running this against real
   PRs. `#1642` references `#1346`, which sits on the already-shipped `v0.8.1`; blind
   inheritance would back-date a PR onto a released version. §1.1's own doctrine settles
   it: *the tag is the line*, so whatever merges now ships in the NEXT version whatever
   milestone its issue carries. This is the mirror of rule 4 — one fabricates forward,
   the other backward.
4. **Bound the sweep by the previous tag.** Sweeping "everything unmilestoned"
   back-dates earlier releases' PRs into this one — a record *fabrication*, not a
   correction.

## Link discovery — and a defect found while building this

`closingIssuesReferences` is authoritative but **under-reports this repo's convention**.
GitHub's parser needs the keyword repeated per issue: `Closes #1, #2, #3` links only
**#1**. Measured on PR #1685, which named four issues and linked one. This repo also
uses a bare `Refs #N` trailer heavily, which creates no link at all.

So links are the UNION of the API's closing references and the body's `Refs`/`Closes`
mentions. Relying on the API alone would silently propagate almost nothing here, and
report success while doing it.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time

DEFAULT_REPO = "OrangePeachPink/sprout"

# `Closes #12`, `Refs #12`, `fixes #12` — the keyword-per-issue forms GitHub honours,
# PLUS the bare `Refs` trailer this repo uses, which GitHub does not link at all.
_KEYWORD = r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?|references?)"
# A keyword followed by a RUN of issue numbers: `Closes #1, #2 and #3`. Matching only
# the first `#N` after the keyword would reproduce exactly the GitHub behaviour this
# union exists to compensate for — which is what the first draft here did, and what the
# test caught.
_REF_RUN = re.compile(rf"\b{_KEYWORD}\b[:\s]*((?:#\d+(?:\s*(?:,|and|&)\s*)?)+)", re.I)
_NUM = re.compile(r"#(\d+)")


def referenced_issues(body: str, api_links: list[int]) -> list[int]:
    """Union of what GitHub linked and what the body says.

    Deliberately a union, not a preference. The API misses `Refs` entirely and misses
    every issue after the first in a comma list; the text misses nothing but can pick up
    a mention in prose. Over-collecting is the safe direction: a wrong extra reference
    surfaces as a CONFLICT and asks a human, whereas a missed reference propagates
    nothing and reports success.
    """
    found: set[int] = set()
    for run in _REF_RUN.findall(body or ""):
        found.update(int(n) for n in _NUM.findall(run))
    found.update(api_links)
    return sorted(found)


class Conflict(Exception):
    """Two milestones among one PR's referenced issues — a scope question."""


def decide_milestone(issue_milestones: dict[int, tuple[int, str, str] | None]):
    """(milestone_id, title) to apply, or None. Raises Conflict when they disagree.

    Issues with NO milestone are ignored rather than treated as a vote for "none" — a
    PR that fixes a milestoned issue and mentions an unmilestoned one still belongs to
    the release.
    """
    named = {ms for ms in issue_milestones.values() if ms is not None}
    if not named:
        return None
    if len(named) > 1:
        detail = ", ".join(
            f"#{n} -> {ms[1]}" for n, ms in sorted(issue_milestones.items()) if ms
        )
        raise Conflict(
            f"referenced issues sit in {len(named)} different milestones ({detail}). "
            "That is a scope question, not a formatting one — resolve it by hand."
        )
    return next(iter(named))


# ---- I/O ------------------------------------------------------------------------


def _run(args: list[str]) -> tuple[int, str]:
    out = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return out.returncode, out.stdout


def _gh_json(args: list[str], default):
    code, raw = _run(["gh", *args])
    if code != 0:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


def pr_facts(number: int, repo: str) -> dict | None:
    return _gh_json(
        [
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,body,milestone,closingIssuesReferences,state",
        ],
        None,
    )


def issue_milestone(number: int, repo: str) -> tuple[int, str, str] | None:
    """(id, title, state). REST, not GraphQL — heavy board work exhausts the GraphQL
    limit while REST stays healthy, and this is the loop that runs 77 times."""
    data = _gh_json(["api", f"repos/{repo}/issues/{number}"], {})
    ms = data.get("milestone")
    return (ms["number"], ms["title"], ms.get("state", "open")) if ms else None


def set_milestone(number: int, repo: str, ms_id: int) -> bool:
    """Write by NUMERIC id, then RE-READ. Rule 1 and rule 2, together.

    `gh pr edit --milestone <title>` is deliberately not used: it resolves by title only
    while the milestone is open, and the corrections that need this happen after it
    closes.
    """
    _run(
        [
            "gh",
            "api",
            "-X",
            "PATCH",
            f"repos/{repo}/issues/{number}",
            "-F",
            f"milestone={ms_id}",
        ]
    )
    for _ in range(4):
        time.sleep(2)
        got = issue_milestone(number, repo)
        if got and got[0] == ms_id:
            return True
    return False


def propagate_one(number: int, repo: str, apply: bool) -> tuple[str, str]:
    """(verdict, detail) for one PR.

    Verdicts: set, would-set, ok, none, CONFLICT, FAIL.
    """
    pr = pr_facts(number, repo)
    if pr is None:
        return "FAIL", f"#{number}: no such PR on {repo}"
    api_links = [i["number"] for i in pr.get("closingIssuesReferences", [])]
    refs = referenced_issues(pr.get("body") or "", api_links)
    if not refs:
        return "none", f"#{number}: references no issue"

    milestones = {n: issue_milestone(n, repo) for n in refs}
    try:
        target = decide_milestone(milestones)
    except Conflict as exc:
        return "CONFLICT", f"#{number}: {exc}"
    if target is None:
        return "none", f"#{number}: referenced issues carry no milestone"

    ms_id, ms_title, ms_state = target
    if ms_state == "closed":
        return "CONFLICT", (
            f"#{number}: referenced issue(s) sit on {ms_title}, which is CLOSED. "
            "Inheriting it would back-date this PR onto a shipped release — and §1.1's "
            "own rule is that the tag is the line: whatever merges now ships in the "
            "NEXT version, whatever milestone its issue carries. Set the open "
            "milestone by hand, or re-milestone the issue if it genuinely slipped."
        )
    current = pr.get("milestone") or {}
    if current.get("title") == ms_title:
        return "ok", f"#{number}: already {ms_title}"
    if not apply:
        return "would-set", f"#{number}: -> {ms_title} (from {sorted(milestones)})"
    if set_milestone(number, repo, ms_id):
        return "set", f"#{number}: -> {ms_title}"
    return "FAIL", (
        f"#{number}: wrote milestone {ms_id} but a re-read does not show it. "
        "GitHub returned 504s on mutations during the v0.8.1 cut and one write "
        "silently did not apply — do not assume this one landed."
    )


def queue_prs(repo: str) -> list[int]:
    """PRs in the maintainer's review queue — the primary propagation moment."""
    prs = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,labels",
        ],
        [],
    )
    return [
        p["number"]
        for p in prs
        if any(x["name"] == "needs:maintainer" for x in p.get("labels", []))
    ]


def merged_since_previous_tag(repo: str) -> list[int]:
    """The fallback sweep, BOUNDED (rule 4).

    Merged PRs from earlier releases are also unmilestoned; sweeping without this bound
    back-dates them into the current version, turning a correction into a fabrication.
    """
    prev = _gh_json(["release", "view", "--repo", repo, "--json", "publishedAt"], {})
    since = prev.get("publishedAt")
    if not since:
        return []
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
            "number,mergedAt,milestone",
        ],
        [],
    )
    return [
        p["number"]
        for p in prs
        if p.get("mergedAt", "") > since and not p.get("milestone")
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument(
        "--pr",
        type=int,
        action="append",
        default=[],
        help="propagate for these PR numbers (repeatable)",
    )
    ap.add_argument(
        "--queue",
        action="store_true",
        help="every PR in the review queue — the primary moment",
    )
    ap.add_argument(
        "--reconcile",
        action="store_true",
        help="fallback sweep: merged since the previous tag, unmilestoned",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="actually write; without it this reports and changes nothing",
    )
    a = ap.parse_args(argv)

    targets = list(a.pr)
    if a.queue:
        targets += queue_prs(a.repo)
    if a.reconcile:
        targets += merged_since_previous_tag(a.repo)
    targets = sorted(set(targets))
    if not targets:
        print("milestone-propagate: nothing to do.")
        return 0

    print(
        f"milestone-propagate: {len(targets)} PR(s)"
        f"{'' if a.apply else ' (dry run — pass --apply to write)'}\n"
    )
    verdicts = [propagate_one(n, a.repo, a.apply) for n in targets]
    for v, detail in verdicts:
        print(f"  {v:<9} {detail}")

    bad = [d for v, d in verdicts if v in {"CONFLICT", "FAIL"}]
    print()
    if bad:
        print(f"milestone-propagate: {len(bad)} need a human.", file=sys.stderr)
        return 1
    changed = sum(1 for v, _ in verdicts if v in {"set", "would-set"})
    print(
        f"milestone-propagate: {changed} change(s), {len(verdicts) - changed} already "
        "correct or not applicable."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
