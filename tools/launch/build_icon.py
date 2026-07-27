#!/usr/bin/env python3
"""#1359 — pack Design's rendered app-icon frames into the Windows shortcut icon.

`Install-SproutShortcut.ps1` points `IconLocation` at `tools/launch/sprout.ico`, so the
desktop icon is whatever this file contains. Design renders each size deliberately
(`docs/design/brand/app-icon/app-icon-<n>.png`) rather than shipping one master to be
resampled — a 16px tile needs different treatment from a 256px one, and downscaling the
big one throws that work away. So this embeds **their** frames, and does not resample.

`sprout.ico` is committed (the shortcut needs a file, not a build step) but it is a
GENERATED artifact: re-run this after any icon change rather than hand-editing.

    python tools/launch/build_icon.py          # rebuild from the rendered frames
    python tools/launch/build_icon.py --check  # verify the committed .ico matches
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_FRAMES_DIR = _REPO / "docs" / "design" / "brand" / "app-icon"
_ICO = _REPO / "tools" / "launch" / "sprout.ico"


def frame_paths(frames_dir: Path = _FRAMES_DIR) -> list[Path]:
    """The rendered PNG frames, smallest first (ICO convention)."""
    out = []
    for p in frames_dir.glob("app-icon-*.png"):
        stem = p.stem.rsplit("-", 1)[-1]
        if stem.isdigit():
            out.append((int(stem), p))
    return [p for _, p in sorted(out)]


def build(dest: Path = _ICO, frames_dir: Path = _FRAMES_DIR) -> list[int]:
    from PIL import Image

    paths = frame_paths(frames_dir)
    if not paths:
        raise SystemExit(f"no app-icon-<n>.png frames under {frames_dir}")
    images = [Image.open(p).convert("RGBA") for p in paths]
    sizes = [im.size[0] for im in images]
    # append_images embeds each rendered frame as-is; `sizes` alone would resample the
    # base image and discard Design's per-size work.
    images[-1].save(
        dest, format="ICO", sizes=[im.size for im in images], append_images=images[:-1]
    )
    return sizes


def frames_in(ico: Path = _ICO) -> list[int]:
    from PIL import Image

    with Image.open(ico) as im:
        return sorted({s[0] for s in im.info.get("sizes", [])})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="#1359: pack the app-icon frames into .ico"
    )
    ap.add_argument("--check", action="store_true", help="verify, don't rebuild")
    args = ap.parse_args(argv)

    expected = sorted(int(p.stem.rsplit("-", 1)[-1]) for p in frame_paths())
    if args.check:
        if not _ICO.exists():
            print(
                f"action needed: {_ICO} missing — run without --check", file=sys.stderr
            )
            return 1
        have = frames_in()
        if have != expected:
            print(
                f"{_ICO.name} has frames {have}, rendered frames are {expected} — "
                "re-run without --check",
                file=sys.stderr,
            )
            return 1
        print(f"sprout.ico: {len(have)} frames {have} — matches the rendered set.")
        return 0

    sizes = build()
    print(f"sprout.ico <- {len(sizes)} frames {sizes} (from {_FRAMES_DIR.name}/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
