# Changelog

All notable changes to Sprout are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); Sprout adheres to
[Semantic Versioning](https://semver.org) per [ADR-0009](docs/adr/0009-versioning-and-release-policy.md).

Each version is also published as a [GitHub Release](https://github.com/OrangePeachPink/sprout/releases)
(auto-generated tag-to-tag via `.github/release.yml`, then curated). This file is the appendable,
in-repo record; per ADR-0009 §3 it states what changed **per component** (firmware / host / docs).

## [Unreleased]

_Next cycle: v0.8.0 "Predict" — planning packet #877._

## [0.7.3] — 2026-07-19 — Monitor: Sprout Gets a Voice

**The surface we designed first is now the product** — the full curated notes live on the
[release](https://github.com/OrangePeachPink/sprout/releases/tag/v0.7.3).

**Firmware**

- The ratified band ladder (the one flash-affecting change): all seven levels are in-soil moods,
  boundaries measured on a six-day in-situ dry-down and maintainer-ratified (ADR-0035 Accepted);
  the coincident water-anchor rule.
- Native suites grew: band-partition invariants (fixture-driven, ratification-ready) and the
  dose-control simulation (Epic #410·C, sim-only — not linked into the shipped build).

**Host / dashboard**

- The production Home + hero (two-surface architecture, ADR-0033 Accepted): the card grid in
  Sprout's voice, most-thirsty first; the Workbench ("Classic Sprout") one click behind.
- The pulse delivered twice: the hero histogram and the segment-bound sparkline.
- The voice pool: event-free variants per mood + `{ago}` templates; one-tap "Glug glug" manual
  watering with honest MANUAL/DETECTED provenance; the 14d sawtooth-finder window.
- The full creative palette (chrome aliases, 12-material identity register, chart-series pass +
  focus-tap); in-app pot-size and location editing; shell route coverage.

**Docs / process / community**

- ADR-0033 + ADR-0035 Accepted; the color-roles charter and BRAND.md carry the grill canon
  (tagline four-slot, register rule, one band vocabulary, absence patterns).
- The audience-scoped instruction-file split (#1125) with the fork-PR credit-protection CI;
  CONTRIBUTORS.md names our first three community contributors.
- Trust Your Sensor live on Pages; the front door portfolio-pass optimal.
- New tooling: the voice-guard, the per-hook CI job summary, the board-hygiene lint.

## [0.7.2] — 2026-07-12 — the monitor you can trust

Mirrored from the [published release](https://github.com/OrangePeachPink/sprout/releases/tag/v0.7.2)
(this file lagged two cuts; healed at the v0.7.3 cut from the published record).

**Firmware**

- Per-channel calibration tiers live on the wire; ed25519 release signing (first live fire);
  the web flasher offers only bench-proven images.

**Host / dashboard**

- The self-supervising collection worker (restarts on any death, refuses loudly, plain-word
  failure logs); the recording state never misrepresented.
- Plants & Sensors: the fleet registry tab — add/map/pause/delete with review-then-save and
  deletion receipts; plant-first sensor picker.
- Calibration chips honest per tier; opt-in environment overlay (context, not cause); era-aware
  provenance; the 15-second dashboard slowness diagnosed to ~3.

## [0.7.1] — 2026-07-10 — Wave 1.1: Stabilize

Mirrored from the [published release](https://github.com/OrangePeachPink/sprout/releases/tag/v0.7.1).

- Point-release on v0.7.0: fixes, polish, docs, and fleet robustness; no new headline capability.
  Full notes on the release.

## [0.7.0] — 2026-07-04 — Wave 1: Monitor

**The plants are online.** Sprout's first release: eleven windowsill plants monitored by WiFi-only
ESP32s — one power cord each, zero data cables — all live in one dashboard, logged around the clock.

### Firmware

- Untethered operation: boards run on brick power and serve their own telemetry over WiFi; no serial
  tether required at runtime.
- Identity model (ADR-0027): minted stable device IDs, channel≠probe split, NVS-persisted across reflash.
- Optional-peripherals doctrine (ADR-0028): minimum Sprout = 1 MCU + 1 soil sensor is complete; every
  peripheral optional, absence first-class.

### Host / dashboard

- One served dashboard with a four-destination IA (Monitor / Capture / Lab / Diagnostics & Logs).
- Honest data surface: raw ADC + band words are truth; percent is only ever a labelled index; canonical
  moods bound to the band map; device-scoped calibration ladder; live-by-default.
- Fleet collection: WiFi pollers + serial under one Start; device registry as the authoritative name home.
- First closed prediction loop: a blind drydown forecast scored 7/8 against install-night actuals.

### Docs / process

- Versioning & release policy (ADR-0009), the wave↔version release train, and this first release.
- Wave-1 install record and closeout (#584).

### Known scope (carried, not hidden)

- C5 bands are provisional until per-board ADC calibration (Wave 2, #443).
- The `!wedge` safety check was not re-run at install (#599).
- The yellow C5 spare needs a recovery re-flash before redeploy.

[Unreleased]: https://github.com/OrangePeachPink/sprout/compare/v0.7.3...HEAD
[0.7.3]: https://github.com/OrangePeachPink/sprout/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/OrangePeachPink/sprout/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/OrangePeachPink/sprout/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/OrangePeachPink/sprout/releases/tag/v0.7.0
