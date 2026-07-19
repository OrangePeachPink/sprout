# Instrument exceptions — source-side spec (firmware)

**Status: SPEC (paper). No firmware behavior change is made by this document** — it specifies what a
later build should do. The build is a delivery-channel (V1) item, gated on Data's schema seam
(§3) and the #995-ratified anchors. Owner: Firmware 🔧.

Refs: #1152 · #1039 (band-model + exceptions rulings) · #898 (per-board envelope) · #952 (cal
chain) · seam → [`TELEMETRY_SCHEMA.md`](TELEMETRY_SCHEMA.md) (Data-owned — coordinate, don't edit).

## 0. Scope

The grill (#1039) locked the ladder as **7 in-soil mood bands (Soaked → Faint), all diagnostics
off-ladder**, and an exceptions table of **four families (open taxonomy):** placement · physics ·
kinematics · comms. This spec covers the **source-side half**: what the device can and should flag
at origin. The host-side half (windowed statistics, cross-reading context) is deliberately out of
scope — see §5 for the split and its rationale.

**Governing principle.** The device flags only **instantaneous implausibility** it can know from
(a) its own raw reading, (b) its own board envelope, and (c) its own immediately-prior sample.
Anything needing a time window, cross-channel context, or watering-event correlation is the host's
job. Raw is **always preserved** (ADR-0006); a flag downgrades *trust*, never the number. The
device never fabricates a value to fill an exception (ADR-0028 absence-first — omit/flag, never a
placeholder reading).

## 1. The existing surface (this spec extends it, does not replace it)

Verified in the current firmware — the seam is already partly built:

- **`quality_flag`** wire field: enum `{OK, SUSPECT, SATURATED, NO_SIGNAL, SENSOR_FAULT}`
  (TELEMETRY_SCHEMA S4; `telemetry_quality_flag()`). `SENSOR_FAULT` takes precedence.
- **`fault=<reason>`** payload companion (`telemetry_fault_reason()`): the coarse token stays in
  the small `quality_flag` enum; the *specific* reason rides the payload so the enum can't balloon
  (Trellis #739 binding). Reasons extend freely; the enum does not.
- **Below-water double-fault already ships:** a raw below `board_capability` `wet_rail_raw` →
  `SENSOR_FAULT` + `fault=dead_adc`.
- **Board envelope** (`board_capability.h`, #898/#899): per-board `air_dry_raw` / `wet_rail_raw`
  — the physical rails this spec keys its thresholds to.
- **Smoothing pipeline (there is NO EMA):** per-measurement **trimmed mean** (drop N high + N low
  of 64) → **dead-band hysteresis** (~60 raw) → **N-consecutive persistence** (~8 s soil) →
  committed level. `spread_warn_raw` already flags an intra-measurement fault when the trimmed-set
  range is too wide.

The exceptions work is therefore mostly **new reason tokens + one symmetric threshold**, not a new
subsystem.

## 2. Family by family (source-side)

### 2.1 Placement — probe-in-air / probe-in-water

- **Detectable at source?** Yes — instantaneous, against the board envelope.
- **Threshold basis:** the reading is *plausible but out of soil* — inside the physical rails yet
  outside the in-soil ladder. Above Faint's top (in-soil ceiling) but ≤ `air_dry_raw` → probe in
  air; below Soaked's floor but ≥ `wet_rail_raw` → probe in water.
- **Wire:** probe-in-water already maps to `SATURATED`; probe-in-air needs representation
  (recommend `SUSPECT` + `fault=probe_air` rather than a new enum value — see §3).
- **Host vs device:** device — its own envelope defines the zone; the host adds nothing here.

### 2.2 Physics — double-faults (below-water-in-water, above-air-in-air)

- **Detectable at source?** Yes — instantaneous.
- **Threshold basis:** *beyond* the physical rails. `raw < wet_rail_raw` (reads lower than the
  saturated-water anchor — impossible even in standing water) or `raw > air_dry_raw` (reads higher
  than the air anchor — impossible even in dry air). This is the maintainer's "can't even read
  this low **in water**" class.
- **Status:** the **below-water half already ships** (`wet_rail_raw` → `SENSOR_FAULT`). This spec
  **adds the symmetric above-air half** (`raw > air_dry_raw` → `SENSOR_FAULT` + `fault=open_adc`)
  using the same `board_capability` envelope. Symmetric and cheap.
- **Wire:** `SENSOR_FAULT` (precedence) + `fault=` ∈ {`dead_adc` (below-water/disconnect),
  `open_adc` (above-air)}. Raw preserved.
- **Host vs device:** device only — the physical rails are board-specific knowledge the host does
  not carry authoritatively.

### 2.3 Kinematics — too-fast spikes, wrong-direction reversals mid-watering

- **Detectable at source?** Partially — the device sees the raw series at the operating cadence,
  but the smoothing damps transients, so the gate must be placed with care.
- **Cadence reality:** the deployed cadence is ~30 s (`loop_period_ms`, runtime-tunable via
  `/cmd cad`, #826). Between committed rows `dt ≈ cadence`; within one measurement, 64 samples over
  a few ms.
- **Too-fast spike:** gate the **per-cadence delta of the trimmed-mean** (pre-persistence):
  `|raw_now − raw_prev|` beyond a physical maximum in one `dt`. Soil moisture cannot change faster
  than water physically moves; the ceiling is **empirical** — the fastest real Δ in the dry-down /
  dose-response corpus (this session's dose-response is a seed). A jump past that in one 30 s step
  is electrical, not soil. The device holds `raw_prev`, so it flags this at zero latency. The gate
  sits **above** the dead-band + persistence (which suppress sub-threshold chatter) — it catches
  what the smoothing lets through, not what it already absorbs.
- **Wrong-direction mid-watering:** raw rising (drying) *during a watering event* is implausible —
  **but the device does not know a watering event is active** (that's pump/host context, and pumps
  aren't wired yet). At source the device can only flag a bare single-step reversal beyond
  dead-band; the **"mid-watering" qualifier is host-side** (needs the event correlation). So:
  device flags the reversal spike, host qualifies it as mid-watering.
- **Wire:** `SUSPECT` + `fault=rate_spike` (device). The mid-watering refinement is host-added.
- **Host vs device:** device = single-step instantaneous rate vs a physical ceiling; host =
  windowed rate/trend + watering-event correlation.

### 2.4 Comms — no-signal, stale

- **Detectable at source?** Mostly no. A device that isn't transmitting cannot announce its own
  silence, and staleness is measured against a wall-clock the device does not hold (no NTP until
  #21).
- **What the device *can* flag:** a dead sensor link — a floating / railed ADC — which is already
  `dead_adc` / `SENSOR_FAULT`. That is the sensor-comms half.
- **What is host-side:** `NO_SIGNAL` (row absence) and staleness (last-seen age vs cadence) — the
  host owns the clock and the row-arrival record.
- **Host vs device:** host for link-level/staleness; device for sensor-disconnect.

## 3. `quality_flag` extension — the schema seam (Data owns TELEMETRY_SCHEMA)

**Proposed, for Data's review — this spec does NOT edit `TELEMETRY_SCHEMA.md`:**

- **Keep the enum small** (Trellis #739). Prefer extending the **payload `fault=<reason>`
  vocabulary** over adding enum values. Recommended reason additions (all additive, opaque tokens):
  `open_adc` (above-air physics), `probe_air` (placement air), `probe_water` (placement water, if
  distinct from `SATURATED`), `rate_spike` (kinematics). `dead_adc` stays (below-water/disconnect).
- **schema_version disposition:** payload-reason additions are **additive** — reasons already ride
  the payload as opaque tokens (#739), so **no schema bump** is implied. A *new `quality_flag`
  enum value* would be a vocabulary change and is Data's call on versioning; this spec recommends
  the payload-only path precisely to avoid that.
- **Ask to Data** (posted on #1152, `for:data`): confirm the reason-vocabulary additions; confirm
  whether any new enum value is wanted vs payload-only; confirm the `schema_version` disposition.

## 4. Detectable-at-source summary

| Family | Sub-type | At source? | Threshold basis | Wire (proposed) |
| --- | --- | --- | --- | --- |
| placement | probe-in-air | yes | `air_dry_raw` ≥ raw > Faint-top | `SUSPECT` + `fault=probe_air` |
| placement | probe-in-water | yes | Soaked-floor > raw ≥ `wet_rail_raw` | `SATURATED` (exists) |
| physics | above-air-in-air | yes (add) | raw > `air_dry_raw` | `SENSOR_FAULT` + `fault=open_adc` |
| physics | below-water-in-water | **ships** | raw < `wet_rail_raw` | `SENSOR_FAULT` + `fault=dead_adc` |
| kinematics | too-fast spike | partial | Δraw > physical max per `dt` | `SUSPECT` + `fault=rate_spike` |
| kinematics | wrong-dir mid-watering | host | needs watering-event ctx | host-qualified |
| comms | no-signal / stale | host | row absence / last-seen age | host-derived `NO_SIGNAL` |
| comms | sensor-disconnect | yes | floating / railed ADC | `SENSOR_FAULT` + `fault=dead_adc` |

## 5. The split argument (why source-vs-host lands where it does)

- **Device owns instantaneous implausibility** from data it alone holds authoritatively: its board
  envelope (#898 rails), its current raw + immediate predecessor, its ADC health. These need no
  window and no cross-context, and the device is the only place they are known at zero latency —
  *before* the smoothing hides them.
- **Host owns windowed + contextual judgments:** multi-row rate/trend, cross-channel correlation,
  watering-event alignment, and staleness/row-absence (which need the wall-clock and the
  arrival record). The host has the history, the clock, and the pump state; the device has none of
  these yet (no NTP #21, no pump wiring).
- **Conservatism corollary:** the device flags conservatively and never destroys the number — raw
  is preserved so the host can always re-derive, and absence is flagged, never filled (ADR-0028).

## 6. Non-goals / next

- **No firmware behavior change in this issue.** The build — adding the above-air check, the
  rate-spike gate, and the reason tokens — is a later delivery-channel (V1) item.
- The kinematics ceiling is **empirical**: it calibrates against the fresh current-fleet dry-down
  and the dose-response corpus, alongside the #995 anchor ratification.
- Taxonomy is **open** (#1039): more families may land; the payload-reason vocabulary is the
  low-friction place to grow.

— Firmware 🔧
