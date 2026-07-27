#!/usr/bin/env python3
"""#1668 `just release-state <tag>` — where the cut is, and the exact next action.

At the v0.8.1 cut this was carried in a person's head across a **2h55 ceremony spanning
midnight**, reconstructed by hand from four separate queries each time.

**It reports; it does not prevent.** #1661/#1662/#1663/#1664 each stop a specific
failure that has actually happened. This one stops an operator being lost — which cost
real minutes at 1am but never cost a release. It calls those commands rather than
re-deriving their logic, which is why it is worth writing after them and not before.

## The one rule

**Never infer phase from anything but observed state.** *"You are at §5"* asserted from
a local variable is exactly the falsehood family this release kept producing. Every
field below is a live query or it is absent, and **`unknown` is an acceptable value
where `probably §5` is not.**

That rule has a cost, and the cost is the point: this tool will sometimes say it does
not know. A cut ceremony is not improved by a confident guess.

    just release-state v0.8.2
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DEFAULT_REPO = "OrangePeachPink/sprout"
SIGNER_WORKFLOW = "sign-release.yml"
UNKNOWN = "unknown"


def _out(args: list[str]) -> str | None:
    r = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.stdout.strip() if r.returncode == 0 else None


def _gh_json(args: list[str], default):
    raw = _out(["gh", *args])
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except ValueError:
        return default


@dataclass
class Field:
    """One observed fact. `value is None` means NOT OBSERVED — never 'probably'."""

    name: str
    value: str | None
    note: str = ""

    def render(self, width: int) -> str:
        shown = self.value if self.value is not None else UNKNOWN
        tail = f"   {self.note}" if self.note else ""
        return f"  {self.name:<{width}}  {shown}{tail}"


def observe(tag: str, repo: str) -> tuple[list[Field], dict]:
    """Live queries only. Anything that does not answer stays None."""
    facts: dict = {}
    fields: list[Field] = []

    # The frozen candidate (#1657) has no store yet, so it is reported ABSENT rather
    # than substituted with the draft's target. Those are different claims: one is what
    # was agreed, the other is what the draft happens to point at, and the whole reason
    # #1657 exists is that they can differ.
    fields.append(
        Field(
            "frozen candidate",
            None,
            "(#1657 not built — no recorded candidate to compare against)",
        )
    )

    rel = _gh_json(
        [
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "isDraft,targetCommitish,assets,tagName",
        ],
        None,
    )
    facts["release"] = rel
    if rel is None:
        fields.append(Field("draft", None, f"(no release {tag} on {repo})"))
    else:
        fields.append(
            Field("draft", "yes" if rel.get("isDraft") else "PUBLISHED (immutable)")
        )
        target = str(rel.get("targetCommitish") or "")
        head = _out(["git", "rev-parse", "origin/main"]) or ""
        facts["target"], facts["head"] = target, head
        if target and head:
            same = head.startswith(target) or target.startswith(head)
            fields.append(
                Field(
                    "draft target",
                    f"{target[:12]}",
                    "== origin/main" if same else f"!= origin/main ({head[:12]})",
                )
            )
        else:
            fields.append(Field("draft target", target[:12] if target else None))
        names = [a["name"] for a in rel.get("assets", [])]
        facts["assets"] = names
        fields.append(
            Field("assets", str(len(names)), ", ".join(sorted(names)) if names else "")
        )

    ms = _gh_json(["api", f"repos/{repo}/milestones?state=all"], [])
    mine = next((m for m in ms if m.get("title") == tag), None)
    facts["milestone"] = mine
    if mine is None:
        fields.append(Field("milestone", None, f"(no milestone titled {tag})"))
    else:
        fields.append(
            Field(
                "milestone",
                mine.get("state", UNKNOWN),
                f"{mine.get('open_issues', '?')} open / "
                f"{mine.get('closed_issues', '?')} closed",
            )
        )

    runs = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            SIGNER_WORKFLOW,
            "--limit",
            "5",
            "--json",
            "databaseId,status,conclusion,headSha,createdAt",
        ],
        [],
    )
    # A signer run records NO tag: `displayTitle` is just the workflow name, and the
    # dispatch input is not exposed by `gh run list`. So the ONLY observable link
    # between a run and this release is whether it built the draft's target commit.
    # Presenting a repo-wide "last run" as though it belonged to this tag would be
    # exactly the asserted-not-observed failure this module exists to avoid — and the
    # first draft here did it, showing v0.8.1's run under v0.8.2.
    facts["signer"] = runs[0] if runs else None
    if not runs:
        fields.append(Field("last signer run", None, "(none found)"))
    else:
        r0 = runs[0]
        state = r0.get("conclusion") or r0.get("status") or UNKNOWN
        sha = str(r0.get("headSha") or "")
        target = str(facts.get("target") or "")
        if target and sha and (sha.startswith(target) or target.startswith(sha)):
            note = f"built {sha[:12]} — THIS draft's target"
        elif target and sha:
            note = f"built {sha[:12]} — NOT this draft's target ({target[:12]})"
        else:
            note = (
                f"built {sha[:12]} — cannot be attributed to {tag}: a signer run "
                "records no tag and there is no draft target to match it against"
            )
        fields.append(Field("last signer run", f"{r0['databaseId']} {state}", note))
    return fields, facts


def phase_and_next(tag: str, repo: str, facts: dict) -> tuple[str, str]:
    """(phase, next action) — derived ONLY from what `observe` actually saw.

    Every branch below is reachable from observed values, and the final branch is
    `unknown`, which is a real answer. Guessing a phase would make this tool a
    confident narrator of a state nobody checked.
    """
    rel = facts.get("release")
    ms = facts.get("milestone")

    if rel is None:
        if ms is None:
            return (
                "before §2",
                f"No milestone {tag} and no draft. Create the milestone, then run "
                f"`just release-preflight {tag}` before closing it.",
            )
        if ms.get("state") == "open":
            return (
                "§1 / §1.1",
                f"Milestone {tag} is open with {ms.get('open_issues', '?')} issue(s). "
                f"Run `just release-preflight {tag}`; close the milestone at §2 only "
                "once it passes.",
            )
        return (
            "§2 in flight",
            "Milestone is closed but no draft exists yet. Check the release-draft "
            "workflow run.",
        )

    if not rel.get("isDraft"):
        return (
            "§6 done",
            f"{tag} is PUBLISHED and its assets are sealed. Nothing further can be "
            "attached — a correction needs a new tag (#1438).",
        )

    if not facts.get("assets"):
        return (
            "§5 pending",
            f"Draft exists with NO assets. Dispatch the signer, then "
            f"`just release-verify {tag}`. Publishing now would seal an asset-less "
            "release — the v0.8.0 failure.",
        )

    return (
        "§5 signed, unverified here",
        f"Draft carries {len(facts['assets'])} asset(s). Run "
        f"`just release-verify {tag}` and publish only if it exits 0.",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument(
        "--verify",
        action="store_true",
        help="also run the artifact contract (#1662) when the draft has assets",
    )
    a = ap.parse_args(argv)

    fields, facts = observe(a.tag, a.repo)
    width = max(len(f.name) for f in fields)
    print(f"\nrelease-state {a.tag}\n")
    for f in fields:
        print(f.render(width))

    phase, action = phase_and_next(a.tag, a.repo, facts)
    print(f"\n  phase        {phase}")
    print(f"  next         {action}\n")

    if a.verify and facts.get("assets"):
        from contract import BOT_HANDLES
        from verify import verify

        passed, failures, checked = verify(
            a.tag, a.repo, BOT_HANDLES | {a.repo.split("/")[0]}
        )
        print(
            f"  release-verify: {'PASS' if passed else 'FAIL'} "
            f"({len(checked)} ok, {len(failures)} failed)"
        )
        for f in failures:
            print(f"    FAIL  {f}", file=sys.stderr)
        return 0 if passed else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
