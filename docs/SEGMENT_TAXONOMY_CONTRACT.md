<!-- cspell:words drydown -->

# Segment taxonomy contract — the C1 written contract (#1245)

**Status:** v1 — the ratified shape (#1245, Trellis PASS on the #1244 C0 evidence,
2026-07-19) with the containment fold landed (`flagged`, never a second `SUSPECT`).
**Owner:** Data (this doc + `tools/analytics/segment_classifier.py`); **Trellis** reviews
contract changes. **One-taxonomy rule:** the wire's exception vocabulary is owned by
**#1152 / [ADR-0035](adr/0035-band-model-and-instrument-exceptions.md) §2** — this
contract **consumes it, never authors a second copy**. **Relates:** #863 (the epic) ·
the #1244 C0 tracer · `docs/TIER_STORE_CONTRACT.md` (the store these segments classify
over).

---

## 1. The four kinds (per-row, per (device, sensor), precedence-ordered)

| kind | meaning | rule (C1) |
| --- | --- | --- |
| `flagged` | the wire flagged the row — an explicit **rollup over the #1152 exception vocabulary**, never a redefinition | any `quality_flag != OK` today; the #1152 `fault=` kinds fold in as they ship (`open_adc`, `rate_spike`, …). Highest precedence. |
| `watering-transient` | a sustained wettening run (the drink arriving) | onset: single-step fall ≥ `ONSET_DROP_RAW` (60); extends while within `NOISE_RAW` (25) of the **running trough**; confirms at total fall ≥ `CONFIRM_DROP_RAW` (150). Catches gentler drinks than the ≥2-band detector (the Bromeliad case). |
| `rebound` | post-transient equilibration — water redistributing; rising raw here is **not** drying evidence | **rate-based (C1):** persists while the forward `REBOUND_WINDOW_M` (30 min) slope ≥ `REBOUND_RATE_CH` (+30 c/h), hard-capped at `REBOUND_MAX_H` (6 h). *(C0's fixed 3 h time-box retired — it truncated slow recoveries like the splash-evaporation arc and over-held fast settles.)* |
| `steady-drying` | the default state between events — the only arc that is drying evidence | everything else |

Precedence per row: `flagged` > `watering-transient` > `rebound` > `steady-drying`.

All constants are **calibrated defaults, Data-tunable**; changing them re-derives
segments (cheap, derived), never touches raw.

## 2. The valid-for-trend mask

`valid_for_trend(rows)` = **steady-drying rows only**. A fit through a transient,
rebound, or flagged row is fitting a different physical process (the live
"+206 c/h *drying* while Soaked" was a rebound being averaged). Consumers: the
Workbench trend fit (shipped, reports `mask_dropped`); forecasts + the next-watering
predictor (#1243/#25) MUST consume the same mask; a freshly-watered segment with no
steady arc yet honestly fits **nothing**.

## 3. The watering PASS (derived event cluster — the #877 retro seam, adopted)

The operator's unit of work is the **pass**, not the plant: she waters the sill as one
event cluster.

- **Definition:** a pass = a fleet-wide, time-gap-clustered group of watering evidence
  (classifier `watering-transient` onsets ∪ manual glug events), with its own identity
  (`pass_id` = the ISO start-minute of the cluster).
- **Threshold:** `PASS_GAP_MIN` = **75 minutes**, a calibrated contract parameter — the
  calibration set is the maintainer's four stated session-truths (07-10 midday incl.
  the dose series · 07-11 eve · 07-13 eve · 07-19), which 75 min reproduces **4/4**
  while a naive 30 min splits the 07-10 session.
- **Placement fences:** the pass is **derived at read/materialize** — the D1 raw tier
  stays wire-truth (a pass is an operator fact, not a wire fact; D2+'s event layer may
  carry `pass_id` as a derived dimension, never a raw column), and the glug journal's
  append-only per-tap write format is unchanged (the pass is a read-time grouping).
- **Consumers:** journal display (one pass row) · the #822 "since the last pass" range
  anchor · pass-level confirm/reject (#1203) · settled-readings-per-pass cal evidence.

## 4. Provenance + shape

Segments and passes are **derived and disposable** — recomputed from raw (or the tier
store) on demand; never a source of truth; never hand-edited. The API shape is the C0
surface: `classify(rows) -> [kind]`, `segments(rows) -> [Segment(kind, i0, i1, t0,
t1)]`, `valid_for_trend(rows) -> [bool]`, plus C1's `passes(events) -> [Pass]`.
Kind strings are this contract's §1 tokens, verbatim — consumers never re-map them.
