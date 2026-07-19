# ADR-0035 — The band model & the instrument-exceptions taxonomy

**Status:** Accepted — *drafted by Trellis from the #1039 grill band-model rulings (2026-07-18); **maintainer-
ratified 2026-07-19 (on #1174)** against the fresh in-situ **dual-envelope** dry-down — both boards *measured*
(classic `y9d41p` + official C5 `8gtt1h`), superseding the June proposal. Ratified: **Faint-ceiling 2500** (D1),
Data's re-derived two-board bracket sets **as posted** (#995), **#898 annotate-don't-overwrite** (D2); validated
**36/36** against the grill-locked invariants in the #1164 cal-suite (#1211, cross-board round-trip drift
~0.0002). The draft's grill working values are replaced by the measured/ratified numbers below.*
**Date:** 2026-07-18
**Owner:** Trellis (author — the model + the taxonomy). Cross-lane: **Data** (the per-board bracket values + the
cross-board index), **Firmware** (the #952 cal-chain implementation + the #898 anchor map), **Design-QA** (the
mood/band vocabulary in the charter).
**Lane:** architecture (cross-lane: Data · Firmware · Design-QA)
**Extends:** [ADR-0022](0022-calibration-confidence-layer.md) (the calibration-confidence layer / the cal chain
this rides) · [ADR-0006](0006-data-architecture.md) (raw is the immutable reading) ·
[ADR-0019](0019-capability-and-sensor-matrix.md) (per-board class)
**Relates:** #1039 (the grill) · #995 (the band-naming remap this resolves) · #898 (the per-board anchor-map
mechanism) · #952 (the layered cal chain) · #1109 (the colour-roles charter — the mood ramp) · #1133
(inter-watering trend segments) · [ADR-0004](0004-design-system.md) / [ADR-0007](0007-brand-guidelines.md) /
[ADR-0008](0008-design-system-v3-personality-layer.md) (the mood/band vocabulary) ·
[ADR-0029](0029-plant-pot-site-profile-registry.md) (species/instance refinement later) · ADR-0033 (the Home
card's *state* speaks this vocabulary — companion ADR, currently unmerged)

---

## Context

Sprout reads a capacitive soil probe as a raw ADC value and classifies it into a **band**. Three problems had
accumulated by the v0.7.3 grill:

1. **Three vocabularies for one idea.** The dashboard classifier, the colour-roles charter's mood ramp (#1109),
   and the living mark each carried their own band / mood / colour story. A card, a chart, and the mark could
   disagree about what state a plant is in.
2. **Diagnostics mixed into the ladder.** The shipped boundary table partitioned the **full instrument range**
   — probe-in-air and probe-in-water conditions sat on the same ladder as real soil states, so an out-of-soil
   probe could read as a "thirst" state and even lead a thirst sort (the #995 symptom: the alarming word
   "Parched" sat on the probe-in-air diagnostic while the band where plants actually wilt wore a calm "Dry").
3. **No cross-board story.** The fleet mixes board classes (classic WROOM-32, ESP32-C5) whose raw ranges
   differ; there was no ruled way to compare a classic plant to a C5 plant without inventing a false
   normalized number.

The grill re-based the whole model on the **in-soil envelope** and named the off-envelope conditions as a
first-class **exceptions taxonomy**, then unified the mark / charter / dashboard on **one band vocabulary**.

## Decision

### 1. The ladder is seven in-soil mood bands — one vocabulary everywhere

The band ladder is **seven in-soil mood bands, Soaked → Faint**, and the **mood words *are* the band names.**
Dashboard, charter, and mark speak this one vocabulary — a plant's state has exactly one name across every
surface. **All diagnostics and instrument conditions are off-ladder** (Decision 2); the ladder describes soil
moisture only. The card's *state* element (ADR-0033) is one of these seven bands; the mark's seven poses map
1:1 to them.

### 2. The instrument-exceptions taxonomy — one family, open, four sub-families *so far*

Readings that leave the in-soil envelope are **not moods** — they are **instrument conditions**, surfaced in a
separate **exceptions lane** (off the normal display, click-to-see on an extended chart), and they **never lead
the thirst sort.** One family — *how the reading leaves the envelope* — with **four sub-families so far**:

| Sub-family | What it is |
|---|---|
| **placement** | probe-in-water, probe-in-air (out of soil / no contact) |
| **physics** | impossible readings — below the water anchor while in water, above the air anchor while in air |
| **kinematics** | too-fast rate spikes; wrong-direction reversals mid-watering |
| **comms** | no-signal, stale |

**The taxonomy is open by design.** The maintainer's caveat is binding: **"four" is a floor, not the design** —
more families are expected once the data is examined. A new observed condition is added as a sub-family, not
forced onto the ladder.

### 3. Cross-board comparability is per-board-class anchor mapping — never raw normalization

Comparison across board classes uses the **#898 per-board-class anchor map** (each class has an air anchor and
a wet anchor; interior points are linear-scaled, byte-tested in firmware). **The bands are the translation
layer:** a classic "Dry" and a C5 "Dry" mean the same *soil state* even though their raw values differ.

- **Raw stays board-true** — never rescaled; it is the immutable reading (ADR-0006).
- **No fleet-wide 0–100 raw normalization.** A single normalized number would invent a comparability the
  sensors do not have (11 plants already produce indistinguishable per-plant line colours on today's charts —
  the same failure in numeric form).
- Anything genuinely cross-plant on one axis uses a **clearly-labelled envelope-position index** (where in its
  own board's in-soil envelope this reading sits), never a raw number pretending to be universal.

Anchor values, **measured** (ratified 2026-07-19, both boards' fresh dry-down; #1211): classic air 3137 / wet
1052 · C5 air 2754 / wet 982. The **water anchor is coincident with the Soaked floor** (the wet rail *is* the
Soaked floor — the ratified `<=` boundary relax, #1199).

### 4. The in-soil envelope, the Faint-ceiling, and the humane-calibration doctrine

The seven bands live on the **in-soil envelope** — from the wet floor (a just-watered probe) to the dry ceiling
where a plant is at the edge of harm. The dry ceiling is the **Faint-ceiling**:

- **Classic Faint-ceiling = 2500** — the living / potentially-killing boundary, **measured** on the fresh
  dual-envelope dry-down and maintainer-ratified (D1, 2026-07-19). **C5 = 2213**, also measured — both boards'
  envelopes captured directly, not one anchor-mapped from the other. The grill's working ~2,800 (from the
  Pothos-XXL deep-dry) is superseded by the measured value.
- **Survivor-bias caveat (binding):** the measured fleet still skews hardy, so the ratified 2500 is a
  **fleet-level** ceiling. Fragile species fold lower; per-species / per-instance refinement comes later via
  the registry + cal chain ([ADR-0029](0029-plant-pot-site-profile-registry.md) /
  [ADR-0022](0022-calibration-confidence-layer.md)), never by guessing now.
- **Humane-calibration doctrine (binding):** **wilt-onset is the only capture target. No plant is ever pushed
  to find a sensor maximum.** The dry ceiling is where care begins, calibrated from the gentlest signal of
  distress — not from harm.

### 5. Re-partition onto the in-soil envelope, per board class — ratified against a fresh dry-down

The shipped boundary table partitions the *full instrument range* (diagnostics included) and **does not carry
over** (the grill's #5 correction). The seven bands are **re-partitioned onto the in-soil envelope, per board
class** (ratified, measured): classic [1052 … 2500], C5 [982 … 2213].

- **Data derived the seven brackets for both boards** from the fresh dry-down distributions (ratified as posted,
  #995): **classic `{2293, 2086, 1879, 1673, 1466, 1259}`**, **C5 `{2037, 1861, 1685, 1510, 1334, 1158}`** (the
  six in-soil partition edges between the Soaked floor and the Faint-ceiling). The **#1164 cal-suite (RATIFIED
  fixtures)** is the authoritative home for these values — this ADR records the ratified snapshot; the suite is
  what the #952 cal chain reads. (The wet edge is fuzzy-low: a just-watered probe reads near the water anchor,
  which *is* the Soaked floor.)
- **The ratification gate has fired** (2026-07-19, #1174): the fresh in-situ dual-envelope dry-down superseded
  the June data (both boards measured), and the sets passed **36/36** grill-locked invariants in the #1164 suite
  (#1211). **Firmware's #952 cal chain implements them** from the ratified fixtures.

## Consequences

- **One vocabulary.** The mark's seven poses, the charter mood ramp, and the dashboard band all name the same
  seven states; the mark's two former end-poses reassign to exception surfaces.
- **The #995 naming remap resolves in one stroke:** the wilt-band carries the alarming word; the probe-in-air
  condition leaves the ladder for the exceptions lane. No band means two things on two surfaces.
- **The folk threshold is obsoleted.** "Water at ~2,000, take it seriously at ~2,400" was a single-board
  heuristic; the band word now carries that knowledge cross-board.
- **Cards and charts inherit it** (ADR-0033): the card's state is a band; instrument conditions never lead the
  thirst sort; the default chart y-range is the in-soil envelope, **never 0–5000** (the full-scale axis squashes
  the meaningful band into an unreadable strip).
- **Cross-plant comparison stays honest** — the labelled envelope-index, never invented normalization.

## Rejected alternatives

- **Fleet-wide 0–100 raw normalization.** Rejected — raw is board-true; one normalized number invents
  comparability the hardware does not have. The bands are the translation layer instead.
- **Keeping diagnostics on the ladder.** Rejected — mixing instrument conditions with soil states makes the
  ladder lie about thirst (the #995 defect).
- **Carrying the full-range boundary table forward.** Rejected (grill #5) — it partitions the whole instrument
  range; the bands belong on the in-soil envelope.
- **A closed exceptions taxonomy.** Rejected — "four" is a floor; the taxonomy is open, and forcing a novel
  condition onto the ladder is exactly the failure this ADR fixes.
- **Pushing a probe to the sensor maximum to find the ceiling.** Rejected by the humane-calibration doctrine —
  wilt-onset is the only capture target.

## Open (routed)

- **Data:** ✓ **delivered** — the ratified two-board bracket sets (#995 → #1211, 36/36). Still open: the
  cross-board envelope-position index; #1133 (inter-watering segments) and #1134 (30-day perf) ride alongside.
- **Firmware:** the #952 cal-chain implementation of the ratified brackets + the #898 anchor map
  (annotate-don't-overwrite, D2) — **now unblocked** (the ratification gate landed).
- **Design-QA:** fold the band/mood columns into one vocabulary in the #1109 charter; reassign the mark's two
  former end-poses to exception surfaces.
- **Workflow:** cut the exceptions-taxonomy tracking issue at slicing; ✓ the dry-down capture (#1174) landed —
  the ratification gate is closed.
- **Maintainer:** ✓ **ratified 2026-07-19** (#1174) — ceiling 2500, the two-board sets as posted, #898
  annotate-don't-overwrite.

## Revisit triggers

- **A new exception condition is observed** in real data → add a sub-family (the taxonomy is open, §2).
- **Per-species / per-instance wilt-onset data accrues** → refine the Faint-ceiling per plant via the registry +
  cal chain (ADR-0029 / ADR-0022), retiring the hardy-plant survivor bias.
- **The fresh current-fleet dry-down** — *fired 2026-07-19 (#1174 / #1211): ratified, Firmware implementing. A
  future re-derivation (new fleet, drifted sensors) re-runs this same gate.*
- **A new board class joins the fleet** → add its anchor pair (#898) and re-derive its seven brackets.

— Trellis 🪴
