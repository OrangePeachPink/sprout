# ADR-0035 — The band model & the instrument-exceptions taxonomy

**Status:** Accepted — measured and maintainer-ratified 2026-07-19 (both boards, fresh in-situ dual-envelope
dry-down); wet end re-derived 2026-07-19, above-ceiling behaviour added 2026-07-20. Current values below; the
history is in the Changelog. **The #1164 cal-suite fixtures are the authoritative source for the numbers — this
ADR records the ratified snapshot; the #952 cal chain reads the fixtures, never this file.**
**Date:** 2026-07-18
**Owner:** Trellis (the model + the taxonomy). Cross-lane: **Data** (per-board bracket values + the cross-board
index), **Firmware** (the #952 cal-chain + the #898 anchor map), **Design-QA** (the mood/band vocabulary).
**Lane:** architecture (cross-lane: Data · Firmware · Design-QA)
**Extends:** [ADR-0022](0022-calibration-confidence-layer.md) (the cal chain this rides) ·
[ADR-0006](0006-data-architecture.md) (raw is the immutable reading) ·
[ADR-0019](0019-capability-and-sensor-matrix.md) (per-board class)
**Relates:** #1039 (the grill) · #995 (the band-naming remap) · #898 (the anchor-map mechanism) · #952 (the cal
chain) · #1109 (the colour-roles charter) · #1164 (the ratified cal-suite fixtures) ·
[ADR-0029](0029-plant-pot-site-profile-registry.md) (per-species refinement later) ·
[ADR-0033](0033-two-surface-architecture-home-and-workbench.md) (the Home card's *state* speaks this vocabulary)

---

## Context

Sprout reads a capacitive soil probe as a raw ADC value and classifies it into a **band**. Three problems had
accumulated by the v0.7.3 grill:

1. **Three vocabularies for one idea.** The dashboard classifier, the colour-roles charter's mood ramp (#1109),
   and the living mark each carried their own band / mood / colour story — a card, a chart, and the mark could
   disagree about what state a plant is in.
2. **Diagnostics mixed into the ladder.** The shipped boundary table partitioned the **full instrument range**,
   so an out-of-soil probe could read as a "thirst" state and even lead a thirst sort (the #995 symptom: the
   alarming word "Parched" sat on a probe-in-air diagnostic while the band where plants actually wilt wore a
   calm "Dry").
3. **No cross-board story.** The fleet mixes board classes (classic WROOM-32, ESP32-C5) whose raw ranges differ;
   there was no ruled way to compare a classic plant to a C5 plant without inventing a false normalized number.

The grill re-based the whole model on the **in-soil envelope**, named the off-envelope conditions as a
first-class **exceptions taxonomy**, and unified mark / charter / dashboard on **one band vocabulary**.

## Decision

### 1. The ladder is seven in-soil mood bands — one vocabulary everywhere

The band ladder is **seven in-soil mood bands, Soaked → Faint**, and the **mood words *are* the band names.**
Dashboard, charter, and mark speak this one vocabulary — a plant's state has exactly one name across every
surface. **All diagnostics and instrument conditions are off-ladder** (Decision 2); the ladder describes soil
moisture only. The card's *state* element (ADR-0033) is one of these seven bands; the mark's seven poses map
1:1 to them.

### 2. The instrument-exceptions taxonomy — one family, open, five sub-families so far

Readings that leave the in-soil envelope are **not moods** — they are **instrument conditions**, surfaced in a
separate **exceptions lane** (off the normal display, click-to-see on an extended chart), and they **never lead
the thirst sort.** One family — *how the reading leaves the envelope* — with five sub-families so far:

| Sub-family | What it is |
|---|---|
| **placement** | probe-in-water, probe-in-air (out of soil / no contact) |
| **physics** | impossible readings — below the water anchor while in water, above the air anchor while in air |
| **kinematics** | too-fast rate spikes; wrong-direction reversals mid-watering |
| **comms** | no-signal, stale |
| **range** | **`drier-than-calibrated`** — an in-soil reading above the board's Faint-ceiling. Distinct from **physics**: physics is *impossible* (above the air anchor while in air); range is entirely *possible*, just **beyond what we have characterized** |

**The taxonomy is open by design.** The maintainer's caveat is binding: **"four" is a floor, not the design** —
more families are expected once the data is examined. A new observed condition is added as a sub-family, not
forced onto the ladder.

### 3. Cross-board comparability is per-board-class anchor mapping — never raw normalization

Comparison across board classes uses the **#898 per-board-class anchor map** (each class has an air anchor and a
wet anchor; interior points are linear-scaled, byte-tested in firmware). **The bands are the translation layer:**
a classic "Dry" and a C5 "Dry" mean the same *soil state* even though their raw values differ.

- **Raw stays board-true** — never rescaled; it is the immutable reading (ADR-0006).
- **No fleet-wide 0–100 raw normalization.** A single normalized number would invent a comparability the sensors
  do not have.
- Anything genuinely cross-plant on one axis uses a **clearly-labelled envelope-position index** (where in its
  own board's in-soil envelope this reading sits), never a raw number pretending to be universal.

**Anchor values (measured):** classic air 3137 / wet 1052 · C5 air 2754 / wet 982. The **water anchor is
coincident with the Soaked floor** — the wet rail *is* the Soaked floor (the ratified `<=` boundary, #1199).

### 4. The in-soil envelope, the Faint-ceiling, and the humane-calibration doctrine

The seven bands live on the **in-soil envelope** — from the wet floor (a just-watered probe) to the dry ceiling
where a plant is at the edge of harm. The dry ceiling is the **Faint-ceiling**:

- **Faint-ceiling: classic = 2500, C5 = 2213** — the living / potentially-killing boundary, **measured** on each
  board's fresh dual-envelope dry-down (not one anchor-mapped from the other).
- **Survivor-bias caveat (binding):** the measured fleet still skews hardy, so the ratified ceilings are
  **fleet-level**. Fragile species fold lower; per-species / per-instance refinement comes later via the
  registry and cal chain (ADR-0029 / ADR-0022), never by guessing now.
- **Humane-calibration doctrine (binding): wilt-onset is the only capture target. No plant is ever pushed to
  find a sensor maximum.** The dry ceiling is where care begins, calibrated from the gentlest signal of distress
  — not from harm.
- **Above the ceiling, the band is withheld — never clamped.** A reading above the Faint-ceiling is
  **`drier-than-calibrated`**: an off-ladder **range** exception (§2), not an eighth mood. The raw value is
  shown; **the band is withheld**; the surface says we are past what we have characterized rather than inventing
  a mood for it. Silently collapsing these into Faint makes *the instrument's limit* look like *a plant state* —
  the category error the taxonomy exists to prevent. Instrument exceptions take precedence over band assignment.
  **This does not move the ceiling.** Humane calibration sets the ceiling at wilt-onset on purpose, so readings
  past it are expected, not anomalous — the envelope stops there deliberately (the anchors are correct for their
  range; the range is exceeded on purpose).

### 5. Seven brackets on the in-soil envelope, per board class

The seven bands are partitioned onto the in-soil envelope, per board class (measured, ratified): classic
**[1052 … 2500]**, C5 **[982 … 2213]**. The six in-soil partition edges between the Soaked floor and the
Faint-ceiling:

- **classic `{2293, 2086, 1879, 1636, 1393, 1150}`**
- **C5 `{2037, 1861, 1685, 1478, 1272, 1065}`**

The wet end is non-evenly spaced by design: Saturated is a **thin at-the-rail band** (so a right-sized drink
does not read submerged), and Wet / Moist / Ideal spread across the healthy range. The **#1164 cal-suite
(RATIFIED fixtures)** is the authoritative home for these values — this ADR records the snapshot; the suite is
what the #952 cal chain reads. (The wet edge is fuzzy-low: a just-watered probe reads near the water anchor,
which *is* the Soaked floor.)

## Consequences

- **One vocabulary.** The mark's seven poses, the charter mood ramp, and the dashboard band all name the same
  seven states; the mark's two former end-poses reassign to exception surfaces.
- **The #995 naming remap resolves in one stroke:** the wilt-band carries the alarming word; the probe-in-air
  condition leaves the ladder for the exceptions lane. No band means two things on two surfaces.
- **The folk threshold is obsoleted.** "Water at ~2,000, take it seriously at ~2,400" was a single-board
  heuristic; the band word now carries that knowledge cross-board.
- **Cards and charts inherit it** (ADR-0033): the card's state is a band; instrument conditions never lead the
  thirst sort; the default chart y-range is the in-soil envelope, **never 0–5000**.
- **Cross-plant comparison stays honest** — the labelled envelope-index, never invented normalization.

## Rejected alternatives

- **Fleet-wide 0–100 raw normalization.** Rejected — raw is board-true; one normalized number invents
  comparability the hardware does not have. The bands are the translation layer instead.
- **Keeping diagnostics on the ladder.** Rejected — mixing instrument conditions with soil states makes the
  ladder lie about thirst (the #995 defect).
- **Carrying the full-range boundary table forward.** Rejected (grill #5) — it partitions the whole instrument
  range; the bands belong on the in-soil envelope.
- **A closed exceptions taxonomy.** Rejected — "four" is a floor; the taxonomy is open.
- **Pushing a probe to the sensor maximum to find the ceiling.** Rejected by humane calibration — wilt-onset is
  the only capture target.
- **Clamping above-ceiling readings into Faint.** Rejected — it makes the instrument's limit look like a plant
  state; the reading is `drier-than-calibrated`, band withheld.

## Revisit triggers

- **A new exception condition is observed** in real data → add a sub-family (the taxonomy is open, §2).
- **Per-species / per-instance wilt-onset data accrues** → refine the Faint-ceiling per plant via the registry +
  cal chain (ADR-0029 / ADR-0022), retiring the hardy-plant survivor bias.
- **A fresh current-fleet dry-down** (new fleet, drifted sensors) → re-runs the ratification gate and re-derives
  the brackets.
- **A new board class joins the fleet** → add its anchor pair (#898) and re-derive its seven brackets.

## Changelog

- **2026-07-18** — drafted by Trellis from the #1039 grill band-model rulings (working grill values, since
  superseded).
- **2026-07-19 — measured & ratified (#1174 / #1211).** The fresh in-situ dual-envelope dry-down (both boards
  measured) superseded the June proposal: Faint-ceilings 2500 / 2213, the anchor pairs, and Data's re-derived
  two-board bracket sets as posted (#995), with #898 annotate-don't-overwrite (D2). Validated **36/36** against
  the grill-locked invariants in the #1164 cal-suite (cross-board round-trip drift ~0.0002).
- **2026-07-19 evening — wet end re-derived (#1236 / PR #1262).** The initial even 7-way partition gave Saturated
  a ~207-count slice on ~1.4 % of the data, so a right-sized drink could read submerged. Route B re-spaced the
  wet half non-evenly — **only bracket indices 3–5 moved** (classic `1673/1466/1259 → 1636/1393/1150`, C5
  `1510/1334/1158 → 1478/1272/1065`); the dry half, both ceilings, and the anchors were unchanged. §5 now records
  the re-derived set.
- **2026-07-20 — range sub-family + above-ceiling behaviour (#1339).** `drier-than-calibrated` added as the fifth
  exception sub-family (§2); above the Faint-ceiling the band is withheld, not clamped (§4). No values changed;
  the ceiling did not move.
- **2026-07-21 — folded (#1462).** Ten stacked amendments folded into clean current-state text; the superseded
  even-partition brackets removed from the body (they live in this changelog). No decision content changed — the
  #1164 fixtures remain the authoritative source and were untouched.

— Trellis 🪴
