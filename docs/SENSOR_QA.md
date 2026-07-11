# Sensor QA - Capacitive Soil Moisture Sensors

**Date:** 2026-06-20
**Project:** plants (capacitive soil-moisture + pump auto-watering)
**Scope:** Verify 4x capacitive soil moisture sensors against the three well-known board defects
before committing them to the build.
**Result:** All four sensors pass all three checks. Cleared for use **as-is** - no rework, no reorder.

---

## Units under test

- **Quantity:** 4 (labeled S1-S4 below)
- **Silkscreen:** "Capacitive Soil Moisture Sensor V2.0.0"
- **Board ID:** `HW-390`
- **Date code:** `20240201` (2024-02-01)
- **Vendor spec:** 3.3-5.5 VDC supply, analog output **0-3.0 VDC**, 3-pin PH2.0 interface, ~99 x 16 mm
- **Source:** UMLIFE watering kit (4 sensors + 4 pumps + 4-ch relay + tubing). Purchase details on file in
  the local `parts` inventory.

### Board component reference (read from macro photos)

| Ref | Marking | Value / part | Role |
| --- | --- | --- | --- |
| Regulator | `662K` (SOT-23, 3-pin) | XC6206-class 3.0 V LDO | Regulates supply to a constant 3.0 V (defends against Issue 1) |
| `U2` | `TLC555` / `2542K` / `XBLW` | CMOS 555 timer | Oscillator (defends against Issue 2) |
| `R1` | `103` | 10 kohm | Timing |
| `R2` | `162` | 1.6 kohm | - |
| `R3` | `331` | 330 ohm | Output series |
| `R4` | `105` | **1 Mohm** | Output bleed-to-ground - **the Issue-3 resistor** |
| `T4` | (red glass) | Diode | Peak detector |

**Header pinout** (silk, top to bottom): `GND` / `VCC` / `AUOT` - note `AUOT` is a factory typo
for **AOUT** (analog out); cosmetic only.

---

## Known defects checked

Source: Flaura project (Martin Uhlmann), "82% of capacitive soil moisture sensors are faulty."
Full detail and citations in [`RESEARCH_capacitive_soil_moisture_sensors.md`](RESEARCH_capacitive_soil_moisture_sensors.md).

1. **Missing 3.0 V voltage regulator** - some boards omit the `662K` regulator and bridge the pads, so
   output drifts with supply voltage (bad on battery).
2. **Wrong timer chip** - cheaper boards use a bipolar `NE555` (needs ~4.5 V) instead of the CMOS `TLC555`
   (works down to ~2-3 V); NE555 boards fail at 3.3 V.
3. **1 Mohm resistor not grounded** - a misplaced via leaves R4's ground side floating, so the sensor
   responds extremely slowly and returns stale/identical readings. (~53% of one tester's 38-board sample.)

---

## Method

- **Issues 1 & 2 - visual.** Read the regulator and timer markings directly from macro photos (see
  `docs/evidence/`). Definitive: the part numbers are legible.
- **Issue 3 - multimeter, unpowered.** The R4-to-ground connection runs under soldermask and cannot be
  judged by eye, so it was metered:
  1. Sensor unplugged; meter in resistance (ohm) mode, ~2 Mohm range.
  2. Probes on the **GND** and **AUOT** header pins; let the reading settle (a filter cap charges off the meter).
  3. A stable **~1 Mohm** = R4 is grounded (PASS). **Open / "OL"** in *both* probe directions = ground link broken (FAIL).
  4. Reading confirmed in both probe polarities.

---

## Results

| Check | S1 | S2 | S3 | S4 |
| --- | --- | --- | --- | --- |
| Issue 1 - `662K` regulator present | PASS | PASS | PASS | PASS |
| Issue 2 - `TLC555` timer | PASS | PASS | PASS | PASS |
| Issue 3 - R4 to GND (AUOT<->GND, Mohm) | **0.997** | **0.993** | **0.994** | **1.000** |

All four Issue-3 readings sit in a **0.993-1.000 Mohm** band (~0.7% spread) - essentially nominal
1 Mohm, in both probe directions, indicating R4 is correctly grounded and on-value on every unit.

---

## Verdict

**All three known defects are absent on all four sensors.** The tight reading cluster also signals a
consistent, good-quality batch. **Use the four sensors as-is** - no resistor rework, no replacement
order. The fact that the boards carry both the `662K` regulator and a genuine `TLC555` (not an NE555)
is itself a quality signal: this is the well-designed variant of the board.

---

## Bonus sensor - SunFounder ESP32 kit (NE555 variant, NOT used for this project)

The SunFounder ESP32 starter kit included its own, *different* capacitive sensor board, checked here
for completeness. It is the cautionary-tale variant from the source video:

- **Silkscreen:** "Capacitive Soil Moisture Sensor v1.2" (v1.2, not the UMLIFE V2.0.0)
- **Issue 1 - regulator:** PASS (`662K` present)
- **Issue 3 - R4 to GND:** PASS (`0.996 Mohm` AOUT<->GND, both directions, after settling)
- **Issue 2 - timer chip:** **FAIL** - `U1` is an `NE555` (Texas Instruments bipolar 555, marked `NE555 / 55A`), not a TLC555.

Why this is worse than a plain no-regulator board: it *also* has the `662K` regulator, which clamps
the chip supply to ~3.0-3.3 V regardless of input voltage - **below the NE555's ~4.5 V minimum.** The
regulator guarantees the NE555 is underfed, and feeding the module 5 V does not help (the regulator
drops it). It might oscillate by luck (some NE555 units do, out of spec) but would be unreliable.

**Disposition:** not used for this project. The four UMLIFE `TLC555` boards are the project sensors.
This NE555 board is kept only as a spare/curiosity (usable only if its regulator were bypassed and it
were fed >=4.5 V - not worth the effort).

---

## Remaining sensor prep (build phase, not defects)

These apply to *every* capacitive sensor regardless of QA result:

- **Waterproofing** - coat the lower portion (below the max-insert line) with conformal coating / epoxy /
  clear nail polish to stop moisture wicking up the traces and corroding them over weeks. Keep the
  electronics end dry.
- **Per-sensor calibration** - record each sensor's dry (in air) and wet (submerged / saturated soil) raw
  ADC value and map to %. Do not assume one calibration fits all four.
- **Power-gating** - drive sensor VCC from a GPIO (or a transistor) and power it only during a reading, to
  reduce long-term degradation and save power.

---

## Evidence

Macro photos (to be added to `docs/evidence/`): full board, component cluster, `662K` regulator
close-up, `TLC555` close-up, `R3`/`R4` area. These are the basis for the Issue 1 & 2 visual passes.
