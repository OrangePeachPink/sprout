# Bring-up checklist - plants controller

**Last updated:** 2026-06-21
**Status:** **Rung 3 complete** - one capacitive sensor (V2.0.0 / TLC555) reads cleanly on GPIO36.
Bench-verified raw 12-bit endpoints: **dry/air ~3150, wet/submerged ~1000** (~2150-count swing;
damp-but-out-of-water ~2700). Phase A (toolchain + first flash) done; sensor pins multimeter-verified;
firmware at 0.2.0. Auto-reset reliable on this board - no BOOT/RST hold needed. Next: Rung 4 (wire the
other three sensors, per-sensor air/water calibration).

We climb one rung at a time; each has a **"proves"** gate that must pass before the next. See
`WIRING.md` for the full power/pin map and `ADR.md` for the architecture decisions.

## Firmware versioning

`PLANTS_FW_VERSION` in `firmware/include/config.h` follows pre-1.0 SemVer:

- **PATCH** (`0.2.x`) - an enhancement or fix *within* the current capability (output formatting, a
  calibration tweak, a bug fix).
- **MINOR** (`0.x.0`) - a new capability / rung completed (all-four sensors, OLED, relay, the watering loop).
- **MAJOR** (`1.0.0`) - the first build trustworthy on real plants.

Keep the version string, this file, and the README aligned when it changes. History: `0.0.1` scaffold ->
`0.2.0` single-sensor read (Rung 3; `0.1.0` was skipped - a one-time gap) -> `0.2.1` human-readable table
with moisture % and a state word.

## Phase A - Toolchain & first flash (ESP32 alone, nothing wired)

- [x] **Rung 1 - Toolchain & first contact**
  - [x] SiLabs CP210x VCP driver (confirmed - v11.5.0.417, signed; verified in Device Manager)
  - [x] USB-C data cable (confirmed - it enumerated)
  - [x] VS Code + PlatformIO IDE extension present (PIO Core 6.1.19; STM32 clangd extension disabled to end the IntelliSense conflict with Microsoft cpptools)
  - [x] Board appears as a COM port (currently COM6 - number can shift between replugs)
  - *Proves: the PC can see and talk to the board.*
- [x] **Rung 2 - First flash**
  - [x] Open `firmware/` in VS Code (toolchain already cached; first build ~9.6s)
  - [x] Build the placeholder -> Upload (15.07s; auto-reset worked, no BOOT hold needed)
  - [x] Serial Monitor @ 115200 -> banner + `firmware version: 0.0.1` received; blue GPIO2 LED blinks ~1 Hz
  - *Proves: build -> upload -> run -> serial all work. Toolchain done.*

## Phase B - Sensing (one, then four)

- [x] **Rung 3 - One soil sensor** (V2.0.0 / TLC555 on GPIO36)
  - [x] Wire ONE: 3V3 / GND / AOUT -> GPIO36 (SVP); no relay/pumps. Pins multimeter-verified at the bench.
  - [x] Read-and-print sketch (fw 0.2.0); endpoints recorded - **dry/air ~3150, wet/submerged ~1000**
    (~2150-count swing; damp-but-out-of-water ~2700)
  - *Proves: ADC + wiring good; first calibration endpoints (dry = high, wet = low).*
- [ ] **Rung 4 - All four sensors**
  - Wire the other three (shared 3V3/GND rail = hub; signals -> GPIO39/34/35)
  - Per-sensor air/water calibration; map raw -> %; store constants in config.h
  - *Proves: four trustworthy, calibrated readings.*

## Phase C - Display (early visual win)

- [ ] **Rung 5 - OLED status** (independent - can slot in right after Rung 2 for a live readout while calibrating)
  - Wire SH1106: 3V3 / GND / SDA -> GPIO21 / SCL -> GPIO22
  - I2C scan -> confirm address (0x3C); add U8g2 (SH1106 driver) to lib_deps; show live %
  - *Proves: I2C + display work; glanceable readout for everything below.*

## Phase D - Actuation (relay dry -> one pump -> four)

- [ ] **Rung 6 - Relay bench-check (NO pumps yet)**
  - Power relay (VCC/GND, JD-VCC jumper ON); toggle a GPIO -> confirm active-LOW (click/LED)
  - Meter terminals: at rest COM<->NC closed, COM<->NO open
  - *Proves: relay polarity + terminal map, before any motor.*
- [ ] **Rung 7 - One pump (dry-run, then water)**
  - One channel: COM <- 5V, NO -> pump+, pump- -> GND; flyback diode across pump; bulk cap on 5V rail
  - First power-on via bench supply, current-limited ~0.5 A
  - Brief dry pulse (don't run dry long) -> then in water -> pumps AND ESP32 doesn't reset
  - *Proves: control -> relay -> pump -> water path; cap/diode tamed the brownout risk.*
- [ ] **Rung 8 - All four pumps**
  - Wire the other three; distribute 5V to the four COMs + common ground (Wago for chunky joins)
  - Confirm each independently; enforce one-pump-at-a-time in code
  - *Proves: every channel actuates; no concurrency.*

## Phase E - Close the loop & soak

- [ ] **Rung 9 - The watering control loop**
  - read -> if below threshold -> dose (fixed ms) -> lock-out -> re-check on a slow cadence
  - Safety: max-runtime cap, one-at-a-time (low-water cutoff arrives with the reservoir)
  - Tune dose over 2-3 cycles on ONE zone, then enable all four
  - *Proves: autonomous closed-loop watering.*
- [ ] **Rung 10 - Time + status polish**
  - WiFi + NTP -> real "last watered HH:MM" on the OLED (logging/notifications = Phase 2, deferred)
  - *Proves: meaningful timestamps; runs unattended.*
- [ ] **Rung 11 - Bench soak test**
  - Run the whole rig on the bench for days with real pots/water -> doses right, no resets, calibration holds
  - *Proves: it works over time before touching your plants.*
- [ ] **Rung 12 - Hand off to the physical build**
  - Breadboard -> Freenove breakout (sturdier); lock final pin map in config.h
  - THEN the deferred physical: reservoir, tubing, zoning, ledge layout, mounting, low-water sensor
