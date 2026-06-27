# Common-cup air-dry + saturated anchors — findings

**Date:** 2026-06-26 → 2026-06-27 · **Lane:** Data · **Authority:** PROPOSED calibration evidence
(not authoritative; Firmware ratifies at A2 — [ADR-0006](../adr/0006-data-architecture.md) §5–6).
Machine sidecar: [`2026-06-26_common-cup-air-water-anchors.json`](2026-06-26_common-cup-air-water-anchors.json).

The first real run of the [common-cup characterization procedure](common-cup-characterization.md): four
co-located probes taken to two known physical states — **open air** and **fully submerged** — to fix the
two endpoints of the moisture ladder and quantify probe/pin variance.

## Hypothesis

With all four probes in one medium at one moisture, the only variable is **probe + ADC pin** (not plant,
not microsite). Open air and a shared cup of water bracket the sensor's full raw-ADC range and fix the
**Saturated floor** and the **air-dry / Parched ceiling** the placeholder ladder is currently guessing.

## Method

One device (`plants_esp32_f4e9d4`, fw 0.7.0), four `UMLIFE_v2_TLC555` capacitive probes on GPIO 34/35/36/39.

- **Air-dry:** all four on a paper towel on the bench, open air. Two chunks (a 5.0 h downtime between) —
  *one state, logged as two sets per the procedure*.
- **Saturated:** all four submerged in **one shared cup of water**, ~23:21 local through the next afternoon.

Source = the always-on **monitor logs** at 30 s cadence (no plant, no soil present). Segmented by raw value
and time-gap state detection; 90 s of handling transient trimmed at each state boundary. Re-homed as labeled
captures under `experiments/` (gitignored) for the DuckDB store and the
[calibration workbench](../../tools/analytics/calibration.py).

## Findings

Raw ADC, higher = drier. Per-probe medians at each state:

| probe | GPIO | air-dry median | saturated median |
| --- | --- | --- | --- |
| s1 | 34 | 3,191 | 977 |
| s2 | 35 | 3,151 | 926 |
| s3 | 36 | 3,166 | 1,020 |
| s4 | 39 | 3,174 | 988 |
| **center** | — | **3,170** | **978** |

- **Dynamic range ≈ 2,192 counts** (978 → 3,170). Both air chunks agreed within ~5 counts — so "really one
  set" is statistically true; the split is only the downtime.
- **Pin offset is real and state-dependent.** Cross-probe spread was **~94 counts in water** but only **~40
  in air**, and the *ordering flips* (s3 reads highest in water, s1 highest in air). So a single constant
  per-pin offset will **not** correct it — the offset depends on the medium.
- **The afternoon skylight bump is ESP32 self-heating, not moisture.** There is no soil or plant in this
  run, so the small co-incident rise across all probes when the device left shade is an electrical/thermal
  artifact, not a drying signal. Good to know the bands must tolerate it.
- Probes were near-flat within each state (|slope| < 0.8 counts/h) — clean, trustworthy anchors.

## Conclusion

- The **placeholder Saturated (900–1050)** and **Parched (3050–3400)** bands **correctly bracket reality** —
  observed submerged 915–1052 and air-dry 3135–3203 both fall inside. The placeholders are well-placed at
  the extremes.
- This fixes the **two endpoints**: saturated center **~978**, air-dry center **~3,170**, and one robust
  **wet ↔ dry divide at ~2,096** (the midpoint the workbench proposes between the two observed bands).
- **It does not calibrate the interior ladder** (Moist / Ideal / Drying / Dry). That needs a controlled
  **dry-down** through the middle — the next characterization run.
- **For Firmware (A2):** treat ~978 and ~3,170 as the anchored endpoints; carry the placeholder interior
  boundaries until a dry-down dataset exists. Per-pin correction should be modeled per-medium, not as a
  constant.

## Provenance

Extracted by the Data lane from monitor `logs/` (device `plants_esp32_f4e9d4`, the original-plant four-probe
co-located run).
Raw captures live local-only under `experiments/2026-06-26_common-cup-airdry-{1,2}` and
`experiments/2026-06-26_common-cup-saturated` (gitignored per [ADR-0012](../adr/0012-experiment-data-architecture.md));
this report + its JSON sidecar are the durable, tracked evidence.

— Data 🌱
