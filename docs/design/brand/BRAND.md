# Sprout — Brand guide

The usable rules for Sprout's brand: identity, voice, the living mark, the mood system, color & type, and
the one boundary that keeps character and instrument from fighting. This is the **canonical written
reference**; its living visual companion is [`Sprout Brand Guidelines.dc.html`](Sprout%20Brand%20Guidelines.dc.html)
(open with `support.js` in the design tool to see the mark animate). The decision behind it is
[ADR-0007](../../adr/0007-brand-guidelines.md); the token foundation it builds on is
[ADR-0004](../../adr/0004-design-system.md).

> **The one-liner.** The brand is a plant that finally has a voice. Sprout is a living, animated character
> — the hero of every surface. Everything else is the soil it grows from.

---

## 1. The direction

**Chosen: Plant's POV** — the plant narrates everything in its own first-person voice. Warm, alive, and it
centers the *plant*, not the engineering.

Excluded (kept on record so we don't drift back):

- **Field Journal** — serif naturalist almanac; sidelines the live character.
- **Beautiful Instrument** — engineering-first; its rigor survives as the *honesty thread* inside the
  winner, not the whole identity.
- **Retro-Futurism** — a decorative skin without a reason.
- **Plant Tamagotchi** — a needy pet contradicts an ambient, hands-off system.

## 2. Voice

Write **as** Sprout, never **about** it.

**Do**

- First person — "I", never "your plant".
- Fact, then feeling — the data earns the warmth.
- One short, glanceable line. Never a paragraph.
- Calm under fault — reassure, explain, pause.

**Don't**

- No baby-talk or cutesy word-mangling.
- No emoji — the mark and color carry the feeling.
- No guilt-tripping — Sprout never nags or shames.
- No fake numbers — never invent a % or an ETA.

**By surface**

| Surface | Example |
|---|---|
| In-app | "I'm thriving. Last drink was two days ago." |
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

## 4. The mood system (band-derived)

**Invariant:** Sprout's mood is a **1:1 function of the calibrated moisture band** — one of seven — and
**never** of the 0–100 relative index. The character reads from the same source of truth as the instrument
(ADR-0004), so it can never contradict it.

| Band (UI · fw) | Mood | Voice |
|---|---|---|
| Saturated · submerged | **Soaked** | "Whoa — that's plenty. I'm soaking it all in." |
| Wet · overwatered | **Refreshed** | "Ahh — just had a good drink. All better." |
| Moist · well watered | **Thriving** | "I'm thriving. My last drink was two days ago." |
| Ideal · OK | **Content** | "Comfortable and green. Just sipping slowly." |
| Drying · needs water | **Thirsty** | "Getting a little thirsty — no rush, maybe tomorrow." |
| Dry · DRY | **Parched** | "I'm properly thirsty now. A drink soon would be lovely." |
| Parched · air-dry | **Faint · check me** | "I can barely feel my soil — am I truly bone-dry, or has my sensor slipped?" |

Two honesty notes:

- **Air-dry** doubles as the diagnostic "probe may not be in soil" band — its voice names the ambiguity
  rather than dramatizing death.
- **"Asleep"** is a **night/diurnal overlay, not a band** — it rides on top of any mood after dark.

## 5. Color & type — Sprout's environment

Color and type are Sprout's surroundings, named for what's around a plant. **All values are consumed from
[`sprout-tokens.css`](../sprout-tokens.css)** (ADR-0004) — never redefined here.

| Name | Token | Role |
|---|---|---|
| Leaf | `--leaf` `#34A853` | primary green |
| Sprout | `--sprout` `#8BD24F` | bright accent / the mark |
| Water | `--st-watering` `#17B6C4` | watering / wet |
| Sun | `--st-dry` `#F5A623` | drying / warmth |
| Soil | `#5A3F28` | earth, the pot |
| Night | `--bg` (dark) `#0E140B` | soil/dark mode |

Type: **Baloo 2** (display & Sprout's voice) · **Hanken Grotesk** (UI & body) · **JetBrains Mono** (all
numbers & data — always).

## 6. Character meets instrument — the boundary

The single most important rule for everyone building on Sprout: **character layers onto the instrument; it
never restyles it.**

- **Sprout belongs:** ambient, empty, loading, onboarding, notification, and single-plant-hero surfaces —
  *beside* the gauge, both reading the same band.
- **Keep Sprout out:** dense numeric readouts, the calibration ladder, and data-integrity tables. No
  character inside the numbers — legibility and honesty win, and the numbers stay clean, mono, tabular.

This boundary is the v1↔v2 reconciliation the Design lane owns (#18 / ADR-0004). Phase 2 proposes the
additive personality layer (mood↔band map, animated mark component, voice strings) — layered on, never a
silent restyle.
