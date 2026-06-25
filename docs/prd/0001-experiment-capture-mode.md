# PRD: Experiment Capture Mode

**Status:** Draft <!-- Draft → Accepted → Implemented -->
**Date:** 2026-06-25
**Owner:** Data lane
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
- **Settable sample rate** (1 s / 5 s in v1; sub-second a labeled stretch).
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
- **R3.** **Bounded session** — the operator sets a duration; the capture **auto-stops** at it.
- **R4.** **In-screen start/stop** — a click in the dashboard begins/ends a capture; no agent involved.
- **R5.** **Settable sample rate** — 1 s and 5 s in v1; sub-second (0.5 / 0.25 / 0.1 s) a **labeled stretch
  goal**, included only if Firmware confirms it is reasonable to try.
- **R6.** **Isolated storage** — experiment captures write to a **separate folder**, never `logs/`, and are
  never auto-discovered by the monitor dashboard's `gather_inputs()`.
- **R7.** **Never-stitch** — a distinct `experiment_id` / session namespace and an explicit `mode` marker,
  so no analysis tool can merge experiment data into the baseline.
- **R8.** **Archival** — a naming convention, a per-experiment manifest, and a zip/store policy for
  completed experiments.
- **R9.** **Findings reports** — durable, paired human (`.md`) + machine (`.json`/`.yaml`), in
  `docs/experiments/`.

## Acceptance criteria

- [ ] The operator can label each probe, set subject, duration, and sample rate, and **start/stop a
      capture entirely from the dashboard**.
- [ ] A bounded capture **auto-stops** at the set duration.
- [ ] Experiment captures land in the **experiment data folder, not `logs/`**.
- [ ] **PROVEN at the gate: the monitor dashboard's `gather_inputs()` cannot auto-discover experiment
      data** — a reviewer confirms the never-stitch guarantee before close (not an aspiration).
- [ ] **1 s and 5 s** rates verified end-to-end; sub-second only behind a labeled flag, and only if
      Firmware confirmed feasibility.
- [ ] A completed experiment produces a **findings report pair** (`.md` + `.json`/`.yaml`) in
      `docs/experiments/`.
- [ ] Monitor mode and the baseline path are demonstrably **unchanged**.

## Open questions

These are the cross-lane unknowns to resolve **in the Discussion**, with **Firmware** confirming
feasibility, before this PRD is locked:

- **Sub-second feasibility (R5).** Can the firmware/logger sample reliably at 1 s, and is sub-second
  (0.5 / 0.25 / 0.1 s) "reasonable to try"? Bounded by firmware timing, serial throughput, and capacitive
  settling physics. *(Maintainer lean: v1 = 1 s / 5 s; sub-second a stretch gated on Firmware.)*
- **Control seam (R4 → [ADR-0011](../adr/0011-experiment-capture-control-plane.md)).** How does an in-screen
  click reach the logger — does `serve.py` expose a control API that launches/stops the logger, or does the
  logger own the control surface and `serve.py` proxy?
- **Auto-stop ownership (R3).** Logger-side timer vs. the control layer.
- **Schema sign-off (R6/R7 → [ADR-0012](../adr/0012-experiment-data-architecture.md)).** The new fields
  (`mode`, `subject`, `experiment_id`, `sample_rate`, per-probe label) are written by the logger and the
  contract is shared with the sibling air-quality project — Firmware + contract sign-off.

## Out of scope / later

- Sub-second sampling beyond what Firmware blesses → a stretch flag, not v1 scope.
- On-device temp / light sensors and environmental correlation → **Epic 2** ([PRD-0002](0002-environmental-context-and-correlation.md)).
- A DuckDB / parquet tier for cross-experiment queries → when CSV re-parse gets slow (ADR-0006 storage ladder).

## Phasing (tracer bullets)

The build order, once Accepted and sub-issues are cut (each a `Refs` PR through the gate):

1. **Isolated capture, manual start** — separate folder + session metadata (label / subject / rate /
   duration) + a launcher. Delivers R1–R3, R5 (1 s/5 s), R6–R7 decoupled from the control plane.
2. **Control-plane spike + ADR-0011** — a thin start/stop-from-browser path to prove the seam, then lock
   the ADR.
3. **Full capture UI** — the control panel (R4): labels / subject / rate / duration / start-stop / status.
4. **Archival + findings + per-state analysis** — R8/R9 + the per-state tooling (mean raw / spread /
   settling per sensor per state) that turns a capture into a findings pair.
