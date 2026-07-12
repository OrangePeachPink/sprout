# Environmental-data value verdict (#922)

_Data lane · feeds the v0.8.0 data-contract review · 2026-07-11_

The maintainer's own doubt is the brief: _"we're doing the collection already, just show
it somewhere... I can't even tell if there is a good reason I wanted it added."_ So this is
two questions, not one: (1) show the env we capture, and (2) decide **which env columns earn
their space** vs bloat the contract and the files.

The overlay (the opt-in, faint, time-aligned layer on a plant's trajectory) is the first
deliverable. This doc is the second — the ruthless column verdict, biased toward TRIM.

## The lens (Design-QA's, applied per column)

> **Does surfacing this column ever change how a user reads a moisture value, or explains a
> surprise?**

- **KEEP** — it has changed / would change a read, or explains an anomaly.
- **DEMOTE** — mildly useful, not glance-worthy: keep logging, drop from the overlay.
- **TRIM** — write-only: logged, never consulted, never changes a read → flag for the
  v0.8.0 contract trim.

The deployment reality anchors every call: **all 11 plants live on a kitchen windowsill**
(indoors, south-facing). Several env columns were specified against an outdoor/greenhouse mental
model that this deployment simply isn't. Indoors is where most of the TRIMs come from.

## The verdict

| Column | Source | Verdict | Why |
|---|---|---|---|
| `temp_context_c` (interior air temp) | ADR-0023 fill, a board's own SHT45 | **KEEP** | Heat drives evaporation. A warm afternoon explaining a faster midday dip is the one correlation a maker would actually consult. **In the overlay.** |
| `rh_context_pct` (interior air RH) | ADR-0023 fill | **KEEP (secondary)** | Humidity modulates the same evaporation. Time-aligned, it explains a _slow_-dry surprise. In the overlay, visually subordinate to temp. |
| solar `night_bands` / `sun_events` | derived (`env_solar`, computed) | **KEEP** | Already rendered as day/night shading — the cheapest, most-read context (a nighttime plateau vs a daytime draw). Derived, zero storage cost. |
| `weather_source` / `solar_source` | provenance tags | **KEEP** | Not data — the honesty label ("derived/model, never authoritative"). Keep for the value+tag-together rule. |
| `pressure_context_hpa` (exterior barometric) | ADR-0023 §3 exterior exception, live weather | **DEMOTE** | Barometric pressure has ~no effect on soil-moisture drying at a windowsill. Genuinely interesting telemetry, but it has never changed a read and wouldn't. Keep logging (cheap, already wired via #567); **off the overlay**. |
| `cloud_cover` (Open-Meteo hourly) | exterior weather | **DEMOTE** | Correlates with evaporation, but redundant with `radiation` + the solar night bands the chart already shows. Keep logging; not overlay-worthy. |
| `radiation` (shortwave, Open-Meteo) | exterior weather | **TRIM-candidate** | For an **indoor** plant this is a weak proxy — the plant sees window light filtered by orientation and glass, not open-sky shortwave. Rarely, maybe never, changes a read indoors. Flag for the v0.8.0 contract trim unless an outdoor deployment materializes. |

## Recommendation for the v0.8.0 data-contract review

1. **Keep** the interior ambient (`temp_context_c`, `rh_context_pct`) and the derived solar
   context. These are the columns that earn a glance; the overlay surfaces them.
2. **Demote** `pressure_context_hpa` and `cloud_cover` to logged-but-not-surfaced — no
   contract change, just not on the chart.
3. **Trim candidate:** `radiation`. It's the clearest write-only column for an indoor
   deployment. Before cutting it, confirm it's never been consulted (it hasn't, to date);
   if an outdoor/greenhouse deployment is ever on the roadmap, it flips back to DEMOTE.

The through-line matches the maintainer's instinct: a column no one has ever consulted is
bloat in the contract and the files, not insurance. The overlay ships the KEEPs; the v0.8.0
review acts on the DEMOTE/TRIM list.

## Honesty guardrail (built into the overlay)

The overlay shows env **beside** moisture, time-aligned, and labels itself _"context, not
cause"_ — it never says (or implies via colour/verdict styling) "dry because hot." The eye
finds the correlation; the chart asserts nothing the data can't back. Same honesty law the
bands hold, and the inverse of #977: you don't wear a claim you haven't earned.
