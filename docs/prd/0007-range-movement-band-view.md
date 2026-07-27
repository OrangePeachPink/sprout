# PRD: Range & movement band-lane view

**Status:** Accepted — maintainer, 2026-07-04 <!-- Draft → Accepted → Implemented -->
**Date:** 2026-07-03
**Owner:** Design lane (visual language) + Data lane (build) — requested by the maintainer
**Epic / issues:** #623 (epic — vertical slices routed to Workflow)

---

## Problem

The maintainer can see a plant's *current* band (dashboard cards), its *raw* signal over time (the raw
trajectory line chart), and where the band *boundaries* sit (the calibration ladder — a one-off config
view). What's missing is the view that answers the question she actually asks while tending:

> *Where has this plant/sensor **lived**, and how did it **move**, over the window I care about?*

Two concrete review scales, same shape:

- **Short event (~15 min):** watch a single watering play out — dry → actively watered → water diffusing
  through and draining → the sensor resettling to a new moist median.
- **Long horizon (a week / "since last re-water"):** the same movement-and-range story across a full
  dry-down cycle.

A one-off visual Data built (seven horizontal band lanes, per-sensor markers, dotted connectors showing
where a reading moved *from* and *to*) proved the concept is exactly right. This PRD makes it a live,
first-class view. The calibration ladder was a static setup/config artifact; this is its live counterpart.

## Goals

- A **live, band-centric** view of each plant/sensor's recent **range** and **movement** over a
  **selectable time window**.
- **Reuse the seven calibrated band lanes and tokens** so it reads as one system with the calibration ladder.
- Serve **both** a short event window (~15 min) and a long horizon (24h / 7d / "since last re-water") from
  the same control.
- Stay inside the **reading rules**: raw + band words only, never %; movement shown as discrete transitions,
  never fabricated continuity; unwired / NO_SIGNAL / uncalibrated entities handled honestly.

## Non-goals

- **Not** a replacement for the calibration ladder (static config) or the raw trajectory line chart — both stay.
- **Not** a calibrated moisture % or engineering units.
- **Not** automation, alerting, or watering triggers derived from movement (later).
- **Not** frame-by-frame animation/playback in v1 (a later enhancement).

## Requirements

- **R1.** Render the **seven calibrated bands as horizontal lanes** — same names, order, and
  `--band-*` tokens as the calibration ladder (per ADR-0004; no hardcoded palette).
- **R2.** One **marker per entity** (per-plant or per-sensor, toggleable) showing its **current** band position.
- **R3.** **Range:** show the span of bands the entity touched within the window (a whisker from wettest to
  driest reached).
- **R4.** **Movement:** show direction/trail of recent movement (start → end within the window) as a
  **discrete connector**, visually distinct from continuous interpolation.
- **R5.** **Window selector:** choose the review window, with presets for a short event (~15 min) and long
  horizons (24h / 7d / "since last re-water"), reusing the existing range vocabulary where it fits.
- **R6.** **Live:** updates in place on the dashboard's refresh cadence, tracking the logger as it appends.
- **R7.** **The reading:** raw + band words only, no %; unwired / NO_SIGNAL entities render **no band**;
  `cal_verified=false` renders **provisional** — consistent with the card reading rules and the #486 findings.
- **R8.** **Per-device fencing:** respect the #575 grouping — an entity belongs to exactly one device; no
  cross-device roll-up.
- **R9.** **Identity + provenance:** each row labeled by plant name / sensor id from the registry
  (ADR-0020); each value carries its provenance, consistent with the dashboard.

## Acceptance criteria

- [ ] The view renders the seven band lanes using `sprout-tokens.css` band colors (no forked palette).
- [ ] For a chosen window, each plant/sensor shows **current position + range span + movement direction**.
- [ ] A window selector switches between at least a short (~15-min) and a long (7d / since-last-re-water)
      horizon, and the view updates accordingly.
- [ ] The view updates **live** on the dashboard refresh cadence without a manual reload.
- [ ] No percentage appears anywhere; movement connectors read as **discrete transitions**, not continuous lines.
- [ ] Unwired / NO_SIGNAL / uncalibrated entities are handled honestly (no unearned band), consistent with #486.
- [ ] Entities are **grouped/fenced per device** (no cross-device mixing).

## Open questions

- **Row granularity default** — per-plant, per-sensor, or both (toggle)? Likely both; default per-plant once
  plant assignments exist.
- **"Since last re-water" detection** — from a watering log, a sharp wet transition, or a manual marker? May
  depend on a watering-event stream that doesn't exist yet.
- **Where it lives in the IA** — its own dashboard section vs a tab. Ties directly to the top-level-tabs IA
  work captured in #596.
- **Range semantics** — a band-span whisker vs raw min–max mapped onto the lanes: which reads more honestly
  while the interior band boundaries are still A2-pending?
- **Marker vocabulary** — reconcile the one-off's markers (filled/open circle, triangle, diamond) into the
  design system's marker set (Design lane).

## Out of scope / later

- Playback / scrubbing animation of the movement across the window.
- Alerting or automation triggered by movement or range.
- Cross-plant comparison overlays.
- Inline annotation of watering events (depends on a watering-event stream).

---

*References:* the maintainer's one-off band-lane visual (lanes + per-sensor markers + movement connectors);
the calibration ladder (`docs/design/` + the live dashboard); issue #486 (per-device grouping + honesty
laws); issue #596 (Wave-1 retrospective, where the IA/tab decision lives); ADR-0004 (token contract);
ADR-0007/0008 (honesty + the character↔instrument boundary).

*Drafted by — Design-QA 🔍 (from the maintainer's request; Design owns the visual language, Data builds).*
