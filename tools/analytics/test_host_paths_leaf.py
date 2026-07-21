#!/usr/bin/env python3
"""#1336 §5.1 — the `host_paths` leaf: one home for the data paths.

The leaf pattern's whole value is that it holds *by construction*, not by discipline.
These tests pin the two properties that make it true — zero internal imports, and one
definition rather than a second copy — because both are easy to lose silently: an
import added for convenience, or a path re-derived locally by someone who did not know
the leaf existed.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import host_paths

_HERE = Path(__file__).resolve().parent


def test_the_leaf_imports_nothing_of_ours() -> None:
    """Layer 0 is defined by this, not merely described by it. An internal import here
    would let a leaf drag a subtree behind it and quietly re-create the cycle risk the
    layer rule exists to remove."""
    ours = {p.stem for p in _HERE.glob("*.py")}
    tree = ast.parse((_HERE / "host_paths.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & ours), f"the leaf imports our modules: {imported & ours}"


def test_the_paths_have_one_definition_not_two() -> None:
    """The re-export in dashboard is a *name*; the leaf is the definition. If either
    module ever computed its own copy, the two halves could disagree about where the
    data is — the failure a shared constant is supposed to make impossible."""
    import dashboard
    import serve

    assert dashboard.LOGS_DIR is host_paths.LOGS_DIR
    assert dashboard.ARCHIVE_DIR is host_paths.ARCHIVE_DIR
    assert serve.LOGS_DIR is host_paths.LOGS_DIR
    assert serve.ARCHIVE_DIR is host_paths.ARCHIVE_DIR


def test_the_paths_still_point_where_they_always_did() -> None:
    """A move must not relocate the data. LOGS_DIR is the repo's logs/; ARCHIVE_DIR is
    the B8 gzip archive inside the data worktree."""
    assert host_paths.LOGS_DIR == host_paths.REPO / "logs"
    assert host_paths.ARCHIVE_DIR == (
        host_paths.REPO / ".data-worktree" / "data" / "archive"
    )
    assert (host_paths.REPO / "tools" / "analytics").is_dir()  # the root really is root


def test_serve_no_longer_imports_the_dashboard_for_a_path() -> None:
    """The named pathology (#1336 / ADR-0038 §5.1): importing a ~2,000-line module to
    obtain two constants. A refactor that leaves the old import in place has moved the
    code without removing the reason it mattered."""
    source = (_HERE / "serve.py").read_text(encoding="utf-8")
    block = source.split("from dashboard import (", 1)[1].split(")", 1)[0]
    for path_const in ("ARCHIVE_DIR", "LOGS_DIR"):
        assert path_const not in block, (
            f"serve.py still pulls {path_const} through dashboard — the leaf exists "
            "precisely so it does not have to"
        )
