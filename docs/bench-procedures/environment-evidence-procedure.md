# Environment evidence procedure

Use this when investigating sunlight, heat, water temperature, wet-reference
(a water reading used as a reference), or ambient sidecar-sensor artifacts. The
goal is not to prove everything in one run; it is to isolate one factor at a
time and preserve enough evidence for Data to correlate raw ADC and environment
rows with local-time interventions.

Refs #331

## What to record every time

| Field | Examples |
| --- | --- |
| Local time | `2026-06-28 13:00 CDT`, intervention at `13:08 CDT`. |
| Firmware/app | ESP32 `fw`, `git`, build time; app/server restart status. |
| Capture | capture ID, source, cadence, duration, COM port. |
| Board exposure | ESP32 in direct sun, shaded by box, room light only. |
| Sensor/cup exposure | probes in direct sun, water cup in sun, wires in sun, all shaded. |
| Sidecar sensors | SHT45/AS7263 in sun, partial shade, full shade, or covered. |
| Ambient temperature | room thermometer, nearby desk thermometer, or "not measured." |
| Water/soil temperature | kitchen thermometer if available, or "not measured." |
| Light state | skylight beam on board, beam on cup only, cloudy, room light. |
| Photos | overview plus close view of board/probes/cup/pot. |

Use common home-lab tools first: cardboard shade, notebook, phone camera, kitchen
thermometer, tape labels, timer, and a stable cup or plant position.

## Evidence photo guidance

Take photos when the physical setup matters:

1. Overview: whole bench showing skylight/light relationship.
2. Board: ESP32/breadboard exposure and any shade.
3. Probes: insertion depth, cup level, or pot positions.
4. Intervention: what changed at the exact local time.

If committing photos, use a small curated set and place them under:

```text
docs/experiments/evidence/YYYY-MM-DD/<capture-id>_<view>.jpg
```

Keep large bursts or personal/background-sensitive photos out of the repo.

## Control patterns

| Control | Change | Hold constant | Can support | Cannot prove alone |
| --- | --- | --- | --- | --- |
| Board shade | Shade ESP32/breadboard only. | Same cup, probes, wires, water. | Board-light or board-temperature artifact. | Whether photons or temperature caused it. |
| Cup/probe shade | Shade cup/probes only. | Same board exposure. | Sensor/water-light artifact. | Board temperature contribution. |
| Full shade | Shade board, cup, probes, and wires. | Same water/soil state. | Recovery from light/heat exposure. | Which shaded part mattered. |
| Water temperature | Cold, room, warm water cups. | Same probes and board exposure. | Temperature sensitivity in wet reference. | Soil behavior. |
| Probe depth | Marked-line depth versus shallow. | Same water/cup/board. | Insertion-depth sensitivity. | Plant microsite behavior. |
| Plant placement | Same plant, same probes, rotated/relocated. | Watering history as much as possible. | Microsite and placement variance. | Sensor-only calibration. |
| Sidecar exposure | Shade SHT45 or AS7263 while soil probes hold position. | Same board/logging/cadence. | Whether ambient temp/RH or NIR rows respond to sun/shade. | Plant truth or soil moisture. |

## Intervention notes

Use local time first because the bench human works in Chicago time.

```text
13:00 CDT - ESP32/breadboard shaded with cardboard. Cup and probes unchanged.
13:08 CDT - Sunlight moved off board; still on cup/wires.
13:14 CDT - Full shade. No physical probe movement.
```

Then record machine time or UTC if the UI provides it.

For moving skylight-beam runs, record each object crossing separately. The
sensor may respond in a different window than the soil probes:

```text
13:25 CDT - Cardboard box lifted; all sensors exposed.
13:48 CDT - ESP32 fully shaded; SHT45/AS7263 still in sun.
13:55 CDT - SHT45 full shade; AS7263 still in sun.
14:03 CDT - AS7263 entered shade; all soil probes shaded.
```

## Finding discipline

Separate these in every write-up:

| Section | Meaning |
| --- | --- |
| Fact | Directly observed or measured. |
| Inference | Best explanation supported by the facts. |
| Speculation | Plausible idea not yet tested. |
| Does not prove | Important limits of the run. |
| Next test | The smallest follow-up that would remove one uncertainty. |

Example:

```text
Fact: Shading the board produced no immediate large step over 60 s.
Inference: A fast photon-only board artifact is not strongly supported by this run.
Speculation: A slower thermal effect may still be present.
Does not prove: It does not separate board temperature from water temperature.
Next test: Add water temperature notes and repeat board-shade versus cup-shade.
```

## Data handoff

For Data, attach or comment with:

- capture IDs
- local intervention times
- raw channel medians/ranges if available
- exposure state tags: `board_sun`, `board_shade`, `cup_sun`, `cup_shade`,
  `full_shade`, `sht45_sun`, `sht45_shade`, `as7263_sun`, `as7263_shade`,
  `water_temp_cold`, `water_temp_room`, `water_temp_warm`
- anomaly tags: `probe_moved`, `water_refilled`, `splash_risk`,
  `temperature_unmeasured`, `logger_restarted`, `photo_available`

If the run should be durable, land the raw slices, an event table, and a manifest
under `docs/experiments/data/<session-id>/`. Keep `logs/` and `_scratch/` as
temporary source material only; Data should not have to mine gitignored files or
prose to rebuild a result.

— Sage
