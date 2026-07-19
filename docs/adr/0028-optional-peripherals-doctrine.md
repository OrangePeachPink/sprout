# ADR-0028 — Optional-peripherals doctrine: the minimum Sprout is complete

**Status:** Accepted — *maintainer-ratified 2026-07-04. Drafted by Trellis from the maintainer's ratified product principle
(stated verbatim on #20, applied on #19). Extends ADR-0019's capability matrix from a technical gating
*mechanism* into the product-experience *doctrine* that governs it. Needed before W2's display architecture
(#20) builds against it.*
**Date:** 2026-07-04
**Owner:** Trellis (architecture) — cross-lane: Firmware (capability descriptor), Design (absence affordance),
Data (calm-empty reads)
**Lane:** architecture
**Extends:** [ADR-0019](0019-capability-and-sensor-matrix.md) (capability & sensor matrix — the *mechanism*) ·
[ADR-0006](0006-data-architecture.md) (raw-first data)
**Relates:** #20 (display / HMI — the first W2 gate) · #19 (tank sensing — sensorless-first application) ·
[ADR-0023](0023-contextual-env-columns.md) (env context already does this) ·
[ADR-0014](0014-operator-control-plane.md) (the served surface is first-class) ·
[ADR-0027](0027-identity-model.md) §4 (capture-time minimum — the same philosophy for identity) · PRD-0005

---

## Context

ADR-0019 established that Sprout is **one capability-gated codebase**: a per-board capability descriptor
(`has_wifi`, channel count, storage…) gates features, and "Tier-0 monitor runs on *anything*." That is the
*mechanism* — how the software expresses what a board can do. It does not yet state the **product principle**
that must govern how absence *feels*.

W2 begins adding peripherals — on-device displays (#20), a tank-level sensor (#19), the env sensors
(SHT45 / AS7263), actuators, a buzzer. Each one risks quietly becoming a *de-facto requirement*: a UI that
assumes a display, a status flow that assumes a tank sensor, an onboarding that implies you need to solder.
That drift is exactly what turns "a hobbyist with one sensor" into a second-class user.

The maintainer ratified the guardrail (verbatim, #20): **"Sprout's minimum viable setup is a microcontroller +
one soil-moisture sensor. Everything beyond that — displays included — is optional enhancement: the
workflow without the peripheral must be first-class, never a degraded experience. No large component /
soldering investment as an entry bar."** This ADR fixes that as doctrine before the W2 peripherals are built.

## Decision

### 1. The minimum viable Sprout is 1 MCU + 1 soil-moisture sensor — and it is *complete*, not a stub

That configuration is a **fully-supported, first-class product**, not a degraded floor you are expected to
grow out of. Everything else — displays, LEDs, buzzer, tank-level sensor, env sensors, RTC, extra channels,
actuators — is **optional enhancement**. "Optional" is load-bearing: the software may never *require* a
peripheral for a core workflow.

### 2. Absence is a first-class path — never an error or a nag

For every feature that *uses* a peripheral, the **without-it path is first-class**: either a real sensorless
equivalent, or an calm-empty state (ADR-0006) — never an error, a broken view, a blocking wall, or a
guilt-tripping "add hardware to continue." An absent capability is *information* ("no display configured";
"tank level: estimated — add a sensor for measured"), presented as an **enhancement invitation**, not a defect.

### 3. Where a sensorless equivalent exists, it is the *primary* path; the sensor is the enhancement

Not merely "works without" — the sensorless path is designed *first* and is the default. Two already-decided
examples this doctrine generalizes:

- **Tank level (#19):** predict from pump-runtime accounting (dispensed volume × pulses), zero added hardware,
  is the **primary** path; a physical level sensor is the optional precision upgrade.
- **Env context (ADR-0023):** no plant-local sensor → calm-empty `context_source=none`; the SHT45 is one
  optional instance of a tier, never assumed present.

### 4. The authoritative status surface is the served dashboard, not any on-device display (the #20 gate)

Per ADR-0014, the operator's first-class status surface is the **served dashboard** — headless, over
WiFi / localhost. An on-device OLED / e-ink / LED is a **redundant glance enhancement**: it may never be the
*only* way to see state, and the product is complete with none. This is the specific architectural constraint #20's
display build must honor — design the glance surface as a *projection* of state that already exists
headlessly, never as the state's home.

### 5. The capability descriptor (ADR-0019) is the single source of what is present; every capability defaults *absent*

Readers branch on the descriptor, and **the absent branch is the first-class one** — it is the minimum
config, the most common real deployment. A capability is present only when the descriptor says so; nothing is
assumed. This makes "minimum Sprout" the default the code is written *for*, not an afterthought bolted beside
a rich-hardware happy path.

### 6. No entry bar

Onboarding a minimum Sprout requires **no soldering, no display, no extra components, no bench** — one MCU,
one sensor, flash (web-flasher #271 / factory image), done. Any peripheral is an additive, later, optional
step. The entry story is "a busy person with one plant," and the architecture owes that person a *complete*
product, not a starter kit with visible missing slots.

## Consequences

- Every W2 peripheral (display #20, tank sensor #19, env, actuators, HMI) is built **"works fully without me"
  first** — the peripheral layers on, it never gates a core workflow.
- ADR-0019's capability matrix gains its governing doctrine: **absent = first-class**, not "degraded floor."
- This is the same principle ADR-0027 §4 applies to *identity* (capture-time minimum = `device_uuid +
  channel + value`; all bindings optional and retroactive) and ADR-0023 applies to *env context* (no sensor →
  calm-empty). One product philosophy, now named across the three.
- Design gains a hard rule: an absent-capability surface reads as an **enhancement invitation**, never an
  error, a nag, or an empty-broken state.
- Raw-first data (ADR-0006) is reinforced: absence is recorded plainly (descriptor `has_X=false`) and read
  calm-empty, never invented into a value — and never into a fabricated *requirement*.

## Rejected alternatives

- **"Peripherals are just Tier-N features that gate on capability" (ADR-0019 alone, no doctrine).** Rejected
  as insufficient: gating makes absence *work*, but does not stop absence from *feeling* degraded — a UI can
  technically run headless while treating headless as broken. The doctrine is the missing product constraint.
- **A "recommended" hardware bill the minimum falls short of.** Rejected: it re-installs the entry bar the
  principle exists to remove. The minimum is complete, not deficient.
- **Requiring a display for the local HMI story (#20).** Rejected: makes the served dashboard secondary and
  the physical panel primary — inverts ADR-0014 and adds a soldering entry bar.

## Open (routed)

- **Firmware:** the capability descriptor already carries `has_wifi` etc. (ADR-0019); add peripheral-presence
  flags (`has_display`, `has_tank_sensor`, `has_env`, …) as they arrive, each defaulting **absent**. Runtime
  detection augments the descriptor; absent is the default.
- **Design:** the absence affordance — an "add optional X" surface that reads as invitation, never error /
  nag — is a design-system decision; the #20 display work is the first to need it.
- **Per-peripheral (W2):** each peripheral issue confirms its first-class without-it path (sensorless
  equivalent or calm-empty) *before* build. #20 (display → served-dashboard-authoritative) and #19 (tank →
  predict-first) are the first two, already aligned.

— Trellis 🪴
