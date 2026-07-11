#!/usr/bin/env python3
"""#926 tripwire — keep the #886/#895 SVG-geometry-moustache class extinct.

The browser validates SVG *geometry* attributes (``d``/``cx``/``cy``/``points`` ...)
when it parses the raw template DOM — BEFORE the x-dc runtime substitutes ``{{ }}``.
So a raw geometry moustache like ``<path d="{{ sparkPath }}">`` throws a console
error on *every* load of the page (``Expected moveto path command, "{{ sparkPath }}"``),
even where the element then substitutes and draws fine. Paint attributes
(``fill``/``stroke``) never error — invalid values there are ignored by spec — which
is why only geometry leaks (see #886, fixed in #895).

The fix is to bind geometry via the runtime's ``sc-camel-`` prefix
(``sc-camel-d="{{ path }}"``): ``collectProps`` strips the prefix into the identical
propGetter key, so render is byte-identical while the SVG parser just sees an unknown
attribute and stays silent.

This guard fails a commit if a *raw* (un-prefixed) geometry attribute holds a
moustache value in any ``docs/design`` ``.dc.html``/``.html`` page. Run standalone:
``python tools/dx/svg_geometry_guard.py --check``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Geometry attributes the SVG parser validates at parse time. A value that *starts*
# with a moustache is a whole-binding — the #886 class. sc-camel- prefixed forms are
# excluded by the (?<![-\w]) lookbehind (the char before the name is '-').
_GEOM = "d|cx|cy|x|y|x1|x2|y1|y2|r|rx|ry|points"
PATTERN = re.compile(r"(?<![-\w])(" + _GEOM + r')="\s*\{\{')

_DESIGN = Path(__file__).resolve().parents[2] / "docs" / "design"


def find_hits(root: Path = _DESIGN) -> list[tuple[Path, int, str]]:
    """Every (file, line-number, attr) with a raw geometry moustache. Skips _archive."""
    hits: list[tuple[Path, int, str]] = []
    if not root.exists():
        return hits
    # "*.html" covers ".dc.html" too — one glob, no double-count.
    for path in sorted(root.rglob("*.html")):
        if "_archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in PATTERN.finditer(line):
                hits.append((path, lineno, m.group(1)))
    return hits


def main() -> int:
    hits = find_hits()
    if not hits:
        return 0
    repo = _DESIGN.parents[1]
    print(
        "svg-geometry-guard: raw {{ }} in an SVG geometry attribute — parse-errors on "
        "every load (#886 class):",
        file=sys.stderr,
    )
    for path, lineno, attr in hits:
        rel = path.relative_to(repo)
        print(
            f'  {rel}:{lineno}  {attr}="{{{{…}}}}"  ->  sc-camel-{attr}=',
            file=sys.stderr,
        )
    print(
        "Fix: prefix the attribute with sc-camel- (the runtime binds it, the parser "
        "ignores it). See #886 / #895.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
