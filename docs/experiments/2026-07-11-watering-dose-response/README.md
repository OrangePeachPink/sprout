# Watering dose-response — 2026-07-11 (v0.7.2 fleet, first per-pot-cal run)

**Session:** v0.7.2 bench + fleet bring-up. First dose-response measured with the **v0.7.2
per-channel / board cal live on the whole fleet** (#4 `cal_tier` + #952 resolution chain,
OTA'd to the fleet tonight) and the **HTTP `/cmd` control surface** (#826) driving cadence
changes over WiFi. Continues the [Jul 7](../2026-07-07-watering-dose-response/) and
[Jul 10](../2026-07-10-bench-watering-and-sensor-cal/) series.

## Method

- **Cal:** classic = per-channel (`cal_tier=channel-cal`, `wipe_airdry_bench_20260628`);
  C5 (c5off1) = board envelope (`cal_tier=board-cal`, `board_envelope_20260710`). Both live
  on the wire — verified from `/telemetry` this session.
- **Cadence:** dropped to 1 s then 5 s via `GET /cmd?c=cad,<ms>` for measurement, restored to
  30 s after. (Doubled as the #826/A4 `/cmd` runtime verification.)
- **Readings:** board-served `/telemetry` (the emitted wire rows), raw ADC (higher = drier).
  Two reads per pot — **immediate** (~seconds after the pour) and **settled** (~10–15 min).
- **Scope:** the 3 driest probed pots, chosen by the maintainer's field rule
  **"raw > 2000 → water"** — the candidate pump-ON trigger.

## Doses + response

| plant | pot | dose | baseline | immediate | **settled** | Δ (settled) | raw/mL | read |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Corn-plant (mini)** (p11, classic s1) | 6″ | ~1 cup | 2225 | 1784 | **1672** (OK) | **−553** | ~2.3 | landed cleanly in the OK band; predictable |
| **Anthurium (Hearts)** (p06, classic s3) | 5″ | ~½ cup | 2221 | 1405 | **1485** (well watered) | **−736** | ~6.1 | **OVERSHOT** — ½ cup too much for the 5″ pot; drained *up* a touch on settle |
| **Pothos (small)** (p01, c5off1 s3) | 6″ | ~¾ cup (½ + slow ¼) | 2097 | ~1957 | **1827** (needs water) | **−270** | ~1.5 | **HUGE reaction lag** — kept wicking 10+ min; see below |

**Pothos trajectory** (the reaction lag, in one line):

`2097 (dry) → 2019 → 1984 (post-½c) → 1957 (post-¼c, +3 min) → 1827 (settled, ~15 min)`

See `data/pothos-small-settle.csv` for the 3-min @5 s window.

## Findings (the model seeds)

1. **~4× per-pot variance in water-efficiency** (settled: 1.5–6.1 raw/mL). The Anthurium is ~4×
   more efficient per mL than the Pothos small. A fixed pump dose is a non-starter — it would
   overshoot the Anthurium and under-serve the Pothos. **Dose-response must be per-pot** — the
   exact reason the v0.7.2 per-channel / board cal matters as the model's substrate.
2. **Reaction lag is the headline finding.** The Pothos small's **immediate** reading (−78)
   under-reported its **settled** effect (−270) by **~3.5×** — it kept wicking for 10+ minutes.
   A naïve "pump until target" loop reading the *instant* response would conclude the water did
   almost nothing and **dose again → soak the pot**. The dosing model must **dose → wait
   (10+ min for slow pots) → re-measure**, and must **never** trust the immediate reading as the
   dose outcome.
3. **Overshoot on small pots.** Anthurium ½ cup → well-watered even after settling back up. Small
   pots want small doses (~¼ cup next time).
4. **Hydrophobic-dry channeling + slow wick.** A bone-dry pot (Pothos small) both channels a fast
   pour and then absorbs slowly. A **slow soak or repeat dose** delivers more to the root zone
   than one fast dump — and the effect arrives late.
5. **`raw > 2000` is a sound pump-ON trigger.** It sits in the Drying band (~1830–2140) — "top up
   as it starts drying, before parched." All three settled below 2000. The **pump-OFF /
   dose-amount** side is what must be per-pot and lag-aware.

## For the dosing model (0.8.0 / 0.9.0)

- **Sense** (done, v0.7.2): per-pot cal live fleet-wide; `/cmd` control; watering
  auto-detection working on the dashboard.
- **Decide** (seeded here): per-pot dose → Δraw + **reaction-lag** characterization. Needs more
  points across dryness levels, and the model must key off **settled**, not immediate, readings.
- **Act** (future): pumps + closed loop — pump-ON at `raw > ~2000` → per-pot dose → **wait** →
  re-measure → pump-OFF at a target band. The wait interval is itself per-pot (slow pots lag).

## Data

- `data/doses.csv` — the three pours (dose → immediate → settled → Δraw).
- `data/pothos-small-settle.csv` — the 3-minute Pothos-small settle curve (@5 s).
