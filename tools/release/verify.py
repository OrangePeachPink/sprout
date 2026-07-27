#!/usr/bin/env python3
"""#1662 `just release-verify <tag>` — assert the artifact contract on a real release.

Run after every signer dispatch. `RELEASE_CUT` §5 asserted `assets > 0`, which passes
on a release missing a signature; at the v0.8.1 cut the real inventory was checked by
hand with ad-hoc Python three times, once per signing cycle.

This is the thin I/O half. Everything it decides lives in `contract.py`, which is pure —
so the rules are tested against hand-built broken releases rather than against whatever
GitHub happens to be serving. What is left here is fetching, and fetching is the part
that must not be mocked: the assets are downloaded and hashed, never trusted from the
API's own metadata.

    just release-verify v0.8.1
    just release-verify v0.8.2 --repo OWNER/REPO
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contract import (
    BOARDS,
    BOT_HANDLES,
    SUMS,
    check_body,
    check_bytes,
    check_inventory,
    check_manifest_labels,
    check_sums_cover,
    merge,
)

DEFAULT_REPO = "OrangePeachPink/sprout"


def _gh(args: list[str]) -> str:
    out = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if out.returncode != 0:
        raise SystemExit(f"release-verify: gh failed: {out.stderr.strip()}")
    return out.stdout


def fetch(tag: str, repo: str, into: Path) -> tuple[dict, dict[str, bytes]]:
    """Release metadata plus the actual asset BYTES.

    The bytes matter. An API that reports an asset exists says nothing about what is
    inside it, and the whole contract is about what is inside it.
    """
    meta = json.loads(
        _gh(
            [
                "release",
                "view",
                tag,
                "--repo",
                repo,
                "--json",
                "assets,body,tagName,targetCommitish,isDraft",
            ]
        )
    )
    if meta.get("assets"):
        _gh(
            [
                "release",
                "download",
                tag,
                "--repo",
                repo,
                "--dir",
                str(into),
                "--pattern",
                "*",
                "--clobber",
            ]
        )
    blobs = {p.name: p.read_bytes() for p in into.iterdir() if p.is_file()}
    return meta, blobs


def verify(tag: str, repo: str, allowed: set[str]) -> tuple[bool, list[str], list[str]]:
    with tempfile.TemporaryDirectory() as td:
        into = Path(td)
        meta, blobs = fetch(tag, repo, into)
        names = set(blobs)
        target = str(meta.get("targetCommitish") or "")

        reports = [check_inventory(names, BOARDS)]

        sums_text = blobs.get(SUMS, b"").decode("utf-8", "replace")
        from contract import parse_sums  # local: keeps the pure module import-light

        sums = parse_sums(sums_text)
        reports.append(check_sums_cover(sums, BOARDS))

        manifests: dict[str, dict] = {}
        for b in BOARDS:
            if not b.web_manifest:
                continue
            raw = blobs.get(b.web_manifest)
            if raw is None:
                continue  # already a failure in check_inventory
            try:
                manifests[b.web_manifest] = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as exc:
                reports.append(
                    _one_failure(f"{b.web_manifest}: not valid JSON ({exc})")
                )

        # Only hash the .bin payloads against SHA256SUMS plus whatever else it lists.
        reports.append(check_bytes(blobs, sums, manifests))
        for mname, m in manifests.items():
            reports.append(check_manifest_labels(mname, m, tag, target))
        reports.append(check_body(str(meta.get("body") or ""), allowed))

        merged = merge(*reports)
        return merged.passed, merged.failures, merged.checked


def _one_failure(msg: str):
    from contract import Report

    r = Report()
    r.fail(msg)
    return r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tag", help="the release tag, e.g. v0.8.2")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument(
        "--allow-mention",
        action="append",
        default=[],
        help="a handle that is a real participant (repeatable)",
    )
    a = ap.parse_args(argv)

    # The repo owner and the known bots are EXPECTED in auto-generated notes ("by
    # @someone in #123"). Flagging them every run would train the operator to skim past
    # this check, which is precisely how a real stray gets published.
    allowed = set(a.allow_mention) | BOT_HANDLES | {a.repo.split("/")[0]}
    passed, failures, checked = verify(a.tag, a.repo, allowed)
    for c in checked:
        print(f"  ok    {c}")
    for f in failures:
        print(f"  FAIL  {f}", file=sys.stderr)
    if passed:
        print(
            f"\nrelease-verify: {a.tag} satisfies the artifact contract "
            f"({len(checked)} checks)."
        )
        return 0
    print(
        f"\nrelease-verify: {a.tag} does NOT satisfy the contract "
        f"({len(failures)} failure(s)). Do not publish.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
