# Sprout design system · v3 — the personality layer (ACCEPTED)

> **Status: Accepted** (2026-06-24). The Phase 2 personality layer and the v1 soil-mode token refinement are
> approved. Ratified as [ADR-0008](../../adr/0008-design-system-v3-personality-layer.md). These files are
> live; the refined dark-mode neutrals are folded into [`../tokens/sprout-tokens.css`](../tokens/sprout-tokens.css).

Additive over [v1](../README.md) and [v2](../../adr/0010-design-library-front-door.md): it **adds a layer**, with one approved
refinement to v1's dark-mode neutrals. The decision it executes is
[ADR-0007](../../adr/0007-brand-guidelines.md) (brand & voice); the token foundation is
[ADR-0004](../../adr/0004-design-system.md), whose **token-consumption contract holds** — color/type are
consumed from `sprout-tokens.css`, never redefined elsewhere.

## The two invariants (why this is safe)

1. **Mood follows the band, never the index.** Every character state derives 1:1 from the seven calibrated
   moisture bands — the same canonical source as the instrument — so the character can never contradict the
   data (ADR-0007 §5).
2. **Character layers on; it never restyles the instrument.** Sprout appears beside the data on
   ambient / empty / loading / onboarding / notification / single-plant-hero surfaces — never inside dense
   numeric readouts, the calibration ladder, or data-integrity tables (ADR-0007 §6).

## What's here

| File | What it is | Consumed by |
| --- | --- | --- |
| [`mood-band-map.json`](mood-band-map.json) | **Canonical** 1:1 band→mood map (mood, motion, mark colors, the air-dry diagnostic caveat, the asleep overlay). | Data (band→mood); `sprout-mark.js` mirrors it |
| [`sprout-mark.js`](sprout-mark.js) | The living mark as a drop-in custom element: `<sprout-mark band="moist">`. Framework-agnostic, reduced-motion aware, fits the ADR-0004 vanilla host. | Data (hero/empty/ambient surfaces) |
| [`voice-strings.json`](voice-strings.json) | First-person line pool keyed by mood and by surface (fault, empty, onboarding, README, social). | Data, GitHub surface (Phase 3) |
| [`sprout-motion.css`](sprout-motion.css) | Sway / breathe / droop / bob keyframes for **hand-rolled** marks (surfaces not using the component). | anyone animating a bespoke mark |
| [`sprout-mark-demo.html`](sprout-mark-demo.html) | Standalone page running the real component in all seven band states. | reviewers, devs |
| [`Sprout v3 Personality Layer.dc.html`](https://orangepeachpink.github.io/sprout/design/components/Sprout%20v3%20Personality%20Layer.dc.html) | The living visual record: additive before/after, the deltas, the seven states, the refined soil mode. Open with `support.js`. | reviewers |

> **The soil-mode refinement is not a separate file** — the approved cool green-charcoal dark neutrals are
> folded into [`../tokens/sprout-tokens.css`](../tokens/sprout-tokens.css)'s `[data-theme="dark"]` block (one tokens file).

## The deltas (v1 → with v3 layered on)

- **v1 instrument components:** unchanged. No recolor, no relayout. v1 stays the canonical source for the
  dashboard/instrument UI.
- **New (additive):** a band→mood bridge, a reusable animated mark, a voice-string pool, and a motion
  stylesheet — consumed *on top of* v1, only on surfaces the boundary allows.
- **One approved v1 change:** the dark / "soil" mode **neutrals** are refined (warm-olive → cool
  green-charcoal) in `sprout-tokens.css`'s dark block. Brand greens and every `--st-*` / `--band-*` meaning
  color are untouched; light mode is untouched. This is the deliberate v1↔v2 reconciliation (ADR-0004),
  reviewed and approved.
- **Net effect:** the dashboards can grow a Sprout-flavored single-plant hero, empty/loading/onboarding
  states, and notification copy — and soil mode reads refined instead of dank — while every dense readout
  stays exactly as honest and legible as today.

## Rationale

Phase 1 ([ADR-0007](../../adr/0007-brand-guidelines.md)) locked the identity, voice, and the
character↔instrument boundary. The cleanest reconciliation of "playful living character" with "honest
instrument" is not to restyle v1 but to add a thin, band-derived layer beside it — plus a measured refinement
of the dark neutrals that were reading muddy. Packaging it as v3 keeps v1/v2 coherent and lets each lane adopt
at its own pace.
