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

![Home card at n=1: the shipped card whose identity-colour frame contradicts the plant's state, the proposed
card whose frame is the state, and the proposed first-run card.](exhibit-home-n1.png)

Left, today (the shipped card): the frame is an assigned **identity** colour — here teal, which means *wet* —
on a plant that's **parched**. State is demoted to a small pill under a dense stats block. Middle, proposed:
the frame **is** the state, the plant speaks, and the stats move to the Workbench. Right, first-run: a
brand-new plant with nothing filled in yet — still a complete, warm card (ADR-0028).

### n = 4 · a small windowsill

![Home cards at n=4 from the real windowsill: today's frames are assigned identity colours unrelated to state;
proposed frames are the state.](exhibit-home-n4.png)

Your real windowsill (the classic board). Today, three of the four frames carry an identity colour unrelated
to state — Anthurium's teal frame on a parched plant is the clearest. Proposed, the frame is the state: the
content Pothos is the calm green one; the parched pair runs warm.

### n = 24 · a full windowsill

![Home cards at n=24: today's tiles wear 24 arbitrary identity colours; proposed tiles use colour only for
state, so the plants needing water pop.](exhibit-home-n24.png)

Illustrative scale. Today, 24 cards wear 24 assigned identity colours — pretty noise you read past. Proposed,
colour can only mean state, so the plants that need water announce themselves. This is rule 3 (identity never
travels by colour) buying rule 1 (state owns the saturation): because colour means *only* state, it stays
legible across two dozen plants at once.

## Identity & differentiation — telling 24 cards apart

The identity block (rule 3) has to make every card distinct at a glance without borrowing the state channel's
colour. It does that through **form**, in a strict priority:

1. **A real photo of your plant** — the best differentiator, and the warmest, most personal thing on the card.
   It differentiates by *content*, so it carries no colour tension. (Local-only registry field; EXIF-stripped
   on export.)
2. **A chosen plant icon** — for when there's no photo yet. A set of ~20 silhouettes covering the most common
   houseplants (see the asset task), so a shelf of cards doesn't all show the same glyph.
3. **A generic fallback** — the neutral seedling, only when nothing is set.

Two more identity dimensions, both **form-first, colour-muted** (charter rule 3, the two-register guardrail):

- **Pot shape** — a small set (~6): tapered classic, straight-wall tall, kettle/round, low bowl, footed,
  cylinder. Shape helps you find the *physical* pot on the shelf (rule 4), and it's colour-free.
- **Pot / foliage colour** — optional, drawn only from the **muted materials** register (terracotta, stone,
  ceramic, sage-glaze, clay, charcoal). Capped in saturation, confined to the thumbnail; it never touches the
  frame. A dusty-blue ceramic pot and a grey-stone kettle read as different plants without competing with the
  state frame.

### The thumbnail slot

**One slot, best-available content** — a photo *replaces* the icon; they never both show. Sizing follows the
card's scale (full portrait at n=1 -> a small silhouette in the grid); even tiny, the silhouette still
differentiates. The **state frame always wins the visual hierarchy** — the thumbnail is secondary.

**No dedicated zoom control.** The responsive grid (fewer columns -> bigger cards -> more thumbnail detail)
plus the existing `details ->` / Workbench reveal already *is* the progressive-disclosure ladder (ADR-0033).

**Caution — photos at scale.** A wall of two dozen photos can start to compete with the state frames. Keep the
photo in a bounded, slightly-recessed thumbnail, let the frame stay the loudest element, and consider a touch
of desaturation on thumbnails at the highest densities. Worth an exhibit before it ships.

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
