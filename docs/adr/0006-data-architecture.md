# ADR-0006 — Data architecture

**Status:** Accepted (2026-06-24)
**Date:** 2026-06-24
**Owner:** Data lane
**Lane:** data/analytics (telemetry schema, calibration, data quality, storage substrate)
**Elaborates:** [ADR-0002](0002-process-tiers.md) #15 (Data store & versioning), #16 (ML / inference).

---

## Context

Sprout produces a continuous multi-sensor telemetry stream that everything downstream depends on:
dashboards, forecasting, calibration, and (eventually) watering decisions. The *shape, integrity,
provenance, and storage* of that data are a domain architecture in their own right — distinct from the
firmware/control architecture (ADR-0001) and from the engineering *process* (ADR-0002).

This ADR homes the **Data-lane domain architecture**: the telemetry schema/contract, the storage
substrate, data quality, sensor calibration, and the Data ↔ Firmware calibration interface. It is the
place a contributor learns *how the data is shaped and trusted.*

## Decision

### 1. Three-layer data model

`raw → normalized → interpreted`, with provenance preserved at every step:

- **Raw** — ADC counts as the device emits them. **Immutable; never rewritten.**
- **Normalized** — parsed, typed, time-stamped readings (one row per sensor per sweep).
- **Interpreted** — bands, derived features, forecasts. May change as calibration improves; the raw it
  came from is retained so history can be re-derived.

Every row carries provenance: `device_id`, `session_id`, firmware version + git hash, host UTC + local
time, `millis_ms`, sensor id / model / position.

### 2. Telemetry schema / contract

The canonical contract is **[`docs/TELEMETRY_SCHEMA.md`](../TELEMETRY_SCHEMA.md)** — schema-v1: a
**long/tidy CSV**, one row per sensor-channel per sample; self-describing `#` provenance headers
re-emitted per rotation segment; a namespaced **`record_type`** discriminator; and the
`{raw_value, value, unit}` + `quality_flag` shape shared cross-project so it stays joinable with a
sibling air-quality sensor project. The schema is **versioned** (`schema_version`); readers map columns
**by name** so an added/reordered column does not break them. `raw_value` is immutable truth; `value`
is interpretation; both are kept.

### 3. Storage substrate ladder (ADR-0002 #15)

Match the substrate to the data's shape; the raw is always the source of truth:

- **Immutable raw CSV** — `logs/*.csv`, gitignored. The capture; never edited.
- **Durable archive** — closed rotated segments gzipped to a **Git LFS** archive branch,
  reconciliation-based catch-up (not a cron). The vault; years inside the free LFS tier at this volume.
- **Derived analysis tier** — a **DuckDB / parquet** store, **rebuilt from the raw**, gitignored, and
  **never backed up** (it is reproducible). For fast multi-day / cross-channel / cross-project queries
  once CSV re-parse gets slow. Planned; not yet stood up.
- A single-writer **SQLite** store is an option if a mutable app-state store is ever wanted — not today.

**The DB / parquet is a derived layer, never the source of truth.** If lost, it is regenerated from the
raw archive.

### 4. Data quality — surface, never smooth

The standing principle: **surface gaps and anomalies; never hide them.**

- **`quality_flag`** enum (`OK / SUSPECT / SATURATED / NO_SIGNAL / …`) per reading.
- **Transport integrity** — a per-line XOR checksum (firmware → logger) drops a corrupted line
  deterministically rather than letting a mangled value enter the data.
- **Gaps** — logging interruptions (a reset, a logger restart) are detected and shown as line breaks +
  shaded spans + an explicit list, not interpolated over.
- **Partial sweeps & cross-channel coherence** — dropped samples and per-probe divergence are surfaced.
- **The legacy `value` (moist%)** is carried for fidelity but **not analysed** — analysis is on
  `raw_value` + band. Any 0–100 figure is a labelled relative index, never VWC.

### 5. Sensor calibration

- **Band model** — a seven-band classifier over inverted raw ADC (higher = drier); the boundaries are
  the **A2** model.
- **Status** — the as-flashed boundaries are an **un-reconciled spec**; reconciliation comes from
  analysing a real dry-down, not from guessing. Until then the dashboard labels bands **proposed**.
- **Per-channel** — the four probes sit on different ADC pins (eFuse cal off) and show a persistent
  ~70–90-count offset (the s2 evidence). **Per-pin/probe calibration (C1)** — same-probe/same-water with
  neighbours powered — is the experiment that separates pin offset from probe from placement, and may
  justify per-channel boundaries.
- Truth is **`raw_value` + band**; calibration improves the interpretation, never the raw.

### 6. The A2 calibration handshake (Data ↔ Firmware interface)

Calibration spans two lanes; this is the contract:

- **Data analyses** the dry-down + cross-probe data and **proposes a boundary set** (with evidence —
  e.g. a boundary editor that sets band edges visually against real readings).
- **Firmware implements** the agreed boundaries in the on-device classifier config and flashes them.
- The **watering threshold** the forecast extrapolates to **must match the firmware's actual watering
  trigger** once it is defined.

Neither lane silently changes the boundaries; they move through this interface.

### 7. Forecasting / ML posture (ADR-0002 #16)

The analytical layer is **classical, native-first**: least-squares drying-rate, statistically-gated
ETAs (no fabricated numbers), diurnal-readiness, per-window stats. **No trained model**, and none is
warranted yet. A model is *earned* by a **named gap** — demonstrated by the predicted-vs-actual loop
(e.g. once weather / temperature / multi-day data shows a non-linear or weather-conditioned predictor
beats the classical baseline). A model, when earned, records its data provenance and its evaluation.

## Consequences

- The data layer has a recorded architecture: provenance, immutability, and honest gap-surfacing are
  first-class, not incidental.
- The storage substrate scales by matching shape to need, with the raw always recoverable.
- The Data ↔ Firmware calibration interface is named, so band boundaries can't drift silently between
  lanes.
- The ML posture is explicit, so a model has to justify itself rather than appear by default.

## Revisit triggers

- A persistent multi-channel dataset outgrows CSV re-parse → stand up the DuckDB/parquet tier.
- C1 shows the probes need per-channel boundaries → per-pin classifier config (Firmware), proposed here.
- Environmental sensors (temp/RH/light) are added → the schema extends (`record_type=env`) and thermal
  correction of the raw becomes possible.
- A model is earned by a named gap → record the model, its data provenance, and its evaluation.
- A sibling air-quality sensor project is co-deployed → exercise and, if needed, refine the shared
  cross-project contract.
