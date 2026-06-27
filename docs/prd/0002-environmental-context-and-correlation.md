# PRD: Environmental Context & Correlation

**Status:** Accepted (2026-06-26) — optionality / offline-first folded in (R9 + a non-goal + an open question)
**Date:** 2026-06-25 (revised 2026-06-26)
**Owner:** Data lane
**Epic / issues:** *not yet cut — accept this PRD, then Workflow cuts the epic + tracer-bullet sub-issues*
**Relates:** [ADR-0006](../adr/0006-data-architecture.md) §7 (analysis posture) + its `record_type=env`
revisit trigger; [ADR-0013](../adr/0013-environmental-data-architecture.md) (the data architecture for
this epic); [PRD-0001](0001-experiment-capture-mode.md) (Epic 1, which produced the data this explains).

---

## Problem

The soil telemetry shows *what* the moisture did, but not *why*. A day's diurnal response is only legible
against the day's conditions: the skylight shaft passing over the plant ~13:00–14:00 produces a visible
bump on a clear day and **zero** change under heavy overcast — and that null result is *correct*, not a
sensor fault. Today the operator has to remember the weather to interpret the chart.

We already have a concrete, unexplained case. The 48 h baseline (the foundational reference from
[Epic 1](0001-experiment-capture-mode.md)) is a fortuitous **cloudy/sunny A/B**: same probe (s3), same pot,
2026-06-24 overcast vs. 2026-06-25 sunny —
and s3 dried **~1.5× faster on the sunny day** (same-hours-of-day control: ~2.04 c/h cloudy vs. ~2.98 c/h
sunny). But those two days **cannot separate** the operator's two hypotheses — **H1** (the dry-down is
nonlinear / accelerating) and **H2** (sun drives faster drying) — because 06-25 is *both* sunnier *and*
drier, so both predict "faster." Decomposing H1 from H2 needs the weather overlaid on the trajectory. That
is this epic: join an **external observation stream** (weather, sun, season) to the telemetry on **time +
place** so the explanation is visible, and the H1/H2 question becomes answerable.

## Goals

- Overlay **computed solar geometry** (when the skylight window occurs; sunrise/sunset) on the soil
  trajectory — **zero external dependency, zero hardware**.
- Overlay **weather** (cloud cover, solar/shortwave radiation, temperature) from a documented external
  source, **cached as dated evidence**.
- A **day-over-day, conditions-annotated** comparison (yesterday vs. today).
- Make the **H1-vs-H2 decomposition** a first-class output: show drying rate against measured radiation /
  cloud cover, so "accelerating" and "sun-driven" can be told apart with data.
- *(Later)* ground-truth with **on-device temp + light** sensors, which double as **calibration input**.

## Non-goals

- Not Epic 1 (capture control) — this consumes Epic 1's data, it does not change capture.
- Not a trained model — classical-first per [ADR-0006](../adr/0006-data-architecture.md) §7; a model is
  *earned* by a named gap (the H1/H2 loop is the candidate that could earn it, not a starting assumption).
- Not a weather dashboard — weather is **context for soil**, never a product in itself.
- Not real-time/operational forecasting — this is explanatory analysis over recorded data first.
- **Nothing here is ever required.** Weather, connectivity (WiFi/HTTP/TCP-IP), and on-device sensors are
  all **optional** layers — core function (soil capture + the offline trajectory) never assumes any of
  them (see R9).

## Requirements

- **R1 — Solar geometry (no dependency).** Compute sun elevation/azimuth, sunrise/sunset, and the
  operator-calibrated **skylight window** from latitude/longitude + date/time. Hemisphere and season fall
  out of it. The location is read from local config (see R6); **no coordinates are hardcoded or committed**.
- **R2 — Weather ingestion.** Hourly cloud cover + solar/shortwave radiation (+ temperature, precip) from a
  documented external API (**Open-Meteo** archive + forecast — free, keyless, global, historically
  retrievable). Responses are **cached as dated evidence** and **never silently refetched or rewritten**
  (immutable-evidence posture, ADR-0006 §4).
- **R3 — Time + place join.** Align hourly, located weather with the 30 s located soil readings on
  timestamp (UTC) + location — the observation model in [ADR-0013](../adr/0013-environmental-data-architecture.md).
- **R4 — Correlation surface.** Overlay solar window + weather bands on the existing trajectory, plus a
  **day-vs-day** conditions-annotated view. The 48 h cloudy/sunny baseline is the first thing it renders.
- **R5 — H1/H2 decomposition.** A view/output that plots drying rate against radiation (and against soil
  dryness) so an *accelerating* curve and a *sun-driven* curve are distinguishable — the named gap that
  would later earn a weather-conditioned predictor.
- **R6 — Location privacy.** The rig's coordinates are the operator's **home** lat/long and the repo is
  public-ready, so they **must never be committed**. They live in a **gitignored local config** (a
  `.example` template ships); committed artifacts (findings, any cached weather kept in-repo) carry only
  **coarsened/qualitative** conditions, never exact coordinates. Same posture as WiFi credentials.
- **R7 — Source registry.** Weather is a new external source — record its provenance per ADR-0006 §7 /
  the research doctrine: origin, jurisdiction, cadence, **trust class** (it is **derived/model**, *not*
  authoritative), schema version, discovery date. AI-generated or interpolated values stay labeled.
- **R8 *(later)* — On-device environmental sensor.** Temp + lux/UV on the controller (Firmware + a part):
  `record_type=env` rows per ADR-0006's trigger. **Temp doubles as calibration input** — it *separates*
  capacitive thermal drift from real moisture change, feeding ADR-0006 §5–6, not only weather colour.
- **R9 — Optional & offline-first (no assumed connectivity).** The whole environmental layer is
  **optional** — Sprout stays fully comfortable to use without it, and **no network is ever required**
  (not WiFi, not HTTP, not TCP/IP). The current host-tethered, offline model is the **baseline**;
  weather/solar is an **additive layer** that degrades cleanly — full (cached weather + computed solar)
  → **solar-only** (R1: zero-dependency, always available) → none — with no broken UI and no nagging.
  The on-device sensors (R8) are **equally optional**: not everyone has, wants, or can configure them,
  and Sprout must read fine without them. *(Broader: how Sprout treats connectivity across the whole
  product — today it's host-tethered — is its own design question; this epic only commits the
  weather/sensor layers to never assume it.)*

### Lane split

- **Data:** R1–R7 — solar geometry, weather ingestion + caching + the source registry, the time+place
  join, the correlation/overlay + day-vs-day UI, the H1/H2 view, and the location-privacy config. Authors
  [ADR-0013](../adr/0013-environmental-data-architecture.md).
- **Firmware:** R8 — the on-device temp/lux/UV sensor, its `record_type=env` rows, and co-authoring the
  ADR-0013 on-device section when that sub-issue is cut.

## Acceptance criteria

- [ ] The home lat/long is **never committed** — it lives in a gitignored local config (a `.example`
      template ships); a reviewer confirms **no coordinate leak** in tracked files *or* cached evidence.
- [ ] **Computed solar geometry** (elevation/azimuth, sunrise/sunset, the skylight window) overlays on the
      soil trajectory with **zero external dependency**.
- [ ] Weather (cloud cover + solar/shortwave radiation, hourly) is ingested from a **documented source**,
      **cached as dated evidence**, and **never silently refetched or rewritten**.
- [ ] Soil readings **join to weather on time + place**; a **day-vs-day** conditions-annotated view exists.
- [ ] The **48 h baseline** (cloudy 06-24 / sunny 06-25, s3) is reproduced as the **first validation case**
      — the drying-rate difference shown against the measured cloud-cover/radiation, with H1 vs H2 called
      out honestly (entangled in these two days; what would disentangle them stated).
- [ ] The weather source has a **registry entry** (origin, cadence, trust class, schema version, discovery
      date) and is labeled **derived/model**, never authoritative.
- [ ] **No trained model** ships unless a named gap earns it; the analysis is classical-first.

## Open questions → decisions (folded into the requirements + ADR-0013)

- **Location & privacy** → **gitignored local config** + a `.example` template; coarsen/qualitative in
  anything committed. (R6 / ADR-0013 §3.)
- **Weather source** → **Open-Meteo** (free, keyless, historical archive + forecast); NWS a US alternative.
  Labeled **derived/model**, cached as dated evidence. (R2, R7 / ADR-0013 §2, §4.)
- **Env data model** → external weather is its **own observation stream** joined on time+place (ADR-0013
  §1); on-device sensors (R8) reuse ADR-0006's **`record_type=env`** in the telemetry stream — two paths,
  one model.
- **Temp = confound, not just colour** → on-board temp feeds **back into ADR-0006 calibration** (separates
  thermal drift from moisture), so R8 is dual-purpose. (ADR-0013 §5.)
- **Local read vs. net pull priority** *(deferred — decide at the junction)* → once on-device
  environmental reads (R8) and net weather (R2) **both** exist, does the **local on-device read take
  priority** over the network pull? Leaning **yes (local-first)**, but not decided until both are real.

## Out of scope / later

- The **on-device sensor tier (R8)** is the largest, hardware-bearing slice — defer to a later phase.
- A **trained / weather-conditioned predictor** — only once the H1/H2 loop demonstrably beats the classical
  baseline (ADR-0006 §7 earns it).
- A **DuckDB/parquet** tier for cross-source queries → when CSV/JSON re-parse gets slow (ADR-0006 ladder).
- **Operational forecasting / watering decisions** from weather → a separate, later decision.
- A **product-wide connectivity model** (whether/how Sprout ever uses a network beyond this optional
  layer, vs. staying host-tethered) → flagged as future design thinking, **out of scope here** — R9 only
  commits *this* epic to never assume connectivity.

## Phasing (tracer bullets)

The build order, once Accepted and sub-issues are cut (each a `Refs` PR through the gate):

1. **Solar + cloud overlay (zero hardware)** — R1–R4 + R6–R7: compute the solar window, ingest + cache
   Open-Meteo cloud-cover/radiation for the rig location (local config), join to the existing soil
   trajectory, and overlay it + a day-vs-day view. **First deliverable: the 48 h cloudy/sunny s3 baseline,
   rendered with its measured conditions.**
2. **H1/H2 decomposition view** — R5: drying-rate-vs-radiation (and vs. dryness), stating honestly what the
   two baseline days can and can't separate, and what a constant-light dry-down would add.
3. **On-device environmental tier** — R8: temp + lux/UV (Firmware), `record_type=env`, feeding **both**
   weather-colour **and** ADR-0006 calibration (thermal-drift separation). The hardware-bearing slice.
