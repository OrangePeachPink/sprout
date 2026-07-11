#!/usr/bin/env python3
"""#925 tripwire — the plant-first identity fallback chain lives in exactly ONE place.

The chain ``plant_name || plant_id || probe || id`` was copy-pasted across ~6 template
sites; the trailing ``|| id`` fallback is how the ``s2@<device_id>`` machine-id leak
(#803/#804/#805) kept coming back. #925 routed every site through ``plantLabel()``.

This guard fails a commit if the raw chain reappears anywhere in ``tools/analytics``
except ``plantLabel()``'s own definition line (marked with the sentinel).
Run standalone: ``python tools/dx/identity_label_guard.py --check``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# plant_name || <opt s./x.>plant_id || <opt>probe || <opt>id
PATTERN = re.compile(
    r"plant_name\s*\|\|\s*[\w.]*plant_id\s*\|\|\s*[\w.]*probe\s*\|\|\s*[\w.]*\bid\b"
)
# The single allowed occurrence: plantLabel()'s definition, carrying this marker.
SENTINEL = "sole home (#925)"

_ANALYTICS = Path(__file__).resolve().parents[2] / "tools" / "analytics"


def find_hits(root: Path = _ANALYTICS) -> list[tuple[Path, int]]:
    """Every (file, line) with a raw identity chain outside plantLabel()."""
    hits: list[tuple[Path, int]] = []
    if not root.exists():
        return hits
    for path in sorted(root.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if PATTERN.search(line) and SENTINEL not in line:
                hits.append((path, lineno))
    return hits


def main() -> int:
    hits = find_hits()
    if not hits:
        return 0
    repo = _ANALYTICS.parents[1]
    print(
        "identity-label-guard: raw plant-first fallback chain outside plantLabel() "
        "(the #803-805 leak class, #925):",
        file=sys.stderr,
    )
    for path, lineno in hits:
        rel = path.relative_to(repo)
        print(
            f"  {rel}:{lineno}  ->  use plantLabel(x)  [+ {{side:true}} if needed]",
            file=sys.stderr,
        )
    print(
        "Fix: route through plantLabel() — the one identity-label home. See #925.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
