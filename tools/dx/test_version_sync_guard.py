"""Tests for the #1407 version-sync guard.

Runs under `just test-dx`. The historical-mentions test is the important one: this
guard's real risk is not missing a drift, it is flagging correct history and getting
itself switched off."""

import re
from datetime import date
from pathlib import Path

from tools.dx import version_sync_guard as g


def _repo(
    tmp_path: Path, version="1.2.3", citation=None, fw=None, html=None, lock=None
) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\n', encoding="utf-8"
    )
    # #1637: a valid citation carries a date. Without one here, every synthetic repo
    # would trip the date check and the version assertions would drown in it — the
    # fixture has to represent a repo that is actually correct.
    (tmp_path / "CITATION.cff").write_text(
        f'version: "{citation or version}"\ndate-released: "2020-01-01"\n',
        encoding="utf-8",
    )
    (tmp_path / "firmware" / "include").mkdir(parents=True)
    (tmp_path / "firmware" / "include" / "config.h").write_text(
        f'constexpr char PLANTS_FW_VERSION[] = "{fw or version}";\n', encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.html").write_text(
        f'  "version": "{html or version}",\n', encoding="utf-8"
    )
    # #1633: a realistic lockfile — OTHER packages first, and one of them deliberately
    # carries the canonical version string. A guard anchored to `version =` rather than
    # to the sprout BLOCK would match here and pass (or go ambiguous) for the wrong
    # reason, so the fixture makes that mistake detectable instead of theoretical.
    (tmp_path / "uv.lock").write_text(
        "[[package]]\n"
        'name = "pandas"\n'
        f'version = "{version}"\n'
        "\n"
        "[[package]]\n"
        'name = "sprout"\n'
        f'version = "{lock or version}"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
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
    findings = g.check(repo)
    # Gutting the file loses BOTH declared claims — the version site and the release
    # date (#1637). Two findings is the honest answer; each names its own loss.
    assert any("matched NOTHING" in f.detail for f in findings)
    assert any("no date-released" in f.detail for f in findings)


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


def test_a_stale_lockfile_is_caught(tmp_path: Path) -> None:
    """#1633, the exact v0.8.1 miss: four sites at the new version, the lock behind.

    The guard reported "4 declared site(s) agree" — green, and true — while uv.lock
    still read the old number. Every routine command runs `uv run --frozen`, so that
    lands on whoever runs the next command after the bump merges, with an error that
    names none of this.
    """
    (f,) = g.check(_repo(tmp_path, version="1.2.3", lock="1.2.2"))
    assert "uv.lock" in f.path
    assert "'1.2.2'" in f.detail and "'1.2.3'" in f.detail


def test_the_lock_pattern_ignores_other_packages(tmp_path: Path) -> None:
    """A lockfile is mostly OTHER packages' versions.

    The fixture's pandas entry sits at the canonical version; if the pattern were a
    loose `version =` it would match twice and fail as ambiguous even when sprout is
    perfectly in sync. Passing here is what proves the anchor is on the sprout block.
    """
    assert g.check(_repo(tmp_path)) == []


def test_a_drifted_lock_is_reported_at_sprouts_line_not_a_namesakes(
    tmp_path: Path,
) -> None:
    """Naming the wrong line sends the reader to edit the wrong package.

    pandas shares the canonical version, so a line-number derived from searching for
    the bare literal could land on pandas' block. The reported line must be sprout's.
    """
    repo = _repo(tmp_path, version="1.2.3", lock="1.2.2")
    (f,) = g.check(repo)
    reported = int(f.path.split(":")[1])
    lines = (repo / "uv.lock").read_text(encoding="utf-8").splitlines()
    assert lines[reported - 1] == 'version = "1.2.2"'
    assert lines[reported - 2] == 'name = "sprout"'


def _cff(tmp_path: Path, body: str) -> Path:
    repo = _repo(tmp_path)
    (repo / "CITATION.cff").write_text(body, encoding="utf-8")
    return repo


def test_a_future_release_date_is_caught(tmp_path: Path) -> None:
    """#1637, and the exact way v0.8.1 got it wrong.

    date-released is written at RELEASE_CUT §1, BEFORE the tag exists — so it is a
    prediction until the publish click. v0.8.1 was set to 2026-07-25 and published
    2026-07-26T01:20:53Z: a US-evening cut lands on the next UTC day. The field was
    wrong on its first outing by exactly this mechanism.
    """
    repo = _cff(tmp_path, 'version: "1.2.3"\ndate-released: "2026-07-27"\n')
    f = g.check_release_date(repo, today=date(2026, 7, 26))
    assert f is not None and "FUTURE" in f.detail


def test_todays_date_is_fine(tmp_path: Path) -> None:
    """Same-day precision is the accepted trade (#1637) — only the future is wrong."""
    repo = _cff(tmp_path, 'version: "1.2.3"\ndate-released: "2026-07-26"\n')
    assert g.check_release_date(repo, today=date(2026, 7, 26)) is None


def test_a_missing_release_date_is_caught(tmp_path: Path) -> None:
    """Every Sprout release before v0.8.1 shipped with no date at all."""
    repo = _cff(tmp_path, 'version: "1.2.3"\n')
    f = g.check_release_date(repo)
    assert f is not None and "no date-released" in f.detail


def test_a_malformed_release_date_is_not_silently_accepted(tmp_path: Path) -> None:
    repo = _cff(tmp_path, 'version: "1.2.3"\ndate-released: "2026-13-99"\n')
    f = g.check_release_date(repo)
    assert f is not None and "not a date" in f.detail


def test_the_real_tree_has_a_sane_release_date() -> None:
    """The live claim: the citation is dated, and not dated in the future."""
    assert g.check_release_date() is None


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
