"""#1336 / ADR-0038 §5.1 — the design-asset leaf stays a LEAF.

The extraction is only worth anything if the leaf property holds. A layer-0 module
that quietly grows an import of ours stops being safe to reach for, and the pathology
(import 2,000 lines to get a Path) creeps back one import at a time.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from design_assets import FONTS_CSS, TOKENS_CSS, head_css, read_css

_HERE = Path(__file__).resolve().parent
_SRC = _HERE / "design_assets.py"
_STDLIB_OK = {"pathlib", "__future__", "os", "sys", "typing"}


def test_the_leaf_imports_nothing_of_ours() -> None:
    """The layer-0 rule, enforced rather than documented."""
    tree = ast.parse(_SRC.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    ours = {p.stem for p in _HERE.glob("*.py")}
    assert not (imported & ours), f"leaf reached into our tree: {imported & ours}"
    assert imported <= _STDLIB_OK, f"unexpected import: {imported - _STDLIB_OK}"


def test_no_sys_path_surgery_in_the_leaf() -> None:
    # 149 of 184 modules manipulate sys.path (ADR-0038's measured condition); a leaf
    # must not, or it is not importable-by-name when the package flip lands.
    src = _SRC.read_text(encoding="utf-8")
    assert "sys.path" not in src


def test_the_paths_point_where_they_always_did() -> None:
    # the extraction must be behaviour-identical — same files, not new ones
    assert TOKENS_CSS.name == "sprout-tokens.css"
    assert TOKENS_CSS.parent.name == "tokens"
    assert FONTS_CSS.name == "sprout-fonts.css"
    assert FONTS_CSS.parent.name == "vendor"


def test_dashboard_re_exports_the_same_objects() -> None:
    # dashboard's own readers are unaffected: the leaf is the definition, the
    # dashboard name is an alias to the identical object
    import dashboard

    assert dashboard.TOKENS_CSS is TOKENS_CSS
    assert dashboard.FONTS_CSS is FONTS_CSS


def test_reading_is_absent_safe() -> None:
    # a stripped deploy without the design tokens renders unstyled, never raises
    assert read_css(Path("no-such-file.css")) == ""
    assert isinstance(head_css(), str)


def test_the_three_pure_consumers_no_longer_import_the_dashboard() -> None:
    """The measurable win: three modules imported ~94 KB for two Paths."""
    for name in ("bench_packages", "experiments_catalog", "lab_studies"):
        src = (_HERE / f"{name}.py").read_text(encoding="utf-8")
        assert "from dashboard import" not in src, name
        assert "from design_assets import" in src, name
