# Contributors Welcome

A living list of areas where **outside contributions are especially welcome** — things the architecture is
*designed to support* but the core team deliberately **does not commit to** (often because we can't test them
ourselves, or they're a long tail better grown by the community than owned by a small team).

> **Status:** seeded pre-release. At public launch, each item here becomes a labeled `help wanted` /
> `good first issue` GitHub issue. Until then this is the durable idea list — **add to it as ideas surface** so
> they don't escape memory.

## How this works

- We design the **seams** so these are drop-in, not core rewrites — e.g. the board-capability descriptor
  (PRD-0005 R1) and the per-channel `sensor_type` profile (PRD-0005 R7).
- A contributor adds support for the thing they love in *their* PR; the maintainer reviews it (and can validate
  on real hardware where she has it).
- **We promise only what we can test.** Everything here is explicitly contributor territory, not a core-team
  deliverable.

## The list

### Hardware

- **Resistive soil-moisture sensors.** The classifier is built around a per-channel `sensor_type` profile
  (PRD-0005 R7), so resistive support is an architecture-ready seam. **Not core-committed** — the team has no
  resistive probes to baseline, so we ship nothing calibrated for them. A contributor with resistive sensors can
  add the profile + a calibration run. *(They read inverted vs. capacitive, corrode via electrolysis, and need
  power-only-during-read excitation — so the seam is real work, not a flag flip.)*
- **Boards beyond the starting lanes (ESP32 + the easy Arduino path).** The board-capability descriptor
  (PRD-0005 R1) is a documented extension point — add a board by adding a descriptor + profile, no core edit.
  Surfaced candidates: STM Nucleo, the wider Arduino family (Mega / Giga / Uno R4 WiFi / Uno Q), and whatever's
  in *your* drawer.
- **The "host-the-whole-stack" tier (Linux-class boards: Raspberry Pi, Arduino Uno Q).** A different shape from
  the MCU-flash targets — a single board that runs the dashboard + logger *itself*. Named and deferred in
  PRD-0005; a strong contributor project.

## Adding to this list

Surfaced an idea in a discussion that's "designed-for, not core-committed"? **Add a bullet here and sign it.**
When we launch, Workflow converts these into labeled `help wanted` issues so contributors can grab them.
