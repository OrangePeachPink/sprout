# ADR-0029 — Plant / pot / site profile registry: the inference dimension

**Status:** Proposed — *drafted by Trellis (2026-07-06) from #675 (the schema half). Owns the schema decision
and the site/placement model; the loader, analysis-tier join, and seed back-fill are Data's half (v0.8.0).*
**Date:** 2026-07-06
**Owner:** Trellis (architecture) — the profile schema + storage/join model; Data owns the loader (v0.8.0)
**Lane:** architecture (cross-lane: Data)
**Extends:** [ADR-0027](0027-identity-model.md) (the stable `plant_id` key + the Plant / Site entities) ·
[ADR-0006](0006-data-architecture.md) (the analysis tier — this is a dimension it joins to) ·
[ADR-0015](0015-no-personal-information-policy.md) (home placement is local-only)
**Relates:** #675 (this — the transitional home + the tracked work) · PRD-0008 (the predictor that conditions on
this) · #674 (the install-record prose this supersedes as the *live* home) · ADR-0028 (absence is first-class)

---

## Context

The install produced rich reference data about each plant, pot, soil, and placement — pot geometry, drip-tray
resoak behaviour, inner/outer-pot water paths, root-bound state, drought-cycle history, probe-contact quality,
care origin. Right now it lives as prose in a **closed PR (#674)** and the maintainer's notes. Closed-issue
numbers go stale the moment we move on; this data needs to become a **first-class, queryable, versioned record**
the inference layer can join to.

A raw ADC count means *different things* in a 2-inch succulent vs a 10-inch drought-cycled pothos vs a
terracotta drip-tray resoaker. Pot geometry, soil-retention class, and care history are exactly the covariates
that turn a bare raw into a plant-aware prediction. This is the **dimension table the predictor (PRD-0008) will
condition on.**

## Decision

### 1. This is a new ADR, not an ADR-0027 extension — because it is a *dimension*, not identity

ADR-0027 defines the Plant and Site **identity** (the stable `plant_id` key + the mutable display labels).
This ADR defines the Plant / Pot / Site **profile** — the slowly-changing set of *attributes* keyed by that
identity, which the inference tier joins to. **0027 = who the plant is; 0029 = what it is like.** Keeping them
separate keeps each single-concern: 0027 is not overloaded with pot geometry, and 0029 owns the rich attribute
schema + the analysis-tier join. This ADR *uses* 0027's `plant_id` and *feeds* ADR-0006's analysis tier.

### 2. It is a dimension, not telemetry

Telemetry (`parse_v1`, per-reading) is the **fact stream**; the profile is a slowly-changing **dimension**
keyed by the stable `plant_id`. Facts join to the dimension on `plant_id` in the analysis tier (ADR-0006). The
profile is **not** repeated on every wire row — it is not a telemetry field, it is a lookup a reading resolves
through, exactly like plant attribution resolves through the device registry.

### 3. Storage mirrors the device registry (ADR-0027), and home placement stays local (ADR-0015)

- **Committed:** the schema + loader (field definitions, validation, the join) as code, and a placeholder
  template `config/plant_profiles.example.json` that documents the shape.
- **Gitignored local instance:** `config/plant_profiles.local.json` — because **pot sizes + home placement
  describe the maintainer's windowsill** and must stay out of a repo that may go public (ADR-0015), the same
  fence as `config/devices.local.json`. The loader reads it into the analysis tier alongside the device
  registry.

### 4. The field model

Grouped, and **every field is absent-safe** (ADR-0028): a minimal profile is just `plant_id` + `label`;
everything else is *optional enrichment*. A plant is fully monitored with no profile at all — the profile only
sharpens prediction.

| Group | Fields |
|---|---|
| Identity | `plant_id` (stable, ADR-0027), `label` (`p01`…), `species_guess` + `species_confidence` |
| Placement / site | `window`, `ledge` (`left`/`right`), wired `device` + `channel`, or `sensorless: true` |
| Pot | `diameter_in`, `shape` (`standard`/`wide-shallow`), `material` (`terracotta`/`plastic`), `has_drip_tray`, `outer_pot_seal` (`none`/`loose`/`watertight-tight`), `effective_size_class` |
| Soil / root | `soil_depth_pct`, `root_bound` (`none`/`likely`/`hard`), `dead_rootball_fraction`, `decorative_top` (`none`/`moss`) |
| Hydrology | `water_delivery_path` (`topsoil`/`inner-outer-gap-sip`/`drip-tray-resoak`), `retention_class` (`chronically-waterlogged`/`good`/`poor-wicking-drought-cycled`/`resoak-buffered`), `drainage_note`, `probe_contact_quality` (`poor`/`good`/`best`) |
| Care history | `care_origin` (`office`/`home`), `watering_cadence`, `rejuvenation_routine`, `drought_cycled` |
| Open questions | `open_questions` (free text) |

### 5. Honest reference data — a guess is labelled a guess (ADR-0006)

The profile is **human-asserted reference data** (the maintainer's observations), not measured or derived — it
is labelled as such. Uncertainty travels with the value: `species_guess` carries `species_confidence`;
`effective_size_class` is an explicit judgement, separate from the measured `diameter_in`. **Open questions are
first-class** (`open_questions`) — the model does not force false certainty where the maintainer has none (e.g.
"does this plant need a beyond-the-windowsill floor-pot strategy?" stays an open question, not a fabricated
field). The field model is **validated against the full #675 seed** — every observation maps to a field (dead
rootballs → `dead_rootball_fraction` + `effective_size_class`; a watertight outer pot with no topsoil →
`outer_pot_seal` + `water_delivery_path`; drip-tray resoak → `water_delivery_path` + `retention_class`).

### 6. Scope

- **v0.7.1 (this ADR):** the schema decision + the field model + the committed `plant_profiles.example.json`
  template. Pure host-side dimension data — zero hardware / actuation risk.
- **Data, v0.8.0 (#675):** the loader + validation + the analysis-tier join so predictions can condition on it,
  and **back-fill the seed** (the maintainer's verbatim #675 observations) into the gitignored local instance.

## Consequences

- The install-day observations become a first-class, queryable, **versioned** dimension keyed by the stable
  `plant_id` — no more stale references to a closed PR.
- The predictor (PRD-0008) conditions on real covariates (pot geometry, hydrology, care history) instead of a
  bare raw — a 2-inch succulent and a 10-inch drought-cycled pothos are no longer read on one scale.
- Home placement stays gitignored (ADR-0015); the public-bound repo carries only the schema + placeholder
  example.
- The dimension grows additively (new fields absent-safe); a profile is **never required** to monitor a plant
  (identity + telemetry stand alone — ADR-0028), so a bare `plant_id` is always valid.

## Rejected alternatives

- **Extend ADR-0027.** Rejected: it overloads the identity ADR with a rich attribute/dimension schema that is a
  different concern (analysis-tier modelling, not wire identity). 0027 answers *who*; this answers *what it is
  like*. Two single-concern records beat one bloated one.
- **Put the profile in the telemetry stream.** Rejected: it is a slowly-changing dimension, not a per-reading
  fact; repeating pot geometry on every row is a modelling error. It belongs in a dimension joined on
  `plant_id` (ADR-0006).
- **Commit the real seed data.** Rejected: pot sizes + home placement are the maintainer's windowsill (ADR-0015
  PII). Committed artifacts are placeholder-only; the real instance is gitignored.

## Open (routed)

- **Data (v0.8.0, #675):** build the loader + validation + the analysis-tier join; back-fill the #675 seed into
  `config/plant_profiles.local.json`. Ping me on the loader PR and I conformance-review the join keys on
  `plant_id`.
- **Trellis:** the `species_guess` confidence vocabulary and the `effective_size_class` scale can tighten once
  Data's loader surfaces how the predictor consumes them — a fast-follow, not a blocker.

— Trellis 🪴
