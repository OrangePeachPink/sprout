# ADR-0033 — Home + Classic Sprout: a converging two-surface architecture (one designed product)

**Status:** Accepted — *amended and ratified by the #1039 grill (Round 1, 2026-07-18); Trellis folded the rulings
from the Proposed draft (2026-07-12, #1049). V1 — lands via the maintainer; **#1044 closes on this.** Written to
the 2026-07-18 session canon (#1099): **the plant speaks for itself**; canonical formula `raw + band = the
reading`.*
**Date:** 2026-07-12 (grill-amended 2026-07-18)
**Owner:** Trellis (architecture) — the surface structure + the convergence model. Design-QA builds the surfaces
(#875); Data provides the seams (no firmware change, #875/INCORPORATION.md).
**Lane:** architecture (cross-lane: Design-QA · Data)
**Extends:** [ADR-0008](0008-design-system-v3-personality-layer.md) (the mark / mood / voice this surface places)
· [ADR-0032](0032-github-pages-design-library-serving.md) (design-library serving). Realizes the #875 finding.
**Relates:** #1044 (this) · #875 (the Voice UI epic) · #1039 (the grill that ratified it) · #1099 (the canon wash)
· #1018 (shell-first serving) · #1041 (the v0.7.3 plan) · [ADR-0004](0004-design-system.md) /
[ADR-0006](0006-data-architecture.md) / [ADR-0007](0007-brand-guidelines.md) (the data model + the
character↔instrument boundary) · [ADR-0028](0028-optional-peripherals-doctrine.md) (absence is first-class)

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
    #7 on a shelf of 24 fails the product.
  - **State** — mood (the mood **colour is the card's key frame**, per the Q2 colour-roles charter — the frame is
    the plant's *current* state, never a fixed identity colour) + the calibrated **band** word + a **first-person
    line.**
  - **Water story** — **last watered** (a **detected** watering event — the raw-cliff signature — not merely a
    logged one) + **next need** (the forecast-boundary helper).
  - Raw numbers stay Classic-Sprout-side (§2).
- **Absence is first-class** (ADR-0028): missing pieces render as graceful absence — the card ships **thin**
  rather than waiting for full data. Two pieces are not yet live and render as placeholders now: **last-watered**
  (the detected-watering-event stream builds in 0.8.0 — the classifier family, reading the same substrate as
  #822 / #25) and **photo** (a new local-only registry field — EXIF-strip on any future export/share path, since
  photos carry GPS).
- **v0.7.3 Home tracer scope** (grill 1c): the living mark + a greeting + the ruled card grid.

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
- **Provisional stays provisional** (ADR-0022). A board on `board-cal` / uncalibrated bands keeps its provisional
  badge inside Home's friendly framing — the mood reflects a *provisional* band, labelled as such.

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

## The migration backlog + one open question for the morning grill

Classic Sprout's contents **are** the migration backlog (§2). **Open question for the morning session:** should
that ledger — the piece-by-piece list of what still needs migrating — live as a **section in this ADR** or as a
**standing issue / board view**? *Trellis lean: a standing board view* — the backlog is living and changes as
pieces retire, which a board tracks better than a static ADR section; this ADR records the *architecture* and the
*convergence commitment*, and points at the ledger wherever it lands. Flagged for the maintainer to rule.

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
