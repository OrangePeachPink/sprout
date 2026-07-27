#!/usr/bin/env python3
"""#1346 tripwire — every GitHub Action is pinned to a *resolvable* commit SHA.

Two failures, one guard, because the second is the one that bites.

**Unpinned.** ``uses: owner/action@v7`` rides a mutable tag. A tag can be repointed at
any commit at any time, so the bytes a workflow runs are whatever upstream decided this
morning. For the release path — which holds the signing key and builds what a stranger
flashes onto their own hardware — that is a supply-chain event, not an inconvenience.

**Pinned to something that is not a commit.** This is the sharp one. ``setup-uv``'s
``v7`` is an *annotated* tag, so ``git/ref/tags/v7`` returns ``object.type = "tag"`` and
``.object.sha`` is the **tag object**, not the commit. ``checkout``, ``setup-just`` and
``cache`` all use *lightweight* tags, where that same one-step lookup is correct. So a
resolver that skips the dereference is right three times out of four and silently wrong
the fourth — which is exactly how ``94527f2e…`` (a tag object) reached a PR as a pin.
Actions requires a **commit** SHA: the job fails at startup with ``unable to find
version``, an error that points at the version rather than at the one bad value.

**A mistyped tag is obvious; a wrong SHA is silent until it runs.** That is the cost of
the pinning discipline, not an argument against it — it just means pins must be
*verified*, not transcribed. Hence two modes:

* **structural** (default, offline, fast): every ``uses:`` is a 40-hex SHA and carries a
  ``# vX.Y.Z`` comment. Runs in pre-commit and CI on every change.
* ``--resolve`` (network): every pinned SHA is a real commit in that repo. Runs in the
  weekly battery, non-blocking — the same shape as the external-link check (#913), and
  for the same reason: network truth rots on the internet's schedule, not on ours.

    python tools/dx/action_pin_guard.py --check            # structural
    python tools/dx/action_pin_guard.py --check --resolve  # + verify upstream
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_WORKFLOWS = ".github/workflows"

# `uses: owner/repo@ref` with an optional trailing `# comment`. Local (`./…`) and docker
# (`docker://…`) uses have no upstream ref to pin, so they never match.
_USES = re.compile(
    r"^\s*(?:-\s*)?uses:\s*(?P<action>[\w.-]+/[\w.-]+(?:/[\w.-]+)*)@(?P<ref>\S+)"
    r"(?:\s*#\s*(?P<comment>.*))?$"
)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_VERSION_COMMENT = re.compile(r"v\d+(\.\d+)*")


class Finding:
    def __init__(self, path: str, line: int, action: str, ref: str, problem: str):
        self.path, self.line = path, line
        self.action, self.ref, self.problem = action, ref, problem

    def __str__(self) -> str:
        return (
            f"  {self.path}:{self.line}  {self.action}@{self.ref[:12]} — {self.problem}"
        )


def workflow_files(repo: Path = _REPO) -> list[Path]:
    d = repo / _WORKFLOWS
    return sorted(p for p in d.glob("*.yml")) + sorted(p for p in d.glob("*.yaml"))


def parse_uses(path: Path) -> list[tuple[int, str, str, str | None]]:
    """Every `uses:` in the file as (line_no, action, ref, comment)."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = _USES.match(line)
        if m:
            out.append((n, m["action"], m["ref"], m["comment"]))
    return out


def check_structure(repo: Path = _REPO) -> list[Finding]:
    """Offline: each `uses:` pinned to a 40-hex SHA and labelled with its version."""
    findings: list[Finding] = []
    for wf in workflow_files(repo):
        rel = wf.relative_to(repo).as_posix()
        for line, action, ref, comment in parse_uses(wf):
            if not _SHA.match(ref):
                findings.append(
                    Finding(
                        rel,
                        line,
                        action,
                        ref,
                        f"not pinned — '{ref}' is a mutable tag/branch, "
                        "not a commit SHA",
                    )
                )
            elif not (comment and _VERSION_COMMENT.search(comment)):
                findings.append(
                    Finding(
                        rel,
                        line,
                        action,
                        ref,
                        "pinned but unlabelled — add a trailing '# vX.Y.Z' so the next "
                        "bump is legible instead of archaeological",
                    )
                )
    return findings


def _api(url: str) -> tuple[int, dict]:
    """GET the GitHub API, preferring `gh` (inherits the user's auth) over anonymous."""
    try:
        p = subprocess.run(
            ["gh", "api", url], capture_output=True, text=True, timeout=30
        )
        if p.returncode == 0:
            return 200, json.loads(p.stdout)
        if "404" in p.stderr or "422" in p.stderr or "No commit found" in p.stderr:
            return 422, {}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    try:  # anonymous fallback — rate-limited, fine for a weekly run
        req = urllib.request.Request(
            f"https://api.github.com/{url}",
            headers={"Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return 0, {}


def check_resolvable(repo: Path = _REPO, api=_api) -> list[Finding]:
    """Network: every pinned SHA is a real COMMIT in that action's repository.

    A tag-object SHA (the annotated-tag trap) answers 422 here, which is the whole
    point — it is indistinguishable from a good pin by reading the file."""
    findings: list[Finding] = []
    seen: dict[tuple[str, str], int] = {}
    for wf in workflow_files(repo):
        rel = wf.relative_to(repo).as_posix()
        for line, action, ref, _ in parse_uses(wf):
            if not _SHA.match(ref):
                continue  # structural check owns that failure
            owner_repo = "/".join(action.split("/")[:2])  # strip any subpath action
            key = (owner_repo, ref)
            if key not in seen:
                status, body = api(f"repos/{owner_repo}/commits/{ref}")
                seen[key] = status if body.get("sha", ref) == ref else 0
            if seen[key] == 0:
                findings.append(
                    Finding(rel, line, action, ref, "network unreachable — not checked")
                )
            elif seen[key] != 200:
                findings.append(
                    Finding(
                        rel,
                        line,
                        action,
                        ref,
                        "NOT A COMMIT in that repo (likely an annotated TAG "
                        "OBJECT — dereference it: "
                        "gh api repos/<action>/git/tags/<sha>). Actions needs a "
                        "commit SHA; this job would fail at startup",
                    )
                )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="#1346: action pins are resolvable commits"
    )
    ap.add_argument(
        "--check", action="store_true", help="report + non-zero on findings"
    )
    ap.add_argument(
        "--resolve", action="store_true", help="also verify each SHA upstream (network)"
    )
    ap.add_argument("filenames", nargs="*", help="ignored (pre-commit passes files)")
    args = ap.parse_args(argv)

    findings = check_structure()
    if args.resolve:
        findings += check_resolvable()

    if findings:
        print(
            "action-pin-guard: workflow actions must be pinned to a resolvable commit "
            "SHA (#1346):",
            file=sys.stderr,
        )
        for f in findings:
            print(str(f), file=sys.stderr)
        return 1 if args.check else 0

    n = sum(len(parse_uses(w)) for w in workflow_files())
    scope = "pinned + labelled" + (" + resolvable upstream" if args.resolve else "")
    print(f"action-pin-guard: {n} action reference(s) {scope}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
