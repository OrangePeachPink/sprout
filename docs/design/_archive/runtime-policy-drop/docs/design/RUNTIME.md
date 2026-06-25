# Design-system runtime policy

How the Claude Design runtime (`support.js`, and `deck-stage.js` for decks) is versioned across
`docs/design/`. Owned by the Design lane; enforced by the intake thread. This is the stable reference to
check against — don't rely on memory.

## Model — self-contained per version

The design system is **additive and append-only**: v1, v2, v3 are dated snapshots, each standalone. The
runtime follows the same rule.

- **Each folder owns its runtime.** Every page loads `./support.js` from **its own folder**. A snapshot
  therefore opens exactly as it was authored and verified — provenance is preserved.
- **Never converge or overwrite a versioned folder's runtime.** `sprout-v2/`, `sprout-v3/`, `brand/` (and any
  future `sprout-vN/`) keep the runtime they shipped with. Drift between folders is *correct*, not a bug to
  fix — it's honest history.
- **Root is the current shared runtime.** Root-level pages (the v1 system page, the Library index, the Deck
  Template) all load root `./support.js`. When a drop's root-level pages are built against a newer runtime,
  intake refreshes **the root copy only** to that runtime. Newer renders older pages backward-compatibly.

## The invariant intake enforces

1. Every page loads `./support.js` from **its own folder** (never reaches across folders for a runtime).
2. Intake touches the **root copy only** — never a versioned folder's runtime.
3. On a drop whose root-level pages load root `./support.js`, refresh the root copy to the runtime that
   export was built against.

## Current state

| Folder | runtime |
|---|---|
| `docs/design/` (root) | `a37fec98` — newer |
| `brand/` | `a37fec98` — newer |
| `sprout-v3/` | `a37fec98` — newer |
| `sprout-v2/` | `ac3b4f23` — older |

So `sprout-v2/` is the only folder on the older runtime; root, `brand/`, and `sprout-v3/` are aligned on the
newer one. (`deck-stage.js` follows the same per-folder rule.)

## The one case to converge

Converge all copies to a single runtime **only** when:

- a runtime change is **not** backward-compatible (an older snapshot would break on its own runtime), **or**
- a cross-cutting **security / critical-bug** fix must reach the older snapshots.

Then it's a **deliberate, recorded migration** (its own note/ADR) — never a silent intake overwrite. Until
such a call, decline convergence.

## Manifest practice

Handoff manifests state the **runtime lineage / version** of any `support.js` they carry — they do **not**
claim "byte-identical" (the copies legitimately differ by snapshot).
