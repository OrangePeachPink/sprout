"""Tests for the #925 identity-label tripwire (the #803-805 leak class)."""

from __future__ import annotations

from pathlib import Path

from identity_label_guard import PATTERN, SENTINEL, find_hits, main


def _hit(s: str) -> bool:
    return PATTERN.search(s) is not None


def test_catches_the_raw_chain_variants():
    assert _hit("const lead = s.plant_name || s.plant_id || s.probe || s.id;")
    assert _hit("const name = x.plant_name || x.plant_id || x.probe || x.id;")
    assert _hit("`Open the ${s.plant_name || s.plant_id || s.probe || s.id} view`")
    assert _hit("plant_name || plant_id || probe || id")  # single-device, no prefixes


def test_ignores_plantlabel_calls():
    assert not _hit("const label = plantLabel(s);")
    assert not _hit("plantLabel(x, {side:true})")
    assert not _hit(
        "const name = x.plant_name || x.plant_id;"
    )  # partial, not the chain


def test_sentinel_line_is_allowed():
    line = "plant_name || plant_id || probe || id  // sole home (#925)"
    assert (
        _hit(line) and SENTINEL in line
    )  # matches the pattern, but the sentinel exempts it


def test_current_tree_is_clean():
    # After #925 every site uses plantLabel(); only the sentinel line has the chain.
    hits = find_hits()
    assert hits == [], "raw identity chain outside plantLabel(): " + ", ".join(
        f"{p.name}:{ln}" for p, ln in hits
    )


def test_main_returns_zero_on_clean_tree():
    assert main() == 0


def test_finds_a_planted_regression(tmp_path: Path):
    root = tmp_path / "tools" / "analytics"
    root.mkdir(parents=True)
    (root / "bad.html").write_text(
        "x.title = `${s.plant_name || s.plant_id || s.probe || s.id}`;",
        encoding="utf-8",
    )
    good = "x = plantLabel(s);\n"
    good += "c = plant_name || plant_id || probe || id; // sole home (#925)"
    (root / "good.html").write_text(good, encoding="utf-8")
    hits = find_hits(root)
    assert len(hits) == 1
    assert hits[0][0].name == "bad.html"
