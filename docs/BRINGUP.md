# Bring-up checklist - plants controller

**Last updated:** 2026-06-21
**Status:** **Phase A complete** - first flash verified end-to-end. Board enumerates as a **Silicon Labs
CP210x** COM port (driver v11.5.0.417, signed; currently **COM6** - number can shift between replugs).
Built, uploaded, and confirmed the serial banner (`firmware version: 0.0.1`) plus the GPIO2 LED heartbeat.
Auto-reset is reliable on this board - no BOOT/RST hold needed for flashing. Next: Rung 3 (one soil sensor).

We climb one rung at a time; each has a **"proves"** gate that must pass before the next. See
`WIRING.md` for the full power/pin map and `ADR.md` for the architecture decisions.

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

- [ ] **Rung 3 - One soil sensor**
  - Wire ONE: 3V3 / GND / AOUT -> GPIO36 (SVP); no relay/pumps
  - Read-and-print sketch; read in air (dry) and water (wet) -> record both raw values
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
