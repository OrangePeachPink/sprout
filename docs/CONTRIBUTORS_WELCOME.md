# Contributors Welcome

Sprout is small on purpose — and that means there's room for *you*. You don't have to be on the core team to
leave a real mark here. This page lists the places where an outside contribution is **especially** welcome, and
where we've built the seams so your work drops in cleanly instead of fighting the core.

> **You're welcome here whether or not you've sent a pull request before.** New to the flow? Start with
> [your first contribution](contributing/your-first-pr.md), then come back and pick something below.

## What's on this page (and what's not)

These are things the architecture is *designed to support* but the core team **does not commit to** — usually
because we can't test them ourselves (no hardware to baseline), or they're a long tail better grown by the
community than owned by a small team.

**We promise only what we can test.** Everything here is explicitly contributor territory, not a core-team
deliverable — which is exactly why your PR matters.

> **Status:** the repo is public and open to contributions **right now** — outside contributors have
> already landed merged PRs here. What's still ahead is the public *launch push*, not your ability to
> take part. These live as a durable idea list rather than a wall of labeled issues because the list
> outlives any one milestone — but if you want one turned into a real, grabbable issue, say so on it
> and we'll label it.

## How it works

1. **Find your area** below — something you have the hardware for, or the itch to build.
2. **Read the seam.** We design extension points so these are drop-ins, not core rewrites — the
   board-capability descriptor (PRD-0005 R1) and the per-channel `sensor_type` profile (PRD-0005 R7). Each item
   names its seam, so you know exactly where you're plugging in.
3. **Build it in your PR.** Add support for the thing you love; the maintainer reviews it (and validates on real
   hardware where she has it).
4. **It ships when it's proven** — no gate-keeping beyond "does it work, and does it do what it says?"

## Where you can help

### Hardware

- **Resistive soil-moisture sensors.**
  - *Seam:* the per-channel `sensor_type` profile (PRD-0005 R7) — resistive is an architecture-ready slot.
  - *Why it's yours:* the team has no resistive probes to baseline, so we ship nothing calibrated for them.
  - *How to start:* add a `resistive` profile + a calibration run from your own probes. (Real work, not a flag
    flip — they read inverted vs. capacitive, corrode via electrolysis, and need power-only-during-read
    excitation. The [trust-your-sensor guide](user/trust-your-sensor.md) has the background.)
- **Boards beyond the starting lanes** (we start with ESP32 + the easy Arduino path).
  - *Seam:* the board-capability descriptor (PRD-0005 R1) — add a board by adding a descriptor + profile, no
    core edit.
  - *How to start:* describe your board's capabilities, drop in the profile, flash, send the PR. Surfaced
    candidates: STM Nucleo, the wider Arduino family (Mega / Giga / Uno R4 WiFi / Uno Q), and whatever's in
    *your* drawer.
- **The "host-the-whole-stack" tier** (Linux-class boards: Raspberry Pi, Arduino Uno Q).
  - *Seam:* a different shape from the MCU-flash targets — one board that runs the dashboard + logger *itself*.
  - *How to start:* it's a strong standalone project (named and deferred in PRD-0005) — open a discussion first
    so we can shape it with you.

## Add to this list (and sign it)

Surfaced a "designed-for, not core-committed" idea in a discussion? **Add a bullet here and sign it** — name the
seam if you know it, plus a one-line "how to start." This page is meant to *grow*: the ideas that escaped memory
belong here too. Ask and we'll label one `help wanted` so you can grab it — no need to wait for launch.

## Wear the badge

Landed a PR — or just cheering us on? There's a little **[contributor card](design/brand/contributor-card.png)**
you're welcome to post anywhere you like — there's a [square one](design/brand/contributor-card-square.png) for
Instagram, and light-theme versions too. Zero pressure; it's just here if you're proud of what we're growing. 🌱

*New to contributing? [Your first contribution](contributing/your-first-pr.md) walks the whole flow.*
