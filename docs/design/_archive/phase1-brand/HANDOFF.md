> ⚠️ **SUPERSEDED — archived 2026-06-25.** Archeology only; do not build from this. Every asset here has a
> current, aligned version surfaced in the **Sprout Design Library** (BRAND.md, the Brand Guidelines page, and
> ADR-0007 all live there now). Kept solely as a record of how we reached today's decisions.

# Design-lane handoff — Phase 1: Brand guidelines & voice

**From:** Design lane · **Date:** 2026-06-24 · **Re:** ADR-0007 + the living brand guide
**Flow:** I zip → Veronica downloads + points Workflow here → Workflow extracts, places each file per the
manifest below, applies the repo edits, commits by proxy after review.

This is **Phase 1 only** (lock the rules). It does **not** touch the backlog or issues (no-fly), and it does
**not** modify the v1 source of truth — that's Phase 2, proposed after this lands.

---

## Manifest — place every file exactly here

| In this zip | → Destination in repo | What / why | Who consumes |
|---|---|---|---|
| `docs/adr/0007-brand-guidelines.md` | `docs/adr/0007-brand-guidelines.md` | **The DECISION.** Brand identity + voice direction + personality, rationale & recorded exclusions, and the instrument↔character boundary. Public-clean, same conventions as 0004. | Workflow (file + register), all lanes (reference) |
| `docs/design/brand/BRAND.md` | `docs/design/brand/BRAND.md` | **The REFERENCE (canonical written).** Usable do/don't rules with examples: voice, living mark + motion, mood↔band map, color/type, the boundary. | Design (owns), Data + Firmware (voice + boundary), GitHub surface (Phase 3) |
| `docs/design/brand/Sprout Brand Guidelines.dc.html` | `docs/design/brand/Sprout Brand Guidelines.dc.html` | **The REFERENCE (living visual).** Renders the animated mark, the four motion states, the seven-band mood system, voice do/don't, and a side-by-side of the integration boundary. | Design (owns); anyone wanting the visual guide |
| `docs/design/brand/support.js` | `docs/design/brand/support.js` | Claude Design runtime so the `.dc.html` renders in the design tool. Byte-identical to the v1/v2 copies; duplicated to keep `brand/` self-contained (same pattern as `sprout-v2/`). | runtime only |

> No binaries over ~1 MB; nothing needs Git LFS. All text/HTML/JS.

## Repo edits to apply

1. **Add the register row** in `docs/adr/0000-record-architecture-decisions.md` — in "The register" table,
   append after the most recent row:

   ```
   | [0007](0007-brand-guidelines.md) | Brand guidelines & voice | **Proposed** | Design lane / design |
   ```

2. **No `0002` row flips this round.** ADR-0007 elaborates area #18 (already confirmed in the 0004 handoff);
   optionally add a link from #18's row to ADR-0007 alongside the existing ADR-0004 link. Nothing else in
   0002 changes.

3. **Status:** 0007 lands as **Proposed**; the maintainer flips it to Accepted (same lifecycle as 0004/0002).

## For the lanes (incorporation note)

- **Data + Firmware:** nothing to adopt yet in Phase 1 — but two rules now bind any plant-facing copy or UI
  you write:
  1. **Mood follows the band, never the index.** Any character/mood state must derive 1:1 from the seven
     calibrated bands (ADR-0007 §5) — the same source of truth as the instrument (ADR-0004). Never from a
     0–100 figure.
  2. **The boundary** (ADR-0007 §6): Sprout the character belongs on ambient/empty/loading/onboarding/
     notification/single-plant-hero surfaces — **never inside dense numeric readouts, the calibration
     ladder, or data-integrity tables.** The dashboards stay clean, mono, honest.
- The **ADR-0004 token contract still holds**: the brand guide consumes color/type from `sprout-tokens.css`,
  it does not redefine them.

## What comes next (not in this zip)

- **Phase 2** — once these rules are locked, I'll *propose* the additive v1 personality layer (mood↔band
  map, animated mark component, voice strings) — layered on, never recoloring the instrument. If it changes
  the system, it ships as **design system v3** (`docs/design/sprout-v3/`, additive over v1/v2) with its own
  incorporation note. "v2 already covers it" is a valid outcome.
- **Phase 3** — GitHub-facing surface (README hero, social preview, issue-form voice, label palette,
  CONTRIBUTING/PR voice, Discussions copy, release-notes tone), co-built once Phase 1 is locked.
