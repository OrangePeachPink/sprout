# ADR-0023 — Contextual env columns: multi-source with a `context_source` tag

**Status:** Proposed — *drafted by Data from #418 (a Data call). The **model** below (multi-source + provenance
tag + no-synthesis) is ratifiable now; the one implementation item — adding a `context_source` column to the
schema + `parse_v1` — needs Workflow/Trellis ratification of the schema change (design-light-before-build).*
**Date:** 2026-06-30
**Owner:** Data (author) — host logger / analytics substrate
**Lane:** data (relates: Firmware emits the raw `plants.env` rows · Sage bench placement · Trellis schema register)
**Extends:** [ADR-0006](0006-data-architecture.md) (honest data / source trust classes) ·
[ADR-0021](0021-parse-v1-telemetry-contract-boundary.md) (single parse boundary)
**Relates:** #418 (this decision) · #345 (ESP32 die-temp) · #377 (`plants.env`) · #300 (telemetry v2 header) ·
ADR-0022 (surface disagreement, don't average it) · #416 (config-provenance RFC — the same self-interpreting
reading principle)

---

## Context

The host CSV reserves `temp_context_c`, `rh_context_pct`, `pressure_context_hpa` on every soil row — **empty
today**. The obvious move is to fill them from the concurrent **SHT45** so a `plants.soil` row carries ambient
context join-free. But temp/RH will soon arrive from **several sources at once**, and a single untagged column
becomes uninterpretable the moment there is more than one feed:

- **SHT45** — on-rig (`breadboard_near_esp32`), factory-calibrated (now, via #377).
- **ESP32 die-temp** — board-proxy, uncalibrated (#345).
- **Weather overlay** — external/room/outdoor, `derived/model` (#367/#368).
- **Future Zigbee / Thread** room/area ambient.

This is the same principle #416 raises for sensor knobs: a reading must be **self-interpreting** — you must be
able to tell what produced a context value, and whether two rows' context are comparable. Averaging sources
into one number would violate honest-data (ADR-0006) and the ADR-0022 posture (surface disagreement, never
average it away).

## Decision

1. **`*_context_*` is multi-source *with provenance*, not single-source-by-policy.** Add one column,
   **`context_source`**, naming the feed that produced that row's context values. A context value without its
   source tag is not allowed.

2. **Exactly one source fills a given row's context columns — never a blend.** No averaging, no synthesis. The
   other concurrent sources remain their own `plants.env` rows on the shared time axis, fully queryable; the
   context column only records *which* source was projected onto the soil row, plus its tag.

3. **Default fill precedence — nearest-calibrated-to-the-plant wins:**

   | Order | `context_source` | Trust class (ADR-0006) | Note |
   |---|---|---|---|
   | 1 | `sht45_onrig` | measured / calibrated | factory-cal, on the rig — primary when present |
   | 2 | `esp32_die` | measured / uncalibrated | #345 board-proxy — fallback + drift diagnostic, tagged uncalibrated |
   | 3 | `weather_openmeteo` | derived / model | regional fallback when no on-rig sensor |
   | 4 | `zigbee_room` / `thread_room` | measured / calibrated (room) | area ambient, not plant-local |
   | — | `none` | — | empty columns; nothing available for that row's window |

4. **Per-deployment configurable.** The precedence list lives in config (a future location/deployment config,
   alongside #365); the table above is the default. Reordering is a *deliberate, logged* choice — never adaptive.

5. **Trust class travels with the value.** `context_source` maps deterministically to a trust class so analytics
   never treats a `derived/model` weather temp as an authoritative on-rig measurement. Consistent with the source
   registry (ADR-0006).

6. **Reconciliation is a later view, not a column.** When multiple sources exist, a future confidence/agreement
   view (mirroring ADR-0022's calibration-confidence) compares them from their `plants.env` rows and flags
   disagreement. The context column stays a single honest projection; it does not pre-judge agreement.

## Consequences

- A soil row becomes ambient-aware **join-free** for the common case, while staying honest about provenance and
  trust — no false precision, no hidden source.
- **One schema change** (`context_source`) is the only cross-lane item: it extends TELEMETRY_SCHEMA v2 and
  `parse_v1` (ADR-0021). That is the implementation slice and needs Workflow/Trellis ratification of the column
  before any code lands — this ADR proposes the model, not the column add.
- Firmware is unaffected: it keeps emitting raw per-sensor `plants.env` rows; contextualization is host-side.
- Unblocks the actual fill of `temp_context_c` / `rh_context_pct` from SHT45 (the #418 ask) without painting us
  into a single-source corner when #345 / weather / Zigbee arrive.

## Open (cross-lane, non-blocking to ratify the model)

- **Trellis / Workflow:** ratify the `context_source` column on the schema + `parse_v1` (the one implementation
  gate). — routed `for:trellis` / `for:workflow`.
- **Sage:** confirm `sht45_onrig` placement provenance (`breadboard_near_esp32`) is the right "plant-local"
  primary, or whether a future in-canopy probe should outrank it.

— Data 🌱
