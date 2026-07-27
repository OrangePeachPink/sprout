#!/usr/bin/env python3
"""#1663 `just release-resign <tag>` — one idempotent transaction.

At the v0.8.1 cut this was a hand-run sequence performed twice, once after a collision.

## The three facts it encodes, all learned the hard way (#1642 documents them; this is
the executable form)

* **`gh release upload` carries no `--clobber`, deliberately** (#1346 — an artifact is
  written once; a name collision fails loud rather than silently replacing published
  bytes). A second dispatch against a draft that already has assets therefore **fails**,
  and the failure reads like a broken signer when it is the write-once rule holding.
* **Retargeting does NOT clear assets.** They stay attached and now describe a commit
  the draft no longer points at — not merely stale, actively misdescribing the release.
  **A retarget always implies a re-sign.**
* **Confirm on a settled read.** A single read taken immediately after a mutation is not
  evidence — the write may not have landed, *or another actor may have written between
  your read and your next command*, which is what actually happened at this cut.

That last one is why step 1 exists and why it is not optional. No pause length protects
against a concurrent writer; only refusing to start does.

    just release-resign v0.8.2
    just release-resign v0.8.2 --expect-target <sha>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SIGNER_WORKFLOW = "sign-release.yml"
DEFAULT_REPO = "OrangePeachPink/sprout"
# The signer takes ~4 minutes. Naive polling loops timed out twice during the v0.8.1
# cut, so the wait is explicit and generous rather than left to a caller's default.
POLL_SECONDS = 15
POLL_BUDGET = 900


def _gh(args: list[str], check: bool = True) -> str:
    out = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and out.returncode != 0:
        raise SystemExit(f"release-resign: gh failed: {out.stderr.strip()}")
    return out.stdout


def _gh_json(args: list[str], default):
    try:
        return json.loads(_gh(args))
    except (ValueError, SystemExit):
        return default


def active_signer_runs(repo: str, tag: str) -> list[dict]:
    """Queued or in-progress signer runs — the concurrent-writer guard (#1656).

    Cheap, stateless, and it does not depend on anyone remembering at 1am. This is the
    check that would have prevented the v0.8.1 collision outright: two dispatches
    against one draft, the second failing on names the first had just attached.
    """
    runs = _gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            SIGNER_WORKFLOW,
            "--limit",
            "20",
            "--json",
            "databaseId,status,displayTitle,createdAt",
        ],
        [],
    )
    return [r for r in runs if r.get("status") in {"queued", "in_progress", "waiting"}]


def release_state(repo: str, tag: str) -> dict:
    """A FRESH read, straight through to the API rather than a subcommand's view."""
    return _gh_json(
        [
            "release",
            "view",
            tag,
            "--repo",
            repo,
            "--json",
            "assets,targetCommitish,isDraft,tagName",
        ],
        {},
    )


def clear_assets(repo: str, tag: str) -> list[str]:
    """Delete every attached asset, then re-read until the deletion has settled."""
    state = release_state(repo, tag)
    names = [a["name"] for a in state.get("assets", [])]
    for n in names:
        _gh(["release", "delete-asset", tag, n, "--repo", repo, "--yes"], check=False)
    for _ in range(12):
        if not release_state(repo, tag).get("assets"):
            return names
        time.sleep(5)
    raise SystemExit(
        "release-resign: assets still present after deletion — refusing to dispatch "
        "into a collision. Re-read and investigate; someone else may be mid-cut."
    )


def dispatch_and_wait(repo: str, tag: str) -> bool:
    before = {
        r["databaseId"]
        for r in _gh_json(
            [
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                SIGNER_WORKFLOW,
                "--limit",
                "20",
                "--json",
                "databaseId",
            ],
            [],
        )
    }
    _gh(["workflow", "run", SIGNER_WORKFLOW, "--repo", repo, "-f", f"tag={tag}"])

    run_id = None
    waited = 0
    while waited < POLL_BUDGET:
        runs = _gh_json(
            [
                "run",
                "list",
                "--repo",
                repo,
                "--workflow",
                SIGNER_WORKFLOW,
                "--limit",
                "20",
                "--json",
                "databaseId,status,conclusion",
            ],
            [],
        )
        if run_id is None:
            fresh = [r for r in runs if r["databaseId"] not in before]
            if fresh:
                run_id = fresh[0]["databaseId"]
                print(f"  signer run {run_id} started")
        if run_id is not None:
            me = next((r for r in runs if r["databaseId"] == run_id), None)
            if me and me.get("status") == "completed":
                ok = me.get("conclusion") == "success"
                print(f"  signer run {run_id} finished: {me.get('conclusion')}")
                return ok
        time.sleep(POLL_SECONDS)
        waited += POLL_SECONDS
    raise SystemExit(
        f"release-resign: signer did not finish within {POLL_BUDGET}s. The run may "
        "still be going — check Actions rather than dispatching again."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument(
        "--expect-target",
        default=None,
        help="the commitish the draft MUST point at; refuses to sign otherwise",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would happen and stop before any mutation",
    )
    a = ap.parse_args(argv)

    # 1. Refuse to start if another signer is live for this repo.
    active = active_signer_runs(a.repo, a.tag)
    if active:
        ids = ", ".join(str(r["databaseId"]) for r in active)
        print(
            f"release-resign: REFUSING — signer run(s) {ids} are still live. A second "
            "dispatch collides with assets the first is about to attach, which is "
            "exactly how the v0.8.1 cut failed. Wait for them.",
            file=sys.stderr,
        )
        return 1

    # 2. Confirm the draft's target is what the operator intends.
    state = release_state(a.repo, a.tag)
    if not state:
        print(f"release-resign: no release {a.tag} on {a.repo}.", file=sys.stderr)
        return 1
    target = str(state.get("targetCommitish") or "")
    assets = [x["name"] for x in state.get("assets", [])]
    print(
        f"  {a.tag}: draft={state.get('isDraft')} target={target} assets={len(assets)}"
    )
    if a.expect_target and not (
        target.startswith(a.expect_target) or a.expect_target.startswith(target)
    ):
        print(
            f"release-resign: target is {target!r}, expected {a.expect_target!r}. "
            "Retarget first — assets built from the wrong target misdescribe the "
            "release rather than merely being stale.",
            file=sys.stderr,
        )
        return 1
    if not state.get("isDraft"):
        print(
            "release-resign: this release is PUBLISHED. Its assets are immutable; a "
            "re-sign needs a new tag (#1438).",
            file=sys.stderr,
        )
        return 1

    if a.dry_run:
        print(f"  dry-run: would clear {len(assets)} asset(s), dispatch, then verify.")
        return 0

    # 3-4. Clear, then dispatch exactly once.
    cleared = clear_assets(a.repo, a.tag)
    print(f"  cleared {len(cleared)} asset(s): {', '.join(cleared) or 'none'}")
    if not dispatch_and_wait(a.repo, a.tag):
        print("release-resign: the signer run failed. Not verifying.", file=sys.stderr)
        return 1

    # 5-6. Verify, and exit on its verdict.
    from contract import BOT_HANDLES
    from verify import verify

    allowed = BOT_HANDLES | {a.repo.split("/")[0]}
    passed, failures, checked = verify(a.tag, a.repo, allowed)
    for c in checked:
        print(f"  ok    {c}")
    for f in failures:
        print(f"  FAIL  {f}", file=sys.stderr)
    if not passed:
        print(
            "release-resign: signed, but the contract FAILS. Do not publish.",
            file=sys.stderr,
        )
        return 1
    print(f"\nrelease-resign: {a.tag} re-signed and verified ({len(checked)} checks).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
