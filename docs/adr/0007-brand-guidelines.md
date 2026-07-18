# ADR-0007 — Brand guidelines & voice

**Status:** Accepted (2026-06-24)
**Date:** 2026-06-24
**Owner:** Design lane
**Lane:** design (brand, UI, design system, tokens, voice)
**Elaborates:** [ADR-0002](0002-process-tiers.md) area #18 (Design system).
**Builds on:** [ADR-0004](0004-design-system.md) (design system & the token-consumption contract).

---

## Context

Sprout's brand was explored across several directions (a charming first-person plant, a naturalist's
field journal, a beautiful engineering instrument, a retro-futurist console, a Tamagotchi pet). The
exploration produced a clear winner and a set of deliberate exclusions, plus a drafted voice, a living
animated mark, and a mood system — but these lived scattered across brand-world, personality, day-in-the-
life, and social-kit pieces. Downstream work (the README hero, social preview, issue-form copy, the UI
personality layer) needs a single, citable identity decision so every surface speaks coherently.

This ADR records that decision. It is the **brand counterpart to [ADR-0004](0004-design-system.md)**: 0004
fixed the token/instrument foundation and named the Design lane as owner of the v1↔v2 reconciliation;
this ADR fixes the identity and voice that the reconciliation layers on. The *usable* rules — with
examples — live in the reference guide at `docs/design/brand/` (`BRAND.md` + the living
`Sprout Brand Guidelines.dc.html`); this record is the decision and its rationale.

## Decision

### 1. Identity — Sprout is a living character

The brand is **a plant that finally has a voice.** Sprout is a living, animated plant character and the
**hero of every surface**; color, type, data, and the applications are the environment that holds it up,
never competing for the spotlight.

### 2. Direction — "Plant's POV" (chosen), with recorded exclusions

The plant narrates everything in its own first-person voice. Alternatives were excluded for reasons worth
keeping on record so we don't drift back:

- **Field Journal** — a serif naturalist almanac; beautiful as an artifact but sidelines the live
  character and reads as something to study, not someone to meet.
- **Beautiful Instrument** — centers the engineering, not the plant (the default we are escaping). Its
  rigor is **retained as the "rigor thread" inside the winner**, not as the whole identity.
- **Retro-Futurism** — a decorative era-skin without a reason; kitsch for its own sake.
- **Plant Tamagotchi** — a needy pet with streaks/levels contradicts an **ambient, hands-off** system
  that asks nothing of you.

### 3. Voice — first person, fact-then-feeling

Every surface speaks **as** Sprout, not **about** it: first-person "I"; **fact, then feeling** (the data
earns the warmth); **one short, glanceable line**; calm, fond, plain; **calm under fault** (reassure,
explain, pause). Hard nos: **no baby-talk, no emoji, no guilt-tripping, and no invented numbers** (never a
invented % or ETA — consistent with the data-integrity rules).

### 4. The living mark & motion

**One mark** — two leaves on a stem — serves as icon, favicon, sticker, and in-app character: *static when
it must be, alive whenever it can be.* A small motion vocabulary maps to context: **sway** (calm idle /
default), **breathe** (alive & well), **bob** (speaking / greeting), **droop** (thirsty / needs water). All
motion honors `prefers-reduced-motion`.

### 5. Mood derives 1:1 from the calibrated band (the invariant)

Sprout's mood is a **function of the seven calibrated moisture bands, never of the 0–100 relative index.**
This is what lets personality and data-integrity coexist — the character cannot contradict the instrument
because both read the same canonical source (ADR-0004). The mapping:

| Band (UI · fw) | Mood |
|---|---|
| Saturated · submerged | Soaked |
| Wet · overwatered | Refreshed |
| Moist · well watered | Thriving |
| Ideal · OK | Content |
| Drying · needs water | Thirsty |
| Dry · DRY | Parched |
| Parched · air-dry | Faint · "check me" |

Two caveats: the **air-dry** band doubles as the diagnostic "probe may not be in soil" band, so its
voice names the ambiguity instead of dramatizing death; and **"asleep"** is a **night/diurnal overlay, not a
band** — it can ride on top of any mood after dark.

### 6. The integration boundary — character layers on, never restyles

The cross-lane rule everyone building on Sprout follows: **character layers onto the instrument; it never
restyles it.**

- **Sprout appears on:** ambient, empty, loading, onboarding, notification, and single-plant-hero surfaces
  — *beside* the gauges, reinforcing them.
- **Sprout stays out of:** dense numeric readouts, the calibration ladder, and data-integrity tables, where
  legibility and clarity win and the numbers stay clean, mono, and tabular.

### 7. Where the reference lives

Usable do/don't rules with examples: `docs/design/brand/BRAND.md` (canonical written reference) +
`docs/design/brand/Sprout Brand Guidelines.dc.html` (living visual guide). All color/type values are
**consumed from `sprout-tokens.css`** per the ADR-0004 contract — the brand guide references them, it does
not redefine them.

## Consequences

- The identity and voice are a single citable decision; README, social, issue forms, and the UI
  personality layer can all build to one source.
- Personality can never break the seven-band reading rule, because mood is band-derived by definition.
- The exclusions are on record, so the brand doesn't quietly slide back into an engineering-first or
  gamified frame.
- This sets up **Phase 2** (the additive v1 personality layer) as a clean, rules-first proposal under #18 /
  ADR-0004 — not a silent restyle of the instrument.

## Revisit triggers

- The calibration work (A2 / 7-band reconciliation) renames or re-bounds a band → update the mood map's
  band column to match; the moods themselves are stable.
- A genuinely new surface needs Sprout where the boundary currently says "out" → decide deliberately and
  record it, rather than eroding the boundary case by case.
- The personality layer ships and the system grows enough to need its own packaging → that becomes design
  system **v3** (additive over v1/v2), recorded as its own ADR.
- Localization is added → re-validate the voice rules (first-person, one line, no guilt) per language.

## References

- `docs/design/brand/BRAND.md` — the canonical written reference (do/don't + examples).
- `docs/design/brand/Sprout Brand Guidelines.dc.html` — the living visual guide.
- [ADR-0004](0004-design-system.md) — design system & the token-consumption contract.
- Source explorations (v2 delivery), reorganized into the `docs/design/` shelves: Brand World (`brand/`),
  Personality Directions (`voice/`), Day in the Life (`motion/`), Social Kit (`go-to-market/`).
