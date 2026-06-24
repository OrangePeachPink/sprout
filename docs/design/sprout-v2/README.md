# Sprout design system — v2 delivery (brand + system expansion)

Design-team delivery received **2026-06-23**, stored here **alongside** (not replacing) the
[v1 system](../README.md) in the parent folder. This is the broader brand world — brand identity, decks,
social kit, narrative pieces, and an expanded design-system source — that builds on v1's dashboard/UI
foundation.

## Provenance

- **Source:** `Plant monitoring application design system (1).zip` (design team, via Claude Design export).
- **Stored as delivered** — the full set is kept intact and self-contained; nothing was pruned, so the
  `.dc.html` sources keep their internal references (runtime + screenshots) working.
- **Relationship to v1:** purely additive. v1 remains the source of truth for the dashboard/instrument UI
  (tokens, the seven-band honesty rules, the five instrument components). This v2 set extends it with brand
  and presentation material. Where a future conflict arises on a shared token, the newer source should be
  reconciled with v1 deliberately — not silently overwritten.
- **Overlap with v1 (verified SHA-256, all byte-identical):** `support.js`, and
  `screenshots/{ladder,personality,personality-dry,top}.png`. They are duplicated here only to keep this
  delivery self-contained; v1's copies are unchanged.

## What's here

| Group | Files |
| --- | --- |
| Expanded design system | `Sprout Design System.dc.html`, `Sprout Design System-print.dc.html`, `Sprout Design System.html` (620 KB standalone — opens directly, no runtime) |
| Brand | `Sprout - Brand World.dc.html`, `Sprout Brand Identity.dc.html`, `Plant Design System.dc.html` |
| Decks & stage | `Sprout Deck.dc.html`, `Sprout Deck-print-vo4pvb.dc.html`, `Sprout - On Stage.dc.html` |
| Narrative / personality | `Sprout Day in the Life.dc.html`, `Sprout - Plant POV.dc.html`, `Sprout Personality Directions.dc.html`, `Sprout Loader.dc.html` |
| Social | `Sprout Social Kit.dc.html` |
| Runtimes | `support.js` (Claude Design runtime, identical to v1), `deck-stage.js` (deck/presentation runtime) |
| Design backlog | `Sprout - Backlog.md` (the design team's own list) |
| Assets | `screenshots/` (14 previews), `uploads/`, `.thumbnail` |

## How to view

- Fastest: open **`Sprout Design System.html`** in a browser — it's a self-contained 620 KB standalone
  render, no runtime needed.
- Interactive sources: open any `*.dc.html` with `support.js` (system pages) or `deck-stage.js` (decks) in
  the design tool, same as v1.

## Status

Stored verbatim for the design team. Not yet folded into v1's engineering guidance — when we build against
the brand pieces, reconcile any token deltas against v1 first (see the [v1 principles](../README.md)).
