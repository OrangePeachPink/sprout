"""Tests for the #1327 NUL-byte guard.

The pure logic (offset finding, exemption, skipping) is unit-tested with temp files; two
integration tests run against the real tree, because the whole point of the guard is a
claim about THIS repo — that the .gitattributes key really does exempt the legitimate
binary, and that the tree is clean so the guard lands green."""

from pathlib import Path

import nul_byte_guard as g


def _write(tmp_path: Path, name: str, data: bytes) -> str:
    (tmp_path / name).write_bytes(data)
    return name


def test_first_nul_reports_the_offset(tmp_path: Path) -> None:
    p = tmp_path / "f.c"
    p.write_bytes(b"abc\x00def")
    assert g.first_nul(p) == 3


def test_first_nul_finds_one_past_a_chunk_boundary(tmp_path: Path) -> None:
    # The scan is chunked; a NUL just past the first chunk must still be found, with an
    # offset relative to the whole file rather than the chunk.
    p = tmp_path / "big.txt"
    p.write_bytes(b"x" * (g._CHUNK + 10) + b"\x00")
    assert g.first_nul(p) == g._CHUNK + 10


def test_clean_file_is_none(tmp_path: Path) -> None:
    p = tmp_path / "clean.txt"
    p.write_text("no nulls here\n")
    assert g.first_nul(p) is None


def test_scan_flags_a_nul_bearing_file(tmp_path: Path) -> None:
    rel = _write(tmp_path, "bad.c", b"static char t[] = {'a', \x00};\n")
    assert g.scan([rel], set(), repo=tmp_path) == [(rel, 24)]


def test_declared_binary_is_exempt(tmp_path: Path) -> None:
    rel = _write(tmp_path, "asset.gif", b"GIF89a\x00\x00")
    assert g.scan([rel], {rel}, repo=tmp_path) == []


def test_missing_file_is_skipped_not_crashed(tmp_path: Path) -> None:
    # A staged delete leaves a tracked path with no file on disk; that is not this
    # guard's business to report.
    assert g.scan(["gone.txt"], set(), repo=tmp_path) == []


def test_the_real_gitattributes_exempts_the_committed_gif() -> None:
    """The exemption key is .gitattributes, not a second allowlist — so prove it works
    on the real declaration rather than a mocked one."""
    paths = g.tracked_files()
    exempt = g.declared_binary(paths)
    gifs = [p for p in paths if p.endswith(".gif")]
    assert gifs, "expected at least one tracked .gif to exercise the binary rule"
    assert set(gifs) <= exempt


def test_the_tree_is_clean_so_the_guard_lands_green() -> None:
    assert g.main([]) == 0
