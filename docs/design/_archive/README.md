# `_archive/` — archeology only

**Nothing in this folder is live.** Everything here is a **superseded** snapshot of how the Sprout brand and
design system reached its current state. It is kept for archeology — tracing *why* a decision was made — not
for building.

> **If it's live and current, you'll find it in the [Sprout Design Library](../Sprout%20Design%20Library.dc.html).**
> That is the single front door for every active design asset (ADR-0010). If something is in here instead, it
> has been replaced by a current, aligned version in the Library.

## What's here

| Folder | What it was | Superseded by (live) |
|---|---|---|
| `pre-v3-originals/` | Pre-alignment page originals, captured before the v3 soil-mode consistency pass. | The aligned pages across the shelves (`foundations/`, `brand/`, `voice/`, `motion/`, `go-to-market/`, `merch/`). |
| `v1-v2-previews/` | Original rendered preview screenshots from the v1 (`screenshots/`) and v2 (`sprout-v2/screenshots/`) deliveries. | Current per-page thumbnails in `library/thumbs/`; the depicted source lives across the shelves + `pre-v3-originals/`. |
| `phase1-brand/` | Phase 1 handoff: first brand guidelines + voice (ADR-0007, BRAND.md, the guide). | `brand/`, `docs/adr/0007-…` |
| `phase2-brand/` | Phase 2 handoff: the v3 personality layer (tokens refinement, mark component, motion, JSON maps, ADR-0008). | `tokens/`, `components/`, `voice/`, `docs/adr/0008-…` |
| `adr-handoff/` | Delivery package for ADR-0004. | `docs/adr/0004-…` |
| `batch2-voice-handoff/` | Delivery package for the voiced issue forms + PR/CONTRIBUTING (PR #47, merged). | `community/` |
| `consistency-pass-handoff/` | Delivery package for the consistency pass + the BRAND.md `--bg` fix. | `foundations/Sprout Brand Consistency Pass.dc.html`, `brand/BRAND.md` |
| `library-handoff/` | An earlier snapshot of the Design Library delivery. | `Sprout Design Library.dc.html` (current) |
| `phase3-github/` | Delivery package for the GitHub-facing surfaces (README, labels). | `community/`, repo `.github/` |
| `welcome-handoff/` | Delivery package for the animated repo-home welcome (standalone export). | `motion/Sprout Welcome.dc.html` |
| `runtime-policy-drop/` | The original runtime policy (named the old `sprout-v2/v3` version folders). | `runtime/RUNTIME.md` (updated for the shelf model) |

Each handoff keeps its original `HANDOFF.md` for delivery context; the brand snapshots are banner-marked **SUPERSEDED**.

## Why archived

These were point-in-time **delivery packages** and prior generations, not working documents. Their content has
since been brought forward, run through the brand **consistency pass**, reorganized into function shelves
(ADR-0010), and is maintained as the live files above. Replaced by a single consolidated export, the old
piecemeal handoffs were moved here on 2026-06-25 so new contributors never trip over a stale version.

*tend well.*
