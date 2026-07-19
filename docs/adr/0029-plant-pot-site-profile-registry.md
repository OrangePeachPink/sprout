# ADR-0029 — Plant / pot / site profile registry: the inference dimension

**Status:** Accepted — maintainer-ratified 2026-07-10 (v0.7.2 ADR batch, #915); dimensions are extend-as-needed by
design (absent-safe fields), no exhaustiveness claim. *Drafted by Trellis 2026-07-06 from #675 (#762); revised
2026-07-07 to harden the field model against the five schema-implications on #675 and the #834 dose→response
evidence (2026-07-06). The loader, analysis-tier join, and seed back-fill are Data's half (v0.8.0). Per ADR-0000
§4 this is an in-place edit; git carries the diff.*
**Date:** 2026-07-06 (revised 2026-07-07)
**Owner:** Trellis (architecture) — the profile schema + storage/join model; Data owns the loader (v0.8.0)
**Lane:** architecture (cross-lane: Data)
**Extends:** [ADR-0027](0027-identity-model.md) (the stable `plant_id` key + Plant/Site entities) ·
[ADR-0006](0006-data-architecture.md) (the analysis tier — this is a dimension it joins to) ·
[ADR-0015](0015-no-personal-information-policy.md) (home placement is local-only) ·
[ADR-0028](0028-optional-peripherals-doctrine.md) (absence is first-class — every field optional; species never
gates) · [ADR-0019](0019-capability-and-sensor-matrix.md) (per-channel calibration — the cross-board raw caveat, §6)
**Relates:** #675 (this — the transitional home + the tracked work) · #834 (the dose→response session grounding the
field model) · PRD-0008 / #25 (the predictor that conditions on this) · #833 / #822 / #832 (Predict-wave consumers
that join to this) · #674 (the install prose this supersedes as the *live* home)

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

**The field model is now empirically grounded.** The 2026-07-06 #834 dose→response session measured, per plant,
how the moisture reading answered a known cup of water. It confirmed the three hardest modelling requirements: an
office-conditioned pot crossed bands cleanly on ½ cup while a drought-hardened home pot barely moved on 1–1.5 cups
(soil history is a real covariate); p04's 8-inch nominal pot behaves far smaller (nominal ≠ effective); and p07's
probe read "dry" while standing water sat in the pot's gap (a reading can *misrepresent* the plant's water state).
This revision hardens the schema against exactly those.

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

### 3. Storage mirrors the device registry — and placement *references* it, never duplicates it

- **Committed:** the schema + loader (field definitions, validation, the join) as code, and a placeholder
  template `config/plant_profiles.example.json` documenting the shape.
- **Gitignored local instance:** `config/plant_profiles.local.json` — pot sizes + home placement describe the
  maintainer's windowsill and must stay out of a public-bound repo (ADR-0015), the same fence as
  `config/devices.local.json`. The loader reads it into the analysis tier alongside the device registry.
- **Placement is referenced, not re-stored (implication 4).** A *wired* plant's device, channel, and physical
  side already live in the device registry (ADR-0027; `side` landed via #806). The profile keys on `plant_id` and
  **resolves** those through the plant→device binding — it does not copy `device` / `channel` / `side`. The one
  exception is a **sensorless** plant (p05 / p08 / p09), which has no device binding: for those the profile is the
  *only* home for placement, so `sensorless: true` + `side` + `window` live here. Rule: wired ⇒ reference the
  device registry; sensorless ⇒ the profile carries placement directly.

### 4. The field model (hardened)

Grouped, and **every field is absent-safe** (ADR-0028): a minimal profile is just `plant_id` + `label`; everything
else is *optional enrichment*. A plant is fully monitored with no profile at all — the profile only sharpens
prediction. The three hard cases the maintainer's data forces are called out inline.

| Group | Fields |
|---|---|
| Identity | `plant_id` (stable, ADR-0027), `label` (`p01`…); `species` (asserted — a real recorded id, e.g. a nursery sticker; provenance has a chain) **and/or** `species_guess` + `species_confidence` (inferred). Both absent-safe; **species never gates** (ADR-0028) |
| Placement | wired ⇒ *resolved* via `plant_id`→device registry (§3). Sensorless ⇒ `sensorless: true`, `side` (`left`/`right`), `window` carried here |
| Pot — **nominal** | `diameter_in` (measured top ⌀), `shape` (`standard`/`wide-shallow`), `depth_class` (`normal`/`shallow`), `material` (`terracotta`/`plastic`), `has_drip_tray`, `outer_pot_seal` (`none`/`loose`/`watertight-tight`) |
| Pot — **effective** *(Case 1: separable from nominal)* | `effective_size_class` — an explicit judgement of the volume that actually holds active root+soil, **distinct from `diameter_in`**; `effective_reduction_factors` (multi: `dead-rootball-voids`, `decorative-moss-top`, `shallow-shape`, `rootbound`) — *why* effective < nominal (p04: all but rootbound) |
| Soil / root | `soil_depth_pct`, `root_bound` (`none`/`likely`/`hard`), `dead_rootball_fraction`, `decorative_top` (`none`/`moss`) |
| Hydrology — drainage pathology *(Case 2: first-class)* | `water_delivery_path` (`topsoil` / `inner-outer-gap-sip` (p05) / `inner-outer-gap-stagnate` (p07) / `drip-tray-resoak` (p10)); `retention_class` (`chronically-waterlogged` / `good` / `poor-wicking-drought-cycled` / `resoak-buffered`); `drainage_note` (free text) |
| Hydrology — probe trust *(Case 2: the reading can mislead)* | `probe_contact_quality` (`poor`/`good`/`best` — physical contact); `probe_reading_caveat` (`represents` (default) / `may-underread-standing-water` (p07) / `may-miss-gap-reservoir` (p05) / free note) — **whether the probe's location represents the plant's true water state**, distinct from contact quality |
| Soil condition *(Case 3: its own covariate)* | `soil_condition` — physical **state**: `well-wicking` / `clumpy-retentive` (p10) / `hydrophobic-non-wicking` (drought-cycled home). The predictor conditions on the *state*; `care_origin` below is the *cause* |
| Care history | `care_origin` (`office`/`home` — the cause), `watering_cadence`, `rejuvenation_routine`, `drought_cycled` (bool) |
| Provenance *(implication 5)* | `observed_by` (e.g. `maintainer`), `observed_date` (ISO), `method` (e.g. "tape, top edge-to-edge, approximated past the live plant; ±0.5in class") — these are **observations, dated, not specs** |
| Open questions | `open_questions` (free text) |

The three hard cases are now separable, first-class attributes rather than free-text notes: **nominal vs effective
pot volume** (two explicit sub-groups + the reduction factors that link them), **drainage pathology** (a
`water_delivery_path` enum that names p07's stagnation trap distinctly from p05's gap-sip and p10's resoak), and
**soil condition** (a `soil_condition` *state* split from `care_origin` the *cause*). The p07 insight — a probe
that reads dry over flooded gap water — becomes `probe_reading_caveat`, the tell a predictor must honour.

### 5. Plain reference data — a guess is labelled a guess, an observation is dated (ADR-0006)

The profile is **human-asserted reference data** (the maintainer's observations), not measured or derived — it is
labelled as such, and now **carries its own provenance** (`observed_by` / `observed_date` / `method`). Uncertainty
travels with the value: `species_guess` carries `species_confidence`, and is distinct from an asserted `species`
(a recorded sticker beats an inference — provenance has a chain); `effective_size_class` is an explicit judgement,
separate from the measured `diameter_in`. **Open questions are first-class** (`open_questions`) — the model does
not force false certainty where the maintainer has none (e.g. "does p05 need a beyond-the-windowsill floor-pot
strategy?" stays an open question, not a fabricated field). The field model is **validated against the full #675
seed** — every observation maps to a field.

### 6. Prediction-consumer caveats (what PRD-0008 must honour)

The profile *conditions* inference; it does not by itself make readings comparable. Two caveats travel with it:

- **Raw is per-board, not cross-comparable.** The classic ESP32 and the C5 have different ADCs / dynamic ranges;
  raw counts and provisional bands do **not** compare across boards (#834). Cross-plant inference must go through
  **per-channel calibration first** (ADR-0019 / #170) — the profile conditions *after* calibration, it is not a
  substitute for it.
- **A probe reading can misrepresent the plant.** Where `probe_reading_caveat` is set (p07), the profile is
  telling the predictor to *distrust that channel's raw as a proxy for the plant's water state* — the reading is
  accurate about the sensor, but the sensor is not seeing the water that matters.

### 7. Scope

- **This ADR (schema, Trellis):** the schema decision + the hardened field model above. **Draft-only** — this
  revision does **not** touch `config/plant_profiles.example.json`; the template gains the new fields as part of
  Data's loader build (they must match the loader anyway), or a Trellis fast-follow once ratified. Zero
  hardware / actuation risk, zero code change here.
- **Data, v0.8.0 (#675):** the loader + validation + the analysis-tier join so predictions can condition on it, the
  matching `example.json` field update, and **back-fill the #675 seed** into the gitignored local instance.

## Consequences

- The install-day observations become a first-class, queryable, **versioned** dimension keyed by the stable
  `plant_id` — no more stale references to a closed PR.
- The predictor (PRD-0008) conditions on real covariates — *effective* pot volume, drainage pathology, soil
  *condition* — instead of a bare raw, and is warned where a probe reading cannot be trusted as a water proxy.
- Nominal and effective size stay separable, so the recorded measurement (`diameter_in`) is preserved *and* the
  judgement that p04 behaves smaller is captured — neither overwrites the other.
- Home placement stays gitignored (ADR-0015); the public-bound repo carries only the schema + placeholder example;
  wired placement is not duplicated out of the device registry.
- The dimension grows additively (new fields absent-safe); a profile is **never required** to monitor a plant
  (identity + telemetry stand alone — ADR-0028), so a bare `plant_id` is always valid.

## Rejected alternatives

- **Extend ADR-0027.** Rejected: it overloads the identity ADR with a rich attribute/dimension schema that is a
  different concern (analysis-tier modelling, not wire identity). 0027 answers *who*; this answers *what it is
  like*. Two single-concern records beat one bloated one.
- **Put the profile in the telemetry stream.** Rejected: it is a slowly-changing dimension, not a per-reading
  fact; repeating pot geometry on every row is a modelling error. It belongs in a dimension joined on `plant_id`.
- **Collapse nominal and effective size into one number.** Rejected: a predictor keyed on nominal Ø is badly wrong
  (p04), but the nominal measurement is still the recorded, re-checkable fact. Keep both, linked by
  `effective_reduction_factors`.
- **Trust every probe reading equally.** Rejected: p07 proves a probe can systematically misread the plant's water
  state; the profile must carry that caveat so the predictor can down-weight it.
- **Duplicate placement into the profile.** Rejected for wired plants: `side`/device/channel already live in the
  device registry (ADR-0027) — reference them; only sensorless plants carry placement here.
- **Commit the real seed data.** Rejected: pot sizes + home placement are the maintainer's windowsill (ADR-0015
  PII). Committed artifacts are placeholder-only; the real instance is gitignored.

## Open (routed)

- **Data (v0.8.0, #675):** build the loader + validation + the analysis-tier join; update `example.json` to the
  hardened field model; back-fill the #675 seed into `config/plant_profiles.local.json`. Ping me on the loader PR
  and I conformance-review the join keys on `plant_id` and the placement-resolution seam (§3).
- **Trellis:** the `species_confidence` vocabulary, the `effective_size_class` scale, and the
  `probe_reading_caveat` enum can tighten once Data's loader surfaces how the predictor consumes them — a
  fast-follow, not a blocker.

— Trellis 🪴
