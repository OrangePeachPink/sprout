# The Home card

> **Status:** design brief for the [#875](https://github.com/OrangePeachPink/sprout/issues/875) epic —
> *the Sprout Voice UI*. **Grill-prep: this proposes, it does not ship.** The card is built to the #875
> contract and applies the color-roles charter ([#930](https://github.com/OrangePeachPink/sprout/issues/930)
> / [PR #1109](https://github.com/OrangePeachPink/sprout/pull/1109)). Open questions for the grill are at the
> bottom — nothing here is settled until they're ruled.

## What the Home card is

The Home card is the plant, speaking. It's the primary object on the Home surface (the app opens here;
the numeric readout moves to the Workbench, per [ADR-0033](../../adr/0033-two-surface-architecture-home-and-workbench.md)).
One card = one plant. A card must answer, at a glance and in Sprout's voice: *how am I doing, which physical
plant am I, and do you need to do anything about me?*

It must stay complete when things are missing — a plant with no photo, no name, and no watering history yet
still gets a warm, whole card (absence is first-class, per
[ADR-0028](../../adr/0028-optional-peripherals-doctrine.md)).

## Anatomy — and the one color channel each part uses

Every part of the card resolves to exactly one color channel from the charter, so nothing competes:

| Part | What it carries | Color channel |
| --- | --- | --- |
| **Mood frame** | the plant's current state — the frame *is* the mood | state ramp |
| **Identity block** | photo · name (or number) · pot descriptor · location chip | **no hue** (chrome-neutral) |
| **State** | mood word + first-person line (the plant speaks) | state ramp (dot + soft wash) |
| **Water story** | *last watered* (a detected event) · *next check* (a forecast) | detected = state accent · forecast = violet |
| **Workbench bridge** | "see the raw numbers →" — raw never lives on the card | chrome-neutral |

The identity block never carries a hue on purpose: color-as-identity doesn't scale (24 plants are not 24
distinguishable colors), and it would steal the saturation the state channel needs. **State color finds the
plant that needs you; the identity block confirms which physical plant it is.**

## Exhibits — today vs. proposed

### n = 1 · one plant, first-run

![Home card at n=1: today's data readout, the proposed voiced card, and the proposed first-run card that is
complete even with nothing filled in.](exhibit-home-n1.png)

Left, today: a competent data readout — a big raw number, a band ladder, a labelled index. Middle, proposed:
the same plant, mood-framed and identity-rich, speaking for itself. Right, first-run: a brand-new plant with
no photo, pot, location, or watering history yet — still a complete, warm card, not a wall of empty fields.

### n = 4 · a small windowsill

![Home cards at n=4: the today grid is four numbers to read; the proposed grid has one amber frame that pulls
the eye straight to the thirsty plant.](exhibit-home-n4.png)

Same four plants, same data. In the proposed grid, the single amber frame pulls your eye straight to the one
plant that's drying. In the today grid, you read every number to find it.

### n = 24 · a full windowsill

![Home cards at n=24: the today grid is a wall of 24 numbers; the proposed grid lets the four warm frames
announce the plants that need water.](exhibit-home-n24.png)

At scale the charter pays off. The plants that need water announce themselves — the warm frames are the whole
interface — while the today grid stays a wall of numbers you have to scan. This is rule 3 (identity never
travels by color) buying rule 1 (state owns the saturation): because color means *only* state, state is
legible across two dozen plants at once.

## What the card consumes (it invents nothing)

- **Band → mood:** [`mood-band-map.json`](mood-band-map.json) is the single source. The card never derives a
  mood from a relative percentage — mood follows the calibrated band ([ADR-0008](../../adr/0008-design-system-v3-personality-layer.md)).
- **The voice:** first-person lines come from [`voice-strings.json`](voice-strings.json), keyed by mood.
- **The tokens:** every color is a token from `sprout-tokens.css` ([ADR-0004](../../adr/0004-design-system.md)),
  organised by the charter's roles. The card adds no new hex.
- **Identity fallback:** when a plant has no name, the number is the identity ("New plant #8") —
  device_id is never the name ([ADR-0027](../../adr/0027-identity-model.md)). Photo is a new, local-only
  registry field; it is EXIF-stripped on any export.

## Open questions for the grill

These are the calls I want ruled before this becomes a build spec:

1. **Headline word.** The card headlines the *mood* word ("Content") with the band as a small tag
   ("band · Ideal"). Right call for a plant-voiced surface — or should the calibrated band word lead, with
   mood as the accent?
2. **First-run state.** I show a brand-new plant with a live reading as a real mood ("Thriving — settling
   in") and only the *water story* empty. Alternative: hold state at calm-empty until N readings establish
   confidence. Which is more honest to a first-run plant?
3. **Empty water story vs. no water story.** Until the detector + forecast land (0.8.0), do we show the slots
   as calm-empty ("— not seen yet"), as drawn here — or hide the water story entirely until it's real?
4. **The Workbench bridge.** Is a text link ("see the raw numbers →") the right bridge, or should raw be a
   tap-to-flip on the card itself? (Either way raw stays off the card face.)
5. **The zoom threshold.** At what plant-count does the grid step down full tile → compact tile → "consider
   zoom"? The n=24 exhibit uses compact tiles; the breakpoint isn't chosen yet.
6. **Photo shape + calm-empty glyph.** Square thumb vs. the plant's natural portrait; and is the faint
   "no photo yet" leaf the right calm-empty mark, or should it be the Sprout mark?

## Scope

**In this brief:** the Home card anatomy, its mapping to the charter's channels, the three scale exhibits,
and the six open questions above.

**Not decided here:** final token values (that's the charter's V2 pass), the Workbench card, the transition
animation between surfaces, and multi-select / bulk-water interactions. Those follow once the questions above
are ruled.
