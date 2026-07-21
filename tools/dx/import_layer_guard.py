#!/usr/bin/env python3
"""#1336 / ADR-0038 §2 — a module may import only from a strictly lower layer.

The rung the extractions wait behind. ADR-0038's measured condition: 149 of 184 host
modules manipulate ``sys.path``, nothing is importable by name, and several Lab modules
import the ~2,000-line ``dashboard`` to obtain two CSS constants. **Any module can
import any other and nothing makes a bad reach awkward** — the mechanism behind the
#1315 two-truths incident, not a tidiness complaint.

    A module may import only from a strictly lower layer.
    Never upward, never sideways.

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
    "parse_v1": 1,  # §1 "telemetry parsing (parse_v1)"
    "card_context": 3,  # §5.3 extraction (#1336) — "dashboard context assembly" (§1)
    # `dashboard` is layer 4 by §1 and is deliberately NOT assigned yet. Assigning it
    # makes this enforcing lint fail the whole tree on a REAL pre-existing violation:
    # serve.py (4) imports dashboard (4) for render/filter_*/gather_inputs — sideways,
    # which §2 forbids by name. That import is what the §5.3 `serve.py` route-table
    # extraction exists to remove, and it is not this extraction. Assigned there, with
    # the violation reported on #1336 rather than silently deferred — an unassigned
    # module is reported as unassigned, never treated as compliant.
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


def check(host: Path = _HOST, layers: dict[str, int] | None = None) -> list[Finding]:
    layers = _LAYERS if layers is None else layers
    ours = {p.stem for p in host.glob("*.py")}
    findings: list[Finding] = []
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
            if t_layer >= layer:
                direction = "SIDEWAYS" if t_layer == layer else "UPWARD"
                findings.append(
                    Finding(
                        module,
                        f"{direction} import of {target} "
                        f"(layer {layer} {_LAYER_NAMES[layer]} -> layer {t_layer} "
                        f"{_LAYER_NAMES[t_layer]}) — ADR-0038 §2 allows strictly lower "
                        "only.",
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
        description="ADR-0038 §2: imports go strictly downward"
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
