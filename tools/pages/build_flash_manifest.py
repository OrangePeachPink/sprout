#!/usr/bin/env python3
"""Combine per-board ESP Web Tools manifests into ONE board-aware flasher manifest.

#271 / ADR-0032 (Actions-Pages). `firmware/scripts/factory_bin.py` emits a
single-board `manifest-<mcu>.json` per verified board, each with a top-level
`provenance` block. The web-flasher page (`docs/flash/index.html`) fetches ONE
`manifest.json`; ESP Web Tools picks the `builds[]` entry matching the connected
chip's `chipFamily`.

This merges them into that one manifest:
- `builds[]` = one entry per board, each with its OWN `provenance` injected, so the
  page's post-connect display can show the C5's own sha256, not the classic's.
- top-level `provenance` = the PRIMARY board's (the pre-connect panel, shown before
  Install). The primary is the close-criterion board (classic).

Only boards with a manifest are included — an unverified board (no manifest,
ADR-0026 D6) is silently absent, so the flasher never offers it. Deterministic
output (stable order = primary first) so a rebuild of identical bins is a no-op diff.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def combine(
    primary: str,
    extra: list[str],
    built_utc: str | None = None,
    parts_prefix: str = "",
) -> dict:
    base = _load(primary)
    prov_top = dict(base.get("provenance", {}))
    if built_utc:
        # #1599 AC2: the alpha panel renders `provenance.built_utc` ("Built"), and
        # factory_bin does not emit one — a per-build timestamp belongs to the publish,
        # not to the image (the same bins can be republished). Passed in rather than
        # read from the clock here so the value is the workflow's single notion of "now"
        # and both manifests in one run agree.
        prov_top["built_utc"] = built_utc
    out = {
        "name": base.get("name", "Sprout"),
        "version": base.get("version", "0.0.0"),
        "new_install_prompt_erase": base.get("new_install_prompt_erase", True),
        "builds": [],
        # pre-connect provenance panel = the primary (close-criterion) board.
        "provenance": prov_top,
    }
    seen: set[str] = set()
    for path in [primary, *extra]:
        # A board absent from WEB_FLASH_VERIFIED (factory_bin.py) emits NO manifest -
        # skip it: the flasher won't offer that board, and the deploy won't break.
        # (The primary is loaded above and must exist - the close-criterion board.)
        if not Path(path).is_file():
            print(f"skip: no manifest at {path} (board not web-flash-verified)")
            continue
        m = _load(path)
        prov = m.get("provenance", {})
        for build in m.get("builds", []):
            fam = build.get("chipFamily")
            if fam in seen:  # first manifest to name a chipFamily wins
                continue
            seen.add(fam)
            # per-board provenance rides its build entry (post-connect display).
            entry = {**build, "provenance": prov}
            if parts_prefix:
                # #1648: ESP Web Tools resolves `parts[].path` RELATIVE TO THE MANIFEST
                # URL, and factory_bin writes a bare basename. Both channels emit the
                # same filenames, so serving different bytes per channel means the two
                # payloads live in different directories while both manifests stay at
                # the URLs the page fetches (./manifest.json, ./manifest-alpha.json).
                # The prefix is what re-points a manifest at its own payload directory.
                entry["parts"] = [
                    {**p, "path": f"{parts_prefix}{p['path']}"}
                    for p in build.get("parts", [])
                ]
            out["builds"].append(entry)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--primary",
        required=True,
        help="close-criterion board manifest (its provenance = the top-level panel)",
    )
    ap.add_argument(
        "extra",
        nargs="*",
        help="additional per-board manifest-<mcu>.json paths",
    )
    ap.add_argument("--out", required=True, help="combined manifest.json output path")
    ap.add_argument(
        "--built-utc",
        default="",
        help="publish timestamp to stamp into provenance.built_utc (#1599)",
    )
    ap.add_argument(
        "--parts-prefix",
        default="",
        help="prefix each parts[].path with this (e.g. 'stable/') so the manifest "
        "points at its own channel's payload directory (#1648)",
    )
    a = ap.parse_args(argv)

    combined = combine(
        a.primary,
        a.extra,
        built_utc=a.built_utc or None,
        parts_prefix=a.parts_prefix,
    )
    if not combined["builds"]:
        print("error: no builds in any input manifest", file=sys.stderr)
        return 1

    Path(a.out).write_text(json.dumps(combined, indent=2) + "\n", encoding="utf-8")
    families = ", ".join(b["chipFamily"] for b in combined["builds"])
    print(
        f"combined manifest -> {a.out}: {len(combined['builds'])} board(s): {families}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
