# ADR-0012 — Experiment data architecture

**Status:** Proposed — *stub; refine through the Experiment Capture Mode Discussion*
**Date:** 2026-06-25
**Owner:** Data lane
**Lane:** data/analytics (experiment data lifecycle)
**Extends:** [ADR-0006](0006-data-architecture.md) (the Monitor-mode data architecture)
**Relates:** [PRD-0001](../prd/0001-experiment-capture-mode.md) R6–R9

---

## Context

[ADR-0006](0006-data-architecture.md) defines the **Monitor-mode** data architecture: the schema-v1
contract, the storage ladder, immutable raw, honest gap-surfacing, calibration, and the Data↔Firmware
handshake. [PRD-0001](../prd/0001-experiment-capture-mode.md) introduces **Experiment mode**, which has a
*different data lifecycle*: short, operator-driven captures against arbitrary subjects at variable rates,
whose central constraint is that they must **never be stitchable into the baseline**.

This ADR extends ADR-0006 for that lifecycle. It does **not** restate ADR-0006; the three-layer model,
immutable raw, quality-flag posture, and storage ladder all carry over unchanged.

## Decision

**Proposed; sub-decisions marked open pending the Discussion + Firmware sign-off.**

### 1. Separate storage (the never-stitch substrate)

Experiment captures write to a **dedicated folder** (proposed `experiments/<experiment_id>/`), **never
`logs/`**. The monitor dashboard's `gather_inputs()` globs `logs/` (+ the B8 archive) only and **must not**
discover experiment data — the same opt-in isolation already used for `logs/legacy/`. *Enforced and
gate-verified per PRD-0001's acceptance criteria.*

### 2. Schema extension (on the schema-v1 contract — ADR-0006 §2)

Add / confirm fields, carried in the `#` provenance header and as columns/payload as appropriate, mapped
**by name** so monitor readers are unaffected:

- `mode` — `monitor` | `experiment` (the discriminator).
- `subject` — free text (e.g. `common-cup`, `air`, `tap-water`).
- `experiment_id` — the isolation namespace.
- `sample_rate` — the cadence in effect.
- per-probe **label** (operator-set).

The contract is **shared cross-project** (the sibling AQ project) → **Firmware + contract sign-off**
required (open). `record_type` may also distinguish experiment readings — to settle in the Discussion.

### 3. Never-stitch guarantee

A distinct `experiment_id` namespace + the `mode` marker; analysis tools **refuse** to merge experiment +
monitor data; and `gather_inputs()` cannot reach the experiment folder. The reviewer **proves** this at the
gate (PRD-0001 acceptance) — it is a checkable guarantee, not an intention.

### 4. Naming + archival

- **Naming:** `<date>_<subject>_<purpose>` (e.g. `2026-06-26_common-cup_wet-dry-airdry`).
- **Manifest:** one per experiment — params (subject, rate, duration, probe labels), and a link to its
  findings report.
- **Archival (open):** zip + store completed experiments on close — to the Git LFS `data` branch (like the
  B8 monitor archive) **or** a separate experiment archive. Decide in the Discussion.

### 5. Findings reports

Paired **human `.md` + machine `.json`/`.yaml`** in **`docs/experiments/`**, *distinct from the raw
captures* (§1). The machine sidecar carries the structured outcomes — per-state mean raw, spread, settling
time, and proposed band anchors — that feed the **A2 reconciliation** and the Data↔Firmware calibration
handshake ([ADR-0006](0006-data-architecture.md) §5–6).

## Consequences

- The experiment lifecycle is isolated by construction: the baseline can't be polluted and future analysis
  can't conflate the two.
- The schema gains an explicit mode/subject dimension without breaking monitor readers (by-name mapping).
- Findings become durable, machine-consumable evidence that drives calibration — closing the loop ADR-0006
  opened.

## Revisit triggers

- Cross-experiment querying outgrows CSV re-parse → the DuckDB/parquet tier (ADR-0006 ladder), scoped to
  experiments.
- Environmental experiments add sensors (temp/light) → coordinate with Epic 2 /
  [PRD-0002](../prd/0002-environmental-context-and-correlation.md) and ADR-0006's `record_type=env` trigger.
