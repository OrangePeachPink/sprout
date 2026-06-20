# Research - Capacitive Soil Moisture Sensors (foundation, defects, fixes, sources)

**Compiled:** 2026-06-20
**For:** the `plants` auto-watering project
**Purpose:** a re-reviewable foundation on how these sensors work, every known defect and its
workaround, how to diagnose them, and what to buy - plus an annotated source index (including
links with ready-to-use Arduino/ESP32 code and calibration/waterproofing tutorials) for when the
project expands.

---

## 0. How this was produced (provenance - read this first)

This document was assembled from a multi-agent web-research run (the `deep-research` workflow:
fan-out web search -> fetch sources -> extract claims -> adversarial verification -> synthesis),
cross-checked against the Flaura YouTube source the project started from and against primary
datasheets.

**Honesty caveat:** on the run that produced these results, the **adversarial-verification stage
was rate-limited by the API and did not actually execute** - every verifier vote came back as an
abstain, and the harness then auto-labeled all claims "inconclusive." That label is an artifact of
the outage, **not** a real refutation. The *front end* worked: 18 sources were fetched and 81
claims extracted. The claims reproduced in section 7 are therefore **source-attributed claims that
have been reviewed by hand against primary sources (the TI TLC555 datasheet) and the Flaura video -
not machine-verified.** Treat them as well-sourced and corroborated, but if a specific number ever
becomes load-bearing, confirm it against the cited primary source.

The "82% faulty" and "53% missing-resistor" figures are **one researcher's sample statistics**
(Martin Uhlmann, 38 boards), corroborated by other teardowns - widespread, but not a guarantee
about any individual board. (Our own four units passed; see [`../SENSOR_QA.md`](../SENSOR_QA.md).)

---

## 1. How a capacitive soil moisture sensor works (FACT)

- The probe's two copper areas on the PCB form a **capacitor**. Soil water changes the soil's
  dielectric constant, which changes that capacitance.
- An onboard **555 timer** runs as an oscillator. Its square-wave output drives the probe
  capacitance through an RC network; a diode + capacitor **peak detector** plus a bleed resistor
  turn that into a steady **analog DC voltage**.
- **More water -> higher capacitance -> lower output voltage.** So **dry = high voltage, wet = low
  voltage** (the mapping feels backwards until you internalize it).
- Output on a well-made (regulated) board is capped around **0-3.0 V** regardless of a 3.3-5.5 V
  supply, which is why it reads cleanly on a 3.3 V ADC with no divider.

**Why capacitive beats resistive:** resistive probes pass DC through exposed metal in wet soil,
which **corrodes / electrolyzes** the electrodes within days. Capacitive probes expose no metal to
the soil, so there is nothing to dissolve - they last far longer.

---

## 2. The three famous defects (REPORTS, corroborated)

### Issue 1 - Missing voltage regulator
A correct board carries a `662K` (XC6206 / HT7333-class) LDO that pins the sensor's supply to a
constant ~3.0 V. Cheaper boards omit it and **bridge the pads**, so the output now drifts with the
supply rail. Harmless on a clean regulated supply; **bad on any battery** (a Li-ion sags from 4.2 V
to ~3.0 V as it drains, dragging the readings with it).

### Issue 2 - Wrong timer chip (NE555 vs TLC555)
- **TLC555** (CMOS) runs from ~2 V (TLC555C) / ~3 V (TLC555I) up to 15 V and draws little current -
  fine on a 3.3 V ESP32 or a Li-ion (per the TI datasheet).
- **NE555** (bipolar) needs ~**4.5 V** minimum, so NE555 boards **will not work at 3.3 V**.
  (A few NE555 boards marked "20M" reportedly work at 3.3 V by luck - a gamble, not a spec.)

### Issue 3 - 1 Mohm output resistor not connected to ground
The 1 Mohm bleed resistor (R4) should tie the analog output to ground. On defective boards a
**misplaced via** leaves its ground side floating - electrically the resistor is not there. Effect:
the output **floats high and responds extremely slowly**, so repeated reads return the **same stale
value**. That quietly ruins any "take 5 readings and average / reject outliers" scheme, because all
5 reads are the identical wrong number. Reported in ~53% of one 38-board sample.

### Which defects matter on which MCU

| Defect | 3.3 V ESP32 (or battery) | 5 V Arduino Uno/Nano (clean supply) |
| --- | --- | --- |
| 1 - missing regulator | **Matters** (especially on battery) | Minor (supply already constant) |
| 2 - NE555 timer | **Fatal** (will not run at 3.3 V) | Usually OK (>=4.5 V available) |
| 3 - ungrounded R4 | **Matters** | **Matters** (defect is supply-independent) |

---

## 3. Other known issues (beyond the three)

- **No waterproofing / corrosion over time.** The lower PCB wicks moisture; traces corrode and
  readings drift over weeks. Fix: conformal coat / epoxy / heat-shrink the lower section, keep the
  electronics dry, and do not insert past the marked line.
- **Per-unit variation.** Even identical boards read differently; calibrate each one.
- **Calibration drift & temperature sensitivity.** Re-check calibration occasionally.
- **ADC range vs supply.** A regulated board's 0-3.0 V output is safe on a 3.3 V ADC. An
  unregulated board run at 5 V into a 3.3 V ADC can exceed the ADC's input range - divide or regulate.
- **Output polarity confusion.** Remember dry = high, wet = low when writing thresholds.
- **Continuous power accelerates aging.** Power-gate the sensor (only on during a read).

---

## 4. How to diagnose a board

**Visual (magnifier / macro photo):**
- Find the 3-pin `662K` regulator (Issue 1).
- Read the 8-pin timer label: `TLC555` good, `NE555` bad (Issue 2).
- Check the via near the two output resistors - it should sit *between* them, not shifted outboard
  (Issue 3). This one is sub-millimeter and often **cannot** be called by eye - meter it.

**Multimeter:**
- *Issue 3, unpowered:* resistance from **AOUT to GND** should be a stable **~1 Mohm**; open / "OL"
  in both directions = the defect. (This is the test used in [`../SENSOR_QA.md`](../SENSOR_QA.md).)
- *Functional, powered:* in dry air the output reads high (~3.0 V) and should **drop promptly
  (~1 s)** to ~1.2-1.7 V when the probe is dunked in water. A defective (ungrounded-R4) board pegs
  high and barely moves, or moves over many seconds. A missing-R4 board can read ~95% of supply in
  free air (cave-pearl diagnostic).

---

## 5. Fixes / workarounds

- **Ungrounded R4 (Issue 3):** solder a fresh **1 Mohm resistor across the AOUT and GND header
  pins**, *or* bridge a short wire from R4's floating (ground-side) pad to ground.
- **Missing regulator (Issue 1):** feed the sensor a clean, constant voltage (e.g. a regulated
  3.3 V rail) instead of a battery.
- **NE555 (Issue 2):** run it at >=4.5 V (5 V Arduino), or replace the board - do not fight it on 3.3 V.
- **Waterproofing:** conformal coat / epoxy / clear nail polish on the lower board; heat-shrink the
  cable entry.
- **Software:** per-sensor calibration (store air & water raw values, map to %); median/averaging
  with **power-gating** between reads.

---

## 6. Buying guidance (for future orders)

Zoom **all the way in** on the product photos and confirm:
- the 3-pin **`662K`** regulator is present;
- the timer is labeled **`TLC555C` / `TLC555I`** (not `NE555`);
- the via sits **between the two output resistors**.

If the photos are too blurry to tell, buy elsewhere. And note: **retailers sometimes ship a
different / faulty board than pictured**, so meter every unit on arrival regardless. For a
guaranteed clean design, the **DFRobot SEN0193** is the regulated reference part (3.3-5.5 V in,
0-3.0 V out).

---

## 7. Raw extracted claims (source-attributed; see section 0 caveat)

### A. Working principle (FACT)
- A capacitive sensor's PCB forms a capacitor (central conductive plate + outer ground plate) and
  senses moisture via the soil's changing dielectric. [electroniclinic]
- Two PCB copper traces act as the capacitor; a 555 timer feeds square waves into an RC integrator
  to produce an output voltage proportional to moisture. [lastminuteengineers]
- The 555 is a fixed-frequency oscillator; the sensor's reactance forms a voltage divider giving a
  DC output of roughly 1.2-3.0 V read by the Arduino ADC. [biomaker]
- Capacitance changes with surrounding water content; the 555 times the charge/discharge. [basontech]
- Coplanar traces filter the 555 output; a peak detector converts the filtered square wave to DC;
  frequency is set by the RC timing network. [thecavepearl]
- TLC555 generates a near-square wave at f = 1.44 / ((R3 + 2*R2) * C3); rising moisture raises probe
  capacitance and lowers output voltage (dry = higher voltage). [hackmd]

### B. Capacitive vs resistive
- Capacitive is preferred because the plates are not exposed to soil, so the sensor does not corrode. [biomaker]
- Resistive sensors corrode over time because their DC current electrolyzes in water. [basontech]
- Resistive sensors rust/corrode (even gold-plated), degrading readings; capacitive has no exposed
  metal. [lastminuteengineers]

### C. Timer chip (TLC555 vs NE555)
- The timer must be a TLC555 (runs at 3.3 V) for correct low-voltage operation; NE555-substituted
  boards may not function. [hackmd]
- TLC555 single-supply 2-15 V; TLC555C rated to 2 V min, TLC555I to 3 V min (Recommended Operating
  Conditions) - confirms 3.0-3.3 V operation on ESP32 or a partially drained Li-ion. [TI datasheet]
- TLC555 is CMOS, high input impedance, tolerates smaller timing caps, low current across the supply
  range - the architectural reason it works at low voltage where the bipolar NE555 (~4.5 V) does not. [TI datasheet]
- NE555 is unreliable at 3.3 V; the author found ~half of NE555 chips would not work even at 5 V in
  the default analog config; avoid boards with the regulator removed AND an NE555. [thecavepearl]
- Prefer regulated TLC555 boards: the TLC555 draws far less current and works at 3.3 V (down to ~2 V),
  the correct choice for battery / 3.3 V ESP32. [thecavepearl]

### D. Voltage regulator
- The onboard 662K regulator drops a higher supply to ~3.0-3.3 V; if it is missing, the input supply
  itself must be held near 3.3 V for correct operation. [hackmd]
- The SEN0193 includes an onboard regulator over 3.3-5.5 V input, so output is fixed 0-3.0 V
  regardless of supply - exactly the regulator the defective clones omit (bridging the pads instead). [dfrobot]

### E. Issue 3 - ungrounded 1 Mohm resistor
- A missing R4-to-ground connection makes some v2.0 sensors discharge extremely slowly: air -> water,
  only a few discharge within 1 s while the rest take >10 s; soldering a wire between the two points
  fixes it. [hackmd]
- The primary defect is a single misplaced via interrupting a copper trace, leaving the 1 Mohm output
  resistor's ground side disconnected. [hackster]
- The defect manifests as the sensor being unresponsive / reacting extremely slowly (stale, identical
  readings). [hackster]
- Repair by soldering a new 1 Mohm resistor between the analog-out pin and ground, or bridging the
  disconnected side to ground with a wire. [hackster]
- Many boards are missing the R4 ground connection; diagnose by the sensor outputting ~95% of supply
  voltage in free air; fix by soldering a 1 Mohm resistor across the output. [thecavepearl]

### F. Prevalence
- Uhlmann (Flaura) reported 82% of the cheap capacitive sensors he bought were faulty - establishing
  the defect as widespread ("an epidemic"), not a one-off. [hackster]

### G. ADC range / regulated reference part
- The DFRobot SEN0193 accepts 3.3-5.5 VDC, usable on both a 3.3 V ESP32 and a 5 V Arduino without the
  low-voltage failure of NE555 clones. [dfrobot]
- Its output tops out at 3.0 VDC even at a 5 V supply, so a 3.3 V ESP32 ADC stays in range with no
  voltage divider needed. [dfrobot]

---

## 8. Source index (18 sources)

Annotated; a star (*) marks sources with ready-to-use code or a hands-on tutorial worth returning to
as the project expands.

| # | Source | Type | Why it's useful |
| --- | --- | --- | --- |
| 1 | * [lastminuteengineers - capacitive soil moisture + Arduino](https://lastminuteengineers.com/capacitive-soil-moisture-sensor-arduino/) | tutorial | Clear wiring + Arduino code; good starting tutorial. |
| 2 | * [The Cave Pearl Project - hacking the sensor / frequency output](https://thecavepearlproject.org/2020/10/27/hacking-a-capacitive-soil-moisture-sensor-for-frequency-output/) | deep blog | Best teardown: NE555 vs TLC555, R4 defect diagnosis, low-power frequency-output hack (advanced). |
| 3 | [how2electronics - interface guide](https://how2electronics.com/interface-capacitive-soil-moisture-sensor-arduino/) | tutorial | Has code, but flagged lower-reliability by the research run - verify specifics. |
| 4 | [biomaker - Aideepen v1.2 notes](https://www.biomaker.org/block-catalogue/2021/12/17/soil-moisture-sensor-aideepen-v12) | secondary | Concise working-principle + voltage-range notes. |
| 5 | * [electroniclinic - circuit diagram + programming](https://www.electroniclinic.com/capacitive-soil-moisture-sensor-arduino-circuit-diagram-and-programming/) | tutorial | Circuit explanation plus Arduino code. |
| 6 | * [basontech - Arduino capacitive sensor guide](https://basontech.com/arduino/capacitive-soil-moisture-sensor-arduino/) | tutorial | Beginner-friendly guide with code. |
| 7 | [Hackster - Flaura smart watering pot](https://www.hackster.io/news/flaura-the-smart-watering-pot-3c7903089eaa) | project | The open-source self-watering pot this whole topic traces back to. |
| 8 | [HackMD - detailed circuit analysis](https://hackmd.io/@0V3cv8JJRnuK3jMwbJ-EeA/ByJgxe1jbl) | technical | The most rigorous circuit + defect write-up; air/water discharge timing. |
| 9 | [TI - TLC555 datasheet (PDF)](https://www.ti.com/lit/ds/symlink/tlc555.pdf) | primary | Authoritative timer spec (2-15 V; TLC555C to 2 V, TLC555I to 3 V). |
| 10 | [savel.org - teardown of the defect](https://www.savel.org/2020/07/09/capacitive-soil-moisture-sensor-designed-by-retarded/) | blog | Independent teardown of the missing-resistor defect. |
| 11 | * [SwitchDoc - waterproofing tutorial](https://www.switchdoc.com/2020/07/tutorial-waterproofing-capacitive-moisture-sensors/) | how-to | How to waterproof the lower board properly. |
| 12 | * [Makersportal - calibration with Arduino](https://makersportal.com/blog/2020/5/26/capacitive-soil-moisture-calibration-with-arduino) | tutorial | Calibration math + Arduino code (use for the calibration step). |
| 13 | * [maakbaas - ESP32 soil moisture (hardware design)](https://maakbaas.com/esp32-soil-moisture-sensor/logs/hardware-design/) | blog | ESP32-specific design log - relevant if we go ESP32. |
| 14 | * [EMQX - hands-on ESP32 guide](https://www.emqx.com/en/blog/hands-on-guide-on-esp32) | tutorial | ESP32 + MQTT path - useful for the logging/monitoring stretch goal. |
| 15 | [DFRobot - SEN0193 wiki](https://wiki.dfrobot.com/sen0193/) | official | The regulated reference sensor; sample code + specs. |
| 16 | [Hackster - "epidemic of faulty sensors" + fix](https://www.hackster.io/news/martin-uhlmann-finds-an-epidemic-of-faulty-soil-moisture-sensors-and-comes-up-with-a-quick-fix-c05153bef67e) | secondary | Coverage of the 82% finding and the quick fix. |
| 17 | * [arduinodiy - capacitive humidity sensor (part 4)](https://arduinodiy.wordpress.com/2018/06/28/a-capacitive-soil-humidity-sensor-part-4/) | blog | Long-running series on these sensors. |
| 18 | [Physics Forums - TLC555 sensor thread](https://www.physicsforums.com/threads/capacitive-soil-moisture-sensor-using-tlc555.970505/) | forum | Discussion / troubleshooting thread. |

Primary video source for the project: Flaura, "Capacitive soil moisture sensors - 82% are faulty"
(https://www.youtube.com/watch?v=IGP38bz-K48).

A verbatim transcript of that video is archived alongside this doc at
[`flaura-video-transcript.txt`](flaura-video-transcript.txt), kept as a source artifact. It is
third-party content - reconsider keeping it if this repo is ever made public.
