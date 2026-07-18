# ADR-0012 — Experiment data architecture

**Status:** Proposed — *schema direction agreed (Firmware conditional approve, Discussion #57); detail
co-authored when sub-issues are cut*
**Date:** 2026-06-25
**Owner:** Data lane
**Lane:** data/analytics (experiment data lifecycle)
**Extends:** [ADR-0006](0006-data-architecture.md) (the Monitor-mode data architecture)
**Relates:** [PRD-0001](../prd/0001-experiment-capture-mode.md) R6–R9

---

## Context

[ADR-0006](0006-data-architecture.md) defines the **Monitor-mode** data architecture: the schema-v1
contract, the storage ladder, immutable raw, gap-surfacing, calibration, and the Data↔Firmware
handshake. [PRD-0001](../prd/0001-experiment-capture-mode.md) introduces **Experiment mode**, which has a
*different data lifecycle*: short, operator-driven captures against arbitrary subjects at variable rates,
whose central constraint is that they must **never be stitchable into the baseline**.

This ADR extends ADR-0006 for that lifecycle. It does **not** restate ADR-0006; the three-layer model,
immutable raw, quality-flag posture, and storage ladder all carry over unchanged.

## Decision

**Proposed; schema approach agreed with Firmware (#57); the archival store + findings schema remain
Data-owned and settle at build.**

### 1. Separate storage (the never-stitch substrate)

Experiment captures write to a **dedicated folder** (proposed `experiments/<experiment_id>/`), **never
`logs/`**. The monitor dashboard's `gather_inputs()` globs `logs/` (+ the B8 archive) only and **must not**
discover experiment data — the same opt-in isolation already used for `logs/legacy/`. *Enforced and
gate-verified per PRD-0001's acceptance criteria.*

### 2. Schema extension — `schema_version=2` (Firmware conditional approve, #57)

The new fields are **host-written**; the **device serial line does not change** (no firmware/device-row
change). They are added as **additive, nullable, shared-core columns** — **not** in `payload` — so the
isolation gate can *filter* on `mode` / `experiment_id`:

- `mode` — `monitor` | `experiment` (**the discriminator**).
- `experiment_id` — the isolation namespace.
- `subject` — free text (e.g. `common-cup`, `air`, `tap-water`).
- `sample_rate` — the cadence in effect.
- per-probe **label** (operator-set).

Conditions (from Firmware):

- **`schema_version` bumps to 2**, documented in [`docs/TELEMETRY_SCHEMA.md`](../TELEMETRY_SCHEMA.md);
  readers map by name, so monitor (v1-shaped) readers are unaffected.
- **`record_type` stays `plants.soil`** — `mode` is the discriminator; the namespace is **not** forked.
- **The sibling air-quality project stays valid and adopts the columns** — its own cross-project todo,
  since the schema-v1/v2 contract is shared.

### 3. Never-stitch guarantee

Isolation is enforced by the **separate `experiments/` folder + the distinct `experiment_id`** (and the
filterable `mode` column) — **not** by the `record_type` namespace. Analysis tools **refuse** to merge
experiment + monitor data, and `gather_inputs()` cannot reach the experiment folder. The reviewer
**proves** this at the gate (PRD-0001 acceptance) — a checkable guarantee, not an intention.

### 4. Naming + archival (Data-owned; settle at build)

- **Naming:** `<date>_<subject>_<purpose>` (e.g. `2026-06-26_common-cup_wet-dry-airdry`).
- **Manifest:** one per experiment — params (subject, rate, duration, probe labels), and a link to its
  findings report.
- **Archival (open):** zip + store completed experiments on close — to the Git LFS `data` branch (like the
  B8 monitor archive) **or** a separate experiment archive. Decide at build.

### 5. Findings reports

Paired **human `.md` + machine `.json`/`.yaml`** in **`docs/experiments/`**, *distinct from the raw
captures* (§1). The machine sidecar carries the structured outcomes — per-state mean raw, spread, settling
time, and proposed band anchors — that feed the **A2 reconciliation** and the Data↔Firmware calibration
handshake ([ADR-0006](0006-data-architecture.md) §5–6).

## Consequences

- The experiment lifecycle is isolated by construction: the baseline can't be polluted and future analysis
  can't conflate the two.
- The schema gains an explicit mode/subject dimension as **filterable columns** without breaking monitor
  readers or the device serial line — and without forking `record_type`.
- A `schema_version=2` bump is now on the cross-project contract; the sibling air-quality project must
  adopt it to stay joinable.
- Findings become durable, machine-consumable evidence that drives calibration — closing the loop ADR-0006
  opened.

## Revisit triggers

- Cross-experiment querying outgrows CSV re-parse → the DuckDB/parquet tier (ADR-0006 ladder), scoped to
  experiments.
- Environmental experiments add sensors (temp/light) → coordinate with Epic 2 /
  [PRD-0002](../prd/0002-environmental-context-and-correlation.md) and ADR-0006's `record_type=env` trigger.
- The sibling air-quality project adopts `schema_version=2` → confirm the shared contract stays joinable
  across both projects.
