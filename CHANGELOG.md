# Changelog

All notable changes to Sprout are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); Sprout adheres to
[Semantic Versioning](https://semver.org) per [ADR-0009](docs/adr/0009-versioning-and-release-policy.md).

Each version is also published as a [GitHub Release](https://github.com/OrangePeachPink/sprout/releases)
(auto-generated tag-to-tag via `.github/release.yml`, then curated). This file is the appendable,
in-repo record; per ADR-0009 §3 it states what changed **per component** (firmware / host / docs).

## [Unreleased]

### v0.7.1 — Wave 1.1: Stabilize _(in progress)_

Point-release on top of `v0.7.0`: fixes, polish, docs, and fleet robustness — no new headline
capability (new features land in `v0.8.0`). Scope tracked in the [`v0.7.1` milestone](https://github.com/OrangePeachPink/sprout/milestone/2).

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

[Unreleased]: https://github.com/OrangePeachPink/sprout/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/OrangePeachPink/sprout/releases/tag/v0.7.0
