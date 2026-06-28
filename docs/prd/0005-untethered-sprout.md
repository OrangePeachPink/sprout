# PRD: Untethered Sprout — standalone operation, dual-mode, tiered onboarding

**Status:** Draft — **ready for review** (maintainer-requested 2026-06-27, from Discussion #243)
**Date:** 2026-06-27
**Owner:** Workflow (synthesis) — binds every lane (Firmware, Data, Design, DX; Trellis advisory)
**Lane:** cross-cutting
**Source:** [Discussion #243](https://github.com/OrangePeachPink/plants/discussions/243) — *"Sprout needs light and
water to grow, not USB cables"*
**Bound ADRs (to be drafted):** dual-mode transport & durability (extends ADR-0006) · capability & sensor matrix ·
network identity & secrets (extends ADR-0015)

---

## Problem

Sprout today assumes a PC: the host logger reads the device over a USB-serial tether, stamps the time, writes the
CSV, and serves the dashboard. That's right for the startup/bench phase — but the destination is a Sprout that
lives on a windowsill or in a greenhouse with **nothing tethered but power**: no PC, no laptop, no cable to a
computer. Done naively, getting there is an overwhelming rewrite.

It isn't — for one reason (Trellis's unlock): **per ADR-0001 the control loop is already headless and
offline-capable — "WiFi is for timekeeping, never the watering decision." So untethered is fundamentally an
*observability + onboarding + identity* problem, not a control problem.** The watering brain ships as-is. That
de-risks the effort and scopes it cleanly.

## Goals

- **Standalone steady-state.** A supported board runs sense → (decide) → act + record with **no PC attached** —
  only power.
- **Dual-mode, one contract.** Tethered stays a first-class mode (dev, experiments, the calibration/characterization
  runners). **One data contract + one control loop across both modes; only transport and presentation differ** —
  never a schema fork.
- **Tiered access (the spine).** A ladder of configs so people start where their parts bin allows:
  - **Tier 0 — Monitor-only.** MCU + ≥1 sensor, no pump/relay/reservoir. Sense → *tell you when to water by hand.*
    Lowest entry bar, cleanest untethered case (no actuation to coordinate) — **this is the shippable MVP.**
  - **Tier 1 — Single-channel watering.** + pump + relay + reservoir.
  - **Tier N — Full.** The current 4-channel build.
- **Approachable onboarding.** Take a board from sensing to online with **no CLI**, in Sprout's voice — the "first
  impression" surface.
- **Honest board support.** ESP32 + the easy Arduino path, with the capability abstraction designed as a
  **community extension point**.

## Non-goals

- **Re-architecting the control loop.** It's already offline-capable; this PRD does not touch the watering decision.
- **Cloud / remote-internet operation.** Local-network and fully-local only; no Sprout-hosted cloud.
- **Supporting every board.** STM Nucleo and Raspberry Pi are **test assets + community-contribution territory**,
  not v1 targets. The long tail is community-grown.
- **Battery / solar power.** "No USB cables" means no *data* tether; **USB/mains power stays.** Battery/solar is a
  later tier.

## What already exists (this builds on it)

- A headless, offline control loop (ADR-0001) + the supervisor as single sample/actuation authority (ADR-0016).
- A **transport-agnostic** telemetry contract (`TELEMETRY_SCHEMA`, `schema_version=2` — fields, not a wire).
- NVS config persistence + a no-hardware-ID identity (#90 / #188).
- The Sprout design system + the **Untethered exploration page** (PR #249, PROPOSED) covering tiers, the sensor
  matrix, captive-portal screens, and offline/online states.

## Requirements

- **R1 — Capability-tiered runtime.** One codebase, **capability-gated** by a per-board descriptor (`has_wifi`,
  ADC pins, channel count, flash/storage). Tier 0 monitor runs on *anything*; WiFi/untethered features light up
  only where the silicon supports them. The descriptor is a **documented extension seam** — an outside contributor
  adds a board without touching core. *(Firmware)*
- **R2 — No-PC onboarding (captive portal).** First WiFi setup with no CLI and no app: the device hosts a temporary
  AP, a catch-all bounces any browser to a config page → pick network + password → saved to NVS → station mode;
  re-opens the AP if WiFi fails. **Works from any browser-capable device** (phone, laptop, tablet — not phone-only).
  *(Firmware + Design + DX)*
- **R3 — "Born wired, lives wireless" firmware delivery.** The first flash is unavoidably wired (you can't OTA a
  blank board), but it must **not** require the Arduino IDE: a **web-flasher** path (ESP Web Tools on ESP32) — plug
  USB, open a page, click Install. Every flash after is **OTA over WiFi**. The "what you need" matrix must state the
  one-time first-flash needs explicitly: **a computer + USB cable + Chrome/Edge** (Web Serial isn't in
  Safari/Firefox/iOS). *(Firmware + DX + Design)*
- **R4 — Source-adapter seam (transport-agnostic data).** The dashboard/analytics read from a **store**; the store
  is fed by whatever transport the board supports (on-device storage + sync · hub-push · device-served).
  `gather_inputs()` / `parse_files()` become **one adapter among several** — built once, every tier/transport plugs
  in unchanged. The **tethered PC is the degenerate hub**, so one model unifies both modes. *(Data)*
- **R5 — Device-owned time.** Untethered, no host stamps `timestamp_utc`. The device must own its timestamp:
  **NTP-on-connect** (WiFi), an optional RTC, or monotonic-uptime + one synced boot-epoch — with a **time-source
  quality flag** in the record so consumers know how the time was set. *(Firmware + Data)*
- **R6 — Durable local storage (capability-honest).** Storage scales with the board: AVR ≈ none (tethered-only
  Tier 0); ESP32 flash ≈ ~a day of buffer (store-and-forward); **+ microSD ≈ months–years** (true standalone
  long-run). The "what you need" matrix states the honest storage expectation per board. *(Firmware + Data)*
- **R7 — Sensor-type seam (capacitive committed; resistive designed-for).** The classifier takes a per-channel
  `sensor_type` profile (it already accepts a per-call cfg) that selects boundary direction (capacitive: higher =
  drier; resistive: inverted), calibration curve, and read strategy (resistive needs power-only-during-read
  excitation and corrodes). **Capacitive is the committed v1 path** (calibrated from the common-cup anchors).
  **Resistive is architecture-ready but *not* v1-committed** — the team has no resistive probes to baseline, so it
  ships nothing calibrated for them; it's a **[Contributors Welcome](../CONTRIBUTORS_WELCOME.md)** item (the seam
  exists; a contributor adds the profile + a calibration run). *(Firmware classifies → Design badges + drift-watch)*
- **R8 — Untethered presentation.** Design surfaces for the untethered states: captive-portal screens, an
  **on-device dashboard** (Tier-0 glance) or a "your Sprout is online" view, and **offline / online / syncing**
  states — all token-faithful, in Sprout's voice. Sync UI drawn **transport-agnostic** so Data's transport choice
  doesn't redraw it. *(Design)*
- **R9 — Network identity & secrets, born-correct.** A device on the home WiFi: WiFi credentials handled safely
  (NVS, never logged), a synthetic hostname/identity (no hardware IDs — extends #188 / ADR-0015), and the on-device
  server with no open ports / no inbound exposure. *(Firmware, extends ADR-0015)*
- **R10 — The "what you need" guide.** A progressive, approachable onboarding artifact — **tier → WiFi-capability →
  sensor-type**, a 3-question guide (not a dense grid), in Sprout's voice, telling someone exactly what their parts
  bin can build (including the first-flash "computer + Chrome + cable, once"). *(DX + Design)*

## Lane split

- **Firmware** — R1 (capability descriptor + extension seam), R2 (captive portal), R3 (web-flash + OTA), R5 (device
  time), R6 (storage), R7 (sensor-type classifier), R9 (identity/secrets).
- **Data** — R4 (source-adapter seam), R5 (time fields + quality flag), R6 (storage/sync model), the schema
  additions.
- **Design** — R2 / R8 / R10 surfaces (captive portal, on-device dashboard, offline/online states, the guide), the
  sensor badges + resistive drift-watch.
- **DX** — R3 / R10 onboarding docs (the no-PC phone-first walkthrough, the board "what you need" matrix).
- **Trellis** — advisory: the staged seams + line-level review of the bound ADRs.
- **Workflow** — this PRD, the ADR + epic decomposition, the gate.

## Acceptance criteria

**MVP milestone — Tier 0 untethered monitor-only:**

- A supported WiFi board (ESP32 first), flashed via the web-flasher, **onboarded to WiFi with no PC/CLI** via the
  captive portal, **self-timestamps**, samples ≥1 sensor, and **serves or syncs** its readings so the dashboard
  shows them — **with no computer attached, only power.**
- The same board with no WiFi or no storage **degrades gracefully** to tethered-only with no code changes
  (capability-gated).
- Both capacitive and resistive `sensor_type` paths exist; capacitive is calibrated, resistive is labeled
  PROVISIONAL.
- The "what you need" guide tells a newcomer exactly what their board + parts can do (including the first-flash
  "computer + Chrome + cable, once").
- **One data contract** the whole way — a Tier-0 untethered reading and a tethered reading are the same schema.

**Later tiers:** Tier 1 (single-channel watering untethered) and Tier N gate on the #191 bench + the actuation line
(ADR-0016 / #94 / #227).

## Decomposition (→ Workflow to slice)

Per Trellis's pre-review, this is **~3 ADRs, not one** — draft them before the epics:

1. **Dual-mode transport & durability** (extends ADR-0006) — the source-adapter seam, the store model,
   store-and-forward / SD / hub / device-served, time ownership. *Decide the durability contract first — it
   collapses the options.*
2. **Capability & sensor matrix** — the per-board descriptor (as an extension point) + the capacitive/resistive
   `sensor_type` model.
3. **Network identity & secrets** (extends ADR-0015) — captive-portal credentials, synthetic hostname,
   no-open-ports.

Then per-lane epics under the PRD, **Tier 0 first** (no actuation surface).

## Open questions

- **Power confirmation:** "no USB cables" = no *data* tether, **USB/mains power stays** (assumed throughout — needs
  the maintainer's explicit confirm).
- **Local-vs-net read priority** (carried from PRD-0002 R9): when both an on-device read and a network pull exist,
  which wins? Deferred, but the transport ADR should leave room.
- **Interior calibration bands:** the common-cup anchors pin the endpoints; the interior ladder needs a controlled
  dry-down (a separate Data run) — affects what "monitor-only tells you" can claim per band.
- **Web-flasher reach for non-ESP32 WiFi-Arduino (Uno R4, Giga):** exact support is Firmware-to-confirm on real
  hardware before we promise it.

## Out of scope / later

- Cloud / internet hosting; battery / solar; the Pi / Uno-Q "host-the-whole-stack" tier (named, deferred);
  supporting every board (community-grown long tail); Tier 1 / N watering untethered (gates on the bench + the
  actuation line).

— Workflow
