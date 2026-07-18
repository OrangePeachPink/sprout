# Sprout Board Support — Bring-up Reference (#436)

> **Status: identities intake-verified (2026-07-01); pins still bench-pending.** The classic
> ESP32 is the known baseline and is **unchanged**. Every S3/C5 pin below is a *candidate* to
> **bench-verify** against the module silkscreen + continuity. Of the new boards, ONE is an
> official Espressif DevKitC (`c5-official-01`); the S3 and the second C5 are clones — apply
> the "clones lie" posture to those two. Chip constraints cite the Espressif datasheets;
> confirm there and at the bench before assigning pins or flashing.

## Targets (intake-verified 2026-07-01 — supersedes the original handoff guesses)

| # | Board (bench ID) | Chip | USB (observed) | Flash / PSRAM | Status |
|---|---|---|---|---|---|
| 1 | classic ESP32 / NodeMCU-32S / ESP-32D | ESP32-D0WD (Xtensa LX6 ×2) | CP2102 (UART) | 4 MB | ✅ baseline (`esp32dev`), unchanged |
| 2a | `c5-official-01` — Espressif ESP32-C5-DevKitC-1-**N8R8** (official; box + silkscreen + module can agree) | ESP32-C5 (RISC-V, dual-band Wi-Fi 6) | CP210x on the `UART` port (COM11) **+ native USB** on the `USB` port (COM12) | **8 MB + 8 MB PSRAM** | 🟡 builds today (#529); `flash_id` + pins pending |
| 2b | `c5-yellow-01` — ESP32-C5-KITC-A clone (module can: `ESPC5-32 H4`) | ESP32-C5 | CH340 on the one tested port (COM10); 2nd port unconfirmed | unknown until `flash_id` (possibly 4 MB) | 🟡 builds today; identity resolved, USB split partial |
| 3 | `s3-n8r2-01` — ESP32-S3-N8R2 dual-USB | ESP32-S3 (Xtensa LX7 ×2) | native USB serial/JTAG (`303A:4001`, COM7) is the **only** working port — the CH343 UART-bridge port is dead (#443); see the serial section | 8 MB + 2 MB PSRAM (`flash_id`-confirmed 2026-07-03) | 🟢 builds + flashes via native USB (esptool-direct) |

> Identity source of truth: the #443 intake evidence packet,
> [`docs/evidence/2026-07-01-esp32-s3-c5-intake/`](../evidence/2026-07-01-esp32-s3-c5-intake/README.md)
> (photos + Device Manager enumerations, curated by Sage). There are TWO C5 variants in
> house; which one the fleet standardizes on is an open maintainer decision on #443.

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

**Anticipated map (in `board_capability.h`, `cal_verified=false`) — bench-verify every pin:**

- Soil (ADC1): GPIO **1, 2, 4, 5** — refined 2026-07-03 to drop strapping **GPIO3** (S3
  strapping = 0/3/45/46) that the earlier `{1,2,3,4}` candidate included.
- Relays: GPIO **6, 7, 15, 16** (non-strapping outputs, clear of USB-JTAG 19/20 + PSRAM pins)
- I²C: SDA **8**, SCL **9** (or the board's labeled Qwiic pins)
- LED: `BOARD_LED_NONE` (generic-clone LED unconfirmed)

### Target 2 — ESP32-C5 (toolchain resolved; do NOT pre-assign pins)

**Resolved (#283 → #529):** the classic `espressif32@7.0.1` pin had **zero** C5 support
(`pio boards esp32c5` → empty, confirmed 2026-06-30) — needed arduino-esp32 3.2+ (IDF 5.4+).
The whole matrix, including C5, now shares one pioarduino pin (ADR-0024 revised); C5 builds
today the same as S3 does. The pin *map* below is still bench-pending — the toolchain
question and the pin-assignment question are separate, and only the first is resolved.

**What we know (intake-verified 2026-07-01; ADC/GPIO still datasheet + bench):**

- ESP32-C5 = single-core RISC-V, **dual-band Wi-Fi 6 (2.4 + 5 GHz)** + BLE — the headline
  new capability, and the reason this is worth doing for the early-adopter audience.
- **TWO variants in house** (intake packet): `c5-official-01` (DevKitC-1-N8R8: CP210x UART
  port + native USB port, 8MB+8MB PSRAM) and `c5-yellow-01` (KITC-A clone: CH340 on the
  tested port, flash TBD). The original "3-pack, CH340, 4MB" handoff description matched
  the clone only. Both serial paths behave classic-like on their UART/CH340 port @ 19200.
- **Anticipated C5 map now entered** in `board_capability.h` (`cal_verified=false`), from the
  datasheet + DevKitC-1 v1.2 user guide — **valid existent GPIOs** (C5 = GPIO0–28):
  - Soil (ADC1): GPIO **1, 4, 5, 6** — the only four non-strapping ADC1 pins (ADC1 = GPIO1–6;
    strapping MTMS/2, MTDI/3 removed → forced, not chosen).
  - Relays: GPIO **0, 8, 9, 10** (the only four free non-strapping outputs; confirm GPIO0
    isn't the boot button at continuity).
  - I²C: **23 / 24** — nominal, no env sensors planned on the C5.
- **Why this replaced the placeholder (bench finding, 2026-07-03, official C5):** the prior
  entry inherited the *classic* pins `{36,39,34,35}`/`{25,26,27,32}`, which **don't exist** on
  the C5 (GPIO0–28) — the first flash flooded continuous `Pin 36 is not ADC pin!` /
  `IO 32 is not set as GPIO` errors that starved the loop before WiFi came up. Valid pins fixed
  it; WiFi bring-up then succeeded (see `docs/evidence/2026-07-03-esp32-c5-native-usb/`).
- Continuity is still **meter-pending (B1)** — the clones lie, and even this official board's
  header→GPIO routing wants confirming; expect per-VARIANT entries if the two C5s' usable pins
  differ.

### ADC1 sensor ceiling per board (scale headroom)

The pin budget above is built around the kit's **4** soil probes. This table is the verified
**ADC1-only** ceiling if a single board ever scales past 4 (ADC2 stays off with Wi-Fi on every
chip, so the ceiling is simply "how many usable ADC1 channels does the family expose?"). It sizes
the card-grid scale ceiling — e.g. 4 boards × 6 = 24 plants. Channel counts are datasheet-verified
(retrieved 2026-07-12); the "clean-for-soil" column subtracts strapping/JTAG/unbonded pins.

| Board | ADC1 channels (datasheet) | Clean-for-soil ceiling | Why |
| --- | --- | --- | --- |
| classic ESP32-D0WD (WROOM-32) | 8 — GPIO32–39 | **6** | WROOM bonds only 6 of the 8 (GPIO37/38 not on the module); none are strapping; 34–39 input-only = fine for ADC. 6 uses every exposed ADC1 pin — zero spare. |
| ESP32-S3 | 10 — GPIO1–10 | **9** | Skip strapping GPIO3; flash/PSRAM (≈GPIO26–32) and native USB-JTAG (19/20) don't touch ADC1. Most headroom of the three. |
| ESP32-C5 | 6 — GPIO1–6 | **4** | GPIO2 & GPIO3 are JTAG **+ boot-strapping** — the same reason the C5 soil map is forced to `{1,4,5,6}`. Reaching 6 means sensors on strap pins (boot-mode risk), so the clean ceiling stays 4. |

**So 6-per-board holds for an all-S3 fleet; classic WROOM reaches exactly 6 (no spare ADC1 pin);
the C5 caps at 4 clean** — a mixed fleet's per-board ceiling is set by whichever C5s are in it.
Secondary constraint: 6 sensors implies 6 pumps → 6 more (digital) GPIOs for relays; on the 32-pin
C5 the total budget (6 sensors + 6 relays + I²C + power) gets tight fast, a second reason the C5
sits at 4.

**Not yet verified (honest — bench-pass trio, no urgency):**

1. That *our* classic module truly doesn't bond GPIO37/38 (standard WROOM-32, but confirm on the
   silkscreen — a bare-chip board that exposes them could reach 8).
2. Whether a capacitive sensor on the C5's GPIO2/3 actually disrupts boot. The datasheet says
   "strapping"; only a bench test says "tolerable or not." Rides the next bench day.
3. The S3's chosen ADC1 pins vs. the relay/I²C map (10 channels exist, but confirm the 6 picked
   don't collide with chosen relay/I²C pins).

Sources (retrieved 2026-07-12): [ESP32-C5 datasheet Table 2-7][c5ds] · [ESP32-S3 IDF ADC][s3adc] ·
[ESP32 IDF ADC][esp32adc], plus the respective datasheets.

[c5ds]: https://documentation.espressif.com/esp32-c5_datasheet_en.html
[s3adc]: https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/adc/index.html
[esp32adc]: https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc/index.html

## Serial per board (the real gotcha)

- **Classic — UART bridge** (CP2102): `Serial` @ 19200 exactly as today; the host logger
  opens the bridge COM port. No change.
- **C5 official (`c5-official-01`)** — CP210x on the `UART`-labeled port (classic-like,
  COM11 at intake) **plus** a native-USB port (COM12). Telemetry stays on the UART path;
  the native port is a bonus (flashing/JTAG) — no CDC flag needed.
- **C5 yellow (`c5-yellow-01`)** — CH340 on the one tested port (COM10), classic-like.
  Second physical port unconfirmed — record it before relying on it.
- **S3 (`s3-n8r2-01`) — RESOLVED at the bench (2026-07-03, #443):** the port **labeled `COM`**
  enumerates as **native USB serial/JTAG** (`303A:4001`, COM7) — NOT a UART bridge — and the
  board's **CH343 UART-bridge port is dead**, so the native USB port is the *only* working
  path. `[env:esp32s3]` therefore now carries `-D ARDUINO_USB_CDC_ON_BOOT=1` in
  `platformio.ini` (no longer speculative): the `esp32-s3-devkitc-1` board id defaults to
  `CDCOnBoot: Disabled`, and this flag routes Arduino `Serial` to the native port so telemetry
  comes out there — which is also the simpler untethered setup. The intake `flash_id` failure
  (`No serial data received` on COM7) was the native USB-JTAG needing manual-bootloader entry;
  driven that way, `esptool flash_id` succeeded and **confirmed the N8R2 marking** (8 MB flash,
  2 MB PSRAM). See the flash procedure below.

## Flashing a native-USB-JTAG board (the esptool-direct fallback)

When a board exposes only the native USB serial/JTAG port (like `s3-n8r2-01`, or a C5 driven on
its `USB` port), PlatformIO's auto-detect can miss it and `upload` / `flash_id` returns
`No serial data received`. The fallback is manual-bootloader entry + esptool aimed straight at
the native port:

1. **Enter the bootloader by hand** — hold **BOOT (GPIO0)**, tap **RESET**, release BOOT. The
   port re-enumerates in download mode.
2. **Point the tools at that exact port** — `esptool --port COMx flash_id` first to confirm
   flash size + PSRAM (this is how the S3's N8R2 marking was confirmed on 2026-07-03), then
   `pio run -e esp32s3 -t upload --upload-port COMx` to flash.
3. **Tap RESET** to run the new firmware. With `ARDUINO_USB_CDC_ON_BOOT=1` set (S3), `Serial`
   and the telemetry stream come back out that same native port — no second cable needed.

The classic ESP32 and the C5/S3 *UART-bridge* ports need none of this: PlatformIO auto-detects
them and `pio run -t upload` just works.

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
