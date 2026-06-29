# ADR-0019 — Capability & sensor matrix (untethered)

**Status:** Proposed — *drafted by Workflow from Discussion #243 + the Firmware lane's take;
Trellis-revised 2026-06-28 (one-codebase wording + sensor-provenance requirement, per the #285 review);
awaiting maintainer ratification + Firmware-lane confirm (#269)*
**Date:** 2026-06-27
**Owner:** Firmware lane / architecture
**Lane:** firmware (cross-lane: Design badges)
**Relates:** [PRD-0005](../prd/0005-untethered-sprout.md) R1 / R7 ·
[CONTRIBUTORS_WELCOME](../CONTRIBUTORS_WELCOME.md) · epic #267 · slice #269

---

## Context

PRD-0005 supports a tier ladder (monitor-only → watering → full) across a heterogeneous board fleet (ESP32 +
the easy Arduino path; AVR has no WiFi, the WiFi Arduino boards and ESP32 do; storage ranges from none to a microSD
card). It must also support both **capacitive** (committed) and **resistive** (designed-for, not core-committed)
probes. Doing this as one codebase — not a fork per board — needs a clean way to express what a board *can* do,
and what a *sensor* needs. The maintainer's scope call: ESP32 + Arduino are the starting lanes; other boards are
a **community extension point**, not a v1 fork.

## Decision

**A per-board *capability descriptor* gates features, and a per-channel *sensor-type profile* selects the
read / calibration behavior — both designed as documented extension seams so a contributor adds a board or a
sensor without touching core.** Concretely:

1. **Capability descriptor (per board).** A small record — `has_wifi`, ADC pins / resolution, channel count,
   storage kind / size — selected per build env and/or detected at runtime (`getChipModel`, building on #188).
   Features **gate on the descriptor**: Tier-0 monitor runs on *anything*; WiFi / untethered features light up
   only where `has_wifi`. One codebase, capability-gated — not two products.
2. **The descriptor is the contributor extension point.** Adding a board = **adding a descriptor entry (+ a
   sensor profile)**, documented, no core edit. The starting lanes ship ESP32 + the easy Arduino path;
   everything else (STM Nucleo, the wider Arduino family, the host-the-stack tier) is
   [Contributors Welcome](../CONTRIBUTORS_WELCOME.md) — designed-for, reviewed on hardware where the maintainer
   has it.
3. **Sensor-type profile (per channel).** A `sensor_type` profile selects **boundary direction** (capacitive:
   higher = drier; resistive: inverted), **calibration curve**, and **read strategy** (resistive needs
   power-only-during-read excitation, and corrodes). The classifier already accepts a per-call cfg, so the seam
   is cheap. **Capacitive is the committed v1 path** (calibrated from the common-cup anchors, ADR-0006 §A2).
   **Resistive is architecture-ready but not v1-committed** — no probes to baseline, so it ships nothing
   calibrated; the seam exists for a contributor. **Provenance requirement:** `sensor_type` + profile-version +
   calibration-source must be **logged in the telemetry provenance** (row/header) so a probe's type or calibration
   change never makes old logs ambiguous — carried by schema v2 (#300), ties to #295 (cal bounds in the header).

### Rejected alternatives

- **A build per board / per sensor.** Rejected: combinatorial fork; the whole point is one codebase that
  degrades by capability.
- **Runtime-only detection (no descriptor).** Rejected: some capabilities (channel wiring, storage) can't be
  reliably auto-detected; an explicit descriptor is also the contributor seam. Runtime detection *augments* it.
- **Commit to resistive now.** Rejected: with no resistive probes to baseline, we'd ship uncalibrated claims.
  Designed-for + Contributors-Welcome is the honest posture.

## Consequences

- One **codebase**, **capability-gated per build target** (not one binary shared across silicon — ESP32 / AVR /
  WiFi-Arduino build per target); Tier-0 monitor is the universal floor.
- The board matrix grows by **community PRs against a documented seam**, not core forks — the public-ready
  posture.
- Capacitive ships calibrated; **resistive ships as a present-but-uncommitted seam** (PROVISIONAL), tracked in
  Contributors Welcome.
- Design reads the descriptor + `sensor_type` for its tier / sensor **badges** (PRD-0005 R8); the resistive
  drift-watch surface is Design's.

## Revisit triggers

- **A contributor lands a non-ESP32 / Arduino board:** confirm the descriptor seam held (no core edit); tighten
  the doc if it didn't.
- **Resistive probes come in hand:** the seam gets a calibration run and resistive moves from PROVISIONAL toward
  committed — revisit the profile, not this seam.
- **A second sensor *kind* entirely** (e.g. on-device environmental, PRD-0002): revisit whether `sensor_type`
  generalizes or needs a sibling.
