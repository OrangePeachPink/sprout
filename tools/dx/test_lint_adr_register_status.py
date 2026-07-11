"""Tests for the ADR register-status lint (#928).

Covers status extraction (leading keyword wins — the drift Trellis kept catching by
hand), file/register mismatches, orphans both ways, duplicate register rows (the
merge-ordering casualty that left two 0029 rows), and a live-repo guard.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_adr_register_status as L


def _adr(adr_dir: Path, num: str, status_line: str) -> None:
    (adr_dir / f"{num}-example.md").write_text(
        f"# ADR-{num} — example\n\n{status_line}\n\nbody\n", encoding="utf-8"
    )


def _register(adr_dir: Path, rows: list[tuple[str, str]]) -> Path:
    """Write a register file whose table has one row per (num, status_cell).

    The 0000 register file carries no `**Status:**` line, so it is neither a file-status
    nor a register row here — it stays out of the comparison (as in the real repo)."""
    lines = ["# register", "", "| # | Title | Status | Owner |", "|---|---|---|---|"]
    for num, status in rows:
        lines.append(f"| [{num}]({num}-example.md) | A title | {status} | An owner |")
    reg = adr_dir / "0000-record-architecture-decisions.md"
    reg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return reg


def test_all_match_is_clean(tmp_path: Path) -> None:
    _adr(tmp_path, "0005", "**Status:** Accepted (2026-01-01)")
    _adr(tmp_path, "0011", "**Status:** Proposed — direction agreed")
    reg = _register(
        tmp_path,
        [("0005", "**Accepted** — ratified"), ("0011", "**Proposed** — draft")],
    )
    assert L.check(tmp_path, reg) == []


def test_status_mismatch_is_flagged(tmp_path: Path) -> None:
    _adr(tmp_path, "0005", "**Status:** Proposed — draft")
    reg = _register(tmp_path, [("0005", "**Accepted** — ratified")])
    findings = L.check(tmp_path, reg)
    assert any("0005" in f and "Proposed" in f and "Accepted" in f for f in findings)


def test_leading_keyword_wins_catches_stale_lead(tmp_path: Path) -> None:
    # the exact 0029/0030/0031 drift: the Status block LEADS with the stale word even
    # though a later clause says the true status — the lead is what a reader trusts.
    _adr(
        tmp_path,
        "0030",
        "**Status:** Proposed — drafted; later Accepted — maintainer-ratified",
    )
    reg = _register(tmp_path, [("0030", "**Accepted** — maintainer-ratified")])
    findings = L.check(tmp_path, reg)
    assert any("says 'Proposed'" in f and "0030" in f for f in findings)


def test_duplicate_register_row_is_flagged(tmp_path: Path) -> None:
    # the merge-ordering casualty: two rows for one ADR (a dict would hide the second).
    _adr(tmp_path, "0029", "**Status:** Accepted")
    reg = _register(tmp_path, [("0029", "**Accepted**"), ("0029", "**Proposed**")])
    findings = L.check(tmp_path, reg)
    assert any("0029" in f and "more than once" in f for f in findings)


def test_file_without_register_row(tmp_path: Path) -> None:
    _adr(tmp_path, "0005", "**Status:** Accepted")
    reg = _register(tmp_path, [])
    assert any("no register row" in f for f in L.check(tmp_path, reg))


def test_register_row_without_file(tmp_path: Path) -> None:
    reg = _register(tmp_path, [("0007", "**Accepted**")])
    assert any("no ADR file" in f for f in L.check(tmp_path, reg))


def test_unparseable_status_is_flagged(tmp_path: Path) -> None:
    _adr(tmp_path, "0005", "**Status:** (nothing recognizable here)")
    reg = _register(tmp_path, [("0005", "**Accepted**")])
    assert any("no recognized status keyword" in f for f in L.check(tmp_path, reg))


def test_live_repo_register_is_clean() -> None:
    # The real tree must pass — it lands green with the drift fixes in this same PR,
    # and any future ADR status drift turns this red.
    assert L.check() == []
