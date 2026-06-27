# Sensor calibration & reference readings

**What this is:** the bench + real-soil characterization readings captured for the 4 capacitive soil
sensors **before** the current long-running dry-down log began. These were taken by hand (probe moved
between conditions, readings read off the serial monitor) during the Rung 3 calibration session on
**2026-06-21**, and are reconstructed here from that session so they're referenceable from disk.

**Boundary marker:** the *current* continuous log (`firmware/logs/device-monitor-260621-224356.log`,
started **2026-06-21 22:43:56**, sensor **#3**, fw `0.3.2`, 30 s cadence) begins right after these
samples. Everything below predates it.

---

## Setup (read this before trusting cross-sensor comparisons)

- **Sensors:** 4x UMLIFE capacitive soil-moisture, **V2.0.0 / TLC555**, QA-passed (see `../SENSOR_QA.md`).
- **One channel only:** every reading below was taken on **GPIO36 (ADC1_CH0)**, one sensor at a time.
  **Pin-to-pin ADC variation is therefore UNMEASURED** — any cross-sensor spread here is *probe + placement*,
  not pin. (This is exactly why the final system calibrates each probe in place; see backlog C1.)
- **Signal chain:** trimmed mean of 100 raw samples (drop 15 high/low, avg middle 70), ESP32 ADC1, 12-bit
  (0–4095), default attenuation, eFuse cal **off**. **Raw is inverted: HIGH = dry, LOW = wet.**
- **Calibration in effect during capture** (fw `0.3.1`/`0.3.2`), boundaries dry→wet:
  `3300  3050  2200  1750  1450  1080  900  800`
  → air-dry(≥3050) · **dry**(2200–3050) · needs water(1750–2200) · OK(1450–1750) ·
  **well watered**(1080–1450) · **overwatered**(900–1080) · water-contact/submerged(<900).
- **Stress history:** **#1** got water on its upper board (contamination, recovered); **#2** had power/ground
  reversed in a hot-swap (recovered). **#3, #4 clean.** **#3** is the probe in the current long-run.

---

## Reference readings by condition (raw ADC; `~` = approx settled value)

### All four sensors (where each was measured)

| Condition | #1 | #2 | #3 | #4 | Level it maps to |
| --- | --- | --- | --- | --- | --- |
| **Air** (open, indoor June) | ~3175 | ~3185 | ~3190 | ~3195 | air-dry (summer), diag |
| **Just-watered soil, in-plant** (full-cycle sweep) | ~1300 | ~1205 | ~1245 | ~1130 | well watered, disp |
| **Field capacity** (drained ~30 min, still moist) | ~1340 | ~1140 | ~1435 | ~1165 | well watered, disp |
| **Saturated soil** (wet pot, undrained) | —‡ | ~970 | ~1045 | ~1065 | overwatered, disp |
| **Pure water** (probe dunked) | ~1010 | ~975 | ~1015 | ~1020 | overwatered, disp |

‡ #1 wasn't cleanly read saturated-in-pot — it was the probe that got **water on its board** during that
watering (readings climbed erratically toward ~2900–3100 = contamination artifact, not moisture). Its
~1010 "pure water" value above is from its later clean full-cycle, after it dried out and recovered.

### Single-sensor reference points (#1 only — the plant was dry/being tested with #1 at the time)

| Condition | Reading | Notes |
| --- | --- | --- |
| **Dry dirt** (bone-dry, distressed plant, >1 week unwatered) | **~2440 (floor) … ~2920** | 4 spots: ~2470, ~2475, ~2635, ~2920. Air gaps push *higher* (drier), so the firmly-bedded **~2440** is the trustworthy "bone-dry soil" value; ~2920 was a loose/re-probed hole. |
| **Damp, out of water (unwiped)** | ~2700 | surface film on the probe; transient |
| **Bench: held in hand** | ~1300–1750 | variable (grip/skin moisture); not a calibration point |
| **Bench: submerged in water** | ~947–1040 (min ~947) | the wet rail |

---

## The waterlogged → drained sequence (what you asked about)

Chronology after the dry plant was watered thoroughly:

1. **First watering** soaked the probe (#1) board → contamination, erratic high readings (~2900–3100). Pulled, dried, recovered.
2. **Saturated / waterlogged pot (undrained):** swapped probes through the soaked pot —
   **#2 ~970**, **#3 ~1045**, **#4 ~1065** — all reading "overwatered/submerged." Key finding: **saturated soil
   reads the same as standing water (~970–1065)** to a capacitive probe (no air gap left around the plates).
3. **Drained ~30 min** (sink) → **field capacity**: **#4 ~1165**, **#2 ~1140**, **#1 ~1340**, **#3 ~1435**
   — all "well watered." The **~270–300-count spread at the *same* drained state is placement/contact
   variance**, not soil.
4. **Full-cycle characterization** of each probe (in-plant → air → water → dry-down) — all four validated
   every band consistently.
5. **#3 installed** in the recovering plant; **current long-running log started** (the boundary above).

---

## Derived calibration anchors (this sensor family)

| Anchor | Raw | Used for |
| --- | --- | --- |
| Air (probe out of soil) | ~3175 | air-dry diagnostic |
| **Dry dirt (bone-dry)** | **~2440** (floor) … ~2920 (air-gap) | "dry" band; the watering target |
| Damp, out of water | ~2700 | (transient; not a band anchor) |
| **Field capacity (drained)** | **~1140–1435** across probes | "well watered" band (1080–1450) |
| **Saturated soil / water** | **~970–1065** | "overwatered" band |
| Wet rail (pure water floor) | ~947 | below this the diagnostics sit (intentionally unreachable in soil) |

These anchored the `0.3.1` boundaries. **Mid bands ("needs water" 1750–2200, "OK" 1450–1750) are
interpolated** — no measured soil point yet; the current dry-down is capturing them.

> **A2 endpoint update (#248).** A later **common-cup** characterization measured all four probes
> *simultaneously* — **air-dry center 3,170** (per-probe 3,151–3,191), **saturated center 978**
> (per-probe 926–1,020; **s2** the wet-biased min). These **ratify the firmware classifier's two
> endpoints** (the A2 Data→Firmware handshake, ADR-0006 §6) — the boundaries are *unchanged*; #248
> confirms they bracket reality. The **interior ladder stays proposed** pending a controlled dry-down.
> Per-pin offset proved **state-dependent** (~94 counts in water vs ~40 in air, ordering flips) — a
> single constant won't correct it, so per-channel work is **C1 / #170**, not A2. Full findings +
> machine sidecar live under `docs/experiments/` (#248).

---

## Caveats (don't over-trust these numbers)

- **Cross-sensor + single-pin:** all on GPIO36, one probe at a time → spread is probe/placement, not pin.
- **Placement variance is large:** ~270 counts at field capacity, up to ~450 counts in dry soil across spots.
  Absolute readings are **not** comparable probe-to-probe; a *single fixed probe's* dry→wet trajectory is.
- **Provisional & cross-sensor calibration:** dry anchor from #1, wet anchors from #2/#3/#4. The deployed
  system calibrates **each probe in place** (backlog C1).
- **Soil/plant-specific:** one plant, one soil type, indoor June, south Chicago window.

---

## Pointers

- Firmware: `firmware/src/main.cpp` (classifier cfg), `firmware/include/config.h`; module `firmware/lib/moisture_classifier/`.
- Calibration commits: `1b4b60e` (`0.3.1` real-soil cal), `0620f30` (`0.3.2` long-run prep).
- Current dry-down log: `firmware/logs/device-monitor-260621-224356.log` (git-ignored; sensor #3).
- Roadmap/decisions: `../BACKLOG.md`. Board/sensor evidence photos: `evidence/`.
