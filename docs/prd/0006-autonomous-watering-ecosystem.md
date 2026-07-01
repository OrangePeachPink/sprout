# PRD: Autonomous watering ecosystem — the one-human-touch loop

**Status:** Draft
**Date:** 2026-07-01
**Owner:** Workflow (synthesis) — binds Data, Design, Firmware, DX
**Lane:** cross-cutting
**Source:** maintainer vision, [#443](https://github.com/OrangePeachPink/plants/issues/443) comment (2026-07-01)
**Bound ADRs (to be drafted):** notification model & preferences · basin depletion / runway estimation
**Epic / issues:** #477 (parent) · R1 #478 · R2 #479 · R3 #480 · R4 #481 · R5 #482 · basin sensing #19

---

## Problem

Sprout's job is to keep plants watered without a human hovering. The watering loop itself already does that — it
senses, decides, and (soon) doses on its own. But an automatic waterer that *silently runs its reservoir dry* isn't
autonomous; it's a trap that fails at the worst possible moment, unnoticed, until a plant is already stressed.

The honest model to aim for is a **household robot that earns its keep by asking almost nothing of you** — and asking
it *well*.

Think of a robot **vacuum-mop**, not a vacuum alone. A vacuum-only robot has a big dust bin and can go a *month*
without a human touching it — near-zero tending. A **mop** robot does more (and is simply required on hardwood, which
is most of this house) — but it needs **water basins** filled, emptied, and rinsed to do its job. That maintenance is
the price of the extra capability. Our maintainer's mop robot — *Rosie* — helps enormously, but the experience has a
floor we should aim well above:

- Rosie **surprises** you. She'll get **halfway through a cleaning and yell that her tank is empty** — no warning, no
  runway, at a moment you didn't choose.
- Rosie then **makes dumb decisions** — she keeps trying to mop with a dry basin, doing worse than nothing.

Sprout is the same shape of problem: a capable automation whose one recurring human dependency is **keeping water in
the basin that feeds the pumps.** If we handle that dependency the way Rosie does — silent until empty, then flailing —
we've built another chore that nags. If we handle it well — **predicted, gentle, ahead of need, in Sprout's voice** —
we've built a genuinely happy plant/greenhouse/human ecosystem where the human does *one* small thing, *on their own
schedule,* and everything else just works.

**The onboarding test for this doc:** a future contributor — say, a purple-haired embedded newcomer DX turned into an
engineer, who Veronica befriended over ESP32s and plant watering from half a world away — should be able to read this
and understand *what* the ecosystem is and *why* it's shaped this way, before they touch a line of code.

## Goals

- **One human-gated action.** In steady state the only thing a person must do is **refill the watering basin.**
  Everything else — sensing, deciding, dosing, logging — runs unattended.
- **Never a surprise.** The human learns a refill is coming **before** it's urgent — with enough runway to act on
  *their* schedule (today vs. a couple of days vs. good for a week), not the machine's.
- **A gentle, welcome nudge — never a nag.** One notification, in Sprout's voice, that gives the human everything they
  need. Not noisy, not redundant, not an alarm mid-task. The bar is *"I'm glad it told me,"* not *"make it stop."*
- **Good-enough prediction, honestly labelled.** A runway estimate accurate enough to be *useful* — not a research
  result. "You're good for about a week" beats a false-precision number.
- **The human stays in control of the nudge itself** — able to adjust when, how often, in what voice, and through what
  medium they're told.

## Non-goals

- **Journal-grade forecasting.** We are not modelling evapotranspiration to a publication standard. Good enough that a
  human knows whether to act today, this week, or later — full stop.
- **Removing the human entirely.** The refill *is* the human's job by design (no plumbing into mains water, no
  auto-refill in v1). We make that job predictable and pleasant, not absent.
- **Actuating pumps here.** This PRD is the *ecosystem around* the watering loop — prediction, notification,
  preferences. The pump/relay/safety-chain work lives in #94 and its children; live actuation stays gated on that.
- **Cloud dependency.** Local-first, consistent with the rest of Sprout. A notification medium may *reach out* (email,
  text) but the prediction and the decision are local.

## What already exists (this builds on it)

- **#19** — tank/basin level sensing + refill reminders (the physical sense; hardware now in hand).
- **#94** — the watering loop / actuation MVP (the thing whose reservoir we're protecting).
- **#25** — next-watering predictor (a sibling forecasting surface; the depletion model is its cousin).
- **PRD-0002 / #197** — environmental context & correlation (solar, weather, temp) — the *inputs* the refined
  prediction leans on.
- **The Sprout design system + brand voice** (`docs/design/`) — the voice every notification must speak in.

## Requirements

Numbered so issues and acceptance criteria can reference them. Tagged with the owning lane. **The first three are the
core trunk — straightforward and high-value. The rest are the deep tendrils — worthwhile, but do *not* over-build
them.**

### Core trunk (do this well, it's not hard)

- **R1 — Basin depletion → runway.** From the pump's measured throughput (cycle time × real **L/hr** delivery) and the
  basin's known capacity + current level (#19), estimate **how much runway is left** in human terms: *act today* /
  *a couple of days* / *good for ~a week*. Start simple — pump-cycle accounting is most of the signal. *(Data)*
- **R2 — Gentle refill notification.** When runway crosses an *ahead-of-need* threshold (not on-empty), send **one**
  notification in **Sprout's voice** — welcome, calm, actionable. Never mid-crisis, never repeated into a nag.
  *(Design + Data/host)*
- **R3 — Notification preferences.** The human controls the nudge: **timing** (how much runway triggers it),
  **frequency** (how often it may repeat / snooze), **voice/tone**, and **medium** (see open question). Sensible
  defaults; easy to adjust; changes take effect without a rebuild. *(Design + DX)*

### Deep tendrils (good-enough, not journal-grade — resist gold-plating)

- **R4 — Environmental refinement of the forecast.** Improve the runway estimate with the factors that actually move
  usage: **seasonality, time of day, indoor comfort temp** (A/C + furnace comfort settings), **external temp**, **sun
  exposure**. Leans on PRD-0002/#197. Every added factor must *earn* its complexity against the "today/few-days/week"
  bar — if it doesn't change the human's decision, it's not worth it. *(Data)*
- **R5 — Pump-rate calibration + lift correction.** Measure the pump's *actual* delivered rate (L/hr) rather than
  assuming the datasheet, and correct for **vertical lift / line length** where they materially change throughput.
  Feeds R1's accuracy. Bench work — needs real water + the pump chain. *(Firmware + Data · `needs:hardware`)*

## Acceptance criteria

- [ ] From a known basin capacity + a running pump schedule, the system reports a **runway in human terms** (today /
      few days / ~week) that a person can act on. *(R1)*
- [ ] The runway estimate is a **clearly-labelled derived value** — honest about its confidence, no false precision.
- [ ] A refill nudge fires **ahead of empty**, once, in Sprout's voice — verified *not* to nag or alarm mid-task. *(R2)*
- [ ] The human can change **when / how often / voice / medium** of the nudge without a rebuild, with sane defaults. *(R3)*
- [ ] Adding an environmental factor (R4) demonstrably shifts the runway estimate *and* is shown to change (or
      deliberately not change) the human's act-now decision — i.e. it earned its place. *(R4)*
- [ ] The runway math uses a **measured** pump rate (R5) where hardware allows, with the lift/line caveat documented. *(R5)*

## Open questions

- **Notification medium — needs input.** What should the delivery options be? Candidates: **on-screen** (the served
  dashboard), **in-browser** (push/notification API), **email**, **text/SMS**, **voice**, … others? The maintainer is
  explicitly unsure and wants the lanes (Design + DX especially) to weigh in on the right starting set — one solid
  default plus a small, sane menu beats a pile of half-wired channels.
- **Ahead-of-need threshold defaults.** What runway triggers the *first* nudge, and how does it escalate as runway
  shrinks — without becoming Rosie? (Likely: one calm nudge at "~a few days," a second only if ignored near "today.")
- **Where the environmental factors live** — reuse the #197 env pipeline directly, or a thin depletion-specific model
  fed by it? (Emerges once R1 is real.)
- **Rate correction fidelity** — does vertical-lift / line-length correction actually matter at our scale, or is the
  measured flat L/hr enough? (Answer at the bench, R5.)

## Out of scope / later

- **Auto-refill / mains-water plumbing.** The human refill is the design; automating it away is a different product.
- **Multi-basin / multi-zone reservoirs.** One basin feeding the pumps for now.
- **Cross-device fleet notification routing** (which of the #448 monitored plants triggered a nudge) — layers on once
  both this and #448 exist.
