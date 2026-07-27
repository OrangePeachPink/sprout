#!/usr/bin/env python3
"""#1524 / #1284 AC5 - generate + validate the OTA release feed (docs/ota/feed.txt).

The feed is the Pages-served pointer a fielded board polls to discover the
current release's signed image for its board class (S3b ruling; the device
parser lives in firmware/lib/ota_pull/ota_pull.h). This tool is that parser's
desk twin: the same contract, enforced at generate/commit time, so nothing the
fleet would reject can land in the tree - and nothing the tree serves can
strand a fleet silently.

The contract (mirrors ota_pull.h):

    # sprout-ota-feed v1
    board=esp32-classic version=0.8.1 image=https://... sig=https://...

- The FIRST non-blank line is the banner, exactly. Blank lines and #-comments
  are skipped anywhere else.
- Artifact lines are whitespace-separated key=value tokens. board / version /
  image / sig are required (missing keys are FATAL on-device); unknown keys are
  ignored (additive-never-stitch).
- Bounds REJECT, never truncate: board and version fit char[24] (23 chars max),
  URLs fit char[256] (255 max) - a silently shortened URL fetches the wrong
  thing.
- A duplicate board rejects the whole feed.
- URLs are https only (the device transport is ota_https_get).
- The feed is deliberately UNSIGNED: a pointer, never an authority. The image's
  ed25519 signature is the only thing that authorises code to run (ota_gate).

A banner-only feed is VALID and means "offers nothing" - the pre-first-release
state; devices stay on their running image.

    python tools/dx/ota_feed.py check [path]                  # pre-commit hook
    python tools/dx/ota_feed.py generate --tag vX.Y.Z         # print the feed
    python tools/dx/ota_feed.py generate --tag vX.Y.Z --write # write docs/ota/
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BANNER = "# sprout-ota-feed v1"

# ota_pull.h bounds are char[N] including the NUL, so max content is N-1.
BOARD_MAX = 23  # OTA_PULL_BOARD_MAX 24
VERSION_MAX = 23  # OTA_PULL_VERSION_MAX 24
URL_MAX = 255  # OTA_PULL_URL_MAX 256

REQUIRED = ("board", "version", "image", "sig")

# Board class (BOARD_CAP.name, firmware/include/board_capability.h) -> the
# factory bin sign-release.yml attaches to the release. A DECLARED table, never
# inferred: a new board joins the feed by an explicit row here, after its
# BOARD_CAP exists and sign-release builds + signs its bin. An unknown board in
# a hand-curated feed FAILS the check - a typo'd class strands a fleet silently
# ("no artifact for this board" is a valid answer, so nothing would scream).
BOARDS: dict[str, str] = {
    "esp32-classic": "sprout-esp32-factory.bin",
    "esp32-c5": "sprout-esp32c5-factory.bin",
}

_REPO_SLUG = "OrangePeachPink/sprout"
_REPO = Path(__file__).resolve().parents[2]
FEED_PATH = _REPO / "docs" / "ota" / "feed.txt"


def validate(text: str) -> list[str]:
    """Every way this feed would fail or mislead the device parser, as messages.
    Empty list = the fleet can use it. Mirrors ota_pull_parse_feed + artifact
    validation; stricter only where the desk can afford it (unknown board,
    https-only, duplicate key within a line)."""
    problems: list[str] = []
    lines = text.splitlines()

    first = next((ln for ln in lines if ln.strip()), None)
    if first is None:
        return ["empty file - not even the banner"]
    if first != BANNER:
        return [
            f"first non-blank line must be the banner {BANNER!r} exactly, "
            f"got {first!r} - the device refuses the whole feed (NO_BANNER)"
        ]

    seen_boards: set[str] = set()
    banner_seen = False
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if not s:
            continue
        if not banner_seen:
            banner_seen = True  # the banner line itself, verified above
            continue
        if s.startswith("#"):
            continue

        fields: dict[str, str] = {}
        for tok in s.split():
            key, sep, val = tok.partition("=")
            if not sep or not key:
                problems.append(
                    f"line {i}: token {tok!r} is not key=value - the device "
                    "reads this as MALFORMED and rejects the whole feed"
                )
                continue
            if key in fields:
                problems.append(
                    f"line {i}: key {key!r} appears twice in one line - "
                    "curation typo; which value wins is undefined"
                )
                continue
            fields[key] = val

        missing = [k for k in REQUIRED if k not in fields]
        if missing:
            problems.append(
                f"line {i}: missing required key(s) {', '.join(missing)} - "
                "missing keys are FATAL on-device (never defaulted)"
            )
            continue

        empty = [k for k in REQUIRED if not fields[k]]
        if empty:
            problems.append(
                f"line {i}: empty value for {', '.join(empty)} - a required "
                "field must be non-empty"
            )

        board = fields["board"]
        if len(board) > BOARD_MAX:
            problems.append(
                f"line {i}: board {board!r} exceeds {BOARD_MAX} chars - "
                "over-long fields are a REJECT on-device, never a truncation"
            )
        if len(fields["version"]) > VERSION_MAX:
            problems.append(
                f"line {i}: version exceeds {VERSION_MAX} chars - "
                "over-long fields are a REJECT on-device"
            )
        for key in ("image", "sig"):
            url = fields[key]
            if len(url) > URL_MAX:
                problems.append(
                    f"line {i}: {key} URL exceeds {URL_MAX} chars - "
                    "over-long fields are a REJECT on-device"
                )
            if url and not url.startswith("https://"):
                problems.append(
                    f"line {i}: {key} URL must be https:// - the device "
                    "transport is ota_https_get; anything else fails on-air"
                )

        if board and board not in BOARDS:
            problems.append(
                f"line {i}: unknown board class {board!r} - not in the "
                "declared table (tools/dx/ota_feed.py BOARDS). A typo here "
                "strands a fleet silently; a new board is a deliberate row."
            )
        if board in seen_boards:
            problems.append(
                f"line {i}: duplicate board {board!r} - a duplicate rejects "
                "the whole feed"
            )
        seen_boards.add(board)

    return problems


def artifact_count(text: str) -> int:
    """Artifact lines in a feed that already passed validate()."""
    lines = [ln.strip() for ln in text.splitlines()]
    body = [ln for ln in lines if ln and not ln.startswith("#")]
    return len(body)


def build_feed(tag: str, asset_names: set[str]) -> str:
    """The feed text for release `tag`, given the release's asset names.

    Fail-closed: EVERY declared board must have BOTH its bin and .sig attached,
    or this raises - an image without a signature is not offerable (ota_gate
    rejects it after a multi-megabyte download), and silently emitting a
    partial fleet is the falsehood-family failure this tool exists to close.
    Dropping a board deliberately is a hand-edit of the committed feed
    (curation, #1258), never a silent skip here.
    """
    version = tag.removeprefix("v")
    base = f"https://github.com/{_REPO_SLUG}/releases/download/{tag}"

    missing: list[str] = []
    for board, bin_name in BOARDS.items():
        for name in (bin_name, bin_name + ".sig"):
            if name not in asset_names:
                missing.append(f"{board}: {name}")
    if missing:
        raise ValueError(
            f"release {tag} is missing signed assets - refusing to emit a "
            f"partial feed: {'; '.join(missing)}"
        )

    out = [
        BANNER,
        f"# generated from release {tag} by tools/dx/ota_feed.py (#1524)",
        "# curation (#1258) = edit this file by hand; devices skip #-comments.",
        "# ota-feed-guard validates every commit of it.",
    ]
    out += [
        f"board={board} version={version} "
        f"image={base}/{bin_name} sig={base}/{bin_name}.sig"
        for board, bin_name in BOARDS.items()
    ]
    text = "\n".join(out) + "\n"

    problems = validate(text)  # never emit what check would refuse
    if problems:
        raise ValueError(
            "generated feed fails its own contract (bug): " + "; ".join(problems)
        )
    return text


def release_assets(tag: str) -> tuple[set[str], bool]:
    """Asset names + isDraft for a release via gh (drafts visible when authed)."""
    p = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--repo",
            _REPO_SLUG,
            "--json",
            "assets,isDraft",
        ],
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        raise SystemExit(f"ota-feed: gh release view {tag} failed: {p.stderr.strip()}")
    doc = json.loads(p.stdout)
    return {a["name"] for a in doc["assets"]}, bool(doc["isDraft"])


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):  # cp1252 consoles (the #1447 lesson)
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(
        description="#1524: the OTA release feed - device-contract twin"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    ck = sub.add_parser("check", help="validate a feed file (exit 1 on problems)")
    ck.add_argument("path", nargs="?", default=str(FEED_PATH))

    gen = sub.add_parser("generate", help="emit the feed for a release's assets")
    gen.add_argument("--tag", required=True, help="release tag, e.g. v0.8.1")
    gen.add_argument(
        "--write", action="store_true", help=f"write {FEED_PATH} instead of stdout"
    )
    args = ap.parse_args(argv)

    if args.cmd == "check":
        path = Path(args.path)
        if not path.exists():
            print(f"ota-feed: {path} does not exist", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        problems = validate(text)
        if problems:
            print(f"ota-feed: {path} would fail the fleet:", file=sys.stderr)
            for msg in problems:
                print(f"  {msg}", file=sys.stderr)
            return 1
        n = artifact_count(text)
        offer = f"{n} board(s) offered" if n else "banner-only (offers nothing)"
        print(f"ota-feed: {path} parses on-device - {offer}.")
        return 0

    # generate
    assets, is_draft = release_assets(args.tag)
    try:
        text = build_feed(args.tag, assets)
    except ValueError as e:
        print(f"ota-feed: {e}", file=sys.stderr)
        return 1
    if is_draft:
        print(
            f"ota-feed: NOTE - {args.tag} is a DRAFT; the asset URLs in this "
            "feed go live at publish (section 5.1 dry-run compatible).",
            file=sys.stderr,
        )
    if args.write:
        FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEED_PATH.write_text(text, encoding="utf-8", newline="\n")
        print(f"ota-feed: wrote {FEED_PATH} ({artifact_count(text)} board(s)).")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
