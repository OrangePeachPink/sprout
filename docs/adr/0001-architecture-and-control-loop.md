# ADR-0001 — Architecture & control loop

**Status:** Proposed (pending Maintainer review)
**Date:** 2026-06-24
**Owner:** Firmware lane / architecture
**Lane:** architecture / firmware
**Supersedes:** the archived v0 record ([`archive/sprout-v0-architecture.md`](archive/sprout-v0-architecture.md))

---

## Context

Sprout is a window-ledge plant waterer for hardy, non-fussy plants. The real problem it solves is
**consistency** — these plants do fine with regular water and suffer mainly from being forgotten.
Guiding values: boring-first, baseline-first, local-first, and "a small thing that works and is honest
about what it doesn't know."

It began as a single-board prototype (the archived v0 record). It has since grown into a multi-part
system — embedded firmware, a host-side logging pipeline, an analytics/forecast dashboard, and a design
system — built across a few focused lanes. **This ADR records the firmware and control architecture
only.** The host telemetry schema, calibration, and data-quality model are a separate, data-owned
decision (ADR-0006); this record points at that boundary rather than crossing it.

One honesty note up front, because the v0 record reads differently: v0 described pumps, a relay board,
and a status display as Phase-1 decisions. The firmware that actually ships today is **read-only** — it
senses and reports, and **does not actuate.** This ADR is careful to separate what is **built today**
from what is **designed but not yet wired**, so a new contributor can trust it.

## Decision

### Platform & sensing (built)

- **MCU:** a classic ESP32 (ESP-32D class), 3.3 V logic, on-board WiFi. Analog sensing uses **ADC1**
  only — ADC2 is unavailable while WiFi is active.
- **Sensing:** four capacitive soil-moisture probes (TLC555 family), one per channel, on fixed,
  input-only ADC1 pins. **Soil moisture is the only control input** (see "soil-only" below). The pin map
  and tuning live in a central config header (`firmware/include/config.h`).
- **Sampling:** a non-blocking cooperative loop sweeps all four channels on a fixed interval, **one
  channel at a time**, discarding a few reads after each ADC-mux switch for sample-and-hold settling,
  then taking a trimmed-mean burst per channel. No two channels are read concurrently.

### Firmware scope today: read-only telemetry (built)

The firmware **senses, classifies, and reports; it does not actuate.** Each sweep runs every channel's
reading through a moisture **classifier** — a banded state machine with hysteresis/deadband and
confirmation windows, so a band only commits after sustained agreement rather than chattering on noise —
and emits one compact line per sensor over the serial link for the host pipeline to record. The
relay/pump outputs are **defined in config but commented out**: no GPIO drives a pump today.

### The control / observability split (the core principle)

The **control path** (soil → pump; simple, hand-tunable) is **decoupled** from the **observability
path** (serial telemetry → host logger → analytics/dashboard). Observability can grow — and has grown
substantially — **without ever touching the control loop.** This separation is the single most
important architectural decision, and it is more true now than at v0: the observability path is richly
built while the control path remains a small, isolated module.

### The control loop: designed, not yet wired

When actuation is enabled, the loop is **closed-loop on soil moisture only**, per channel:

- a per-channel "dryish" threshold triggers a **fixed-duration pump dose**, empirically tuned over the
  first few cycles; the loop is **self-correcting** — an imperfect dose is corrected on the next check;
- a **slow check cadence** provides the post-water **settle / lock-out for free** (water takes minutes
  to reach the probe; re-reading too soon would over-water);
- **safety interlocks:** one pump at a time; a maximum pump run-time cap; a **health/spread veto** so a
  floating or disconnected probe (which can read a plausible "dry") cannot trip a pump; a
  **no-improvement fault** that latches a channel whose dose doesn't move the reading; a soak lock-out;
  and a planned low-reservoir cutoff.

The supervisor that implements this — the irrigation state machine and its veto / latch / fault logic —
**exists in the firmware libraries and is exercised by host-run unit tests**, but is **not wired into
the running firmware.** The device stays read-only until calibration and the safety reconciliation land.

### Why soil-moisture-only control

Environmental conditions (temperature, humidity, light) are deliberately **not** in the control loop.
Soil moisture is the **integrated output** of all of them, so measuring the inputs to *predict* watering
need is redundant when the output is measured directly. Environmental sensors remain a **logging-only,
non-prescriptive** future input — an observability concern, never a control input.

### Module shape & toolchain

- **Config-driven:** pins, thresholds, calibration anchors, and dose times live in the central config
  header — behavior changes are config edits, not logic edits.
- **Framework-agnostic core:** the moisture classifier and the irrigation supervisor are plain C with
  **no Arduino dependencies**, so they compile and run **on the host** for fast unit tests with no board
  and no flash. A thin Arduino `main` wires sampling → classify → emit, and (later) classify → decide →
  actuate.
- **Toolchain:** **PlatformIO** (`esp32dev`, Arduino framework), with the platform and framework
  versions pinned in `platformio.ini` — the firmware's lockfile. Build config lives in-repo; no
  IDE-specific project files.

## Consequences

- The watering behavior stays **small, isolated, and hand-tunable**, and is easy to reason about.
- Logging, analytics, dashboards, and additional zones are **additive** and cannot disturb control.
- Because the control logic is framework-agnostic C, the safety-critical state machine is **verified on
  the host before it ever drives a pump** — actuation is gated behind passing tests plus calibration,
  not flashed hopefully.
- Running **read-only today** means there is **no actuation risk** while sensing and calibration mature;
  enabling the loop is a bounded, well-understood next step rather than an open question.
- The system runs **headless and offline-capable**; WiFi is for timekeeping and (future) notifications,
  never for the watering decision.

## Revisit triggers

- **Control wired (read-only → actuating):** revisit when the supervisor is enabled on hardware —
  confirm thresholds, dose times, and the interlock set against real calibrated channels first.
- **More than four zones:** needs a larger relay board and more ADC channels or an analog multiplexer —
  revisit the sensing/actuation topology.
- **Per-channel calibration lands:** thresholds and band boundaries move from shared placeholders to
  per-probe values — revisit.
- **A second actuator class** (valves, lighting): revisit the control/observability split so new
  actuators stay on the control side without coupling to observability.
- **Environmental sensing ever proposed for the control loop:** a major revisit — it would overturn the
  soil-only principle and must be argued explicitly.
