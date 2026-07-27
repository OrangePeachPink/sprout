"""Tests for the #926 SVG-geometry-moustache tripwire (the #886 class)."""

from __future__ import annotations

from pathlib import Path

from tools.dx.svg_geometry_guard import PATTERN, find_hits, main


def _hit(s: str) -> bool:
    return PATTERN.search(s) is not None


def test_catches_raw_geometry_moustaches():
    # The exact #886 leaks.
    assert _hit('<path d="{{ sparkPath }}">')
    assert _hit('<circle cx="{{ sparkX }}" cy="{{ sparkY }}">')
    assert _hit('<polyline points="{{ c.spark }}">')
    assert _hit('<polygon points="{{ areaPoints }}">')


def test_ignores_the_sc_camel_prefixed_fix():
    # The #895 fix form must NOT trip the guard.
    assert not _hit('<path sc-camel-d="{{ sparkPath }}">')
    assert not _hit('<circle sc-camel-cx="{{ sparkX }}" sc-camel-cy="{{ sparkY }}">')
    assert not _hit('<polyline sc-camel-points="{{ c.spark }}">')


def test_ignores_paint_and_literal_geometry():
    # Paint attrs are ignored-if-invalid by spec — not the class.
    assert not _hit('<path fill="{{ leafColor }}" stroke="{{ stemColor }}">')
    # Literal (already-substituted) geometry is fine.
    assert not _hit('<path d="M12 26 V12">')
    assert not _hit('<circle cx="0" cy="12" r="3.6">')
    # A partial-value moustache inside transform (translate) is not a whole-binding
    # geometry attr and is left to the author — not flagged here.
    assert not _hit('<path transform="translate({{ x }} 0)">')


def test_current_design_tree_is_clean():
    # The whole point: after #895, the class is empty. This is the regression lock.
    hits = find_hits()
    assert hits == [], "raw SVG geometry moustaches present: " + ", ".join(
        f"{p.name}:{ln} {attr}" for p, ln, attr in hits
    )


def test_main_returns_zero_on_clean_tree():
    assert main() == 0


def test_finds_a_planted_bad_file(tmp_path: Path):
    root = tmp_path / "docs" / "design" / "foundations"
    root.mkdir(parents=True)
    (root / "bad.dc.html").write_text(
        '<svg><path d="{{ leak }}"></path></svg>', encoding="utf-8"
    )
    (root / "good.dc.html").write_text(
        '<svg><path sc-camel-d="{{ ok }}"></path></svg>', encoding="utf-8"
    )
    hits = find_hits(tmp_path / "docs" / "design")
    assert len(hits) == 1
    assert hits[0][0].name == "bad.dc.html"
    assert hits[0][2] == "d"
