# PRD: Experiment Capture Mode

**Status:** Draft <!-- Draft → Accepted → Implemented -->
**Date:** 2026-06-25
**Owner:** Data lane (with Firmware: serial ownership + `set_cadence`)
**Epic / issues:** *parent epic Issue to be cut from this PRD once Accepted*

---

## Problem

Sprout today has a single mode: **passive monitoring** — always-on, fixed 30 s cadence, one subject, one
append-forever `logs/` folder. That is the right shape for the long baseline, but it cannot run the
*characterization* work the project needs next: dunking the four probes in a common cup of water to
separate sensor bias from soil microsite (C1), measuring the band anchors at known wet/dry/air-dry states
to reconcile the proposed boundaries (A2), and watching how fast a probe's reading actually moves when its
medium changes.

Those are **operator-driven experiments**: short, labeled, against arbitrary (often non-plant) subjects,
at sample rates far faster than 30 s, started and stopped by hand. Their data must be **kept apart from
the monitoring baseline** — both so the always-on record stays clean, and so future analysis can never
stitch a burst of experiment readings into the baseline and mistake them for a real event.

This PRD adds that second mode — **Experiment mode** — beside Monitor mode, with provenance isolation as a
first-class guarantee, not an afterthought.

## Goals

- A distinct **Experiment mode** that never touches the Monitor-mode path or the running baseline.
- The operator drives a capture **entirely from the dashboard** — label probes, set subject, set
  duration, set sample rate, start/stop — with no agent in the loop.
- Experiment captures are **provenance-isolated**: a separate data folder and a distinct id namespace, so
  no tool can auto-discover or stitch them into the baseline.
- **Settable sample rate** — 5 s / 1 s / **0.5 s** for today; 0.25 / 0.1 s a labeled deeper stretch.
- Durable **findings reports** (human + machine readable) as the output of an experiment.

## Non-goals

- **Not** changing Monitor mode, the schema's monitor path, or the 48 h baseline capture.
- **Not** the calibration *analysis* itself — that consumes the captures and feeds the A2 reconciliation
  per [ADR-0006](../adr/0006-data-architecture.md) §5–6; it is downstream work, not this PRD.
- **Not** multi-device orchestration or remote control.
- Environmental correlation (weather / sun / temp) is **Epic 2** ([PRD-0002](0002-environmental-context-and-correlation.md)).

## Requirements

- **R1.** Per-probe **labels**, operator-set, persisted with the capture.
- **R2.** A **subject** field — arbitrary, non-plant allowed (e.g. `common-cup`, `air`, `tap-water`).
- **R3.** **Bounded session** — the operator sets a duration; the capture **auto-stops** at it. Auto-stop
  is owned by the **capture process itself** (fail-safe: it stops even if `serve.py` or the browser dies);
  a manual stop is a secondary signal.
- **R4.** **In-screen start/stop/configure** — a click in the dashboard begins / ends / configures a
  capture; no agent. `serve.py` owns the operator **control API** and **launches a bounded capture
  process**; that process owns the serial port, issues `set_cadence`, and writes the isolated file
  ([ADR-0011](../adr/0011-experiment-capture-control-plane.md), Option A refined).
- **R5.** **Settable sample rate.** Cadence is **firmware-timed** (the device free-runs; the capture reads
  passively), set at runtime via a `set_cadence` serial command — not host-polling. **For-today tiers:
  5 s / 1 s / 0.5 s** (0.5 s confirmed reasonable as-is). **Deeper sub-second — 0.25 / 0.1 s — a labeled
  stretch**, gated on Firmware's three knobs: raise baud, shrink the sample burst (16–32, not 100),
  single-channel.
- **R6.** **Isolated storage** — captures write to a **separate folder** (`experiments/<experiment_id>/`),
  never `logs/`, and are never auto-discovered by the monitor dashboard's `gather_inputs()`.
- **R7.** **Never-stitch** — enforced by the separate folder + a distinct `experiment_id` + a `mode`
  (`monitor` | `experiment`) **shared-core column** (filterable, *not* buried in payload). `record_type`
  stays `plants.soil`; **`mode` is the discriminator**. The schema bumps to **`schema_version=2`**
  (additive, nullable, mapped by name) so monitor readers are unaffected.
- **R8.** **Archival** — a naming convention, a per-experiment manifest, and a zip/store policy for
  completed experiments.
- **R9.** **Findings reports** — durable, paired human (`.md`) + machine (`.json`/`.yaml`), in
  `docs/experiments/`.
- **R10.** **Serial-port mutual exclusion** — a capture needs **exclusive** ownership of the device serial
  port (COM6); it **cannot run while Monitor mode holds the port**. Starting one is refused with an honest
  message unless the monitor has released it. This makes "don't disturb the baseline" an **enforced
  invariant**, not a guideline.

### Lane split (confirmed with Firmware, Discussion #57)

- **Data:** the `serve.py` control API, launching the bounded capture process, the isolated folder +
  isolation gate, the schema columns (host-written), archival, findings, and the analytics.
- **Firmware:** serial-port ownership, the `set_cadence` runtime command, device timing, and co-authoring
  the [ADR-0011](../adr/0011-experiment-capture-control-plane.md) /
  [ADR-0012](../adr/0012-experiment-data-architecture.md) detail when sub-issues are cut.

## Acceptance criteria

- [ ] The operator can label each probe, set subject, duration, and sample rate, and **start/stop a
      capture entirely from the dashboard**.
- [ ] A bounded capture **auto-stops** at the set duration — **and still auto-stops if `serve.py` or the
      browser is killed mid-capture** (capture-process-owned, fail-safe).
- [ ] Experiment captures land in the **experiment data folder, not `logs/`**.
- [ ] **PROVEN at the gate: the monitor dashboard's `gather_inputs()` cannot auto-discover experiment
      data** — a reviewer confirms the never-stitch guarantee before close (not an aspiration).
- [ ] **5 s, 1 s, and 0.5 s** rates verified end-to-end; 0.25 / 0.1 s only behind a labeled flag and only
      with Firmware's three knobs applied.
- [ ] Starting a capture while Monitor mode holds the serial port is **refused with an honest message**
      (R10 mutex) — the running baseline is never interrupted.
- [ ] `schema_version=2` is documented; monitor readers are unaffected and **HotBoxAQ stays valid**.
- [ ] A completed experiment produces a **findings report pair** (`.md` + `.json`/`.yaml`) in
      `docs/experiments/`.
- [ ] Monitor mode and the baseline path are demonstrably **unchanged**.

## Resolved by the Discussion (Firmware, #57)

The four open questions are answered; the agreed direction is folded into the requirements above and the
ADR stubs (full ADR detail co-authored when sub-issues are cut):

- **Sample rate.** Firmware-timed; runtime `set_cadence` command (no host-polling). 5 s / 1 s / 0.5 s for
  today; 0.25 / 0.1 s a knob-gated stretch (R5).
- **Control seam (ADR-0011).** Option A refined: `serve.py` owns the control API + launches a bounded
  capture process that owns the port; `serve.py` stays out of the port/data (R4).
- **Auto-stop.** Capture-process-owned, fail-safe (R3).
- **Schema (ADR-0012).** Conditional approve: host-written, device line unchanged; additive/nullable
  shared-core **columns**, `schema_version=2`, `record_type` stays `plants.soil`, `mode` discriminates
  (R7).

**Still open (Data-owned, settle at build):** the archival store location (LFS `data` branch vs. a
separate experiment archive) and the exact `docs/experiments/` findings schema.

## Out of scope / later

- 0.25 / 0.1 s sub-second beyond the knob-gated stretch → not for-today scope.
- On-device temp / light sensors and environmental correlation → **Epic 2** ([PRD-0002](0002-environmental-context-and-correlation.md)).
- A DuckDB / parquet tier for cross-experiment queries → when CSV re-parse gets slow (ADR-0006 storage ladder).
- **HotBoxAQ adoption** of the `schema_version=2` columns is a **HotBox-side todo** (propose → HBAQ), not
  part of this epic.

## Phasing (tracer bullets)

The build order, once Accepted and sub-issues are cut (each a `Refs` PR through the gate):

1. **Isolated capture, manual start** — separate folder + `schema_version=2` metadata (label / subject /
   rate / duration / `mode` / `experiment_id`) + a capture process that owns the port and `set_cadence`.
   Delivers R1–R3, R5 (5 s/1 s/0.5 s), R6–R7, R10 decoupled from the browser control plane.
2. **Control-plane spike + ADR-0011** — a thin start/stop-from-browser path (`serve.py` control API →
   capture process) to prove the seam + the mutex, then lock the ADR.
3. **Full capture UI** — the control panel (R4): labels / subject / rate / duration / start-stop / status.
4. **Archival + findings + per-state analysis** — R8/R9 + the per-state tooling (mean raw / spread /
   settling per sensor per state) that turns a capture into a findings pair.
