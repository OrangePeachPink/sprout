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
| 2 | Amazon ESP32-C5 3-pack | ESP32-C5 (RISC-V, dual-band Wi-Fi 6) | **CH340 (UART)** | 4 MB, 32-pin | 🟡 builds today (#529); pins to sort |
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

**Confirmed:** the pinned toolchain (pioarduino, shared across the whole matrix since #529)
supports S3 — board ids `esp32-s3-devkitc-1` (N8) and `rymcu-esp32-s3-devkitc-1` (**N8R2**,
matches your listing). The toolchain compiles the firmware today (verified: `pio run -e
esp32s3` builds clean — see the PR).

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

### Target 2 — ESP32-C5 (toolchain resolved; do NOT pre-assign pins)

**Resolved (#283 → #529):** the classic `espressif32@7.0.1` pin had **zero** C5 support
(`pio boards esp32c5` → empty, confirmed 2026-06-30) — needed arduino-esp32 3.2+ (IDF 5.4+).
The whole matrix, including C5, now shares one pioarduino pin (ADR-0024 revised); C5 builds
today the same as S3 does. The pin *map* below is still bench-pending — the toolchain
question and the pin-assignment question are separate, and only the first is resolved.

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
- **S3 — CONFIRMED, no code change needed (verified 2026-07-01):** PlatformIO's
  `esp32-s3-devkitc-1` board id **defaults to `CDCOnBoot: Disabled`** in the framework's
  `boards.txt` — i.e. it already targets the UART-bridge-compatible path, same as classic,
  with no `-D ARDUINO_USB_CDC_ON_BOOT` flag needed in `platformio.ini`. **The one thing still
  genuinely bench-gated:** whether your specific Amazon clone board actually *has* a separate
  UART bridge chip, or only a native-USB port (cheap clones sometimes omit the bridge).
  Check at the bench — if only native-USB enumerates, add
  `build_flags = -D ARDUINO_USB_CDC_ON_BOOT=1` to `[env:esp32s3]` in `platformio.ini` (one
  line, ready to add — not added speculatively since the current default is the safer bet).

## Integration status (updated 2026-07-01 — most of the original plan is now DONE)

1. **✅ DONE — per-board pin map**, `firmware/include/board_capability.h`. Landed as descriptor
   **fields on `board_capability_t`** (`soil_pins`/`relay_pins`/`led_pin`/`i2c_sda`/`i2c_scl`),
   not the separate `board_pins.h` this doc originally sketched — ADR-0019 §1 already lists
   pins as a descriptor field, so `config.h`/`main.cpp` source `SENSOR_PINS`/`RELAY_PINS`/
   `LED_PIN`/`ENV_I2C_SDA`/`SCL` straight from `BOARD_CAP`. Classic is byte-identical
   (regression-locked in the native test); S3 carries the candidate map below, PROVISIONAL.
2. **✅ DONE (structure) — per-board calibration.** `board_capability_t.cal_boundary[6]` +
   `cal_verified` (bool). **Verified first:** classic and S3 share the SAME
   `SOC_ADC_MAX_BITWIDTH=12` (checked directly against the framework's `soc_caps.h` for both
   chips) — so **resolution isn't the gap**, calibration data is. Classic's `cal_boundary` is
   the real #248 bench-anchored endpoints (`cal_verified=true`); S3/C5 carry the SAME numbers
   as an explicit, honestly-flagged PLACEHOLDER (`cal_verified=false`) — printed in the boot
   banner (`# board cal: PLACEHOLDER...`) so it's never silently mistaken for real data.
   **Still open:** the actual per-board bench measurement (#443) to replace the placeholder.
3. **✅ DONE — CI board matrix.** #499 (ADR-0024): `esp32s3`/`esp32c5` compile-check on every
   PR via a non-blocking `experimental-boards` job, isolated from `gate` (can't red the
   required check). `esp32s3` is a permanent uncommented env now (shares `esp32dev`'s pinned
   platform, zero extra toolchain cost); `esp32c5` pins its own isolated platform (#442).
4. **✅ CONFIRMED — factory image.** `factory_bin.py` (the `post:` build step, #271) is
   generic — inherited via `extends = env:esp32dev`, no board-specific code. Verified clean
   for `esp32s3`: `sprout-esp32-factory.bin` + `manifest.json` both build correctly.
5. **Still open — physical bring-up.** The bench checklist below, hardware-gated (#443).

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
