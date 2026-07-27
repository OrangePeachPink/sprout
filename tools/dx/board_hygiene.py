#!/usr/bin/env python3
"""#732 board-hygiene lint — the board must tell the truth.

Codifies the reconcile sweeps Workflow ran by hand (the 2026-07-19 morning
reconcile is the type specimen) into one command. Three drift classes:

1. **closed-not-Done** (BLOCKING): an issue/PR that is closed or merged whose
   board card is not in a terminal column (Done / Won't Do). A 15-minute grace
   window absorbs the project-automation lag right after a merge/close.
2. **stale In Progress** (advisory): an open issue sitting In Progress with no
   activity for ``--stale-days`` (default 4) — the #1027 class: a column
   claiming work that nobody is doing.
3. **oversized milestone** (advisory): more than ``--milestone-warn`` (default
   40) open issues on one milestone — a planning smell, not a defect.

Advisory classes never fail the run; class 1 exits non-zero unless
``--advisory``. Event-driven by doctrine: run at release cut (RELEASE_CUT.md)
or on demand via ``just board-hygiene`` — never on a calendar.

Needs a token with ProjectV2 read scope (the local ``gh`` login has it; plain
CI GITHUB_TOKEN does not — which is why this is a local/cut-time tool, not a
per-PR CI job).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

PROJECT_ID = "PVT_kwHOCpHTeM4Bbmep"  # the Sprout board (user project #2)
TERMINAL = {"Done", "Won't Do"}
CLOSED_STATES = {"CLOSED", "MERGED"}
GRACE = timedelta(minutes=15)  # project-automation lag after merge/close

_QUERY = """
query($cursor: String) {
  node(id: "PROJECT_NODE_ID") {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          content {
            __typename
            ... on Issue {
              number title state closedAt updatedAt
              milestone { title }
            }
            ... on PullRequest { number title state closedAt updatedAt }
          }
        }
      }
    }
  }
}
""".replace("PROJECT_NODE_ID", PROJECT_ID)


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def classify_closed_not_done(item: dict, now: datetime) -> bool:
    """Class 1: closed/merged content whose card is not terminal (post-grace)."""
    content = item.get("content") or {}
    if content.get("state") not in CLOSED_STATES:
        return False
    status = (item.get("status") or "").strip()
    if status in TERMINAL:
        return False
    closed_at = _parse_ts(content.get("closedAt"))
    # inside the grace window, automation may still be moving the card
    return not (closed_at is not None and now - closed_at < GRACE)


def classify_stale_in_progress(item: dict, now: datetime, stale_days: int) -> bool:
    """Class 2: an OPEN issue In Progress with no activity for stale_days."""
    content = item.get("content") or {}
    if content.get("__typename") != "Issue" or content.get("state") != "OPEN":
        return False
    if (item.get("status") or "") != "In Progress":
        return False
    updated = _parse_ts(content.get("updatedAt"))
    return updated is not None and (now - updated) >= timedelta(days=stale_days)


def milestone_counts(items: list[dict]) -> Counter:
    """Open-issue count per milestone title (board-derived)."""
    counts: Counter = Counter()
    for item in items:
        content = item.get("content") or {}
        if content.get("__typename") == "Issue" and content.get("state") == "OPEN":
            ms = (content.get("milestone") or {}).get("title")
            if ms:
                counts[ms] += 1
    return counts


def _fetch_items() -> list[dict]:
    """All board items as {status, content} dicts, via the gh CLI (paginated)."""
    items: list[dict] = []
    cursor: str | None = None
    while True:
        cmd = ["gh", "api", "graphql", "-f", f"query={_QUERY}"]
        if cursor:
            cmd += ["-f", f"cursor={cursor}"]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if out.returncode != 0:
            err = out.stderr.strip()
            print(f"board-hygiene: gh api failed: {err}", file=sys.stderr)
            sys.exit(2)
        page = json.loads(out.stdout)["data"]["node"]["items"]
        for node in page["nodes"]:
            fv = node.get("fieldValueByName") or {}
            items.append({"status": fv.get("name"), "content": node.get("content")})
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]


def _label(content: dict) -> str:
    kind = "PR" if content.get("__typename") == "PullRequest" else "#"
    title = (content.get("title") or "")[:64]
    return f"{kind}{content.get('number')} {title}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stale-days", type=int, default=4)
    ap.add_argument("--milestone-warn", type=int, default=40)
    ap.add_argument(
        "--advisory", action="store_true", help="never exit non-zero (report only)"
    )
    args = ap.parse_args()
    # Windows consoles default to cp1252; issue titles carry arrows/em-dashes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    now = datetime.now(timezone.utc)

    items = _fetch_items()
    closed_not_done = [
        i for i in items if classify_closed_not_done(i, now) and i.get("content")
    ]
    stale = [i for i in items if classify_stale_in_progress(i, now, args.stale_days)]
    oversized = {
        ms: n for ms, n in milestone_counts(items).items() if n > args.milestone_warn
    }

    print(f"board-hygiene (#732): {len(items)} cards swept")
    if closed_not_done:
        n = len(closed_not_done)
        print(f"\nCLOSED-NOT-DONE ({n}) — cards owed a terminal column:")
        for i in closed_not_done:
            print(f"  [{i.get('status') or 'no status'}] {_label(i['content'])}")
    if stale:
        d = args.stale_days
        print(f"\nSTALE IN-PROGRESS ({len(stale)}) — no activity >= {d}d:")
        for i in stale:
            print(f"  {_label(i['content'])}")
    if oversized:
        print("\nOVERSIZED MILESTONES (advisory):")
        for ms, n in sorted(oversized.items()):
            print(f"  {ms}: {n} open issues (> {args.milestone_warn})")
    if not (closed_not_done or stale or oversized):
        print("clean — the board tells the truth.")

    if closed_not_done and not args.advisory:
        print("\nexit 1: closed-not-Done drift must be fixed (or automation broke).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
