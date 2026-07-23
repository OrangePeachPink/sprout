"""Tests for the #1407 version-sync guard.

Runs under `just test-dx`. The historical-mentions test is the important one: this
guard's real risk is not missing a drift, it is flagging correct history and getting
itself switched off."""

import re
from pathlib import Path

from tools.dx import version_sync_guard as g


def _repo(tmp_path: Path, version="1.2.3", citation=None, fw=None, html=None) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n', encoding="utf-8"
    )
    (tmp_path / "CITATION.cff").write_text(
        f'version: "{citation or version}"\n', encoding="utf-8"
    )
    (tmp_path / "firmware" / "include").mkdir(parents=True)
    (tmp_path / "firmware" / "include" / "config.h").write_text(
        f'constexpr char PLANTS_FW_VERSION[] = "{fw or version}";\n', encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.html").write_text(
        f'  "version": "{html or version}",\n', encoding="utf-8"
    )
    return tmp_path


def test_all_agreeing_passes(tmp_path: Path) -> None:
    assert g.check(_repo(tmp_path)) == []


def test_one_drifted_site_is_named_with_both_values(tmp_path: Path) -> None:
    (f,) = g.check(_repo(tmp_path, version="1.2.3", citation="1.2.2"))
    assert "CITATION.cff" in f.path
    assert "'1.2.2'" in f.detail and "'1.2.3'" in f.detail  # found AND expected


def test_the_citation_is_covered(tmp_path: Path) -> None:
    """The surface that sent us here: a stale citation is copied verbatim, forever."""
    findings = g.check(_repo(tmp_path, version="2.0.0", citation="0.7.3"))
    assert any("CITATION.cff" in f.path for f in findings)


def test_firmware_and_jsonld_are_covered(tmp_path: Path) -> None:
    findings = g.check(_repo(tmp_path, version="2.0.0", fw="1.0.0", html="1.5.0"))
    assert len(findings) == 2


def test_a_pattern_matching_nothing_fails_loudly(tmp_path: Path) -> None:
    """Silence is a failure: a restructured file must not read as a clean pass."""
    repo = _repo(tmp_path)
    (repo / "CITATION.cff").write_text("# version moved elsewhere\n", encoding="utf-8")
    (f,) = g.check(repo)
    assert "matched NOTHING" in f.detail


def test_an_ambiguous_pattern_fails_loudly(tmp_path: Path) -> None:
    """Two matches means we cannot say which one we are watching."""
    repo = _repo(tmp_path)
    (repo / "docs" / "index.html").write_text(
        '  "version": "1.2.3",\n  "version": "9.9.9",\n', encoding="utf-8"
    )
    (f,) = g.check(repo)
    assert "ambiguous" in f.detail


def test_a_missing_site_fails_loudly(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "CITATION.cff").unlink()
    (f,) = g.check(repo)
    assert "MISSING" in f.detail


def test_historical_mentions_are_never_flagged(tmp_path: Path) -> None:
    """THE test for this guard. Prose recording an OLD version is correct and must
    survive every future bump — rewriting it would falsify the record. A guard that
    grepped for the literal would flag all of these and get itself disabled."""
    repo = _repo(tmp_path, version="9.9.9")
    (repo / "docs" / "history.md").write_text(
        "The v0.7.3 wash (PR #1099) retired a register.\n"
        "Velocity modes — standing policy as of v0.7.3.\n"
        'version = "0.7.3"  # in a code block, quoting the old pyproject\n',
        encoding="utf-8",
    )
    assert g.check(repo) == []  # the drifted-looking prose is invisible to the guard


def test_the_real_tree_agrees() -> None:
    """The live claim: every declared site in THIS repo is in sync right now."""
    assert g.check() == []


def test_the_real_tree_patterns_each_match_exactly_once() -> None:
    """Guards the guard: every declared pattern is really watching one live site."""
    for rel, pat in (g._CANON, *g._SITES):
        text = (g._REPO / rel).read_text(encoding="utf-8")
        assert len(pat.findall(text)) == 1, f"{rel} is not matched exactly once"


def test_canonical_source_is_pyproject() -> None:
    assert g._CANON[0] == "pyproject.toml"
    assert isinstance(g._CANON[1], re.Pattern)
