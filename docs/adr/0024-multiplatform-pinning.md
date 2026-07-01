# ADR-0024 — Multi-platform toolchain pinning (one isolated pin per target)

**Status:** Proposed — *drafted by Trellis from #442 (DX-aligned). The first instance (`esp32c5`) is DX's to
wire; this ADR fixes the posture so future board additions don't re-litigate it. Awaiting maintainer
ratification.*
**Date:** 2026-07-01
**Owner:** Architecture (Trellis) — the posture; DX owns the per-target toolchain wiring.
**Lane:** architecture (cross-lane: DX / Firmware toolchain)
**Extends:** [ADR-0019](0019-capability-and-sensor-matrix.md) (one codebase, per-target build env)
**Relates:** #283 (the `espressif32@7.0.1` pin) · #442 (ESP32-C5) · #436 (multi-board)

---

## Context

#283 pinned `espressif32@7.0.1` for **reproducibility** — the classic-ESP32 toolchain (Xtensa GCC 8.4.0) is
deliberately frozen; that's a feature, not staleness. But newer silicon can't build on that pin: the ESP32-C5
(RISC-V, WiFi-6) needs `arduino-esp32 3.2+ / IDF 5.4+`. #442 asked the sharp question: does adding a board
justify **un-pinning**? The framing that resolves it (DX): reproducibility is not "pinned vs unpinned" — it's
**how many** pinned platforms the repo carries, and whether they're isolated.

## Decision

**Support multiple platforms with one *isolated, exact* pin per platform target — never by un-pinning or
advancing the shared matrix.**

- A new board on a platform-distinct toolchain gets its **own `[env:<board>]`** pinned to an **exact** platform
  release (`==`, never a floating range — the same discipline as `7.0.1`), plus a capability descriptor
  (ADR-0019).
- The **shipping targets stay on their proven pin.** A new or experimental platform's toolchain break is
  **isolated** — its own CI job — and can never red the shipping builds.
- Moving the **whole** matrix to a newer platform is a **deliberate, separately-justified** decision (it
  re-qualifies every shipping target), **not** a side effect of adding one board.

Reproducibility is therefore **per-target and permanent**; the number of platforms the repo carries is
orthogonal to it. The framework-agnostic C core (`lib/`) and the host-native tests are platform-independent, so
a new platform touches only the Arduino-glue layer — the isolation is clean.

## Rejected alternatives

- **Un-pin / move the whole matrix to support one new board.** Rejected: re-qualifies every shipping target
  against a newer toolchain for a board nobody owns yet — wrong blast radius, and it discards #283's
  reproducibility for a speculative gain.
- **Keep the single pin; refuse new platforms.** Rejected: needlessly blocks growth when the isolation cost is
  one CI build.
- **A floating version range on the new env.** Rejected: reproducibility requires an exact pin per target — the
  same rule #283 set.

## Consequences

- The board matrix grows by **adding isolated pinned envs** (+ descriptors), not by matrix-wide bumps.
- CI grows by **one job per platform-distinct board**; an experimental toolchain break stays contained.
- Experimental / brand-new boards (e.g. C5) are **opt-in, Contributors-Welcome builds** until validated on real
  hardware (ADR-0019 posture).
- First instance: **`esp32c5`** (#442) — DX-wired on an exact newer-platform pin; `esp32dev` / `esp32dev_env` /
  `7.0.1` untouched; #436 S3 work unaffected.

## Revisit triggers

- **The classic-ESP32 platform reaches end-of-life, or a security fix forces a bump** → a deliberate
  whole-matrix move, separately justified (not this ADR's default path).
- **The CI build-count from many boards becomes a real cost** → revisit whether experimental envs build
  on-demand rather than on every PR.
- **Two targets can share one platform pin** → fine; the rule is *exact-pin-per-target*, not one-env-per-pin.

*Register in `docs/adr/0000-record-architecture-decisions.md` on acceptance.*
