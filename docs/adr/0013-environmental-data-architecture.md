# ADR-0013 — Environmental data architecture

**Status:** Accepted — implemented and in use; Data-led, §5 co-authored with Firmware. *(Truth-pass 2026-07-22,
issue #1460: env `record_type` + the rig-location / env-overlay surfaces are live on `main`.)*
**Date:** 2026-06-26
**Owner:** Data lane
**Lane:** data/analytics (external context streams, provenance, location privacy)
**Extends:** [ADR-0006](0006-data-architecture.md) (the soil-telemetry data architecture) — specifically
its `record_type=env` revisit trigger and §7 source-registry posture.
**Relates:** [PRD-0002](../prd/0002-environmental-context-and-correlation.md) R1–R8.

---

## Context

[ADR-0006](0006-data-architecture.md) homes the **soil-telemetry** data architecture: the schema-v1/v2
contract, the storage ladder, immutable raw, provenance, and the calibration handshake. It already
anticipates this epic — its revisit triggers name "environmental sensors are added → the schema extends
(`record_type=env`)" and "a model is earned by a named gap."

[PRD-0002](../prd/0002-environmental-context-and-correlation.md) introduces a *different kind* of data: an
**external observation stream** (weather, computed sun geometry) that is **not device telemetry** and is
joined to soil readings on **time + place**, plus a *later* on-device environmental sensor tier. This ADR
defines how that data is shaped, sourced, joined, and — critically — how the operator's **home location**
stays out of a public-ready repo. It does **not** restate ADR-0006; the three-layer model, immutable raw,
and quality posture carry over.

## Decision

### 1. External context is its own observation stream (joined, not stitched)

Weather and computed solar geometry are **not** rows in the device CSV. They are a **separate observation
stream**, stored apart from `logs/`, and **joined** to soil readings at analysis time on **timestamp (UTC)
and location** — never merged into the raw telemetry. The soil raw stays the immutable canonical source
(ADR-0006 §1); environmental context is an overlay layer that can be re-derived or re-fetched without
touching it. Each environmental observation carries the research-doctrine fields: **location + CRS,
timestamp UTC, source id, raw value, processed value, unit, confidence/quality, lineage, and the
software/source version** that produced it.

### 2. Weather source — Open-Meteo, cached as dated evidence

The weather source is **[Open-Meteo](https://open-meteo.com)** (free, keyless, global; an **archive** API
for history + a forecast API), with **NWS** a US-only alternative if needed. It is a **derived/model**
source — interpolated grid output, **not** an authoritative station reading — and is labeled as such
everywhere (§4). Each fetch is **cached as dated evidence** under a gitignored evidence path and **never
silently refetched or rewritten** (the immutable-evidence posture of ADR-0006 §4): a re-pull writes a new
dated artifact beside the old, so a chart can always be traced to the exact response that produced it.

### 3. Location privacy — the home coordinates never enter the repo

The rig's latitude/longitude are the operator's **home**, and the repo is public-ready, so they are
treated like a credential:

- Coordinates live **only** in a **gitignored local config** (e.g. `config/location.local.json`); a
  committed **`.example`** template documents the shape with placeholder values.
- `.gitignore` covers the local config and the raw weather cache (same lane as the WiFi-credential rule).
- **Anything committed** — findings reports, in-repo summaries, fixtures — carries conditions only
  **qualitatively or coarsened** ("overcast; ~0.2 kW/m² midday", or a city/grid-cell label), **never** the
  exact coordinates. A reviewer confirms **no coordinate leak** in tracked files *or* cached evidence at
  the gate (PRD-0002 acceptance).

### 4. Source registry entry

Per ADR-0006 §7 and the research doctrine, the weather source is registered with: **origin** (Open-Meteo),
**jurisdiction/coverage**, **update cadence** (hourly), **trust class = derived/model** (explicitly *not*
authoritative), **schema version**, and **discovery date**. Computed solar geometry is registered as a
**derived/computed** source (an algorithm over location+time, no external call). Any AI-generated or
interpolated value stays labeled and never silently promoted to authoritative.

### 5. On-device environmental sensor — `record_type=env`, dual-purpose (later; Firmware)

The later on-device tier (PRD-0002 R8) is **device telemetry**, so unlike §1 it *does* live in the stream,
as **`record_type=env`** rows (ADR-0006's named trigger) — a distinct record type from `plants.soil`,
emitted by the firmware, host-stamped the same way. Crucially, **on-board temperature is dual-purpose**: it
is weather-ground-truth *and* a **calibration input** that lets ADR-0006 §5–6 *separate* capacitive thermal
drift from real moisture change. That calibration role — not just weather colour — is why the sensor earns
its place. Firmware co-authors this section's detail (pin map, sensor model, cadence) at sub-issue cut.

### 6. Analysis posture — classical-first; a model is earned

Consistent with ADR-0006 §7: the correlation is **classical** (overlays, drying-rate regressions against
radiation, day-vs-day deltas). The **H1 (accelerating) vs H2 (sun-driven)** decomposition is the **named
gap** — if a weather-conditioned predictor demonstrably beats the classical baseline on the
predicted-vs-actual loop, *then* a model is earned, and it records its data provenance and evaluation. No
trained model ships by default.

## Consequences

- Soil raw stays the immutable canonical source; environmental context is a re-derivable overlay that can
  never pollute the baseline.
- The home location cannot leak: it is gitignored config by construction, and committed artifacts are
  coarsened — the public-ready posture holds.
- Weather is plainly classed (derived/model, cached, traceable), so a chart's context can always be traced
  to the exact response behind it.
- The on-device tier has a clear, dual-purpose justification (calibration *and* context), so it is not
  hardware-for-its-own-sake.
- The ML posture stays disciplined: the H1/H2 loop must *earn* a model rather than assume one.

## Revisit triggers

- The on-device environmental sensor is actually built → Firmware co-authors §5 (pin map, model, cadence)
  and ADR-0006's calibration math absorbs the temperature term.
- The H1/H2 predicted-vs-actual loop shows a weather-conditioned predictor beats the classical baseline →
  a model is earned; record it, its provenance, and its evaluation (ADR-0006 §7).
- External-context volume outgrows cached-JSON re-parse → fold weather into the DuckDB/parquet derived tier
  (ADR-0006 storage ladder), still re-derivable and never the canonical source.
- A second site/rig is added → the location config generalizes to per-rig, and the join key carries the
  rig/location id.
