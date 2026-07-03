# Sprout design system

The front door to every active design asset is the **Sprout Design Library** — a clickable index of the
whole system. Start there:

**→ [Sprout Design Library](Sprout%20Design%20Library.dc.html)**

## Shelves

- **`tokens/`** — the token contract (`sprout-tokens.css`), consumed, not redefined.
- **`components/`** — the living mark, motion, and shared component code.
- **`foundations/`** — the design system + the Brand Consistency Pass (the standard + its changelog).
- **`brand/`** — the brand guide, the mark, banners, and the social-preview image.
- **`voice/`** — voice & personality.
- **`onboarding/`** — first-meeting surfaces: the front doors, the sensor guide, untethered states.
- **`motion/`** — the welcome loop, day-in-the-life, loader, mark demo.
- **`go-to-market/`** — decks and the social kit.
- **`merch/`** — the print-ready merch catalog + production spec.
- **`runtime/`** — the shared `support.js` runtime + [`RUNTIME.md`](runtime/RUNTIME.md).
- **`_archive/`** — superseded generations, banner-marked, kept as history (not for building).

## How it works

Per [ADR-0010](../adr/0010-design-library-front-door.md): **if an asset is live, it's surfaced in the
Library; if it isn't, it's archived.** The honesty rules (raw counts + the calibrated band are truth; a
percentage is a labelled index, never VWC) and the character↔instrument boundary are decisions of record —
see [ADR-0004](../adr/0004-design-system.md) (design system), [ADR-0007](../adr/0007-brand-guidelines.md)
(brand & voice), and [ADR-0008](../adr/0008-design-system-v3-personality-layer.md) (personality layer).
