"""Epic sub-issue hygiene lint — makes the ADR-0003 §2 standard self-enforcing.

ADR-0003 §2 defines an **Epic** as "a parent issue with **native sub-issues**
(progress bar)" — not a body full of `- [ ] #N` markdown checkboxes. Prose
checklists go stale silently: a child split off *after* the body was written
(e.g. #302, split from #271) never appears in the checklist, and automated
sweeps that trust the prose miss it. Native sub-issues give a real progress bar,
a trustworthy roll-up, and a relationship the API can query — which is what lets
the release/verification sweeps rely on structure instead of stale text.

This lint scans OPEN issues and reports, **warn-only by default**, any epic that
tracks work in prose the native way would track it:

  PRIMARY   an `epic`-labelled issue that has `- [ ] #N` checkbox refs but
            *zero* native sub-issues  → it should be wired with sub-issues.
  PARTIAL   an `epic`-labelled issue with some native sub-issues but ALSO
            checkbox `#N` refs that aren't linked → finish the migration.
  NOTICE    an issue *titled* like an epic ("Epic: …") that lacks the `epic`
            label → it won't be governed by this standard at all (label it).

It reads live GitHub issue data (sub-issue relationships aren't in the repo
tree), so it runs via `gh` (local: your authenticated CLI; CI: GITHUB_TOKEN) —
NOT as a file/pre-commit lint. Same logic local == CI; only the token differs.

Usage:
  # local (uses your `gh auth`):
  uv run --frozen python tools/dx/lint_epic_subissues.py
  # gate mode (non-zero exit if any finding) — for an optional required check:
  uv run --frozen python tools/dx/lint_epic_subissues.py --strict

Exit: 0 when clean (or warn-only); 1 only with --strict and findings, or on a
usage error. API/tooling unavailability is a notice, never a hard failure — a
hygiene warn must not break unrelated CI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

DEFAULT_REPO = "OrangePeachPink/plants"
EPIC_LABEL = "epic"
CHECKBOX = re.compile(r"^\s*-\s*\[[ xX]\]")
REF = re.compile(r"#(\d+)")
TITLE_LOOKS_EPIC = re.compile(r"^\s*epic\b", re.IGNORECASE)

IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def gh_graphql(query: str, variables: dict | None = None) -> dict:
    """Run a GraphQL query via gh; force UTF-8 (bodies carry em-dashes/emoji)."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in (variables or {}).items():
        cmd += ["-F", f"{k}={v}"]
    r = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if r.returncode != 0:
        return {"_error": (r.stderr or "").strip()}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        return {"_error": f"bad JSON from gh: {e}"}


def fetch_open_issues(repo: str) -> list[dict] | None:
    """All OPEN issues (paginated) with the fields the lint needs; None on failure."""
    owner, name = repo.split("/", 1)
    nodes: list[dict] = []
    cursor = "null"
    while True:
        after = "null" if cursor == "null" else f'"{cursor}"'
        q = f"""query{{repository(owner:"{owner}",name:"{name}"){{
          issues(first:100, after:{after}, states:OPEN){{
            pageInfo{{hasNextPage endCursor}}
            nodes{{number title body
              labels(first:20){{nodes{{name}}}}
              subIssues(first:100){{nodes{{number}}}}}}}}}}}}"""
        d = gh_graphql(q)
        if "_error" in d or "errors" in d:
            return None
        conn = d["data"]["repository"]["issues"]
        nodes.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return nodes


def checkbox_refs(body: str) -> list[int]:
    out: list[int] = []
    for line in (body or "").splitlines():
        if CHECKBOX.match(line):
            for m in REF.finditer(line):
                n = int(m.group(1))
                if n not in out:
                    out.append(n)
    return out


def hashes(refs: list[int]) -> str:
    return " ".join(f"#{r}" for r in refs)


def emit(kind: str, title: str, msg: str) -> None:
    """Human line + a GitHub Actions annotation when running in CI."""
    print(f"  {kind.upper()}: {msg}")
    if IN_ACTIONS:
        # kind is 'warning' or 'notice' — both are non-failing annotations.
        print(f"::{kind} title={title}::{msg}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Epic sub-issue hygiene lint (ADR-0003 §2)."
    )
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPO))
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 if any finding (for use as a required check)",
    )
    args = ap.parse_args(argv)

    issues = fetch_open_issues(args.repo)
    if issues is None:
        print(
            "notice: GitHub issues API unreachable (gh unauthenticated/offline) — "
            "skipping epic hygiene lint (not a failure)."
        )
        return 0

    findings = 0
    summary: list[str] = []

    for it in issues:
        num = it["number"]
        labels = {n["name"] for n in it["labels"]["nodes"]}
        native = {c["number"] for c in it["subIssues"]["nodes"]}
        refs = [r for r in checkbox_refs(it["body"]) if r != num]
        is_epic = EPIC_LABEL in labels

        if is_epic and refs:
            unlinked = [r for r in refs if r not in native]
            if unlinked and not native:
                findings += 1
                emit(
                    "warning",
                    "Epic hygiene",
                    f"#{num} tracks {len(unlinked)} child(ren) as prose checkboxes, "
                    f"no native sub-issues (ADR-0003 §2): {hashes(unlinked)}. "
                    f"Wire them (gh addSubIssue / the backfill helper).",
                )
                summary.append(f"| #{num} | prose-only | {hashes(unlinked)} |")
            elif unlinked:
                findings += 1
                emit(
                    "warning",
                    "Epic hygiene",
                    f"#{num} partially migrated — {len(unlinked)} checkbox ref(s) "
                    f"not linked as sub-issues: {hashes(unlinked)}.",
                )
                summary.append(f"| #{num} | partial | {hashes(unlinked)} |")

        if not is_epic and TITLE_LOOKS_EPIC.match(it["title"] or ""):
            emit(
                "notice",
                "Epic labelling",
                f"#{num} is titled like an epic but lacks the `{EPIC_LABEL}` "
                f"label, so the standard won't govern it (ADR-0003 §2).",
            )
            summary.append(f"| #{num} | unlabelled-epic | — |")

    if IN_ACTIONS and summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("### Epic sub-issue hygiene (ADR-0003 §2)\n\n")
            fh.write("| Epic | Issue | Unlinked checkbox refs |\n|---|---|---|\n")
            fh.write("\n".join(summary) + "\n")

    if findings == 0:
        print(
            "epic sub-issue hygiene: clean — every open epic uses native sub-issues. ✅"
        )
        return 0

    print(
        f"\nepic sub-issue hygiene: {findings} epic(s) need attention (warn-only; "
        f"run with --strict to gate)."
    )
    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
