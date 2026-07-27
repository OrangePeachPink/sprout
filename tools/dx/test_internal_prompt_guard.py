"""#1659 — the internal-material guard, and the false positives it must not have.

The #1117/#1129 incident is the standing proof this exists: a contributor's agent read
our then-public instruction files and faithfully imitated internal conventions, twice,
across two PRs. The contributor did nothing wrong — every public doc is executable input
for every reader's agent.

The hardest requirement here is NOT catching internal files. It is not firing on the
legitimate ones, because a guard that cries wolf gets switched off and then catches
nothing at all.
"""

from __future__ import annotations

from pathlib import Path

from tools.dx import internal_prompt_guard as g

# Every one of these is tracked in this repo RIGHT NOW and is legitimately public. The
# obvious denylist — *runbook*, *transcript*, *relay*, *lane* — matches all five.
REAL_PUBLIC_FILES = [
    "docs/bench-procedures/front-door-launch-runbook.md",
    "docs/bench-procedures/pumps-relays-bringup-run-sheet.md",
    "docs/flaura-video-transcript.txt",
    "docs/design/foundations/Sprout Band-Lane Visual Language.dc.html",
    "docs/design/library/thumbs/band-lane-visual-language.png",
    "docs/process/RELEASE_CUT.md",
    "docs/team/OPERATIONS.md",
    "README.md",
]

SHOULD_REJECT = [
    "_internal/notes.md",
    "internal/lane-brief.md",
    ".agents/workflow.md",
    "docs/lane-runbook-workflow.md",
    "docs/prompts/certify.md",
    "lane-prompts/dx.md",
    "docs/transcripts/2026-07-26.md",
    "docs/sprout-workflow-lane.md",
    "notes/dx-lane-notes.md",
    "docs/relay-draft-to-design.md",
]


def test_no_legitimate_public_file_is_rejected() -> None:
    """THE test. The naive denylist fires on five of these; this one must fire on none.

    A guard's first day is when it earns or loses the right to keep running.
    """
    for rel in REAL_PUBLIC_FILES:
        assert g.check_path(rel) is None, f"false positive on a real public file: {rel}"


def test_the_whole_tracked_tree_is_clean() -> None:
    """The live claim, not a sample: every file in this repo passes right now.

    If a future pattern is added carelessly this fails immediately, which is the point —
    the cost of a bad pattern lands on its author rather than on the next contributor.
    """
    assert g.scan(g._tracked()) == []


def test_internal_shapes_are_rejected() -> None:
    for rel in SHOULD_REJECT:
        assert g.check_path(rel) is not None, f"missed internal shape: {rel}"


def test_the_sentinel_catches_an_innocuously_named_file(tmp_path: Path) -> None:
    """The amendment's whole point.

    A path denylist catches `sprout-workflow-lane-runbook.md`. It does not catch
    `notes.md` — and nobody reviewing a diff titled `notes.md` looks twice.
    """
    p = tmp_path / "notes.md"
    p.write_text(
        f"# notes\n<!-- {g.SENTINEL} -->\nlane procedure...\n", encoding="utf-8"
    )
    assert g.check_path("notes.md") is None, "the path alone is innocuous, as intended"
    assert g.check_content(p) is not None


def test_an_ordinary_file_has_no_sentinel(tmp_path: Path) -> None:
    p = tmp_path / "notes.md"
    p.write_text("# notes\njust some public prose about plants.\n", encoding="utf-8")
    assert g.check_content(p) is None


def test_the_guard_does_not_trip_on_itself() -> None:
    """The self-reference problem, solved without a skip-list.

    A guard that searches for a literal string cannot contain that literal. The usual
    fix is to skip its own filename — but a skip-list silently stops protecting the
    guard's whole directory, so the sentinel is assembled at runtime instead and the
    guard is scanned like everything else.
    """
    here = Path(g.__file__)
    assert g.check_content(here) is None, "the guard flags itself"
    assert g.check_content(Path(__file__)) is None, "the guard flags its own tests"
    assert g.SENTINEL not in here.read_text(encoding="utf-8"), (
        "the literal sentinel appears in the guard source — it will self-trip"
    )


def test_the_known_gap_is_documented_not_hidden() -> None:
    """The sentinel only protects docs that carry it.

    A new internal file authored without the marker is unprotected. That limit belongs
    in the module text, because the counterpart check lives in the OTHER repo and a
    reader here has no way to discover it otherwise.
    """
    assert "only protects documents that carry it" in (g.__doc__ or "")
    assert "internal* repo" in (g.__doc__ or "") or "internal repo" in (g.__doc__ or "")
