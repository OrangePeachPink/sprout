# Reference: late-night irrigation variants (NOT ACTIVE)

**Status: ARCHIVED REFERENCE - NOT COMPILED, NOT WIRED, NOT THE BASELINE.**

These files are uncommitted late-night prototypes from **2026-06-23**, developed in a separate thread and never
checked into git as they were written. They are preserved here purely as **design reference** for whoever builds
out the irrigation supervisor and its roadmap items (A1, A3, D1-D4). They live under `docs/` (outside
`firmware/lib` and `firmware/src`) and are renamed with `_designB` / `_designC` suffixes so **no build ever picks
them up**.

The canonical, active irrigation engine is [`firmware/lib/irrigation/irrigation.{c,h}`](../../../firmware/lib/irrigation/).
Do not build against anything in this folder.

## What's here

- `irrigation_designB.{c,h}` - **"design B"**: a leaner rewrite (`irrigation_t`, a `wants_water()` predicate,
  simple callbacks). **This is where the A1 health-veto latch (`max_health_warn` + `warn_count`) and the
  `irrigation_health_warn()` accessor were first written.** It was the source for the A1 graft into the active
  module.
- `irrigation_controller_designC.{c,h}` - **"design C"**: an earlier ancestor of the active `irrig_ctrl_t`
  design (string event seam, `max_consecutive_doses`, 9-band enum names like `MOIST_WATER_CONTACT`). Source of
  the `last_water_ms` telemetry idea. Otherwise superseded by the active module; would not compile against the
  committed 7-band classifier.

## How the active module relates (best-of-all-worlds synthesis, 2026-06-23)

The active `firmware/lib/irrigation/irrigation.{c,h}` is a deliberate synthesis of all the variants:

- **A (the committed skeleton, kept as the base):** structured `irrig_event_t` logging seam, true
  no-improvement fault (`min_improvement_raw`), pump-overrun failsafe, anti-starvation rotation, dose-to-target
  hysteresis.
- **B -> grafted in:** the `max_health_warn` sustained-fault latch, per-channel `warn_count`, and the
  `irrig_health_warn()` accessor (**BACKLOG A1**).
- **C -> grafted in:** the `last_water_ms` per-channel last-dose timestamp (feeds **D1** pump logging and
  **E3** interval prediction).
- **D (new design work):** clean accessors (`irrig_health_warn`, `irrig_warn_count`, `irrig_last_water_ms`),
  a distinct `IRRIG_EV_HEALTH_FAULT` event, and backlog-hook docs so downstream items build cleanly.

## Other late-night artifacts (routed elsewhere, not archived here)

- **9-band `moisture_classifier.{c,h}`** (pasted the same night): superseded by the committed **7-band**
  classifier (`f42ced4`, v0.6.0). Recoverable from git history; not re-archived. Do not reintroduce.
- **Old `plants_project_backlog.md`** (pasted the same night): superseded by the committed `BACKLOG.md`
  (which has B8 + Section E's E5-E7 + the 7-band A2).
- **`plant3_moisture_dashboard.html`** (pasted the same night): analytics/dashboard work (Rung-3 data, dark
  theme - not Sprout-styled). Belongs to the **analytics thread** (BACKLOG E2/E7), not firmware reference.

_Provenance: messy late-night session, 2026-06-23; left out of git as it was developed._
