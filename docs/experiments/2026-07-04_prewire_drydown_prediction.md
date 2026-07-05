# Pre-wire drydown prediction — hypothesis scored against install-night actuals

**Date:** 2026-07-04 local CDT · **Lane:** Data 🌱
**Authority:** BENCH EVIDENCE — a data-driven prediction scored against the operator's
live install-verification readings. Not A2/C1 calibration-ratified.
**Sources:** the 06-29 Sage survey
([`…_p01_p07_rescue_survey_recovery.md`](20260629_sage_p01_p07_rescue_survey_recovery.md),
[`…_p08_p11_continuation.md`](20260629_sage_p08_p11_continuation.md)) + the 07-01 48h checks
(`experiments/20260701_*`) → prediction → the 2026-07-04 19:38 CDT install readings (all 8
in-soil channels, read by the operator during install verification).

## Hypothesis

From each plant's last-known settle (07-01) plus ~3.2–3.3 days of drydown to the 7–8 pm
go-live, predict a **bracketed** raw range (not a spot value) and a **water / hold** verdict
for tonight. Drydown model: **~200–450 raw/day** in the dry regime (faster the first day from
a very-wet start), asymptoting to the air-dry ceiling (~3100–3400 classic), with **plant-type
care rules overriding a dry sensor** (cactus/succulent/marginata/cachepot ≠ water-me).

## Critical caveat, applied at scoring time (Firmware)

The four **C5 plants (p01/p03/p07/p10)** read on the **official C5's uncalibrated ADC
(#443)** — a compressed, lower scale (air-dry ~2775, not ~3100). A C5 raw reads **~300 counts
lower / "wetter-looking"** than the same wetness on the classic. My brackets were authored on
the **classic** scale (bounds 3050…1050), so for the C5 plants the *band verdict* is the
trustworthy signal, and the *absolute* raw is expected to undershoot the classic-scale bracket
by ~300. Scored accordingly.

## Predicted vs actual

| # | Plant | Board | Predicted (call) | **Actual** (07-04 19:38) | Score |
|---|---|---|---|---|---|
| **p02** | Pothos (XXL) | classic | dry · **water** | **2,847 · DRY** | ✅ hit |
| **p03** | Pothos (XL) | C5* | dry · **water** | **2,229 · DRY** (~2,530 classic-eq) | ✅ hit |
| **p10** | Pothos (office) | C5* | dry · **water** | **2,289 · DRY** (~2,590 classic-eq) | ✅ hit |
| **p04** | Dracaena? (cane) | classic | light-if-dry | **2,441 · DRY** | ✅ light |
| **p01** | Pothos (small) | C5* | check → hold if <2100 | **1,584 · OK** (~1,880 classic-eq) | ✅ hold |
| **p07** | Bromeliad? | C5* | hold (drainage first) | **2,179 · DRY** | ✅ hold |
| **p11** | Corn-plant? (mini) | classic | needs-water · light *(corrected)* | **1,905 · needs water** | ✅ hit |
| **p06** | Anthurium "Lovable Hearts" | classic | needs-water · **water** | **1,443 · well-watered** | ❌ **miss** |

`*` C5 provisional scale (reads ~300 compressed). Sensorless **p05 / p08 / p09** = no probe;
care rules hold (marginata / cactus / succulent — normally dry, do not water on a sensor read).

**Score: 7 of 8.**

## The one real miss — p06 Anthurium

Predicted needs-water and flagged it to water; **actual is 1,443 · well-watered ("Moist ·
thriving")** — a clean, tight, stable read (spread 24, quality OK), not a sensor glitch.

**Why the model missed:** the linear ~200–450 raw/day drydown assumed p06 kept drying from its
06-29 soak. But p06 took a **1⅔-cup rehab pour** after being parched, and a drought-recovery
Anthurium in fresh-wetted mix *holds* — retention is non-linear right after a heavy soak,
especially for a plant that wants consistent moisture. The model over-dried the one plant that
was actively re-establishing its water-holding. **Correct action: HOLD p06** — it is retaining,
which is the recovery outcome we wanted. **Lesson:** a recently heavily-rehydrated recovery
plant needs a slower drydown assumption (or a wider wet-side bracket) than a steady-state pot.

## The p11 sub-story — a faulty sensor, caught and vindicated

The first-pass prediction read p11 as *"submerged — hold, has reserves,"* a verdict carried
**entirely by a faulty channel**: the 07-01 P11 `s3` fell to a **median ~420 (min 180)** — below
the physical wet rail (~900 = "wetter than a cup of water") and it kept reading low in open air
afterward (a shorted/water-contaminated probe). Excluding it, p11's reliable 07-01 channels
(s1=1574 OK, s4=1466 well-watered) were only *normally* watered → should be drying by tonight.

**The correction was independently confirmed by the live probe:** if p11 were genuinely
drowning, tonight's read would be ~1,000. It reads **1,905 · needs water** — dry-side, on the
classic's scale, no caveat — landing at the low edge of the corrected bracket (~1,900–2,900).
The fix moved the prediction to match reality, and the measurement proved the fix right.

**Honesty note:** the impossible s3 reading was ingested in the *first* pass without being
flagged (the sub-rail `min=180` was sitting in the extract). It was caught by hand, not by the
pipeline. That gap is the subject of the fault-flag enhancement (below).

## What held, and what it teaches

- **The water-tonight anchors held:** p02, p03, p10 all measured dry, as predicted.
- **The holds held:** p01 (OK, under the 2100 threshold), p07 (dry, but drainage-first).
- **C5-scale lesson:** the four C5 plants' *band verdicts* all landed, but their *absolute* raws
  undershot the classic-scale brackets by ~200–500 — explained by the #443 compression. **Next
  time: author per-board brackets** (classic vs C5 cal scale), don't share one scale across boards.
- **Recovery-plant lesson:** p06 — slow the drydown assumption for a just-rehabbed plant.

## Reconciled water decision (measurement-final)

| Do | Plants |
|---|---|
| ✅ Water | **p02, p03, p10** (all dry) |
| 💧 Light | **p04, p11** (dry-side) |
| ⛔ Hold | **p06** (moist — the flip), **p01** (OK, under threshold), **p07** (drainage first), **p05 / p08 / p09** (sensorless — care rules) |

## Action taken tonight (operator)

**Hold all watering to 2026-07-05; log overnight first.** Nothing is parched-critical over the
next ~12 h (p02/p03/p10 are dry, not desiccated; the rest have margin), and more logged data
sharpens tomorrow's call. The prediction + these actuals are the baseline for the closed loop.

## Follow-ups

- **Sensor-fault flag (filed #670):** the p11 s3 impossibility should have been auto-flagged at
  ingest, not caught by hand. Parse-boundary `implausible_wet` gate (raw preserved) + a Firmware
  self-declare companion.
- **Per-board brackets** for the next prediction (classic vs C5 cal scale, #443).
- **Re-score after tomorrow's data** once drydown continues and any watering lands — extend this
  table with the 07-05 actuals.

— Data 🌱
