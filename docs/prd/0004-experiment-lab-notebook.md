# PRD: Experiment Lab Notebook — catalog, analysis, and a living log of what we learned

**Status:** Draft — **ready for review** (maintainer-requested 2026-06-26)
**Date:** 2026-06-26
**Owner:** Data lane (with Design; minimal Firmware)
**Epic / issues:** *cut from this PRD via `/to-issues` into tracer-bullet slices*
**Relates:** [ADR-0005](../adr/0005-application-surface-and-frontend.md) (the served surface this extends),
[ADR-0006](../adr/0006-data-architecture.md) (raw-immutable + derived tiers),
[ADR-0011](../adr/0011-experiment-capture-control-plane.md) /
[ADR-0012](../adr/0012-experiment-data-architecture.md) (how captures are recorded),
[PRD-0001](0001-experiment-capture-mode.md) (Experiment capture — the recording side this reviews).
Builds on / folds in [#27](https://github.com/OrangePeachPink/plants/issues/27) (DuckDB/parquet analysis tier),
[#24](https://github.com/OrangePeachPink/plants/issues/24) (review analytics + per-cycle features),
[#17](https://github.com/OrangePeachPink/plants/issues/17) (calendar/temporal fields). A new ADR
(experiment-notebook data model + notes durability + analysis tier) is authored when the data-model slice is cut.

---

## Problem

Experiment Capture (Epic 1) can **record** bounded captures — but once recorded, an experiment effectively
disappears. Each lands in `experiments/<id>/` as a CSV plus a `manifest.json`, and there is no way to:

- **See what experiments exist** — you'd have to browse a gitignored folder by hand.
- **Load one for review** — there is no per-experiment analysis view.
- **Record what you were trying to learn**, what you ran, and what you concluded.
- **Connect a group of experiments** into a single finding.

So captures accumulate as opaque files, and the knowledge — *why* we ran it, *what* we tried, *what we
concluded* — lives only in the operator's head or in a chat that scrolls away. The project's own doctrine is
"truth has a chain" and "learning is part of the deliverable"; right now the experiment chain stops at the
raw CSV.

> Maintainer, 2026-06-26: *"Will there be a separate 'load experiment for analysis' pipeline where I can see
> the catalog of past experiments — title, metadata, date, time, duration, number of samples — and record
> some thoughts on the hypothesis of what we were trying to identify or prove or learn, the analytics and
> statistics we ran, and our conclusion on the pattern, so we have a living log of 'we thought of X, we tried
> Y1/Y2/Y3 against it, and now we conclude Z'?"*

## Goals

- **A catalog of every experiment** — all past captures at a glance, with their metadata, sortable/filterable.
- **Load-for-analysis** — open any capture into a review view: its trajectory + descriptive stats per probe.
- **A living lab notebook** — record, per experiment, the **Hypothesis → Method → Findings → Conclusion**,
  kept durably alongside the evidence.
- **Studies** — group related experiments into one finding: *"we thought X, tried Y1/Y2/Y3, concluded Z."*
- **Durable knowledge** — the notes (the precious part) are backed up, not stranded in a gitignored folder.

## Non-goals

- **Not heavy ML / prediction** — this is the descriptive review + notebook layer; the predictor is a later epic.
- **Not editing raw capture data** — captures are immutable evidence; the notebook layers interpretation on top.
- **Not a change to how captures are recorded** — Epic 1 owns that; this is the read/review side.
- **Not the always-on monitor dashboard** — that surface already exists; the Notebook is the *experiment*-centric
  view (they can share substrate, but the monitor's live logging is untouched).

## What already exists (this builds on it)

- **Experiment captures** (Epic 1, #62) — each `experiments/<id>/` holds `<id>.csv` plus **`manifest.json`**
  carrying `experiment_id`, `subject`, `sample_rate_s`, `duration_s`, `stopped_by`, per-probe `labels`,
  `started_utc` / `ended_utc`, `capture_version`, and a `transport` block (`rows`, `sweeps`, `dropped`,
  `crc_fail`, `idle_noise`). **The catalog reads these manifests** — no CSV re-parse to list.
- **The served dashboard** (`serve.py` + `dashboard_template.html`, ADR-0005) — the surface the Notebook plugs
  into as a new view; the channel-card stats (median / spread / slope / range / band) are the per-probe stat
  vocabulary to reuse.
- **The schema-v2 parser** (`parse_v1` / analytics tier) — parses a capture CSV into readings for the detail view.
- **Adjacent analytics backlog** — #27 (DuckDB/parquet tier), #24 (review analytics + per-cycle feature
  table), and #17 (calendar/temporal fields): the substrate this draws on at scale.

## Requirements

- **R1 — Experiment catalog.** A browsable list of every capture, built from `manifest.json` (no CSV re-parse to
  list): title (human `subject` / label), date·time (`started_utc` + local), **duration**, **sample count**
  (`sweeps` / `rows`), source, per-probe labels, and a quality glance (`dropped` / `crc_fail`). Sortable +
  filterable (by subject, date, study).
- **R2 — Load-for-analysis (detail view).** Open a capture → its raw trajectory chart + **per-probe descriptive
  stats** (median, spread, range, slope, band) + the manifest facts. This is #24's descriptive layer applied to
  one experiment — "load experiment for analysis," answered.
- **R3 — Lab notes (the living log).** Per experiment, an editable, durable record with at least: **Hypothesis**
  (what we set out to identify / prove / learn), **Method** (what we ran / the conditions), **Findings** (what the
  stats showed), **Conclusion** (the pattern we concluded). Authored in-app; saved beside the experiment; versioned.
- **R4 — Studies (grouping + roll-up).** Group related captures into a named **study** (e.g. *common-cup
  wet/dry/air-dry characterization*) with a study-level living-log entry and a side-by-side compare across its
  members → the *"we thought X, tried Y1/Y2/Y3, concluded Z"* record.
- **R5 — Durable, separated knowledge.** Raw captures are immutable evidence; **the notebook notes are human
  interpretation, clearly distinct and never rewriting the data** (doctrine: interpretation is a layer, not a
  source). Because `experiments/` is **gitignored / local-only**, the **notes must have a durable, backed-up home**
  (tracked, or pushed like the monitor archive) so a disk loss can't erase the living log. *(Exact home is the
  ADR's call.)*
- **R6 — Scales without re-parsing.** Catalog + cross-experiment views stay responsive as captures accumulate —
  via a derived, rebuildable index/store (folds in #27's DuckDB/parquet tier, #24's per-experiment feature
  set, and #17's calendar fields). Derived + gitignored + rebuildable from raw; never the source of truth.
- **R7 — Token-faithful, Design-owned UI.** The catalog, detail, notes editor, and studies views follow the Sprout
  design system; no net-new UI primitives without Design. The always-on auto-logger archive to `origin/data`
  continues unchanged.

## Lane split

- **Data:** the catalog index (manifest reader), the detail-view stats, the notes data model + persistence +
  durability, the studies model, the analysis substrate (#27/#24/#17). Authors the experiment-notebook ADR (data
  model + notes durability + analysis-tier decision) when the data-model slice is cut.
- **Design:** the Lab/Notebook UX — catalog cards, the detail layout, the notes editor (Hypothesis / Method /
  Findings / Conclusion), the studies view — token-faithful (Sprout).
- **Firmware:** minimal — confirm the capture `manifest.json` carries everything the catalog needs (it largely
  does); no device change expected.

## Acceptance criteria

- [ ] The operator can **see a catalog** of all past experiments — title, date·time, duration, sample count —
      without opening a file browser (R1).
- [ ] The operator can **open any experiment** and see its trajectory + per-probe stats — "load for analysis" (R2).
- [ ] The operator can **write and save** a Hypothesis / Method / Findings / Conclusion per experiment, and it
      **persists durably** (survives a relaunch; backed up, not only in gitignored `experiments/`) (R3/R5).
- [ ] The operator can **group experiments into a study** and record a study-level conclusion; the members are
      viewable together (R4).
- [ ] Raw capture data is **never modified** by the notebook; notes are clearly an interpretation layer (R5).
- [ ] The catalog stays responsive across many experiments (R6), and the UI is token-faithful (R7).
- [ ] The existing capture-recording path and the monitor auto-archive are **behaviourally unchanged** — this adds
      a read/review surface, it does not alter recording.

## Phasing (tracer bullets)

Cut via `/to-issues`; each a `Refs` PR through the gate:

1. **Catalog (read-only).** R1 — a Lab view listing experiments from their manifests: title, date·time, duration,
   samples, labels. **First win: every past experiment visible in one place, no folder-browsing.**
2. **Detail / load-for-analysis.** R2 — open a capture → trajectory + per-probe descriptive stats + manifest facts.
3. **Lab notes.** R3 + the durability half of R5 — author + persist Hypothesis / Method / Findings / Conclusion per
   experiment, in a durable / backed-up store. **Authors the experiment-notebook ADR.**
4. **Studies + roll-up.** R4 — group captures into a study, a study-level conclusion, side-by-side compare → the
   living log of *"thought X, tried Y1/Y2/Y3, concluded Z."*
5. **Analysis substrate (scale).** R6 — the derived DuckDB/parquet index + per-experiment feature set + calendar
   fields (folds in #27/#24/#17), so catalog + studies stay fast and queryable. *(Can move earlier if the catalog
   needs it sooner.)*

## Out of scope / later

- ML prediction / anomaly detection over the feature set — a later epic; the substrate here enables it.
- Cross-project joins (e.g. the companion air-quality project's environmental context against an
  experiment) — PRD-0002's territory, joinable later via the shared telemetry schema.
- Exporting a study as a published report artifact — a later nicety once the living log exists.
