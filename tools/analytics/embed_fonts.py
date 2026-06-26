#!/usr/bin/env python3
"""Generate tools/analytics/vendor/sprout-fonts.css — the Sprout brand fonts,
base64-embedded so the dashboard renders in-brand fully offline (no Google-Fonts
CDN; ADR-0005). Downloads the latin subsets from fontsource and inlines them as
@font-face data URIs. Run after a font / weight change:

    python tools/analytics/embed_fonts.py

Fonts are SIL OFL (redistributable). Mirrors the vendored-Chart.js offline pattern.
"""

from __future__ import annotations

import base64
import sys
import urllib.request
from pathlib import Path

# (display family, fontsource id, weights) — weights match the dashboard's usage.
FONTS = [
    ("Baloo 2", "baloo-2", [500, 600, 700]),
    ("Hanken Grotesk", "hanken-grotesk", [400, 500, 600, 700]),
    ("JetBrains Mono", "jetbrains-mono", [400, 500, 600]),
]
OUT = Path(__file__).resolve().parent / "vendor" / "sprout-fonts.css"


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=30).read()


def main() -> int:
    blocks, total = [], 0
    for family, fid, weights in FONTS:
        for w in weights:
            url = (
                f"https://cdn.jsdelivr.net/fontsource/fonts/{fid}@latest/"
                f"latin-{w}-normal.woff2"
            )
            data = fetch(url)
            if data[:4] != b"wOF2":
                sys.exit(f"not woff2: {url}")
            total += len(data)
            b64 = base64.b64encode(data).decode("ascii")
            blocks.append(
                f"@font-face{{font-family:'{family}';font-style:normal;"
                f"font-weight:{w};font-display:swap;"
                f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}"
            )
            print(f"  {family} {w}: {len(data)} bytes")
    header = (
        "/* Sprout brand fonts - GENERATED, do not hand-edit.\n"
        " * Latin subsets of Baloo 2 / Hanken Grotesk / JetBrains Mono (SIL OFL),\n"
        " * base64-embedded for fully-offline in-brand rendering (no CDN; ADR-0005).\n"
        " * Source: fontsource. Regenerate: python tools/analytics/embed_fonts.py\n"
        " */\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + "\n".join(blocks) + "\n", encoding="utf-8", newline="\n")
    print(f"raw woff2 total: {total} bytes; css: {OUT.stat().st_size} bytes -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
