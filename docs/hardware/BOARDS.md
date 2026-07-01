# Sprout Board Support — Bring-up Reference (#436)

> **Status: pre-work / structure.** The classic ESP32 is the known baseline and is
> **unchanged**. Every S3/C5 pin below is a *candidate* to **bench-verify** against the
> module silkscreen + continuity — the lab boards are generic Amazon clones, **not**
> official Espressif DevKitC. Chip constraints cite the Espressif datasheets; confirm
> there and at the bench before assigning pins or flashing.

## Targets (from the hardware handoff)

| # | Board (as listed) | Chip | USB bridge | Flash / PSRAM | Status |
|---|---|---|---|---|---|
| 1 | classic ESP32 / NodeMCU-32S / ESP-32D | ESP32-D0WD (Xtensa LX6 ×2) | CP2102 (UART) | 4 MB | ✅ baseline (`esp32dev`), unchanged |
| 2 | Amazon ESP32-C5 3-pack | ESP32-C5 (RISC-V, dual-band Wi-Fi 6) | **CH340 (UART)** | 4 MB, 32-pin | ⛔ toolchain-blocked (#283) |
| 3 | Amazon "ESP32-S3-DevKitC N8R2" | ESP32-S3 (Xtensa LX7 ×2) | UART bridge **+ native USB** | 8 MB, 2 MB PSRAM (claimed) | 🟡 builds today; pins + USB to sort |

## What Sprout needs from a board (the pin budget)

- **4 × ADC-capable GPIO** — the soil probes. **ADC1 only** (ADC2 is unusable while Wi-Fi is on, every chip).
- **4 × output-capable GPIO** — the relays. Avoid strapping / boot pins.
- **2 × GPIO** — I²C SDA/SCL for the env sensors (#376).
- **1 × GPIO** — onboard LED (optional heartbeat).
- **USB-serial** — telemetry @ 19200; the host logger must be able to open the port.

## Chip constraints + candidate maps

### Target 1 — classic ESP32-D0WD (BASELINE — do not change)

The shipping map (`firmware/include/config.h`), for reference:

- Soil (ADC1, input-only pins): GPIO **36, 39, 34, 35**
- Relays: GPIO **25, 26, 27, 32** (avoids strapping 0/2/12/15)
- I²C (env build): SDA **21**, SCL **22**
- LED: GPIO **2** · Serial: CP2102 UART bridge @ 19200

### Target 3 — ESP32-S3 (buildable now; verify the N8R2 marking)

**Confirmed:** the pinned `espressif32@7.0.1` supports S3 — board ids `esp32-s3-devkitc-1`
(N8) and `rymcu-esp32-s3-devkitc-1` (**N8R2**, matches your listing). The toolchain
compiles the firmware today (verified: `pio run -e esp32s3` builds clean — see the PR).

**Chip facts (confirm vs the S3 datasheet):**

- Xtensa LX7 dual-core, 2.4 GHz Wi-Fi/BLE. GPIO **0–21 and 26–48** (22–25 don't exist).
  **No input-only pins** (unlike the classic's 34–39).
- **ADC1 = GPIO 1–10** (channels 0–9); ADC2 = GPIO 11–20 (unusable with Wi-Fi). → the four
  soil probes must move onto four of **GPIO 1–10**.
- **Strapping pins: GPIO 0, 3, 45, 46** — keep relays off these.
- **Native USB-Serial-JTAG on GPIO 19/20.** The DevKitC exposes *both* a UART-bridge port
  and a native-USB port; `ARDUINO_USB_CDC_ON_BOOT` decides whether `Serial` is the USB-CDC
  or the UART. The host logger must open whichever port enumerates — **bench-confirm.**
- **PSRAM (the `R2`/`R8` suffix) reserves SPI pins** for flash/PSRAM (≈ GPIO 26–32; octal
  PSRAM also 33–37). **N8R2 = 8 MB flash + 2 MB PSRAM** — bench-confirm which GPIOs the
  module reserves before putting a relay there.

**Candidate map — STARTING POINT, bench-verify every pin:**

- Soil (ADC1): GPIO **1, 2, 3, 4**
- Relays: GPIO **5, 6, 7, 15** (clear of strapping 0/3/45/46 + PSRAM pins)
- I²C: SDA **8**, SCL **9** (or the board's labeled Qwiic pins)
- LED: the board's `LED_BUILTIN`

### Target 2 — ESP32-C5 (toolchain-blocked; do NOT pre-assign pins)

**Blocked:** `espressif32@7.0.1` has **zero** C5 support (`pio boards esp32c5` → empty,
confirmed 2026-06-30). C5 needs a newer platform / arduino-esp32 3.2+ (IDF 5.4+) or the
pioarduino fork → the **#283 toolchain-pin revisit**.

**What we know (confirm vs the C5 datasheet + your board):**

- ESP32-C5 = single-core RISC-V, **dual-band Wi-Fi 6 (2.4 + 5 GHz)** + BLE — the headline
  new capability, and the reason this is worth doing for the early-adopter audience.
- Your 3-pack uses a **CH340 UART bridge** → serial should behave like the classic (UART @
  19200), **not** native USB-CDC — *simpler* than the S3 on the serial front.
- ADC / GPIO specifics **must come from the C5 datasheet + bench.** Per your handoff, do
  **not** assign C5 pins before recording the module marking, silkscreen, and continuity —
  so this doc intentionally leaves the C5 map **blank** until then.

## Serial per board (the real gotcha)

- **Classic + (your) C5 — UART bridge** (CP2102 / CH340): `Serial` @ 19200 exactly as today;
  the host logger opens the bridge COM port. No change.
- **S3 — native USB-CDC available**: if the firmware talks over native USB, set
  `-D ARDUINO_USB_CDC_ON_BOOT=1`; over the UART bridge, leave it off. The 19200 telemetry
  contract *and* the host logger's port pick depend on this — decide per board at the bench.

## Integration plan (when bench time comes)

1. **Extract the pin map to board-conditional config.** Today `config.h` hard-codes the
   classic `SENSOR_PINS`/`RELAY_PINS` and the env build hard-codes I²C 21/22 in `main.cpp`.
   Move them behind `#if defined(CONFIG_IDF_TARGET_ESP32 / _ESP32S3 / _ESP32C5)`.
   - **#343 caveat:** editing `config.h` trips the changed-files clang-format gate on its
     protected manual alignment. Do the extraction **after #352** (changed-lines gate) *or*
     as a deliberate, approved one-time `config.h` reformat — don't sneak it in.
   - Suggested shape (a new `board_pins.h` that `config.h` includes):

     ```c
     #if defined(CONFIG_IDF_TARGET_ESP32)      /* classic (baseline) */
     #define SOIL_PINS  {36, 39, 34, 35}
     #define RELAY_PINS {25, 26, 27, 32}
     #define I2C_SDA 21
     #define I2C_SCL 22
     #elif defined(CONFIG_IDF_TARGET_ESP32S3)  /* PROVISIONAL — bench-verify */
     #define SOIL_PINS  {1, 2, 3, 4}
     #define RELAY_PINS {5, 6, 7, 15}
     #define I2C_SDA 8
     #define I2C_SCL 9
     #elif defined(CONFIG_IDF_TARGET_ESP32C5)  /* TBD at the bench (#436) */
     #error "ESP32-C5 pin map not assigned yet — bench-verify first"
     #endif
     ```

2. **Per-board calibration.** Each chip's ADC (reference, attenuation, linearity) shifts the
   soil raw endpoints → each board needs its **own** `SENSOR_CAL_BOUNDARY` (#170 /
   `calibration.h`). Do not reuse the classic's `{3050…1050}`.
3. **Activate the PlatformIO env** (uncomment `esp32s3`; add `esp32c5` once a supporting
   platform lands) and **decide the CI board matrix** — building S3/C5 in CI pulls extra
   toolchains, so it's kept out of the default `pio run` for now (a DX / Workflow call).
4. **Bench bring-up** per the checklist below, then a boot + telemetry sanity capture like
   the classic (banner git rev + `# health:` OK + valid checksums).

## Bench-verification checklist (per physical board)

Run this **before** assigning pins / flashing — the boards are clones, so trust the
silkscreen + meter, not the listing:

- [ ] Record the **module marking** (chip + module, e.g. `ESP32-S3-WROOM-1 N8R2`); photo both sides.
- [ ] Note the **USB bridge** (CH340 / CP2102 / native-USB) and which COM port(s) enumerate.
- [ ] `esptool.py flash_id` → confirm **flash size** (+ PSRAM) vs the listing (N8R2 vs N8R8; 4 MB C5).
- [ ] From the silkscreen, list **every exposed GPIO** and mark: ADC-capable, strapping/boot,
      input-only, flash/PSRAM-reserved, USB (D+/D−).
- [ ] Choose **4 ADC1 pins** (soil), **4 output pins** (relays, no strapping), **2 I²C pins**; record it.
- [ ] **Continuity-check** each chosen header pin → the intended GPIO (clone header labels can lie).
- [ ] Decide the **serial path** (UART bridge vs native USB-CDC) and the `ARDUINO_USB_CDC_ON_BOOT` value.
- [ ] Bench-verify **relay polarity** (active-low CW-022) before any pump is connected — same rule as the classic.

---

Refs #436 · #283 (toolchain) · #170 (per-board cal) · #271 (factory image) · #376 (I²C env)

— Firmware 🔧
