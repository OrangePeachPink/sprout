# v3 personality layer — incorporation note (Data + Firmware)

**Status: Accepted** (2026-06-24). What to adopt and how to consume it. The
[ADR-0004](../../adr/0004-design-system.md) token contract holds throughout: color/type come from
`sprout-tokens.css`, and the refined dark-mode neutrals now live in that same file.

## The two rules that bind everyone

1. **Mood follows the band, never the 0–100 index.** Use [`mood-band-map.json`](mood-band-map.json) to turn a
   calibrated band into a mood. Never derive a mood/face/voice from a relative percentage.
2. **Character layers on; it never restyles the instrument.** Sprout (mark + voice) goes on
   ambient / empty / loading / onboarding / notification / single-plant-hero surfaces. It stays **out** of
   dense numeric readouts, the calibration ladder, and data-integrity tables.

## Data lane — how to consume

- **Band → mood:** read `mood-band-map.json`. Look up the reading's UI band (or firmware level) to get its
  `mood`, `motion`, and `markColors`. This is the single source; don't hard-code a second mapping.
- **The mark:** load `sprout-mark.js` and place `<sprout-mark band="moist"></sprout-mark>` (or
  `mood="thriving"`). Attributes: `band` | `mood` | `size` (px height, default 72) | `static` (no motion).
  It's a framework-agnostic custom element — drops straight into the served dashboard (vanilla host, per
  ADR-0004). Put it on the single-plant hero, empty, and loading states — **not** in the channel grid's
  numbers.
- **Voice:** pull copy from `voice-strings.json` — `byMood[mood]` for status lines, `bySurface[...]` for
  fault/empty/onboarding/etc. Pick one line; never concatenate, never inject a number the data doesn't have.
- **Hand-rolled marks:** if a surface needs a bespoke inline mark (e.g. a one-off hero), use
  `sprout-motion.css` for the sway/breathe/droop/bob classes instead of the component.
- **Soil (dark) mode:** nothing extra to load — the refined cool green-charcoal neutrals are folded into
  `sprout-tokens.css`'s `[data-theme="dark"]` block. Just toggle `data-theme="dark"` as before; it now reads
  refined rather than dank. Light mode and all status/band colors are unchanged.

## Firmware lane — how to consume

- **No code change required.** The mood map keys off the existing seven-level `moisture_classifier` enum, so
  the layer rides on what firmware already emits.
- **On A2 (band-boundary reconciliation):** when the raw boundaries are calibrated, only the band column in
  `mood-band-map.json` is affected — the moods themselves are stable. Coordinate that edit with the Design
  lane (it owns the map), don't fork it.
- **The air-dry caveat (updated by the #1039 band ruling):** `air-dry` is a *diagnostic*, not a band — it
  lives OFF the seven-word ladder, renders in the exceptions lane in neutral with a plain reason, and never
  wears a mood word. The map's `faint` linkage is lookup plumbing only; keep that framing anywhere you
  surface it.

## What this does NOT change

- v1 instrument components — untouched.
- The token contract (ADR-0004) — color/type still consumed from `sprout-tokens.css`.
- The seven-band reading rules — reinforced, never bypassed.
- **Light mode and all `--st-*` / `--band-*` meaning colors** — the soil-mode refinement touches dark
  **neutrals** only; no meaning color moves in either theme.
