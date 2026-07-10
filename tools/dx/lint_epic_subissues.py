"""Epic sub-issue hygiene lint — makes the ADR-0003 §2 standard self-enforcing.

ADR-0003 §2 defines an **Epic** as "a parent issue with **native sub-issues**
(progress bar)" — not a body full of `- [ ]` markdown checkboxes. Prose
checklists go stale silently: a child split off *after* the body was written
(e.g. #302, split from #271) never appears in the checklist, and automated
sweeps that trust the prose miss it. Native sub-issues give a real progress bar,
a trustworthy roll-up, and a relationship the API can query — which is what lets
the release/verification sweeps rely on structure instead of stale text.

It reports, **warn-only by default**, on each open `epic`-labelled issue:

  BODY CHECKBOXES   any `- [ ]` / `- [x]` task-list checkbox in the body — the
                    second-tracker smell (#739): state must live only in native
                    sub-issues, never a body checklist (#810 AC1).
  UNATTACHED REFS   `#N` refs in a bundle/scope section that aren't attached as
                    native sub-issues (best-effort, warn-only — #810 AC2).
  NOTICE            an issue *titled* like an epic ("Epic: …") that lacks the
                    `epic` label → the standard won't govern it (label it).

It reads live GitHub issue data (sub-issue relationships aren't in the repo
tree), so it runs via `gh` (local: your authenticated CLI; CI: GITHUB_TOKEN) —
NOT as a file/pre-commit lint. Same logic local == CI; only the token differs.

Usage:
  # scan every open issue (weekly sweep / local check; annotations only):
  uv run --frozen python tools/dx/lint_epic_subissues.py
  # one issue + post/update its hygiene comment (the issues-event path, #810):
  uv run --frozen python tools/dx/lint_epic_subissues.py --issue 739 --comment
  # gate mode (non-zero exit if any finding) — for an optional required check:
  uv run --frozen python tools/dx/lint_epic_subissues.py --strict

Exit: 0 when clean (or warn-only); 1 only with --strict and findings, or on a
usage error. API/tooling unavailability is a notice, never a hard failure — a
hygiene warn must not break unrelated CI.

The `--comment` surface is **idempotent** (#810 AC4): exactly one marker-tagged
comment per epic, updated in place across runs (never comment-per-edit), and
flipped to "resolved" when the epic goes clean.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

DEFAULT_REPO = "OrangePeachPink/sprout"
EPIC_LABEL = "epic"
CHECKBOX = re.compile(r"^\s*[-*+]\s*\[[ xX]\]")
REF = re.compile(r"#(\d+)")
TITLE_LOOKS_EPIC = re.compile(r"^\s*epic\b", re.IGNORECASE)
# A heading that opens a bundle/scope/children section (the AC2 heuristic).
SCOPE_HEADING = re.compile(
    r"^\s{0,3}#{1,6}\s.*\b(bundle|scope|sub-?issues?|child(ren)?|includes?|checklist)\b",
    re.IGNORECASE,
)
ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
# Hidden HTML comment that tags the one bot-maintained hygiene comment per epic.
MARKER = "<!-- epic-lint:hygiene -->"

IN_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"

ISSUE_FIELDS = (
    "number title body labels(first:20){nodes{name}} "
    "subIssues(first:100){nodes{number}}"
)


def gh_graphql(query: str) -> dict:
    """Run a GraphQL query via gh; force UTF-8 (bodies carry em-dashes/emoji)."""
    r = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
            nodes{{{ISSUE_FIELDS}}}}}}}}}"""
        d = gh_graphql(q)
        if "_error" in d or "errors" in d:
            return None
        conn = d["data"]["repository"]["issues"]
        nodes.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return nodes


def fetch_one_issue(repo: str, number: int) -> list[dict] | None:
    """Just one issue's lint fields (the --issue event path); None on failure."""
    owner, name = repo.split("/", 1)
    q = f"""query{{repository(owner:"{owner}",name:"{name}"){{
      issue(number:{number}){{{ISSUE_FIELDS}}}}}}}"""
    d = gh_graphql(q)
    if "_error" in d or "errors" in d:
        return None
    node = d["data"]["repository"]["issue"]
    return [node] if node else []


# --- pure detection (unit-tested) ------------------------------------------


def body_has_checkboxes(body: str) -> bool:
    """True if the body has ANY task-list checkbox line (#810 AC1)."""
    return any(CHECKBOX.match(line) for line in (body or "").splitlines())


def checkbox_refs(body: str) -> list[int]:
    """Issue numbers referenced on checkbox lines (order-preserving, deduped)."""
    out: list[int] = []
    for line in (body or "").splitlines():
        if CHECKBOX.match(line):
            for m in REF.finditer(line):
                n = int(m.group(1))
                if n not in out:
                    out.append(n)
    return out


def scope_section_refs(body: str) -> list[int]:
    """`#N` refs inside a bundle/scope/children section (best-effort, #810 AC2)."""
    out: list[int] = []
    in_scope = False
    for line in (body or "").splitlines():
        if SCOPE_HEADING.match(line):
            in_scope = True
            continue
        if ANY_HEADING.match(line):  # any other heading closes the section
            in_scope = False
            continue
        if in_scope:
            for m in REF.finditer(line):
                n = int(m.group(1))
                if n not in out:
                    out.append(n)
    return out


def hashes(refs: list[int]) -> str:
    return " ".join(f"#{r}" for r in refs)


def epic_findings(issue: dict) -> list[str]:
    """Hygiene findings for one epic (empty list = clean). AC1 + AC2."""
    num = issue["number"]
    native = {c["number"] for c in issue["subIssues"]["nodes"]}
    body = issue["body"] or ""
    out: list[str] = []

    if body_has_checkboxes(body):
        refs = [r for r in checkbox_refs(body) if r != num]
        detail = ""
        if refs:
            unlinked = [r for r in refs if r not in native]
            detail = f" (checkbox refs {hashes(refs)}" + (
                f"; unwired: {hashes(unlinked)})"
                if unlinked
                else "; all already wired as sub-issues — just delete the checkboxes)"
            )
        out.append(
            "**Body task-list checkboxes.** This epic tracks work as `- [ ]` body "
            "checkboxes. Epic state lives **exclusively in native sub-issues** "
            f"(ADR-0003 §2), never a body checklist.{detail} Move them to sub-issues "
            "and delete the checkboxes."
        )

    cb = set(checkbox_refs(body))
    scope = [
        r
        for r in scope_section_refs(body)
        if r != num and r not in native and r not in cb
    ]
    if scope:
        out.append(
            f"**Unattached scope refs (best-effort).** {hashes(scope)} appear in a "
            "bundle/scope section but aren't attached as native sub-issues. Attach "
            "them — or, if they're only context, this is a warn you can ignore."
        )
    return out


def comment_body(findings: list[str]) -> str:
    """The rendered hygiene comment (marker included). Idempotent by marker."""
    return (
        f"{MARKER}\n### 🤖 Epic hygiene (ADR-0003 §2)\n\n"
        + "\n\n".join(f"- {f}" for f in findings)
        + "\n\n*Maintained by `lint_epic_subissues.py` — it updates in place, never "
        "spams, and resolves itself when the epic is clean.*"
    )


def resolved_body() -> str:
    return (
        f"{MARKER}\n### 🤖 Epic hygiene (ADR-0003 §2) — resolved ✅\n\n"
        "Epic state is fully in native sub-issues; no body task-list checkboxes or "
        "unattached scope refs. Nice."
    )


# --- GitHub write surface (idempotent comment, #810 AC4) -------------------


def find_marker_comment(repo: str, issue: int) -> str | None:
    """The id of this epic's existing hygiene comment (by MARKER), or None."""
    r = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo}/issues/{issue}/comments",
            "--paginate",
            "--jq",
            f'.[] | select(.body | contains("{MARKER}")) | .id',
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        return None
    ids = [x for x in r.stdout.split() if x.strip()]
    return ids[0] if ids else None


def gh_write(method: str, path: str, payload: dict) -> bool:
    """POST/PATCH via gh with a JSON body on stdin (safe for multi-line content)."""
    r = subprocess.run(
        ["gh", "api", "-X", method, path, "--input", "-"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode == 0


def upsert_comment(repo: str, issue: int, body: str) -> str:
    """Update the existing marker comment in place, else create one. Never spams."""
    cid = find_marker_comment(repo, issue)
    if cid:
        ok = gh_write("PATCH", f"repos/{repo}/issues/comments/{cid}", {"body": body})
        return "updated" if ok else "error"
    ok = gh_write("POST", f"repos/{repo}/issues/{issue}/comments", {"body": body})
    return "created" if ok else "error"


def resolve_comment(repo: str, issue: int) -> str:
    """Flip a now-clean epic's existing hygiene comment to resolved (idempotent)."""
    cid = find_marker_comment(repo, issue)
    if not cid:
        return "none"
    ok = gh_write(
        "PATCH", f"repos/{repo}/issues/comments/{cid}", {"body": resolved_body()}
    )
    return "resolved" if ok else "error"


def emit(kind: str, title: str, msg: str) -> None:
    """Human line + a GitHub Actions annotation when running in CI."""
    print(f"  {kind.upper()}: {msg}")
    if IN_ACTIONS:
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
    ap.add_argument(
        "--issue",
        type=int,
        default=None,
        help="check only this issue number (the issues-event path)",
    )
    ap.add_argument(
        "--comment",
        action="store_true",
        help="post/update ONE marker-tagged hygiene comment per flagged epic "
        "(idempotent — updates in place, resolves when clean). Needs issues:write.",
    )
    args = ap.parse_args(argv)

    issues = (
        fetch_one_issue(args.repo, args.issue)
        if args.issue is not None
        else fetch_open_issues(args.repo)
    )
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
        is_epic = EPIC_LABEL in labels

        if is_epic:
            fs = epic_findings(it)
            if fs:
                findings += 1
                for line in fs:
                    emit("warning", "Epic hygiene", f"#{num}: {line}")
                summary.append(f"| #{num} | {len(fs)} finding(s) |")
                if args.comment:
                    res = upsert_comment(args.repo, num, comment_body(fs))
                    print(f"  comment #{num}: {res}")
            elif args.comment:
                r = resolve_comment(args.repo, num)
                if r != "none":
                    print(f"  #{num}: prior hygiene comment {r}")

        if not is_epic and TITLE_LOOKS_EPIC.match(it["title"] or ""):
            emit(
                "notice",
                "Epic labelling",
                f"#{num} is titled like an epic but lacks the `{EPIC_LABEL}` "
                f"label, so the standard won't govern it (ADR-0003 §2).",
            )
            summary.append(f"| #{num} | unlabelled-epic |")

    if IN_ACTIONS and summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write("### Epic sub-issue hygiene (ADR-0003 §2)\n\n")
            fh.write("| Epic | Result |\n|---|---|\n")
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
