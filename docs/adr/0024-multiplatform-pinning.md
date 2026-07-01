# ADR-0024 — Toolchain pinning (one exact pin for the active matrix)

**Status:** Accepted — *revised 2026-07-01 by explicit maintainer direction (relayed via Workflow on #283),
superseding this ADR's original per-target-isolation posture. The reproducibility discipline (exact `==` pin,
never floating) survives; what changes is how many targets share one pin.*
**Date:** 2026-07-01 (originally drafted 2026-07-01; revised same day)
**Owner:** Architecture (Trellis) — the posture; DX owns the toolchain wiring; Firmware owns the classic
re-qualification.
**Lane:** architecture (cross-lane: DX / Firmware toolchain)
**Extends:** [ADR-0019](0019-capability-and-sensor-matrix.md) (one codebase, per-target build env)
**Relates:** #283 (the original `espressif32@7.0.1` pin decision) · #442 (ESP32-C5) · #436 (multi-board) · #443
(bench re-qualification)

---

## Context

The original #283 decision pinned `espressif32@7.0.1` for reproducibility. When #442 asked whether adding the
ESP32-C5 (which needs `arduino-esp32 3.2+ / IDF 5.4+`) justified un-pinning, this ADR's first version answered
**no** — isolate the new platform on its own exact pin, keep the shipping matrix frozen. That posture shipped
and worked (`esp32c5` on pioarduino, `esp32dev`/`esp32dev_env` untouched, #491/#495).

**The maintainer has since made a deliberate, separately-justified whole-matrix decision** — exactly the
revisit trigger this ADR's first version named ("a security fix forces a bump → a deliberate whole-matrix
move"), fired here on project-maturity grounds instead: *pre-1.0, fast-moving, no install base, no tech debt to
protect — the original `7.0.1` pin was an arbitrary starting point, not a commitment.* The factual gate that
makes the move safe: Arduino-ESP32 3.x (IDF 5) **still fully supports classic ESP32** (not dropped), and the
one IDF4/IDF5 API break in this codebase (`esp_task_wdt_init`) is **already written dual-path**
(`#if ESP_IDF_VERSION >= 5`, from #499/#502) and compiles green on the `esp32c5` CI job today. No WiFi/timer/LEDC
code exists yet to carry a separate breaking-API surface. The migration seam is close to zero-cost.

## Decision

**One exact pin for the whole active matrix, on the pioarduino platform fork — matrix moves happen together,
deliberately, never as a side effect of adding one board.**

- `esp32dev` / `esp32dev_env` / `esp32dev_wdttest` / `esp32s3` / `esp32c5` all pin to the **same exact release**
  (`==`, never floating — the discipline that survives from this ADR's first version) on **pioarduino**
  (`https://github.com/pioarduino/platform-espressif32.git#55.03.39` — the same tag `esp32c5` already proved).
- **pioarduino is named honestly**: it is the community-maintained successor for Arduino-ESP32 3.x on
  PlatformIO — Espressif ended official first-party PlatformIO support for the 3.x line. It's the de-facto
  standard path, not a fringe choice, and exact pinning contains the risk of depending on a community fork the
  same way it contained the risk of the original Espressif-official pin.
- **A per-board isolated pin is still the right pattern for a genuinely experimental/unproven platform** —
  a board with no bench hardware yet, or one whose support is still shaky upstream. Once a platform is proven
  (bench-verified, like classic ESP32 and now C5/S3 will be), it graduates into the one shared matrix pin
  rather than staying isolated forever. Isolation is a **staging state**, not a permanent per-board default.
- **One safety gate, unconditional:** the new-toolchain classic build does **not** become the live greenhouse
  logger until the wedge test passes on it at the bench (#191 discipline) — no toolchain change bypasses the
  hardware-safety re-qualification.

### What changed vs. this ADR's original decision (superseded, kept for the record)

The original text (2026-07-01, superseded same day) read: *"Support multiple platforms with one isolated,
exact pin per platform target — never by un-pinning or advancing the shared matrix... Moving the whole matrix
to a newer platform is a deliberate, separately-justified decision... not a side effect of adding one board."*
That principle held until the maintainer made exactly the deliberate, separately-justified call it reserved —
this revision executes it, it doesn't contradict the original reasoning. The **isolation-by-default** posture
is superseded; the **exact-pin, never-floating, deliberate-not-incidental** discipline is not.

## Rejected alternatives

- **Stay isolated per-board indefinitely.** Rejected now: for a pre-1.0 project with no installed base and a
  near-zero migration seam (the one API break is already handled), isolation defers a cheap consolidation for
  no real reproducibility gain — the classic target's dual-path WDT code already proves the seam is small.
- **A floating version range on the shared pin.** Rejected: reproducibility requires an exact pin regardless of
  how many targets share it — unchanged from the original decision.
- **Un-pin without re-qualifying the classic build.** Rejected: the ADC driver changed IDF4→IDF5; raw counts may
  shift. The classic target must be bench re-qualified (wedge test, ADC A/B, band re-check) before the new
  toolchain drives the live logger — safety discipline, not optional.

## Consequences

- **DX** points `esp32dev` / `esp32dev_env` / `esp32dev_wdttest` / `esp32s3` to the same exact pioarduino pin
  `esp32c5` already uses. CI simplifies to one toolchain matrix instead of two.
- **Firmware** fixes any incidental compile breaks (expected minor — the WDT seam already exists) and builds
  the **#21 WiFi scaffold directly against the new pin** — a sequencing win: WiFi code gets written once on the
  3.x API, never ported from 2.x later.
- **Firmware** adds a **classic re-qualification section to the #443 bench run sheet**: re-flash on the new
  toolchain, re-run the wedge test fresh, an ADC sanity A/B against current raw counts (honest-data law — verify
  and record any shift), and re-check bands against the just-landed per-channel calibration.
- **Data**: no schema change. `firmware_version` in the telemetry header carries the toolchain lineage. The
  live-logger switch to the new toolchain should land at an experiment boundary and be annotated, so a bench
  dataset's lineage stays clean and comparable (ties to ADR-0025's no-auto-adjust / provenance doctrine).
- The board matrix now grows by **adding a board to the one shared pin** (plus its capability descriptor,
  ADR-0019) once past the experimental-isolation staging state — not by a per-board pin proliferating forever.

## Revisit triggers

- **A future board needs a toolchain the shared pin can't support** → back to per-target isolation for that one
  board, following this ADR's original (still-valid) isolation pattern, until it can join the shared pin.
- **Post-1.0 / an installed base exists** → re-evaluate whether "advance the matrix freely" still holds, or
  whether reproducibility should tighten again (this decision's rationale is explicitly pre-1.0-scoped).
- **The classic re-qualification (#443) surfaces an ADC/behavior regression** → do not cut the live logger over
  until resolved; the wedge-test gate (#191) is unconditional regardless of toolchain.

*Registered in `docs/adr/0000-record-architecture-decisions.md`.*
