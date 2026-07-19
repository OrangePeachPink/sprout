"""Credit-protection nudge detector (#1126).

Pure detection logic for the fork-PR credit-protection check. Given the commit
list of an external (fork) pull request, decides whether the contributor's
credit is at risk — because a commit was authored/committed as the *maintainer's*
GitHub identity, or carries an internal `Lane:` trailer — and therefore whether
the workflow should post its one warm, non-blocking nudge comment.

Framing note (the whole point, per #1126): this protects the contributor's
credit. It is NOT fraud detection. A "hit" means "you deserve this credit and
it's about to land on the wrong graph," never "you did something wrong."

Split out as a module (not inline workflow JS) so the detection is unit-tested
under `just test-dx` (pytest tools/dx/) — a fork PR can't be exercised in CI
locally, so the logic earns its confidence here. The workflow (credit-nudge.yml)
does only the GitHub plumbing: fetch commits, call this, upsert the comment.

CLI: `python tools/dx/credit_nudge.py <commits.json>` (or stdin) — prints
`nudge` or `clear` on stdout and always exits 0 (it must never block a PR)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# The maintainer account whose identity must never end up crediting a
# contributor's commit. GitHub noreply emails take two forms:
#   <id>+<login>@users.noreply.github.com   or   <login>@users.noreply.github.com
# We match on the login half so a *contributor's own* noreply
# (e.g. 42+SomeoneElse@users.noreply.github.com) is never a false positive.
MAINTAINER_LOGIN = "OrangePeachPink"

_NOREPLY_SUFFIX = "@users.noreply.github.com"
_LANE_TRAILER = re.compile(r"^Lane:\s", re.MULTILINE)


def is_maintainer_identity(email: str | None) -> bool:
    """True iff `email` is the maintainer account's GitHub noreply address.

    Matches both `<id>+login@…` and `<login>@…` forms, case-insensitively;
    a contributor's own noreply (different login) is intentionally not matched."""
    if not email:
        return False
    e = email.strip().lower()
    if not e.endswith(_NOREPLY_SUFFIX):
        return False
    local = e[: -len(_NOREPLY_SUFFIX)]
    if "+" in local:
        local = local.split("+", 1)[1]
    return local == MAINTAINER_LOGIN.lower()


def has_lane_trailer(message: str | None) -> bool:
    """True iff any line of the commit message begins with a `Lane:` trailer."""
    if not message:
        return False
    return _LANE_TRAILER.search(message) is not None


def evaluate(commits: list[dict]) -> dict:
    """Classify a PR's commits. Returns {"nudge": bool, "hits": [ {sha, reasons} ]}.

    `commits` is the shape of GitHub's `GET /repos/{repo}/pulls/{n}/commits`
    response: each item has `sha` and `commit.{author,committer}.email` +
    `commit.message`. Missing fields are treated as absent, never as errors."""
    hits: list[dict] = []
    for c in commits or []:
        commit = (c or {}).get("commit", {}) or {}
        author_email = (commit.get("author") or {}).get("email")
        committer_email = (commit.get("committer") or {}).get("email")
        message = commit.get("message")

        reasons = []
        if is_maintainer_identity(author_email):
            reasons.append("author-is-maintainer-identity")
        if is_maintainer_identity(committer_email):
            reasons.append("committer-is-maintainer-identity")
        if has_lane_trailer(message):
            reasons.append("lane-trailer")

        if reasons:
            hits.append({"sha": (c or {}).get("sha", "")[:12], "reasons": reasons})

    return {"nudge": bool(hits), "hits": hits}


def _load(argv: list[str]) -> list[dict]:
    if len(argv) > 1:
        raw = Path(argv[1]).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else []
    return data if isinstance(data, list) else []


def main(argv: list[str]) -> int:
    try:
        result = evaluate(_load(argv))
    except Exception as exc:  # never block a PR on our own error
        print(f"credit-nudge: skipped (input error: {exc})", file=sys.stderr)
        print("clear")
        return 0
    if result["nudge"]:
        print("credit-nudge: hits =", json.dumps(result["hits"]), file=sys.stderr)
        print("nudge")
    else:
        print("clear")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
