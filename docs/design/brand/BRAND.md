# Sprout — Brand guide

The usable rules for Sprout's brand: identity, voice, the living mark, the mood system, color & type, and
the one boundary that keeps character and instrument from fighting. This is the **canonical written
reference**; its living visual companion is [`Sprout Brand Guidelines.dc.html`](https://orangepeachpink.github.io/sprout/design/brand/Sprout%20Brand%20Guidelines.dc.html)
(open with `support.js` in the design tool to see the mark animate). The decision behind it is
[ADR-0007](../../adr/0007-brand-guidelines.md); the token foundation it builds on is
[ADR-0004](../../adr/0004-design-system.md).

> **The one-liner.** The brand is a plant that finally has a voice. Sprout is a living, animated character
> — the hero of every surface. Everything else is the soil it grows from.

## 0. The words we lead with — the four-slot canon (#1039, ruled 2026-07-18)

One line per job; no surface picks its own hook again:

| Slot | The line | Where it lives |
|---|---|---|
| **The tagline** | **"Plants with a pulse."** | under the wordmark, social cards, the masthead |
| **The valediction** | **"Tend well."** | the universal sign-off (longstanding brand) |
| **The invitation** | **"Tend a tiny jungle."** | the Home grid's invitation, first-run welcome |
| **The descriptor** | "A plant that finally has a voice." | definitional/body copy — a description, not branding |

**The compact lockup:** *"plants with a pulse · tend well."* **Dispositions:** "Know before they show" is
feature/body copy, never branding. **"One plant. One voice." is retired as external copy** (it breaks at
n = 2); "one voice" survives only as the internal consistency mantra. **The pulse mandate:** the tagline is
a promise — every tagline-bearing surface shows a pulse visual (chart / histogram / sparkline).

---

## 1. The direction

**Chosen: Plant's POV** — the plant narrates everything in its own first-person voice. Warm, alive, and it
centers the *plant*, not the engineering.

Excluded (kept on record so we don't drift back):

- **Field Journal** — serif naturalist almanac; sidelines the live character.
- **Beautiful Instrument** — engineering-first; its rigor survives as the *reading-first thread* inside the
  winner, not the whole identity.
- **Retro-Futurism** — a decorative skin without a reason.
- **Plant Tamagotchi** — a needy pet contradicts an ambient, hands-off system.

## 2. Voice

Write **as** Sprout, never **about** it — and mind the register (#1138, ruled 2026-07-18):
**first-person voice surfaces personify freely** ("Hi — I'm Sprout"); **third-person definitional text says
what Sprout IS** — an app, an open-source project, a plant-care tool. *Sprout is not a plant. Sprout's voice
is a plant-first voice. Sprout's brand is a plant that can speak for itself.*

**Do**

- First person — "I", never "your plant".
- Fact, then feeling — the data earns the warmth.
- One short, glanceable line. Never a paragraph.
- Calm under fault — reassure, explain, pause.

**Don't**

- No baby-talk or cutesy word-mangling.
- No emoji — the mark and color carry the feeling.
- No guilt-tripping — Sprout never nags or shames.
- No invented numbers — never make up a % or an ETA.

**By surface**

| Surface | Example |
|---|---|
| In-app | "Feeling great today, thanks for asking." |
| Push | "Getting thirsty over here — no rush, maybe tomorrow." |
| Fault | "I can't feel my soil sensor — I've paused my pump to be safe." |
| Social | "Day 30: still alive, still green. We're a good team." |
| README | "Hi, I'm Sprout. Here's how I keep four plants happy." |
| Empty state | "No plants yet — add one and I'll start watching." |

## 3. The living mark & motion

One mark — two leaves on a stem — is the icon, favicon, sticker, and in-app character. *Static when it
must be, alive whenever it can be.* All motion honors `prefers-reduced-motion`.

| Motion | Use |
|---|---|
| **Sway** | calm idle — the default |
| **Breathe** | alive & well — thriving |
| **Bob** | speaking / greeting |
| **Droop** | thirsty / needs water |

### Avatar / profile mark

For square-but-circular surfaces (Google / GitHub profile, social avatar), use
[`sprout-avatar.svg`](sprout-avatar.svg) — the editable master — or [`sprout-avatar.png`](sprout-avatar.png)
(1024², exported). The mark is composed **circle-safe**: the seedling sits inside the inscribed circle, so a
circular crop only ever loses the corner ground. Brand greens over the soil-mode radial ground; reads down to
~40px. Export a PNG at whatever size the surface needs from the SVG.

### Profile header / cover mark

For wide cover surfaces (Hackaday.io, and cover-photo bands generally), use
[`sprout-hackaday-header.svg`](sprout-hackaday-header.svg) — the editable master — or
[`sprout-hackaday-header.png`](sprout-hackaday-header.png) (1400×500, exported). The canvas is **1400×500**
(2.8∶1) — the size these surfaces store — but they re-crop it with `background-size: cover`, centered, into a
*wider-shorter* band (~4.6∶1 on desktop, wider on big monitors). So it's composed **center-safe two ways**:
every signature element (the edge seedlings, the full-width moisture trace, the seven-band hairline) lives in
the vertical-center safe band that survives the crop, and the horizontal center is kept **dark** so an
overlaid name + summary stay legible. It shares the seedling and soil-mode ground with the avatar, so a
profile reads as one system. Re-export the PNG from the SVG at the surface's store size.

### Asleep / signoff illustration

The **"asleep" overlay** (§4) as a full scene, for sleeping-plant / user-signoff / logout surfaces:
[`sprout-asleep.svg`](sprout-asleep.svg) — the animated master — or [`sprout-asleep.png`](sprout-asleep.png)
(exported). A dimmed seedling with **folded leaves** (nyctinasty — real plants fold at night, so it reads as
*resting*, not wilting) under a crescent moon, breathing slow. The night palette derives from the soil/dark
tokens (ADR-0008) cooled one shade; brand greens dimmed ~30%. Self-contained, CSS-animated,
`prefers-reduced-motion`-aware. A share-ready **1200×630 card** ([`sprout-asleep-card.svg`](sprout-asleep-card.svg)
/ [`sprout-asleep-card.png`](sprout-asleep-card.png)) adds the wordmark and a goodnight line for social; the
posting cadence stays gated and the caption is the maker lane's — this is the ready asset. A
**work-in-progress variant** ([`sprout-asleep-card-wip.svg`](sprout-asleep-card-wip.svg) /
[`sprout-asleep-card-wip.png`](sprout-asleep-card-wip.png)) exposes the night palette with labels under a
"work in progress" header — an honest *building-in-the-open* cue for pre-release posts.

## 4. The mood system (band-derived)

**Invariant:** Sprout's mood is a **1:1 function of the calibrated moisture band** — one of seven — and
**never** of the 0–100 relative index. The character reads from the same source as the instrument
(ADR-0004), so it can never contradict it.

**One vocabulary (#1039, ruled 2026-07-18): the seven mood words ARE the band names** — Soaked → Faint,
wet → dry, in-soil only. Dashboard, charter, and mark speak the same words. (Firmware levels remain the wire
lookup keys; they never render.)

| The word | fw lookup | Voice (from the pool) |
|---|---|---|
| **Soaked** | submerged | "Whoa — that's plenty. I'm soaking it all in." |
| **Refreshed** | overwatered | "Cool and damp around my roots — feeling fresh." |
| **Thriving** | well watered | "Feeling great today, thanks for asking." |
| **Content** | OK | "Comfortable and green. Just sipping slowly." |
| **Thirsty** | needs water | "Getting a little thirsty — no rush, maybe tomorrow." |
| **Parched** | DRY | "I'm properly thirsty now. A drink soon would be lovely." |
| **Faint** | (driest in-soil) | "Very little moisture reaching me — I could really use some water." |

Three notes:

- **Diagnostics live OFF the ladder.** Air-dry ("probe may be out of soil") is an *exception*, not a band —
  it renders in the exceptions lane, in neutral, with a plain reason. The exception families so far:
  placement · physics · kinematics · comms — an open taxonomy ("four is a floor").
- **Absence has three named patterns** (internal names, never rendered): **present-or-silent** (an optional
  line renders real information or not at all) · **calm-empty** (a must-exist surface shows a warm designed
  empty — "— not seen yet") · **first-class-absent** (absence that is information carries a reason, never a
  data-pretending null).
- **"Asleep"** is a **night/diurnal overlay, not a band** — it rides on top of any mood after dark.

## 5. Color & type — Sprout's environment

Color and type are Sprout's surroundings, named for what's around a plant. **All values are consumed from
[`sprout-tokens.css`](../tokens/sprout-tokens.css)** (ADR-0004) — never redefined here — and **every color
question resolves through the color-roles charter** (one job per channel; #930/#1109):

- **State owns all saturation** — the seven-hue ramp wearing the seven mood words; a card's frame IS its
  mood, never an identity color.
- **Chrome is the muted neutral family** — sprout-soft · mist · sand · soil (`--sprout-soft`, `--mist`,
  `--sand`, `--soil-*`).
- **Identity travels by the identity block**, and its *materials* (pots, foliage) may carry muted color from
  the `--mat-*` register (terracotta … persimmon … slate) — the two-register principle: muted materials can
  never be mistaken for vivid state.
- **Chart series stroke in the materials register** (`--series-1..12`); the band-ground carries state;
  focus-on-interaction saturates one line to ink.
- The mark's earth-brown pot is asset-internal artwork, not a UI token.

Type: **Baloo 2** (display & Sprout's voice) · **Hanken Grotesk** (UI & body) · **JetBrains Mono** (all
numbers & data — always).

## 6. Character meets instrument — the boundary

The single most important rule for everyone building on Sprout: **character layers onto the instrument; it
never restyles it.**

- **Sprout belongs:** ambient, empty, loading, onboarding, notification, and single-plant-hero surfaces —
  *beside* the gauge, both reading the same band.
- **Keep Sprout out:** dense numeric readouts, the calibration ladder, and data-integrity tables. No
  character inside the numbers — legibility wins, and the numbers stay clean, mono, tabular.

This boundary is the v1↔v2 reconciliation the Design lane owns (#18 / ADR-0004). Phase 2 proposes the
additive personality layer (mood↔band map, animated mark component, voice strings) — layered on, never a
silent restyle.
