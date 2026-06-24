# ADR-0004 — Design system & the token-consumption contract

**Status:** Accepted (2026-06-24)
**Date:** 2026-06-24
**Owner:** Design lane
**Lane:** design (brand, UI, design system, tokens, voice)
**Elaborates:** [ADR-0002](0002-process-tiers.md) area #18 (Design system) and the **Design half** of
area #17 (Frontend stack).

---

## Context

Sprout's design system is not a proposal — it is **already built and in use**. v1 (the dashboard/instrument
foundation: tokens, the seven-band moisture-honesty rules, and five instrument components) ships as
`docs/design/`, with the core tokens lifted into a ready-to-use `docs/design/sprout-tokens.css`. A broader v2
brand delivery (brand world, decks, social kit, narrative pieces, an expanded system source) was added
**additively** under `docs/design/sprout-v2/` and does not replace v1.

ADR-0002 area #18 proposed exactly this shape (design tokens as CSS custom properties + a small component set)
and area #17 left the frontend stack as "a conscious choice to be recorded," shared between the Design and
Data lanes. The served app today mixes a vanilla, self-contained analytics dashboard (Chart.js) with a
*planned* React+TypeScript+Tailwind control page. That seam needs an explicit owner boundary so the two lanes
don't author conflicting decisions. This ADR records the design system as built and pins the **Design→Data
interface** — the one place color/type/space/radius/elevation are defined.

## Decision

### 1. The design system is ratified as built

- **v1 is the source of truth for the dashboard / instrument UI** — tokens, the seven-band honesty rules, and
  the five instrument components (dense data grid, analysis chart, calibration range ladder,
  distribution + integrity, engineering tokens). Authoritative source: `docs/design/sprout-design-system.dc.html`.
- **Tokens are CSS custom properties** in `docs/design/sprout-tokens.css`: brand + neutrals, the seven
  `--band-*` moisture bands, the `--st-*` status colors, quality flags, the three type roles
  (`--font-display` Baloo 2 / `--font-ui` Hanken Grotesk / `--font-data` JetBrains Mono), a 4px space scale,
  radius, and elevation. A `data-theme="dark"` toggle provides "soil" mode.
- **v2 (brand) is additive.** It extends v1 with brand and presentation material; it does **not** supersede
  v1's engineering guidance.

### 2. The non-negotiable data-honesty principles (carry into every build)

These come from the v1 source and the data-lane integrity review; they are part of the system, not styling
preferences:

- **Raw counts + calibrated band are the truth; a percentage is not.** Any 0–100 figure is a clearly-labelled
  *relative index* between wet/dry calibration anchors — never presented as VWC.
- **Mood / state / status color / automation derive from the calibrated band, never from the index.** A
  reading is one of seven bands; the band drives everything downstream.
- **Every number is mono, right-aligned, tabular** (`--font-data`). Data looks like data.
- **State is color.** The `--st-*` and `--band-*` tokens name meaning; never recolor a band.

### 3. The token-consumption contract (the Design → Data interface)

This is the heart of this ADR and the resolution of the #17 seam.

- **`docs/design/sprout-tokens.css` is the single source of truth** for color, type, space, radius, and
  elevation. There is exactly one definition of these values; no lane maintains a parallel set.
- **Design owns** the token + component *system* and *how tokens are consumed* (this contract). **Data owns**
  the served-app runtime / stack and consumes the tokens; it does not redefine them.
- **Consumption rule:** consumers reference the custom properties (`var(--leaf)`, `var(--band-ideal)`,
  `var(--space-md)`, …) and toggle themes via `data-theme="dark"` on the root. They do **not** hard-code the
  hex/px literals or fork the palette.
- **The decided host stack for now is vanilla + these tokens** (matching the existing self-contained
  analytics dashboard).
- **The control-page framework decision is deferred** to its own later decision (Data lane). **If/when** it
  adopts Tailwind, the Design lane will pin the **token-consumption bridge** at that point: the Tailwind theme
  maps *to* the CSS custom properties (Tailwind reads the vars), so `sprout-tokens.css` stays the one source of
  truth rather than spawning a second palette in `tailwind.config`. Recorded here as a revisit trigger, not
  decided now.

### 4. v1 ↔ v2 reconciliation policy (under #18, Design-owned)

- v1 remains source-of-truth for the dashboard/instrument UI.
- When we build against v2 brand pieces, **token deltas are reconciled against v1 deliberately** — diffed and
  resolved by the Design lane — **never silently overwritten**.
- Overlapping assets already verified byte-identical (`support.js`, the shared screenshots) stay duplicated
  only to keep the v2 delivery self-contained; that is not a fork.

### 5. Confirmation of ADR-0002 rows (Design lane)

- **#18 Design system** — **confirmed as proposed**, no override. "Design tokens (color/type/space/radius) as
  CSS custom properties + a small component set" describes exactly what is built.
- **#17 Frontend stack (Design half)** — **confirmed.** Design owns the token + component system and the
  consumption contract above; Data owns the served-app runtime/stack; the control-page framework is deferred.
  Host stack for now: vanilla + Sprout tokens.

## Consequences

- The already-built design system gains a ratified, citable decision record instead of living implicitly in
  `docs/design/`.
- Color/type/space/radius/elevation have exactly one source of truth, with a stated rule for how every
  consumer (vanilla today, a framework later) reads it — removing the risk of a drifting second palette.
- The #17 seam between Design and Data is unambiguous: one lane defines the tokens, the other consumes them.
- The seven-band honesty rules are recorded as binding system principles, not soft guidance, so future UI
  cannot quietly reintroduce a fake-VWC percentage.
- v2 brand work can proceed without endangering v1's instrument UI, because the reconciliation rule is
  explicit and Design-owned.

## Revisit triggers

- **The control page adopts a framework (e.g. React + Tailwind)** → Design pins the token-consumption bridge
  (Tailwind theme ↔ CSS custom properties) as an addendum or successor ADR; one source of truth must hold.
- **Real per-pin calibration lands** → the placeholder raw band boundaries in the source are replaced with
  calibrated values (coordinated with the A2 / 7-band reconciliation in the firmware/data lanes); the band
  *names* and tokens do not change.
- **A v2 brand token genuinely needs to change a v1 instrument token** → reconcile deliberately and record the
  delta, rather than overwriting v1.
- **The component set outgrows "small"** (a real component library with versioning/distribution is wanted) →
  spin design-system distribution into its own ADR.

## References

- `docs/design/README.md` — v1 system overview and the non-negotiable principles.
- `docs/design/sprout-tokens.css` — the tokens (the consumption surface).
- `docs/design/sprout-design-system.dc.html` — the authoritative v1 source (every token + component).
- `docs/design/sprout-v2/README.md` — the additive v2 brand delivery and its v1 relationship.
