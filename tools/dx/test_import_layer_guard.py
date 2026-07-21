"""Tests for the #1336 / ADR-0038 §2 import-layer guard.

Runs under `just test-dx`. Supersedes `tools/analytics/test_design_assets_leaf.py`,
whose two assertions (a leaf imports nothing of ours; a leaf does no sys.path surgery)
are carried below as the layer-0 rules — generalised from one module to every module
assigned layer 0."""

from pathlib import Path

import import_layer_guard as g


def _tree(tmp_path: Path, **modules: str) -> Path:
    for name, src in modules.items():
        (tmp_path / f"{name}.py").write_text(src, encoding="utf-8")
    return tmp_path


def test_downward_import_is_allowed(tmp_path: Path) -> None:
    host = _tree(tmp_path, low="X = 1", high="import low")
    assert g.check(host, {"low": 1, "high": 4}) == []


def test_upward_import_is_caught(tmp_path: Path) -> None:
    host = _tree(tmp_path, low="import high", high="Y = 2")
    (f,) = g.check(host, {"low": 1, "high": 4})
    assert "UPWARD" in f.detail and "high" in f.detail


def test_sideways_import_is_caught(tmp_path: Path) -> None:
    """The rule is strictly lower — equal layers are not a loophole."""
    host = _tree(tmp_path, a="import b", b="Z = 3")
    (f,) = g.check(host, {"a": 4, "b": 4})
    assert "SIDEWAYS" in f.detail


def test_leaf_importing_ours_is_caught(tmp_path: Path) -> None:
    """Carried from test_design_assets_leaf: a leaf reaches into nothing of ours."""
    host = _tree(tmp_path, leaf="import other", other="W = 4")
    (f,) = g.check(host, {"leaf": 0, "other": 1})
    assert "LEAF imports of ours" in f.detail


def test_leaf_doing_path_surgery_is_caught(tmp_path: Path) -> None:
    """Carried from test_design_assets_leaf: a leaf must be importable by name when
    the package flip lands (ADR-0038 §5.4)."""
    host = _tree(tmp_path, leaf="import sys\nsys.path.insert(0, '.')\n")
    (f,) = g.check(host, {"leaf": 0})
    assert "sys.path surgery" in f.detail


def test_stdlib_imports_are_never_a_violation(tmp_path: Path) -> None:
    host = _tree(tmp_path, leaf="import json\nfrom pathlib import Path\n")
    assert g.check(host, {"leaf": 0}) == []


def test_an_unassigned_target_is_not_judged(tmp_path: Path) -> None:
    """No guessing: an import of a module with no assignment cannot be ruled on, and
    is counted in the coverage line rather than assumed compliant OR assumed broken."""
    host = _tree(tmp_path, top="import mystery", mystery="Q = 5")
    assert g.check(host, {"top": 1}) == []


def test_a_stale_assignment_is_caught(tmp_path: Path) -> None:
    """An assignment pointing at a module that no longer exists is watching nothing."""
    (f,) = g.check(_tree(tmp_path, real="A = 1"), {"ghost": 2})
    assert "ASSIGNED but missing" in f.detail


def test_the_real_tree_has_no_violations() -> None:
    """The live claim: every assigned module obeys ADR-0038 §2 today."""
    assert g.check() == []


def test_coverage_is_honest_about_what_is_unchecked() -> None:
    """The guard's own limit, asserted: it judges a subset, and says so. If these ever
    become equal the lint covers the tree — and this test should be the thing that
    notices."""
    assigned, total = g.coverage()
    assert 0 < assigned <= total
    assert total > 20  # a scan finding nothing would otherwise pass loudly


def test_every_assignment_points_at_a_real_module() -> None:
    for module in g._LAYERS:
        assert (g._HOST / f"{module}.py").exists(), f"{module} is assigned but absent"
