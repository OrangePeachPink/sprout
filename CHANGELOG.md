# Changelog

All notable changes to Sprout are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); Sprout adheres to
[Semantic Versioning](https://semver.org) per [ADR-0009](docs/adr/0009-versioning-and-release-policy.md).

Each version is also published as a [GitHub Release](https://github.com/OrangePeachPink/sprout/releases)
(auto-generated tag-to-tag via `.github/release.yml`, then curated). This file is the appendable,
in-repo record; per ADR-0009 §3 it states what changed **per component** (firmware / host / docs).

## [Unreleased]

_Next cycle: v0.8.2._

## [0.8.1] — 2026-07-25 — Architecture hardening, and the Predict delta

**The release that went back for what v0.8.0 named but did not deliver.** A blind eight-track theme
review found that v0.8.0 shipped titled _"Predict"_ with its headline model reaching no surface; the
gap became [PRD-0009](docs/prd/0009-monitor-and-predict.md) and eight of its nine ratified
requirements shipped here. The rest of the release hardened the seams underneath — and found, five
separate times, the same defect class: **a layer correct about the question it asks, silent about the
one nobody wired.**

**Firmware**

- Signed-pull OTA reached hardware: the S3 pull transport orchestrator (fetch → parse → decide →
  gated apply) and the real `fetch_feed`/`esp_ota` bindings, dark by construction (#1284, ADR-0026).
- The feed parser fails closed — a duplicate board class rejects the whole feed; an empty feed offers
  nothing rather than reporting broken.
- The C5's measured board-level cal rails landed, so `open_adc` can fire (#1433).
- The signed classifier step is emitted, making `rate_spike` auditable from the wire (#1434 AC0).
- ADR-0011/0012/0013 moved Proposed → Accepted: status now matches shipped reality (#1460).

**Host / dashboard**

- **The attention model** — one composed state per plant in one place (R11), consumed rather than
  re-minted by everything downstream: the harm level (G2), the calm signal (G3), the post-watering
  hold (G5), and the rule that an untrustworthy reading predicts nothing (R12).
- **The ranked queue** ordered by forecast rather than wetness (R2), with `QUEUE_ORDER is
  attention.RESOLUTION_ORDER` asserted so the queue cannot drift from the word on the card.
- The forecast on the history chart with an unmistakable boundary (R6), and the confidence
  vocabulary in which the interval _is_ the how-sure (R3).
- **Add-a-board, end to end** (#1541): declared devices with pending binding and
  reconcile-on-first-contact, the guided flow, the visual pin map, the board-aware flash handoff,
  connected-hardware enumeration, and adoption for answering-but-unregistered boards.
- The zero state names the real state instead of waiting forever; Stop-server is on Home from the
  first run; the serial lock names its holder and says what to do.
- Sensor health stopped ratcheting: three bare counts became rate gates, dropout cadence is measured
  locally rather than pooled across logging regimes, and an instrument with no readings gets **no
  verdict** rather than a clean bill of health (#1626).
- Classic-surface performance: the wide-window build halved, an RSS-per-request instrument, and
  charts that say when they are frozen rather than going silently stale.

**Docs / process / community**

- **The package flip** — `tools` importable by name; 227 lines of `sys.path` surgery deleted,
  byte-identical output (#1453). Route table extracted from `serve.py`; control-plane hardening riders.
- **Release integrity, walked rather than assumed** (#1346): the §5.1 dry-run seam walk found a
  cut-blocking defect on its first run — the signer could not resolve a draft because `gh` ran before
  `actions/checkout` with no repo context, and would have produced a **second** asset-less release.
- RELEASE_CUT gained the `assets>0` hard gate, the missed-prior-sections check, and **§1.1: the tag is
  the line** — milestone reconciliation in both directions at every cut, with PRs milestoned as a rule.
- The theme-conformance gate: a themed release is not closed until expectation → promise → delivery
  has been asked. Plus the architecture-review cadence, and the contributor-agent contract in
  `AGENTS.md` — attribution, credit, and bot-review provenance, written after a contributor's
  reviewer bot appeared in our threads.
- The collective is a **greenhouse**, not a fleet, on every user surface (#1506).
- A first-time contributor claimed a `good first issue` and opened their PR inside the release window;
  it is still in review at the tag, so the credit lands with the merge rather than here (#1616).

### Known scope carried into v0.8.2

- The health analysis still reads pre-epoch bench rows — ADR-0037's boundary is not enforced in
  `sensor_health` (#1634). Post-epoch lab sessions remain unmarked on the timeline (#1635).
- `version-sync-guard` does not inspect `uv.lock`; the v0.8.1 bump passed green with a stale lockfile
  and was caught by hand (#1633).
- The dry-run walk cannot exercise the release path, so a genuine tag yielding `0.8.1` rather than
  `0.8.1-alpha` is checked at the cut, not by the walk (#1630).

## [0.8.0] — 2026-07-21 — Predict (the foundations, not the forecast)

**Recorded late, and honestly.** This section was missing for four days while `[Unreleased]` still
announced v0.8.0 as the next cycle — the canonical record denying a tagged release (ADR-0009 §6.3).
The v0.8.1 cut added a standing check for exactly this.

**The release shipped its foundations, not its name.** `predictor.py` reached no surface and
`backtest.py` was dark; the retro never asked whether the theme had become true. That finding produced
PRD-0009 and the theme-conformance gate. **It also published with zero assets** — the signer ran on
`release: published` and GitHub refused the upload with `HTTP 422: Cannot upload assets to an
immutable release`. The signed bytes existed; the door had already closed (#1438, #1346).

**Firmware**

- Channel declaration and the board-class token (ADR-0036): a channel is a first-class board
  declaration, and a waiting channel is a state rather than a gap (#1027).
- OTA pull, native-tested with no network and no hardware: the decision core (S3a) and the feed
  parser built to the ruled contract (S3b) (#302, #1284).
- PlatformIO pinned to 6.1.19 across the whole workflow fleet.

**Host / dashboard**

- The owner-cal wizard, host write path and surface (#963); above the ceiling, the band is withheld
  (#1339).
- Identity read-path translation — v4 `sN` folds to `chN` at join time (#1315); a deleted plant
  resolves to `None` at every instant.
- Structured placement on the temporal move, and reassignment that is deliberate rather than a silent
  remap (#1188, #1500–#1502, ADR-0029).
- Release channels in the flasher — stable by default, alpha behind a checkbox — and a build cannot
  wear a release version it isn't.
- Both cross-board comparisons as selectable renderings (#832); a persistent way home from the
  Workbench (#1150).

**Docs / process / community**

- **ADR-0038** (module boundaries and the import rule) Accepted, with the import-layer lint enforcing
  strictly-downward imports; **ADR-0037** (the production epoch and data admissibility) Accepted, with
  the epoch stamped as data at `2026-07-06T00:00:06Z` (#1330).
- The seam suites (#1338): tier contract vs. the store, wire schema vs. firmware and host, ratified
  doctrine vs. shipped behaviour.
- The product version agrees everywhere it is declared (#1407); tracked paths stay Windows-clonable
  (#1337); the action fleet SHA-pinned, with a guard that they resolve.
- The firmware-free contributor path became the default gate.

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

[Unreleased]: https://github.com/OrangePeachPink/sprout/compare/v0.8.1...HEAD
[0.8.1]: https://github.com/OrangePeachPink/sprout/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/OrangePeachPink/sprout/compare/v0.7.3...v0.8.0
[0.7.3]: https://github.com/OrangePeachPink/sprout/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/OrangePeachPink/sprout/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/OrangePeachPink/sprout/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/OrangePeachPink/sprout/releases/tag/v0.7.0
