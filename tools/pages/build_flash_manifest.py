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


def combine(primary: str, extra: list[str]) -> dict:
    base = _load(primary)
    out = {
        "name": base.get("name", "Sprout"),
        "version": base.get("version", "0.0.0"),
        "new_install_prompt_erase": base.get("new_install_prompt_erase", True),
        "builds": [],
        # pre-connect provenance panel = the primary (close-criterion) board.
        "provenance": base.get("provenance", {}),
    }
    seen: set[str] = set()
    for path in [primary, *extra]:
        m = _load(path)
        prov = m.get("provenance", {})
        for build in m.get("builds", []):
            fam = build.get("chipFamily")
            if fam in seen:  # first manifest to name a chipFamily wins
                continue
            seen.add(fam)
            # per-board provenance rides its build entry (post-connect display).
            out["builds"].append({**build, "provenance": prov})
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
    a = ap.parse_args(argv)

    combined = combine(a.primary, a.extra)
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
