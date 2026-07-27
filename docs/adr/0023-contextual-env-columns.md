# ADR-0023 — Two context families: interior ambient vs exterior conditions

**Status:** Accepted — *the maintainer ratified v2 on 2026-07-02, same day as directing the rework (v1
conflated two physically unrelated environments under one precedence table; the maintainer's design review
found it). Drafted by Workflow from the maintainer's direction; Data confirms as author lane post-ratification.*
**Date:** 2026-06-30 (v1) · 2026-07-02 (v2 rework)
**Owner:** Data — host logger / analytics substrate
**Lane:** data (relates: Firmware emits the raw `plants.env` rows · Sage bench placement · Trellis schema register)
**Extends:** [ADR-0006](0006-data-architecture.md) (raw-first data / source trust classes) ·
[ADR-0021](0021-parse-v1-telemetry-contract-boundary.md) (single parse boundary)
**Relates:** #418 (this decision) · #345 (ESP32 die-temp — *excluded from context, see Decision 5*) · #377
(`plants.env`) · #366/#367 (solar geometry + weather ingestion — the exterior family) · ADR-0022 (surface
disagreement, don't average it) · PRD-0006 R4 (exterior conditions refine the runway forecast)

---

## Context

The host CSV reserves `temp_context_c`, `rh_context_pct`, `pressure_context_hpa` on every soil row — empty
today. v1 of this ADR proposed filling them from a single precedence list spanning every available source:
on-rig sensor, ESP32 die temperature, a weather feed, room sensors.

**The maintainer's review found the core flaw: that list mixes sources that do not measure the same physical
thing.** A plant on an indoor windowsill sits behind glass: the air it actually lives in is the *house's*
interior air, causally decoupled from outdoor temperature, rain, and humidity. Projecting a weather-feed
temperature into the plant's ambient-context column is not "lower-trust context" — it is a value for a
different environment wearing a context costume. Meanwhile exterior conditions *do* matter — but for what they
actually drive: sun position and angle through the window, expected sun-hours, cloudiness, season, and the
growth cycle the plant is in.

A context value must be **self-interpreting** (the #416 principle), and it must first be **the right quantity
at all**. That forces a split.

## Decision

**Context is two separate families. They never fill each other's columns.**

### 1. Interior ambient — the air the plant is actually in

The reserved soil-row columns (`temp_context_c`, `rh_context_pct`, and `context_source`) belong to this family
exclusively. Fill precedence is by **proximity class**, not by instrument brand:

| Tier | Proximity class | Example `context_source` values | Trust class (ADR-0006) |
|---|---|---|---|
| 1 | `plant_local` — an on-rig / in-canopy T·RH sensor | `sht45_onrig`, future in-canopy probes | measured / calibrated |
| 2 | `room` — smart-home ambient for the room/area | `zigbee_room`, `thread_room`, `matter_room`, `ecobee`, `ha_ambient` | measured / calibrated (room) |
| — | `none` — nothing local exists | columns stay empty | — |

- The class is the tier; the `context_source` value records the actual instrument (provenance). An `SHT45` is
  one *instance* of `plant_local` — most deployments will have no plant-local sensor and a growing share will
  have some room-class source; the model must welcome whatever instrument a user actually has.
- **A weather feed never fills interior temperature or humidity. Empty is accurate; projected weather is not.**
- Exactly one source fills a given row's interior columns — never a blend, never synthesis (ADR-0022 posture).
  Other concurrent sources remain their own `plants.env` rows, fully queryable.
- A context value without its `context_source` tag is not allowed; the tag maps deterministically to a trust
  class (ADR-0006) that travels with the value.

### 2. Exterior conditions — what the sun and season are doing

The weather ingestion (#367) and solar geometry (#366) time-series **are this family, and they already
exist** as their own datasets. This ADR names their purpose and fences them:

- They drive **light and cycle analytics**: sun position/angle through the window, expected sun-hours,
  cloud/irradiance, season, expected growth cycle — and PRD-0006 R4's runway-forecast refinement.
- They are **never projected onto a soil row's interior ambient columns**. Correlation between the families is
  analysis-time work against both datasets, not a column fill.

### 3. The pressure exception

Buildings are not pressure vessels: indoor barometric pressure tracks outdoor closely. `pressure_context_hpa`
**may** therefore fill from the exterior family (e.g. `context_source=weather_openmeteo` for the pressure
column only), explicitly tagged. This is stated as physics, not as a crack in the fence — temperature and
humidity remain interior-only.

### 4. Per-deployment configuration — deliberate, logged, never adaptive

The tier list lives in deployment config (alongside #365). Reordering within the interior family, or an
explicit open-air override (a genuinely outdoor plant whose ambient *is* the weather) is a deliberate, logged
choice. The default for every indoor deployment is the table above with weather fenced out. Nothing reorders
itself.

### 5. ESP32 die temperature is not context — at all

Die temp (#345/#536) is chip junction temperature: a **development and drift diagnostic**, self-heated well
above ambient, plainly labeled `board-proxy — never ambient` by its own implementation. It stays exactly what
it is — its own labeled `plants.env` row type for dev-team analytics — and never fills any context column in
any tier. It is not a production runtime value for a deployed Sprout.

### 6. Reconciliation is a later view, not a column

When multiple interior sources exist, a future confidence/agreement view (mirroring ADR-0022) compares them
from their own rows and flags disagreement. The context columns stay a single accurate projection.

## Consequences

- A soil row becomes ambient-aware join-free **with the right quantity**: interior air, from the nearest real
  instrument, or plainly empty.
- The exterior family needs **no new storage** — weather + solar layers already exist; they gain a stated
  purpose and a fence.
- The only cross-lane schema item is unchanged from v1: adding `context_source` to TELEMETRY_SCHEMA v2 +
  `parse_v1` (through the ADR-0021 boundary) — the implementation slice that follows ratification.
- Firmware is unaffected: it keeps emitting raw per-sensor rows; contextualization is host-side.
- Unblocks the #418 fill (SHT45 as a `plant_local` instance) without wiring a model that breaks the moment a
  real user shows up with an Ecobee and no soldering iron.

## Open (routed)

- **Data:** confirm this v2 as author lane — especially the proximity-class tiers and the `room`-class source
  naming for the smart-home integrations.
- **Sage:** the placement question folds into the `plant_local` class definition — what physical placement
  qualifies a sensor as plant-local vs room (e.g. `breadboard_near_esp32` today).
- **Maintainer:** ratify; #418 closes on ratification and the `context_source` implementation slice gets cut.

— Workflow ⚙️ (v2 from maintainer design review; v1 by Data 🌱)
