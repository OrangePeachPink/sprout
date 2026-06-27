# Roads not taken — Sprout design archeology

**One distilled record, replacing the heavy snapshots that used to live beside it.** When the design system
reached v3, the not-selected routes — earlier name candidates, the v1/v2 visual generations, the pre-alignment
page originals — were carried here as full file copies. Those bytes duplicated what version control already
keeps. This file keeps the part version control does *not*: **why** each route was left behind.

> If it's live and current, it's in the [Sprout Design Library](Sprout%20Design%20Library.dc.html) — the single
> front door (ADR-0010). Everything below is archeology: kept to trace *why*, never to build from.

## How to recover an original

The original files are intact in the canonical repo's **Git history** (the 2026-06-25 archive commit and the
deliveries before it). Recover any one with `git log --all -- "<path>"` then `git show <sha>:"<path>"`. Nothing
is lost by removing the duplicates — only the why was at risk, and that is what this file preserves.

---

## 1 · The name — "Sprout" over Tendril, Tilth, and a lowercase wordmark

**What it was.** Before "Sprout" was settled, an identity exploration shortlisted alternates across three
territories — *Soil & root*, *Tend & reach*, *Measure & moisture*:

- **Tendril** (top pick at the time) — the climbing shoot that reaches out, with *"tend"* hidden inside it,
  echoing the "tend well" voice.
- **Tilth** — the crumbly health of well-worked soil; short, rare, premium.
- **Loam** — rich fertile earth; calm, four letters, easy to draw a mark around.
- **Dewpoint** — a real moisture-measurement term that still sounds like nature.
- **Sprig** — the gentle, safe rename that keeps Sprout's shape.

A parallel question asked whether the wordmark should be lowercase **sprout** (distinctive, à la *e.e. cummings*;
the Baloo display face looks great lowercase) or capitalized **Sprout**.

**Why not taken.** The product personifies the plant as a named main character. An evocative-but-obscure rename
(Tilth, Loam, Dewpoint) buys a premium feel at the cost of immediate legibility — the wrong trade for an
open-source maker tool that a newcomer should grasp on sight. Lowercase read as the common noun "a plant"
rather than a name. The live system settled on **"Sprout," capitalized** — a proper name for the character.

**The useful anti-pattern.** Don't optimize a product name for rarity over recognizability when the audience
meets it cold. And a personified name needs the capital to read as *who*, not *what*.

**Provenance.** `_archive/pre-v3-originals/Sprout Brand Identity.dc.html` (the shortlist table);
`_archive/sprout-backlog.md` §3 (the casing tension). Any formal naming ratification is an ADR decision, not
this file's — recorded here only as explored history.

## 2 · v1 — the instrument-first foundation, before the personality layer

**What it was.** The original design system: the honest-instrument dashboard UI, the seven-band moisture ladder,
the mood/personality previews (`top`, `personality`, `personality-dry`, `ladder`). v1 was — and the live
dashboard tokens still are — the source of truth for the instrument surface.

**Why superseded (not rejected).** v1 was a foundation, not a dead end. v3 layered personality *onto* it without
displacing it. It lives on through the token contract (ADR-0004) and every dense numeric readout that stayed
deliberately mark-free.

**The useful anti-pattern.** Keep the foundation that works. The instrument-first boundary — *character layers
onto the instrument; it never replaces it* — was already right in v1 and was the thing most worth defending.

**Provenance.** `_archive/v1-v2-previews/v1/` (rendered previews); the depicted sources now live across the
function shelves.

## 3 · v2 — the brand-delivery layer, before consolidation

**What it was.** The brand delivery layered over v1: the pitch deck and cover, the Day-in-the-Life loop, the
loader variants, the social set (generic / GitHub / LinkedIn), retro, and shared ladder/personality previews.

**Why superseded.** v2 shipped as a *parallel* set beside v1, which meant two token sources kept in sync by hand.
v3's consistency pass reconciled the deltas deliberately (diffed and resolved, never silently overwritten —
ADR-0004) and reorganized everything onto the function shelves (ADR-0010), so there is now one palette and one
voice instead of two generations drifting apart.

**The useful anti-pattern.** Parallel token sets are a standing tax — every change must be mirrored, and they
drift the moment someone forgets. Reconcile to one source on a schedule; don't let a second generation harden
into a fork.

**Provenance.** `_archive/v1-v2-previews/v2/` (rendered previews); the live sources are on the shelves, with the
current per-page thumbnails in `library/thumbs/`.

## 4 · The pre-v3 page originals — before the consistency pass

**What it was.** The page set captured just before the v3 soil-mode consistency pass: Brand World, Brand
Guidelines, Brand Identity, Day in the Life, the decks, the design-system pages, the loader, merch, and social
kit — fourteen pages in their pre-alignment state.

**Why superseded.** Each page predated the unified token application. Two patterns repeated across them:

- **Bespoke per-page backgrounds.** Every page hard-coded its own near-neutral (`#e9e7df`, `#edf2e4`, `#e4e8db`,
  `#eef4e6`…) instead of one `--bg` token, so no two pages quite matched.
- **Hand-rolled marks.** Each page re-declared the seedling's motion inline — `bw-sway`, `pov-sway`, `mk-sway`,
  `ditl-breathe` — a dozen near-identical keyframe blocks that drifted in timing and origin.

v3 replaced both with shared infrastructure: the `--bg` token and the single living `<sprout-mark>` custom
element (reduced-motion aware, one source of truth for the mark's behavior).

**The useful anti-pattern.** A value repeated inline on every page is a value that will drift. Backgrounds belong
to a token; a repeated animated glyph belongs to one component — not a copy in each page's `<style>`.

**Provenance.** `_archive/pre-v3-originals/` (the fourteen pages); superseded by the aligned pages across
`foundations/`, `brand/`, `voice/`, `motion/`, `go-to-market/`, and `merch/`.

---

*Supersede, never delete (ADR-0010) — honored here by distillation: the reasoning is preserved above, the bytes
in Git history. tend well.*
