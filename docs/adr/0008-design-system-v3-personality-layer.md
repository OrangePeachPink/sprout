# ADR-0008 — Design system v3: the personality layer

**Status:** Accepted (2026-06-24 — Design lane authored; reviewed and approved, including the v1 soil-mode token change)
**Date:** 2026-06-24
**Owner:** Design lane
**Lane:** design (brand, UI, design system, tokens, voice)
**Elaborates:** [ADR-0002](0002-process-tiers.md) area #18 (Design system).
**Implements:** [ADR-0007](0007-brand-guidelines.md) (brand guidelines & voice).
**Builds on:** [ADR-0004](0004-design-system.md) (token-consumption contract — still in force).

---

> **Accepted.** The Phase 2 personality layer and the v1 soil-mode token refinement were reviewed and
> approved on 2026-06-24. The refined dark neutrals are folded into `sprout-tokens.css`'s dark block.

## Context

[ADR-0007](0007-brand-guidelines.md) locked Sprout's identity, voice, and the character↔instrument boundary.
The open question it left was *how* to bring that living character onto the product without compromising the
v1 instrument — the v1↔v2 reconciliation the Design lane owns under #18 / [ADR-0004](0004-design-system.md).
This ADR records the chosen execution: an **additive layer**, not a restyle.

## Decision

Add the brand personality to the system as **design system v3** under `docs/design/` — **additive
over v1/v2**, with v1 unchanged as the canonical source for the instrument UI. v3 consists of:

1. **A canonical band→mood map** (`mood-band-map.json`) — the 1:1 bridge from the seven calibrated bands to
   Sprout's moods, motion, and mark colors. The single source for "which mood is this reading in."
2. **The mark as a drop-in component** (`sprout-mark.js`) — a framework-agnostic custom element
   (`<sprout-mark band="…">`), reduced-motion aware, fitting the ADR-0004 vanilla host.
3. **A voice-string pool** (`voice-strings.json`) — first-person lines keyed by mood and by surface.
4. **A motion stylesheet** (`sprout-motion.css`) — the sway/breathe/droop/bob vocabulary for hand-rolled
   marks.
5. **A refined soil (dark) mode** — the dark-mode **neutrals** are shifted from v1's warm-olive surfaces to a
   cooler, deeper green-charcoal that reads refined rather than dank. This is the **one place v3 changes a v1
   value**; reviewed and approved, the refined values are **folded into `sprout-tokens.css`'s
   `[data-theme="dark"]` block** (one tokens file). Light mode and every `--st-*` / `--band-*` meaning color
   are untouched.

Two invariants are binding (from ADR-0007): **mood derives 1:1 from the calibrated band, never the index;**
and **the character layers onto the instrument, never restyling it** (no character inside dense readouts, the
calibration ladder, or data-integrity tables).

The **ADR-0004 token contract holds**: v3 consumes color/type from `sprout-tokens.css` and does not redefine
tokens — with one deliberate, recorded exception, the soil-mode neutral refinement above, which is the
v1↔v2 reconciliation this lane owns (executed deliberately, never silently).

## Consequences

- v1 instrument components are untouched; the dashboards stay exactly as legible and honest as today.
- The product can grow Sprout-flavored hero / empty / loading / onboarding / notification surfaces from one
  shared, band-derived source — no per-surface reinvention, no drift from the data.
- Each lane adopts at its own pace; firmware needs no code change (the map keys off the existing enum).
- The v1↔v2 reconciliation is executed deliberately and on the record, never as a silent overwrite.

## Revisit triggers

- A2 calibration re-bounds or renames a band → update only the band column of `mood-band-map.json`; moods are
  stable.
- A surface needs Sprout where the boundary says "out" → decide and record it, don't erode the boundary.
- The component set grows enough to want real packaging/versioning/distribution → spin that into its own ADR.

## The register row (add)

```text
| [0008](0008-design-system-v3-personality-layer.md) | Design system v3: the personality layer | **Accepted** | Design lane / design |
```
