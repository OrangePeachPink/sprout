#!/usr/bin/env python3
"""#1336 / ADR-0038 §2 — imports go to a lower layer, or the same layer below 4.

The rung the extractions wait behind. ADR-0038's measured condition: 149 of 184 host
modules manipulate ``sys.path``, nothing is importable by name, and several Lab modules
import the ~2,000-line ``dashboard`` to obtain two CSS constants. **Any module can
import any other and nothing makes a bad reach awkward** — the mechanism behind the
#1315 two-truths incident, not a tidiness complaint.

    A module may import from a lower layer, or the same layer below layer 4.
    Never upward; never sideways within layer 4; never a same-layer cycle.

    Amended 2026-07-22 (#1452): same-layer composition below the delivery tier is
    legitimate — a layer-3 module importing another layer-3 module is normal, not a
    tangle. Layer 4 keeps the no-sideways rule, and a same-layer cycle stays a defect.

**A declared table, never an inferred one.** Layer assignment is an architecture
decision (Trellis owns the boundaries; Data owns the modules), so this file records
assignments that have been *made* rather than guessing from directory names. An
unassigned module is reported as unassigned — never quietly treated as compliant.

**Coverage is printed every run.** A lint that judges three modules out of 184 and
prints only "OK" would read exactly like one that judges all of them. The counts are
the honest statement of how much of the tree this rule covers yet, and watching the
unassigned number fall is how the ladder's progress is visible.

**Layer 0 carries two extra rules**, inherited from the #1336 leaf tests this
supersedes: a leaf imports nothing of ours at all, and a leaf performs no ``sys.path``
surgery — it must be importable by name when the package flip (ADR-0038 §5.4) lands.

Out of scope by design: ADR-0038 §3's one-implementation rule covers templates, SQL and
JavaScript, which no import graph can see. That is #1338's seam-conformance harness, and
until then it is enforced at review.

    python tools/dx/import_layer_guard.py            # advisory: report, exit 0
    python tools/dx/import_layer_guard.py --check    # enforcing on assigned modules
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_HOST = _REPO / "tools" / "analytics"

# ADR-0038 §1. Assignments are added as the owning lane makes them — deliberately,
# one at a time. Every name here has been verified against the tree; see the tests.
_LAYERS: dict[str, int] = {
    "board_pinouts": 0,  # #1027 — the recommended soil pinout, mirrored from firmware
    "design_assets": 0,  # §5.1 leaf extraction (#1336 / PR #1387)
    "host_paths": 0,  # §5.1 leaf extraction (#1336) — the data paths
    # #1452 — the extracted route table: a pure string-matching LEAF (no I/O, no
    # import). serve (4) → serve_routes is a legal DOWNWARD edge. It is NOT layer 4: §2
    # forbids "sideways within layer 4" and serve imports it, so a route table at 4
    # would be exactly that. Trellis RATIFIED the leaf placement on #1452 (the first
    # ruling's "4" was corrected there).
    "serve_routes": 0,
    "parse_v1": 1,  # §1 "telemetry parsing (parse_v1)"
    "channel_identity": 2,  # #1454 — the S1-seam join (analysis; imports parse_v1 only)
    "card_context": 3,  # §5.3 extraction (#1336) — "dashboard context assembly" (§1)
    # `dashboard` is layer 3 — ruled on #1452 (Trellis): zero HTTP I/O, pure
    # context→string composition, imports only downward or same-layer (card_context, 3).
    # serve (4) → dashboard (3) is a legal downward edge, and dashboard → card_context
    # is legal same-layer composition below the delivery tier per §2 as amended
    # 2026-07-22 (#1513; guard aligned in #1519). Assigned here per the #1452 chain.
    "dashboard": 3,
    "serve": 4,  # §1 "HTTP routes, CLI entry points"
}

_LAYER_NAMES = {
    0: "leaves",
    1: "domain",
    2: "analysis",
    3: "application",
    4: "delivery",
}


class Finding:
    def __init__(self, module: str, detail: str):
        self.module, self.detail = module, detail

    def __str__(self) -> str:
        return f"  {self.module}.py  {self.detail}"


def internal_imports(src: str, ours: set[str]) -> set[str]:
    """The modules of ours this source imports (flat names — sys.path surgery means
    everything is a bare stem today)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found & ours


def _same_layer_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Elementary cycles in the same-layer import graph (§2's acyclic proviso). Each is
    normalised to start at its smallest node and de-duplicated; output is sorted for a
    stable finding order. One layer's same-layer graph is tiny, so a plain path-tracking
    DFS is enough."""
    found: set[tuple[str, ...]] = set()

    def dfs(node: str, path: list[str]) -> None:
        for nxt in sorted(edges.get(node, ())):
            if nxt in path:
                cyc = path[path.index(nxt) :]
                i = cyc.index(min(cyc))
                found.add(tuple(cyc[i:] + cyc[:i]))
            else:
                dfs(nxt, [*path, nxt])

    for start in sorted(edges):
        dfs(start, [start])
    return [list(c) for c in sorted(found)]


def check(host: Path = _HOST, layers: dict[str, int] | None = None) -> list[Finding]:
    layers = _LAYERS if layers is None else layers
    ours = {p.stem for p in host.glob("*.py")}
    findings: list[Finding] = []
    same_layer_edges: dict[str, set[str]] = {}
    for module, layer in sorted(layers.items(), key=lambda kv: (kv[1], kv[0])):
        p = host / f"{module}.py"
        if not p.exists():
            findings.append(Finding(module, "ASSIGNED but missing — stale assignment."))
            continue
        src = p.read_text(encoding="utf-8")
        reached = internal_imports(src, ours)

        if layer == 0:
            # A leaf that grows one import stops being safe to reach for, and the
            # import-2000-for-a-constant pathology creeps back one import at a time.
            if reached:
                findings.append(
                    Finding(module, f"LEAF imports of ours: {sorted(reached)}")
                )
            if "sys.path" in src:
                findings.append(
                    Finding(
                        module,
                        "LEAF does sys.path surgery — it must be importable by name "
                        "when the package flip lands (ADR-0038 §5.4).",
                    )
                )
            continue

        for target in sorted(reached):
            t_layer = layers.get(target)
            if t_layer is None:
                continue  # unassigned: unjudgeable, counted in the coverage line
            if t_layer > layer:
                findings.append(
                    Finding(
                        module,
                        f"UPWARD import of {target} "
                        f"(layer {layer} {_LAYER_NAMES[layer]} -> layer {t_layer} "
                        f"{_LAYER_NAMES[t_layer]}) — ADR-0038 §2: never upward.",
                    )
                )
            elif t_layer == layer:
                if layer == 4:
                    findings.append(
                        Finding(
                            module,
                            f"SIDEWAYS import of {target} within layer 4 "
                            f"({_LAYER_NAMES[layer]}) — ADR-0038 §2 forbids same-layer "
                            "imports at layer 4.",
                        )
                    )
                else:
                    # Same-layer below 4 is legitimate composition (§2 as amended
                    # 2026-07-22, #1452); recorded so the acyclic proviso is checkable.
                    same_layer_edges.setdefault(module, set()).add(target)
            # else t_layer < layer: a strictly-lower import, allowed.

    # §2's acyclic proviso: same-layer imports below 4 are legal only while the
    # same-layer graph has no cycle — "A importing B and B importing A at one layer is
    # the tangle by another name, and the guard should reject it as usage grows."
    for cycle in _same_layer_cycles(same_layer_edges):
        lyr = layers[cycle[0]]
        findings.append(
            Finding(
                cycle[0],
                f"SAME-LAYER CYCLE at layer {lyr} ({_LAYER_NAMES[lyr]}): "
                f"{' -> '.join([*cycle, cycle[0]])} — ADR-0038 §2 allows "
                "same-layer imports below 4 only while acyclic.",
            )
        )
    return findings


def coverage(
    host: Path = _HOST, layers: dict[str, int] | None = None
) -> tuple[int, int]:
    layers = _LAYERS if layers is None else layers
    total = len([p for p in host.glob("*.py") if not p.stem.startswith("test_")])
    return len(layers), total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="ADR-0038 §2: down or same-layer below 4; no up, no sideways-in-4"
    )
    ap.add_argument(
        "--check", action="store_true", help="enforce (non-zero on a violation)"
    )
    ap.add_argument("filenames", nargs="*", help="ignored (pre-commit passes files)")
    args = ap.parse_args(argv)

    findings = check()
    assigned, total = coverage()

    if findings:
        print("import-layer-guard: ADR-0038 §2 violations:", file=sys.stderr)
        for f in findings:
            print(str(f), file=sys.stderr)

    # Printed on EVERY run, pass or fail: three modules judged out of 184 must never
    # read like the whole tree was judged.
    print(
        f"import-layer-guard: {assigned} of {total} host modules have a layer assigned "
        f"({total - assigned} unassigned, therefore unchecked). "
        f"{len(findings)} violation(s)."
    )
    if findings and args.check:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
