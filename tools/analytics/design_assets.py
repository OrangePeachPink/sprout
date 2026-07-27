#!/usr/bin/env python3
"""Layer 0 — the design-asset leaf (#1336, ADR-0038 §5.1).

**Zero imports beyond the stdlib, by rule.** This is a layer-0 module: it may be
imported by anything and imports nothing of ours, so reaching for a token path can
never drag a subsystem along with it.

It exists because of the diagnosis ADR-0038 opens with, measured rather than felt:

    Several Lab modules import the ~2,000-line `dashboard` module
    **to obtain two CSS constants.**

Four modules did — ``bench_packages``, ``experiments_catalog``, ``lab_studies``, and
``lab_detail`` — and three of them wanted *nothing else from it at all*. Importing 94 KB
to get a `Path` is the pathology in one line: the module had no seams, so you could not
take a piece without taking the whole thing.

The ADR's framing is worth keeping next to the code, because it explains why this
near-trivial file is the FIRST step of the hardening ladder rather than a tidy-up:

    "Importing two thousand lines to get a string means the module has no seams —
    you cannot take a piece without taking the whole."

Extractions (identity, ``build_context``, the route table) come after leaves and the
lint precisely because they are the risky ones; this one changes nobody's behaviour.
"""

from __future__ import annotations

from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]

# The ONE token source (the design system's own file) and the vendored font face
# stylesheet. Paths, not contents: reading is the caller's choice, and a surface that
# only needs the path never pays for the read.
TOKENS_CSS = _REPO / "docs" / "design" / "tokens" / "sprout-tokens.css"
FONTS_CSS = _HERE / "vendor" / "sprout-fonts.css"


def read_css(path: Path) -> str:
    """The file's text, or ``""`` when it isn't there.

    Absent-safe on purpose: a stripped deploy that ships without the design tokens
    should render an unstyled-but-working page, never raise. This is the same
    read-if-exists-else-empty the callers were each writing inline."""
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def head_css() -> str:
    """Tokens + fonts concatenated for a page ``<head>`` — the pairing every caller
    actually wanted when it reached for both constants."""
    return read_css(TOKENS_CSS) + read_css(FONTS_CSS)
