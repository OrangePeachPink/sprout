# Design-system runtime policy

How the Claude Design runtime (`support.js`, and `deck-stage.js` for decks) is carried across
`docs/design/`. Owned by the Design lane; enforced by the intake/proxy. This is the stable reference —
don't rely on memory.

## Model — one current runtime, carried per folder

As of the **v3 front-door reorg (ADR-0010)**, the design system is organized by **function** (shelves:
`foundations/`, `brand/`, `voice/`, `motion/`, `go-to-market/`, `merch/`, `components/`, `tokens/`), not by
dated version snapshots. The runtime follows suit:

- **`runtime/support.js` is the canonical source.** `runtime/` also holds `deck-stage.js` and this policy.
- **Each folder that contains a page carries a sibling `support.js`.** Every `.dc.html` loads `./support.js`
  from **its own folder**, so a page opens correctly wherever it sits and stays portable. `go-to-market/`
  (and any folder with decks) also carries a sibling `deck-stage.js`.
- **All copies track one current runtime.** Because shelves are functional groupings — not standalone version
  snapshots — the sibling copies are meant to be **identical**. On a runtime bump, the proxy refreshes **every
  copy together** from `runtime/support.js`. (This is the deliberate change from the old per-snapshot model;
  see below.)

## The invariant intake/proxy enforces

1. Every page loads `./support.js` from **its own folder** (never reaches across folders for a runtime).
2. On a runtime bump, refresh **all** sibling copies from `runtime/support.js` in one pass — keep them in sync.
3. A non-backward-compatible runtime change is a **deliberate, recorded migration** (its own note/ADR), never
   a silent overwrite.

## Why this changed (history)

The earlier policy versioned the runtime **per snapshot** — `sprout-v2/`, `sprout-v3/`, `brand/` each kept the
runtime they shipped with, and drift between them was treated as honest provenance. The front-door reorg
(ADR-0010) dissolved the version folders into function shelves for ease of entry, so that snapshot-provenance
rationale no longer applies to the active tree. **The original version snapshots — with their original
runtimes intact — live in the canonical repo's Git history** (the pre-prune `_archive/` commits); the
not-taken reasoning is distilled in `_archive/roads-not-taken.md`. The active tree runs one current runtime.

## Manifest practice

The export manifest states the runtime version the export was built against. Within the active tree the
sibling copies are identical; archived snapshots retain whatever runtime they shipped with.
