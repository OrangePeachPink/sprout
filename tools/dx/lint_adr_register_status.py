#!/usr/bin/env python3
"""Lint: every ADR file's Status must match its register row (#928).

Trellis caught register-vs-file Status drift by hand twice (0025, then 0029 — a
ratification batch flipped the register row and appended "Accepted" mid-block while
the file's Status line still *led* with "Proposed"). This makes that drift a red gate
instead of a manual catch.

For every ``docs/adr/NNNN-*.md`` it compares the status keyword on the file's
``**Status:**`` line against the status in that ADR's row of the register table in
``0000-record-architecture-decisions.md``. Red on a mismatch, on an ADR file with no
register row, on a register row with no file, or on a duplicate register row.

The status keyword is the **first** of {Proposed, Accepted, Rejected, Deprecated,
Superseded} after the marker: by convention an ADR leads its Status line (and its
register cell) with the *current* status, so a later word in a rationale clause
(``… revised … then Accepted``) does not count — leading with the stale word is
exactly the drift this catches.

File-based and deterministic (no network), so pre-commit == ``just check`` == CI.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_STATUSES = ("Proposed", "Accepted", "Rejected", "Deprecated", "Superseded")
_STATUS_RE = re.compile(r"\b(" + "|".join(_STATUSES) + r")\b")
_ADR_DIR = Path(__file__).resolve().parents[2] / "docs" / "adr"
_REGISTER = _ADR_DIR / "0000-record-architecture-decisions.md"

# an ADR filename: NNNN-kebab-title.md (four digits); the register itself is 0000.
_FILE_RE = re.compile(r"^(\d{4})-.+\.md$")
# the file's Status line: `**Status:** <keyword> …` (only the first such line counts).
_STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*\s*(.*)$")
# a register row: `| [NNNN](file.md) | title | status cell | owner |`.
_ROW_RE = re.compile(r"^\|\s*\[(\d{4})\]\(")


def _first_status(text: str) -> str | None:
    """The first status keyword in ``text``, or None if none is present."""
    m = _STATUS_RE.search(text)
    return m.group(1) if m else None


def file_statuses(adr_dir: Path) -> dict[str, str | None]:
    """{NNNN: status keyword} read from each ADR file's `**Status:**` line.

    None means the file has a Status line with no recognizable keyword (a finding);
    a file with no Status line at all is omitted (the register cross-check flags it)."""
    out: dict[str, str | None] = {}
    for md in sorted(adr_dir.glob("*.md")):
        m = _FILE_RE.match(md.name)
        if not m:
            continue
        status: str | None = None
        found = False
        for line in md.read_text(encoding="utf-8").splitlines():
            sm = _STATUS_LINE_RE.match(line.strip())
            if sm:
                found = True
                status = _first_status(sm.group(1))
                break
        if found:
            out[m.group(1)] = status
    return out


def register_rows(register: Path) -> list[tuple[str, str | None]]:
    """[(NNNN, status keyword), …] — one per register row, in file order.

    A list (not a dict) so a duplicated ADR number stays visible rather than being
    collapsed by last-write-wins — a duplicate row is itself drift (#928)."""
    rows: list[tuple[str, str | None]] = []
    for line in register.read_text(encoding="utf-8").splitlines():
        rm = _ROW_RE.match(line)
        if not rm:
            continue
        cells = line.split("|")
        # `| link | title | status | owner |` -> ['', link, title, status, owner, '']
        status_cell = cells[3] if len(cells) > 3 else ""
        rows.append((rm.group(1), _first_status(status_cell)))
    return rows


def check(adr_dir: Path = _ADR_DIR, register: Path = _REGISTER) -> list[str]:
    """Human-readable findings; empty means every ADR status agrees."""
    files = file_statuses(adr_dir)
    findings: list[str] = []
    # duplicate register rows for one ADR — a merge-ordering casualty (#928); a dict
    # would silently keep only one (and maybe the wrong status), so flag the extras.
    seen: dict[str, str | None] = {}
    for num, status in register_rows(register):
        if num in seen:
            findings.append(f"ADR-{num}: appears more than once in the register")
        else:
            seen[num] = status
    for num in sorted(set(files) | set(seen)):
        f = files.get(num, "__missing__")
        r = seen.get(num, "__missing__")
        if f == "__missing__":
            findings.append(f"ADR-{num}: in the register but no ADR file found")
        elif r == "__missing__":
            findings.append(f"ADR-{num}: ADR file exists but no register row")
        elif f is None:
            findings.append(f"ADR-{num}: file has no recognized status keyword")
        elif r is None:
            findings.append(f"ADR-{num}: register has no recognized status keyword")
        elif f != r:
            findings.append(f"ADR-{num}: file says '{f}', register says '{r}'")
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint ADR Status vs register row (#928).")
    ap.add_argument("--check", action="store_true", help="(default) fail on drift")
    ap.parse_args(argv)
    findings = check()
    if findings:
        print("ADR register-status lint — MISMATCH:")
        for f in findings:
            print(f"  - {f}")
        print(f"\n{len(findings)} finding(s) — reconcile file Status vs register.")
        return 1
    print("ADR register-status lint — OK (all ADR statuses match the register).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
