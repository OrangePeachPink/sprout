# PRD: Environmental Context & Correlation

**Status:** Draft — **PARKED behind Epic 1** (Experiment Capture Mode); details still emerging
**Date:** 2026-06-25
**Owner:** Data lane
**Epic / issues:** *not yet cut — this is a captured idea, not an approved epic*

---

> **Parked.** This is a deliberately light stub so the idea is not lost. It unblocks once Epic 1 is
> advancing and the additional detail arrives. Documentation path when it wakes: Discussion (Ideas) →
> this PRD (filled in) → an ADR for the external-data-source architecture (extends
> [ADR-0006](../adr/0006-data-architecture.md)) → epic + sub-issues.

## Problem

The soil telemetry shows *what* the moisture did, but not *why*. A day's diurnal response is only legible
against the day's conditions: the skylight shaft passing over the plant ~13:00–14:00 produces a visible
bump on a clear day and **zero** change under heavy overcast — and that null result is *correct*, not a
sensor fault. Today the operator has to remember the weather to interpret the chart. This work joins an
**external observation stream** (weather, sun, season) to the telemetry on **time + place** so the
explanation is visible.

## Goals (sketch)

- Overlay **computed solar geometry** (when the skylight window occurs) + **weather** (cloud cover, solar
  radiation) on the soil trajectory.
- **Day-over-day** comparison (yesterday vs. today, conditions-annotated).
- *(Later)* ground-truth with **on-device temp + light** sensors.

## Non-goals

- Not Epic 1 (capture control).
- Not a trained model — classical-first per [ADR-0006](../adr/0006-data-architecture.md) §7; a model is
  earned by a named gap.

## Requirements (sketch — TBD)

- **R1.** Solar geometry: compute the skylight-window timing and sunrise/sunset from lat/long + date (no
  external dependency; hemisphere/season fall out of it).
- **R2.** Weather ingestion: cloud cover + solar/shortwave radiation (+ temp, precip), hourly, from a
  weather API (Open-Meteo / NWS), **cached as dated evidence** (never silently refetched/rewritten).
- **R3.** Time + place join: align hourly located weather with 30 s located soil readings.
- **R4.** Correlation surface: overlay + day-vs-day view.
- **R5.** *(Later)* on-device temp + lux/UV sensor — Firmware + a hardware part.

## Open questions

- **Location & privacy:** the rig's location is the operator's home lat/long, and the repo is
  public-ready — precise coordinates **must never be committed** (gitignored config, or coarsen to a
  city/grid cell). Same posture as WiFi credentials.
- **Source registry:** weather is a new external source with provenance classes (authoritative station /
  derived city model / on-device) — capture origin, cadence, trust, schema version, discovery date.
- **Temp as a confound, not just context:** capacitive readings drift with temperature; on-board temp
  would *separate* temperature drift from real moisture change — so it doubles as **calibration input**
  feeding ADR-0006, not only weather colour.

## Out of scope / later

- The on-device sensor tier (R5) is the largest, hardware-bearing slice — defer to a later phase.
- First tracer-bullet slice when this wakes: solar-window + cloud-cover overlay (R1–R3), which delivers
  the yesterday-vs-today comparison with **zero hardware**.
