# The color-roles charter

> **Status:** the rescoped **#930** deliverable, ruled at the 2026-07-18 night-1 grill (Q2). **This charter
> — the rules — is V1.** The specific token *values* proposed inside these rules are **V2** (Design-QA
> proposes; iterations follow). Governs every surface that uses color. Builds on
> [ADR-0004](../../adr/0004-design-system.md) (tokens) and [ADR-0008](../../adr/0008-design-system-v3-personality-layer.md)
> (the band-derived mood layer); consumes values from [`sprout-tokens.css`](../tokens/sprout-tokens.css),
> never redefines them.

## Why this exists

Color was doing many jobs with no plan: per-plant identity colors that never changed with mood, a mood
system whose color never reached the card frame, a seven-band ladder with its own hues, a watering board that
was colors-on-colors, and history charts of indistinguishable same-hue lines. The fix isn't a nicer palette —
it's **one job per channel.** Color is a system with roles, and each role gets exactly one.

## The charter — one job per channel

### 1. State owns all the saturation

The plant's **current state — its mood — is the only thing allowed to be saturated.** A card's frame *is* its
mood; it is never a fixed identity color. Mood and band hues are **the state language**, and they read the
same on every surface that shows state (card frame, chip, gauge, band ladder). Saturation means "something is
happening here" — so only state gets to say it.

### 2. Chrome is a muted neutral family

Everything that isn't state — backgrounds, surfaces, borders, structural chrome — lives in a **muted neutral
family** grouped around **sprout-soft · mist · sand · soil**. (The group, not necessarily those exact four —
values are the V2 pass.) Chrome may **never** compete with state; if a neutral reads as a mood, it's wrong.

**Ruled out by name** (they sit too close to the shipped state hues and would blur the state channel):
leaf-deep, terracotta, shoot, sage, sun, sky, petal, honey, and blossom. The three directions offered in the
original #930 are rejected *as offered* — the muted-neutral family replaces them.

### 3. Identity never travels by color

A plant's identity is **never** carried by a hue. Color-as-identity doesn't scale — 24 plants are not 24
distinguishable colors (11 already blur on today's charts) — and it steals the saturation the state channel
needs. **Identity travels by the identity block:** name (or number-as-identity), a plant photo, the location
chip, and the pot descriptor.

### 4. The action flow this buys

> **State color finds the plant that needs you. The identity block tells you which physical plant it is.**

Color *finds*; identity *confirms*. That is the whole answer to "how do I know which of my plants to water" —
the saturated frame pulls your eye to the thirsty one, and the name/photo/location/pot on that card send you
to the right pot on the shelf.

### 5. State speaks one language

Mood hues (ADR-0008) and the seven band hues (ADR-0004) **reconcile into a single state language** — one
consistent set of state colors, not two parallel systems a viewer has to hold in their head. Wherever state
appears, it's the same hue for the same meaning. (The consolidated value set is part of the V2 token pass.)

## Scope

**In this charter (V1):** the four color roles above (state · chrome · identity · charts), the muted-chrome
*family*, and the mood↔band consolidation *principle*.

**V2 (Design-QA proposes token values inside these rules):** the muted-neutral chrome values, the consolidated
state-hue set, and the swatch sheet — all consumed from / folded into `sprout-tokens.css`, never redefined.

**Rides the Classic-migration backlog (not the first tracer):** multi-series charts. Per-plant line colors are
**declared failed** (indistinguishable at scale); the redesign explores focus-on-interaction, one-plant
emphasis with muted others, and letting the band-ground carry the meaning — a dedicated design pass, later.

## References

- Ruling: [#930](https://github.com/OrangePeachPink/sprout/issues/930) (rescoped) · the #1039 night-1 grill
  (Q2, 2026-07-18) · the #875 Home-card contract (state frame + identity block).
- Foundations: [ADR-0004](../../adr/0004-design-system.md) · [ADR-0008](../../adr/0008-design-system-v3-personality-layer.md)
  · [`sprout-tokens.css`](../tokens/sprout-tokens.css) · the [design doctrine](design-doctrine.md).
