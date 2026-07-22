# Bench run sheet — verify the Arduino starter sketch (#1494)

**Owner at the bench:** the maintainer. **Prepared by:** Design 🔍 (for the #1494 on-ramp).
**Why a bench step:** the sketch compiles clean (`arduino-cli`, `unor4wifi`, 20% flash) and its
output shape is verified in the editor, but two claims are only true if a real board says so:
that the **mood words** read right in the Serial Monitor (ch.1, shipped) and that the **raw
line plots** in the Serial Plotter (ch.3, DX's output fix — see the note at the end).

Nothing here flashes anything but the starter, and only over USB. No production board is touched.

---

## What you need

- **Arduino Uno R4 WiFi** + a USB-C cable.
- **One capacitive soil sensor** (HW-390 or the kit's), signal wire to **A0**, plus GND and 3.3/5 V.
- A cup of water and a dry spot (open air) to swing the reading.
- Arduino IDE with the sketch `arduino-starter/arduino-starter.ino` open.

## Steps

1. **Flash.** Open the sketch, select **Tools → Board → Arduino Uno R4 WiFi**, pick the port,
   and **Upload**. It should compile and flash without a library install (that's the point of
   the starter).

2. **Serial Monitor — the mood words (ch.1).** Open **Tools → Serial Monitor**, set **9600 baud**.
   You should see the boot line, then one reading per second:

   ```text
   raw=NNN  <mood line>
   ```

   Swing the sensor and confirm all three ratified moods appear, each with its friendly line:
   - **probe in open air** (driest) → `Thirsty - I could really use a drink. Grab the watering can.`
   - **probe in damp soil / between** → `Content - comfy, nothing to do. I'm happy.`
   - **probe in the cup of water** (wettest) → `Soaked - ahh, just drank; let me soak it up. …`

   ✅ **Pass:** the mood word leads, the friendly line follows, and the mood tracks wet↔dry
   correctly. (If a band feels off, that's a **calibration** call — the `DRY_READING` /
   `WET_READING` constants are illustrative; measure yours and edit them. Not a sketch bug.)

3. **LED blink.** With `BLINK_WHEN_THIRSTY = true`, the onboard **LED lights when the reading is
   in `Thirsty`** (drier than `THIRSTY_ABOVE`) and goes dark otherwise. ✅ **Pass:** LED follows
   the thirsty state as you wet/dry the probe.

4. **Serial Plotter — the live raw line (ch.3).** Open **Tools → Serial Plotter**, **9600 baud**.
   - **Today (before DX's ch.3 fix):** each line mixes `raw=NNN` with the prose mood line, so the
     Plotter likely won't graph a clean series — this is the **known ch.3 gap**, not a failure of
     ch.1. Note what you see and move on.
   - **After DX lands the ch.3 output fix** (a numeric `raw:NNN` line separate from the voice
     line, or a plotter mode): re-run this step and confirm the **raw value plots as a clean
     line** that rises as the soil dries and drops when you dip the probe. ✅ **Pass** is a
     legible live curve — the boot line's promise ("watch it live in the Plotter") made true.

## Sign-off

- [ ] Step 2 — all three mood words read correctly (ch.1) ✅
- [ ] Step 3 — LED tracks the thirsty state ✅
- [ ] Step 4 — raw plots cleanly (⏳ after DX's ch.3 output fix)

Record the result on **#1494** (a line + a photo of the Serial Monitor is plenty). Steps 2–3
close ch.1's hardware verification; step 4 closes with DX's ch.3.

---

*Note — ch.3 & ch.4 are not the maintainer's to build:* ch.3 (the Serial-Plotter output shape)
is DX's (`for:dx`); this run sheet only asks the bench to **verify** it once it lands. ch.4 (the
architect-clean pass) is Trellis's (`for:trellis`). ch.1 (the word-mark moods) shipped in
[PR #1505](https://github.com/OrangePeachPink/sprout/pull/1505).

— Design 🔍
