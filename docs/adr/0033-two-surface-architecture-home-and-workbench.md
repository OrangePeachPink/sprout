# ADR-0033 — Two-surface architecture: Home (the user surface) + Workbench (the instrument)

**Status:** Proposed — *drafted by Trellis (2026-07-12) **before** the #1039 grill, which amends + ratifies its
Round 1. This draft frames the grill's structural questions; it is **not** Accepted here — V1 (ADR class), it
lands via the maintainer after the grill.*
**Date:** 2026-07-12
**Owner:** Trellis (architecture) — the surface structure + the honesty seam. Design-QA builds the surfaces
(#875); Data provides the seams (no firmware change, #875/INCORPORATION.md).
**Lane:** architecture (cross-lane: Design-QA · Data)
**Extends:** [ADR-0008](0008-design-system-v3-personality-layer.md) (the mark / mood / voice this surface places)
· [ADR-0032](0032-github-pages-design-library-serving.md) (design-library serving). Realizes the #875 finding.
**Relates:** #1044 (this) · #875 (the Voice UI epic) · #1039 (the grill that ratifies) · #1018 (shell-first
serving) · #1041 (the v0.7.3 plan) · [ADR-0004](0004-design-system.md) / [ADR-0006](0006-data-architecture.md) /
[ADR-0007](0007-brand-guidelines.md) (honesty law + the character↔instrument boundary) ·
[ADR-0028](0028-optional-peripherals-doctrine.md) (absence is first-class)

---

## Context

We designed the product first — brand, voice, character, motion, onboarding — and then shipped only the
**instrument** (logs, capture, calibration, integrity, diagnostics). #875's finding: the app has a debugging
dashboard, but it has **never had a user surface**. v0.7.3 builds the designed surface now, *before* Predict
(0.8.0) and Water (0.9.0), so those layers inherit the voice, brand, and honesty framing instead of bolting them
on later.

So the app grows a **second surface.** This ADR fixes the **structure** — what the surfaces are, how honesty
applies to each, how you move between them, what serves first-run, how they are served — so every tracer bullet
(#875 T1–T6) builds against a ratified frame. The grill (#1039 Round 1) rules the UX *within* that frame; where a
choice is the grill's, this draft presents it as a **fork with a Trellis lean**, not a decree.

## Decision (proposed — the grill amends + ratifies)

### 1. Two surfaces, one app, one honest data spine

- **Home — the user surface (designed).** The plant owner's front door: the living mark (`<sprout-mark>`), mood,
  first-person voice, the single-plant concept hero (name · mood word · calibrated band · RAW + a *labelled*
  relative index · the seven-band ladder with position · a one-day soil-signal sparkline · local time),
  onboarding. It answers *"who needs water, at a glance."*
- **Workbench — the instrument surface (kept).** Today's dashboard — Monitor · Capture · Lab · Diagnostics —
  unchanged in function: dense readouts, calibration, integrity, provenance, experiment capture. The
  development / operator surface, preserved.
- **One data spine.** Both surfaces read the **same** parsed telemetry (`parse_v1` → `build_context`). Home is not
  a different *truth* — it is a different *presentation* of the same numbers. No surface holds data the other
  cannot reach.

### 2. The honesty law applies to BOTH surfaces — the character↔instrument boundary IS the honesty seam

This section is the ADR's spine. Home is friendly; **friendliness is not license to soften or fabricate.**

- **Mood is 1:1 from the calibrated band, never the index** (ADR-0007 / 0008). Sprout's mood word, voice line, and
  mark colour are a faithful *rendering* of `mood-band-map.json` — the character restates the honest band, it does
  not make a new claim.
- **Character layers onto the instrument, never restyling it** (ADR-0008). No character copy inside dense
  readouts; no mood word standing in for a number. The two-surface split **makes this boundary structural** —
  character lives on Home, the instrument on the Workbench.
- **Raw + band = truth; the 0–100 is a *labelled* relative index; absence is first-class** (ADR-0004 / 0006 /
  0028) — on Home too. Home leads with mood + band, and the honest raw / index / calibration-confidence is always
  one step away (the plant's instrument detail, on the Workbench). Home never shows an invented "% watered."
- **Alarms are earned; absence is not an alarm** (ADR-0028, T6). Untethered / asleep / empty states render with
  character but never fabricate urgency — a sensorless plant reads *"alive, not probed,"* never *"in distress."*
- **Provisional stays provisional** (ADR-0022). A board on `board-cal` / uncalibrated bands keeps its honest
  provisional badge inside Home's friendly framing — the mood reflects a *provisional* band, labelled as such.

### 3. Navigation contract (structure; the grill rules the exact affordance)

- **Home is the front door; the Workbench is reachable *from* it, never hidden.** "Tuck the workbench behind it"
  (#875) means Home is default and primary while the Workbench is one deliberate step away and always reachable —
  honesty means we do not conceal the instrument.
- The four current tabs (Monitor / Capture / Lab / Diagnostics) live **under** the Workbench. Whether any
  single-plant view is *promoted* onto Home is a grill call (fork 4).
- **Fork 1 (grill R1) — the affordance:** a persistent top-level switch (Home ⇄ Workbench) · a menu entry · a
  per-plant *"details →"* deep-link into the Workbench. **Trellis lean:** a persistent switch **plus** the existing
  per-plant *"details →"* landing in the Workbench single-plant view.

### 4. First-run landing (structure; the grill rules)

- **First run → onboarding** (T5: *Hi, I'm Sprout → plug in your probe → name your probes → you're set*), handing
  into the registry tab (#921). A never-configured app (no `config/devices.local.json`) **is** a first-run.
- **Returning user → Home** — a configured app lands on the user surface, not the instrument.
- **Fork 2 (grill R1) — returning-user default:** always-Home · remember-last-surface · Home-unless-deep-linked.
  **Trellis lean:** always-Home (the user surface is the front door by definition; the Workbench is entered
  deliberately).

### 5. Serving / template structure — shell-first (the #1018 fix is a structural requirement)

- **The served HTML is a fast static shell; data hydrates client-side.** Today `/` runs the full ~10 s analytics
  pipeline *server-side* just to emit the document (#1018) — a Home landing must **not** pay the Monitor's 7-day
  context assembly. The shell serves instantly; each surface fetches its own data async (Home fetches an
  at-a-glance summary; a Workbench tab fetches its dense payload on demand). This is binding regardless of the
  routing model below.
- **Fork 5 (grill / engineering R1) — the routing model:**
  - **A — one shell, client-routed surfaces:** one served HTML; Home + Workbench are client-rendered views over
    shared JS; one origin, one boot. The current tab switch (pure `style.display`, zero fetch) extends naturally.
  - **B — two server routes** (`/` = Home, `/workbench`): each a lightweight shell; cleaner isolation, two boots.
  - **Trellis lean: A.** It matches the existing single-page tab model, keeps **one** incorporation of the
    design-library components (ADR-0008), and lets #1018's decouple-shell-from-pipeline fix apply once, to one
    shell. Either way the binding requirement is the same: **no surface pays another surface's data cost to
    render.**
- **Design-library incorporation (ADR-0008 / ADR-0032).** Home *places* the built-but-never-placed components
  (`sprout-mark.js`, `sprout-motion.css`, `voice-strings.json`, `mood-band-map.json`) per #875/INCORPORATION.md,
  incorporated into the local served app (`serve.py`) under the same vanilla-host contract as the Workbench
  (ADR-0004). The Pages-served Design Library (ADR-0032) stays the **source / showcase**; the app **incorporates**
  it — it does not iframe or link out to it.

## Consequences

- Every #875 tracer bullet (T1–T6) builds against a **ratified two-surface frame**; the grill rules UX inside it,
  not structure — the v0.7.2 pattern (contracts first → parallel V2 building).
- The character↔instrument boundary becomes **structural** (the surface line), so honesty cannot erode into the
  friendly surface. The #875 finding's fix is load-bearing, not cosmetic.
- Predict (0.8.0) and Water (0.9.0) **inherit** the surface: a forecast or a pump status is a Home hero element
  *and* a Workbench readout from day one, not a retrofit.
- Shell-first serving resolves #1018 as a structural side effect and sets the pattern for every future surface.
- The Workbench is preserved intact — no regression to the instrument the operator relies on.

## The forks the grill rules (Round 1 map — this draft frames them)

1. Navigation affordance (§3) — persistent switch vs menu vs per-plant deep-link. *Lean: persistent switch + per-plant details→.*
2. Returning-user default landing (§4) — always-Home vs remember-last vs Home-unless-deep-linked. *Lean: always-Home.*
3. What Home shows per plant at a glance (§1 concept hero) — the card's exact contents (Design owns; grill rules).
4. Where the Workbench lives + what it keeps (§3) — all four tabs under Workbench, or promote a single-plant view to Home.
5. Serving model (§5) — A (one shell, client-routed) vs B (two routes); both shell-first. *Lean: A.*
6. Which surface serves first-run (§4) — onboarding-then-Home. *Lean: as drafted.*

## Rejected / not-chosen

- **Restyle the one dashboard with character ("just make it friendlier").** Rejected — it violates ADR-0008's
  "character layers onto the instrument, never restyling it," puts mood copy inside dense readouts, and blurs the
  honesty seam. Two surfaces keep the boundary clean.
- **Home as a separate app / an iframe of the Design Library.** Rejected — one app, one data spine, one honesty
  law; Home *incorporates* the components (ADR-0008), it does not embed the showcase.
- **Server-rendered Home over the full pipeline.** Rejected — #1018: the shell must not pay the data cost; Home
  hydrates async.

— Trellis 🪴
