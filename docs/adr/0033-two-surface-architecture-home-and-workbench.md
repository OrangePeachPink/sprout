# ADR-0033 — Home + Classic Sprout: a converging two-surface architecture (one designed product)

**Status:** Accepted — *amended and ratified by the #1039 grill (2026-07-18); Trellis folded the rulings from the
Proposed draft (2026-07-12, #1049) — Round 1 (the two surfaces) plus the back-half rulings: the band vocabulary,
the colour-roles two-register lock, detected-rewater-shown-now, the glanceability doctrine, and the ledger = a
board view. V1 — lands via the maintainer; **#1044 closes on this.** Written to the 2026-07-18 session canon
(#1099): **the plant speaks for itself**; canonical formula `raw + band = the reading`.*
**Date:** 2026-07-12 (grill-amended 2026-07-18)
**Owner:** Trellis (architecture) — the surface structure + the convergence model. Design-QA builds the surfaces
(#875); Data provides the seams (no firmware change, #875/INCORPORATION.md).
**Lane:** architecture (cross-lane: Design-QA · Data)
**Extends:** [ADR-0008](0008-design-system-v3-personality-layer.md) (the mark / mood / voice this surface places)
· [ADR-0032](0032-github-pages-design-library-serving.md) (design-library serving). Realizes the #875 finding.
**Relates:** #1044 (this) · #875 (the Voice UI epic) · #1039 (the grill that ratified it) · #1099 (the canon wash)
· #1018 (shell-first serving) · #1041 (the v0.7.3 plan) · [ADR-0004](0004-design-system.md) /
[ADR-0006](0006-data-architecture.md) / [ADR-0007](0007-brand-guidelines.md) (the data model + the
character↔instrument boundary) · [ADR-0028](0028-optional-peripherals-doctrine.md) (absence is first-class) ·
ADR-0035 (the band model + exceptions taxonomy the card's state speaks — companion ADR, filed separately as
Proposed) · #1109 (the colour-roles charter) · #1133 (inter-watering trend segments)

---

## Context

We designed the product first — brand, voice, character, motion, onboarding — and then shipped only the
**instrument** (logs, capture, calibration, integrity, diagnostics). #875's finding: the app has a debugging
dashboard, but it has **never had a user surface**. v0.7.3 builds the designed surface now, *before* Predict
(0.8.0) and Water (0.9.0), so those layers inherit the voice, brand, and design system instead of bolting them on
later.

The grill (#1039, Round 1) ruled the structure. The headline amendment to the pre-grill draft: **this is not two
permanent surfaces — it is a *migration* architecture.** The app *is* Home; the old dashboard is a transitional
staging area that retires piece by piece. The end state is **one designed product with layered depth**, in
Sprout's voice throughout.

## Decision (ratified by the #1039 grill)

### 1. The app opens onto Home — a glanceable per-plant card grid, in Sprout's voice

- **Home is the app's opening surface** (grill 1a). It is a **glanceable per-plant card grid** — *"which plant"*
  and *"how thirsty is it,"* in Sprout's voice, is the center of the experience. It scales gracefully from **1 to
  24+ plants** (one plant never looks lonely; 24+ stays scannable).
- **The card contract** (grill Q3 — supersedes the pre-grill hero sketch). Each card carries:
  - **Identity block (the crucial element)** — plant name (or number-as-identity) plus real-world disambiguators:
    pot type / colour / descriptor, a **location chip** (left/right windowsill; others: kitchen / bedroom /
    office…), and an **optional plant photo.** A card that says *"plant #7 is thirsty"* with no way to find plant
    #7 on a shelf of 24 fails the product. **Identity travels by the identity block, never by colour** (the Q2
    charter's two-register lock, #1109): state owns the vivid register; identity materials (photo, pot) are a
    *muted* register — **one thumbnail slot, best-available: photo → chosen icon → generic fallback**, and the
    responsive grid **sizes** the thumbnail (**scale, not a zoom control** — the tile→card→Classic ladder *is* the
    progressive disclosure). The action flow: **state colour finds the plant that needs you; the identity block
    confirms which physical plant it is.**
  - **State** — mood (the mood **colour is the card's key frame**, per the Q2 colour-roles charter — the frame is
    the plant's *current* state, never a fixed identity colour) + the calibrated **band** word (one of the **seven
    in-soil mood bands**, Soaked → Faint — the *one* state vocabulary across dashboard, charter, and mark;
    ADR-0035) + a **first-person line.** Instrument conditions
    (probe-in-air, probe-in-water) are **off-ladder exceptions** (ADR-0035), never a mood and never a thirst
    state — they surface in an exceptions lane and never lead the thirst sort.
  - **Water story** — **last watered** (a **detected** watering event — the raw-cliff signature), **shown now
    labelled `source="detected"`** (grill Q2: the detected re-water is the owner's #1 water cue — ship it; the
    classifier tunes/validates in 0.8.0), plus a one-tap **manual "I just watered this"** (`source="manual"`) as
    interim ground truth. **Next need** (the forecast-boundary helper) is **volume-gated** — detector-fed drying
    rates drive next-need times only after enough confirmed events.
  - Raw numbers stay Classic-Sprout-side (§2).
- **Absence is first-class** (ADR-0028): missing pieces render as graceful absence — the card ships **thin**
  rather than waiting for full data. **Photo** is a new local-only registry field (EXIF-strip on any future
  export/share path, since photos carry GPS) and renders **`calm-empty`** (the generic mark) until set; the
  **detected-watering classifier** hardens in 0.8.0 (reading the same substrate as #822 / #25) but ships its
  events *now* per the water story above — not as a placeholder.
- **v0.7.3 Home tracer scope** (grill 1c): the living mark + a greeting + the ruled card grid.
- **Glanceability is Home's success metric — the 30-second loop** (grill product doctrine, verbatim intent):
  *glance → decide what needs water → figure out which one → know how much → go, then come back in a day or two.*
  Every card / grid / chart decision is judged against it. The single-plant hero ships with **at least one
  per-plant chart** (a histogram minimum, Tufte-esque) — the tagline promises a pulse, so *where we say "pulse,"
  show pulse.*

### 2. Classic Sprout is the transitional instrument — a migration architecture, not a second standing surface

- The old dashboard (today's Monitor / Capture / Lab / Diagnostics) becomes **"Classic Sprout,"** reachable via a
  **small link — only for as long as we need it** (grill 1b). It keeps its instrument function (dense readouts,
  raw numbers, calibration, integrity, provenance, experiment capture) **while it exists.**
- **Classic Sprout's contents are literally the migration backlog.** Each piece of Classic utility **retires** as
  it is either subsumed into the designed product (re-expressed in Sprout brand + voice) or proven unneeded. The
  link shrinks over time; when the backlog is empty, the link is gone.
- **The convergence commitment (the end state):** **one designed product with layered depth** — not two surfaces
  held apart forever. Home is the destination; Classic Sprout is scaffolding with a demolition date.
- Experiment capture (#372) lives Classic-side today and is one of the backlog items to migrate into the product.

### 3. Sprout speaks for itself on every surface — the character↔instrument boundary is the surface line

The spine. Home is warm and friendly; that is not license to soften or invent.

- **Mood derives 1:1 from the calibrated band, never the index** (ADR-0007 / 0008). Sprout's mood word, voice line,
  and mark colour *restate* the calibrated band (`mood-band-map.json`) — the character is the plant **speaking for
  itself**, not a new claim laid over the reading.
- **Character layers onto the instrument, never restyling it** (ADR-0008). No character copy inside dense
  readouts; no mood word standing in for a number. The two-surface split makes this boundary **structural** —
  character on Home, the raw instrument in Classic Sprout.
- **`raw + band = the reading`; the 0–100 is a *labelled* relative index; absence is first-class** (ADR-0004 /
  0006 / 0028) — on Home too. Home leads with mood + band; the raw / index / calibration-confidence is one step
  away in Classic Sprout. Home **won't invent a percentage.**
- **Alarms are earned; absence is not an alarm** (ADR-0028). Untethered / asleep / empty states render with
  character but never manufacture urgency — a sensorless plant reads *"alive, not probed,"* never *"in distress."*
- **Provisional stays provisional — as system-level cal state, never a per-card badge** (ADR-0022; the
  2026-07-18 grill, item 3). Home's mood reflects a *provisional* band without wearing a chip for it; the cal
  state lives once on the Workbench's Plants & Sensors surface, with a defined path to clearing.

### 4. Navigation + first-run

- **Home is where the app opens** (grill 1a); **Classic Sprout is a small link from it** (grill 1b), never hidden
  while it exists, never a co-equal permanent destination.
- **First run → onboarding** (T5: *Hi, I'm Sprout → plug in your probe → name your probes → you're set*), handing
  into the registry tab (#921). A never-configured app (no `config/devices.local.json`) is a first-run. A
  configured app opens on Home.

### 5. Serving / template structure — shell-first, one shell

- **The served HTML is a fast static shell; data hydrates client-side** (#1018) — binding. Today `/` runs the full
  ~10 s analytics pipeline server-side just to emit the document; a Home landing must **not** pay that. The shell
  serves instantly; Home fetches its card-grid summary async, and Classic Sprout's dense payloads load on demand.
- **One shell, client-routed** (the pre-grill fork, resolved by the migration model): Home is the default view and
  Classic Sprout is a client-routed view behind the small link — one origin, one boot, one incorporation of the
  design-library components (`sprout-mark.js`, `sprout-motion.css`, `voice-strings.json`, `mood-band-map.json`, per
  #875/INCORPORATION.md), the same vanilla-host contract as today (ADR-0004). Two standing server routes are
  rejected — Classic Sprout is transitional, not a co-equal permanent route. The Pages-served Design Library
  (ADR-0032) stays the source/showcase; the app **incorporates** the components, it does not iframe them.

## Consequences

- Every #875 tracer builds against a **ratified** frame: Home is the card grid, its card contract is fixed, and
  Classic Sprout is the shrinking backlog — the grill rules UX inside this, not structure.
- The product **converges**: there is one designed destination, and a visible, shrinking list of what still needs
  migrating — not a permanent instrument/product split.
- Predict (0.8.0) and Water (0.9.0) **inherit** Home: a forecast or pump status is a card element from day one.
- Shell-first serving resolves #1018 structurally and sets the pattern for every future surface.
- Nothing in Classic Sprout regresses while it exists; it is preserved until each piece is migrated or retired.

## The migration backlog (ruled: a board view)

Classic Sprout's contents **are** the migration backlog (§2). **Ruled by the grill (docket 13): the ledger is a
native filtered board view over migration-labelled issues** — live work items that close as they land, never a
stale list — *not* ADR prose. This ADR records the *architecture* and the *convergence commitment* and points at
that board view. A **slice-to-issues pass** (Workflow, post-grill) decomposes Classic element-by-element
(trajectory chart, drying-rate table, band history + stats, forecasts, diagnostics, wiring, the histogram wish)
and maps each to its voiced destination (Home card / hero / Classic-retire). **Investment rule on the record: no
new feature work lands in Classic** — design the voiced surfaces instead (the #993 / #372 reframe).

## Rejected / not-chosen

- **Two permanent standing surfaces.** Rejected by the grill (1b): Classic Sprout is transitional; the end state
  is one designed product.
- **"A Day in the Life" (one-plant replay) as a product surface.** Demoted by the grill to **gimmick / marketing
  tier** — its home is the teaser pipeline (FD-7), not v0.7.3; no tracer builds it.
- **Restyle the one dashboard with character ("just make it friendlier").** Rejected — it violates ADR-0008's
  "character layers onto the instrument, never restyling it," puts mood copy inside dense readouts, and blurs the
  boundary. The split keeps the boundary clean; migration collapses it deliberately, piece by piece.
- **Home as a separate app / an iframe of the Design Library.** Rejected — one app, one data spine; Home
  *incorporates* the components (ADR-0008), it does not embed the showcase.
- **Server-rendered Home over the full pipeline.** Rejected — #1018: the shell must not pay the data cost.

— Trellis 🪴
