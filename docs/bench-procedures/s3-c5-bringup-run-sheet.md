# S3 / C5 bring-up run sheet

**One execution-ordered sheet for the maintainer's bench slot** — assembled from
[`docs/hardware/BOARDS.md`](../hardware/BOARDS.md)'s per-board checklist,
[`docs/BRINGUP.md`](../BRINGUP.md)'s Phase A pattern, and the "reads-0" debug path from tonight's
live troubleshooting. Follow it live, in order, per board. No doc-hopping needed mid-session.

Refs #443 · #436 (parent) · #191/#93 (classic re-qualification, conditional §5)

## Scope

Two physical boards this session: **ESP32-S3** (Amazon "DevKitC N8R2"-style) and **ESP32-C5**
(Amazon 3-pack, CH340 bridge). **No WiFi steps** — #21's scaffold doesn't exist yet; WiFi
bench-verify is a later session once it lands. This sheet covers: identify the board, flash it,
verify soil-sensor + boot behavior, record evidence.

Run §1–§4 once per physical board. Run §5 only if #283's toolchain decision has landed since the
last classic bring-up.

## §1 Pre-flight (per board, before flashing)

The boards are generic clones — trust the silkscreen + meter, not the listing.

- [ ] **Photograph** front + back (module marking legible, e.g. `ESP32-S3-WROOM-1 N8R2`).
- [ ] **Identify the USB bridge** — CH340 vs CP2102 vs native-USB — and note which COM port(s)
      enumerate when plugged in (Device Manager or `pio device list`).
- [ ] **Confirm flash size + PSRAM:** `esptool.py --port <COMx> flash_id` → record the reported
      flash size (and PSRAM if the tool reports it) against the listing (N8R2 vs N8R8; C5 = 4 MB).
- [ ] **Inventory every exposed GPIO from the silkscreen**, marking: ADC-capable, strapping/boot
      pin, input-only, flash/PSRAM-reserved, USB (D+/D−). Use the candidate maps in
      [BOARDS.md](../hardware/BOARDS.md#chip-constraints--candidate-maps) as the starting point,
      not gospel.
- [ ] **Choose 4 ADC1 pins (soil), 4 output pins (relays, no strapping pins), 2 I²C pins** —
      record the exact chosen GPIOs here, in this sheet's §4 evidence table, not just in memory.
- [ ] **Continuity-check** each chosen header pin → the intended GPIO. Clone header silkscreen
      labels can lie; a multimeter continuity beep is the only trustworthy source.
- [ ] **Decide the serial path** — UART bridge or native USB-CDC (see §2's per-board note) — and
      the `ARDUINO_USB_CDC_ON_BOOT` value that follows from it.
- [ ] **Do NOT wire relays/pump this session.** Bench-verify relay polarity separately, later,
      per the classic board's existing convention — this sheet is soil-sensor + boot bring-up only.

## §2 Flash

| Board | Env | Command | Serial path |
| --- | --- | --- | --- |
| ESP32-S3 | `esp32s3` | `pio run -d firmware -e esp32s3 -t upload --upload-port <COMx>` | Same pinned platform as classic — no new toolchain. **Check which port enumerates first**: the DevKitC exposes *both* a UART-bridge port and a native-USB port. If only the native-USB port shows telemetry, add `-D ARDUINO_USB_CDC_ON_BOOT=1` to the `[env:esp32s3]` build flags and reflash — this is a real gotcha, not cosmetic (see BOARDS.md "Serial per board"). |
| ESP32-C5 | `esp32c5` | `pio run -d firmware -e esp32c5 -t upload --upload-port <COMx>` | CH340 UART bridge — behaves like the classic's `Serial` @ 19200, no CDC decision needed. |

Both envs currently build the **classic pin map** (soil `36/39/34/35`, relays `25/26/27/32`,
I²C `21/22`) — these are **placeholder pins that don't physically exist correctly on S3/C5**
(BOARDS.md §"Integration plan" step 1 — the board-conditional `config.h` extraction hasn't landed
yet). **Do not expect soil readings to be meaningful until that lands.** This session's flash is
for board-identity + boot-behavior verification, not sensor accuracy — see §3's "reads-0" note.

## §3 Verify

- [ ] **Boot banner** — capture the full banner: `fw=`, `git=`, build time, `board:` line
      (chip/wifi/channels/adc/storage/tier0), `session_id=`.
- [ ] **Health line** — `# health: ch0=... ch1=... ch2=... ch3=...` — record verbatim, all four.
- [ ] **Per-channel sanity read** — capture 3–4 telemetry rows per channel. Two outcomes, both are
      valid data (this is a wiring/pin-map bring-up, not a calibration pass):
  - Channel reads *something* nonzero and stable → the placeholder pin happens to land on a
    usable ADC1 pin on this chip. Note it; still not calibrated.
  - **Channel reads 0 or pinned** → walk the debug ladder before calling it a fault: (1) is this
    GPIO actually ADC-capable on this chip (ADC2 is unusable with WiFi on every chip — see
    BOARDS.md chip constraints)? (2) is it input-only-only on classic but not on S3 (no true
    input-only pins on S3 — different failure mode)? (3) continuity-check the physical wire
    against §1's inventory — clone silkscreen mislabels are common. A 0-read from a placeholder
    pin on the wrong physical GPIO is **expected**, not a firmware bug.
- [ ] **Reset behavior** — power-cycle or reset button; confirm the banner reprints cleanly
      (auto-reset works, or note if BOOT/RST hold was needed — chip-specific, record it).

## §4 Record

Fill in one row per board, right here in this file (append as a new row before committing, or as a
PR/issue comment if this sheet is reused across sessions):

| Field | ESP32-S3 | ESP32-C5 |
| --- | --- | --- |
| Module marking (photo ref) | | |
| USB bridge + enumerated COM port(s) | | |
| `esptool.py flash_id` output (size, PSRAM) | | |
| Chosen soil pins (4× ADC1) | | |
| Chosen relay pins (4×, no strapping) | | |
| Chosen I²C pins (SDA/SCL) | | |
| Serial path used (UART bridge / native USB-CDC) | | |
| Flash: pass/fail | | |
| Boot banner: pass/fail | | |
| Health line: pass/fail | | |
| Per-channel sanity: pass/fail (note which channels read 0 and why) | | |
| Reset behavior: pass/fail (BOOT/RST hold needed?) | | |

If this run should be durable beyond the sheet itself (e.g. photos), land them under
`docs/evidence/` following the existing board_photos/ pattern, and link them here.

## §5 Classic re-qualification (conditional — only if #283's toolchain decision has landed)

If DX has repointed the shared toolchain pin (#283 — a whole-matrix bump, not the isolated-per-board
approach) since the classic board was last bench-verified, the classic board's safety-critical path
needs a fresh pass before trusting it again. This is **not** a routine step — skip this section
entirely if #283 hasn't landed yet.

- [ ] **Wedge re-test** — flash `esp32dev_wdttest` on the classic board, send `!wedge*74`, confirm
      the watchdog still fires within `WDT_TIMEOUT_MS` (8000ms) and the reboot's `allRelaysOff()`
      still runs first in `setup()`. Same procedure as
      [`docs/hardware/watchdog-wedge-bench-verify.md`](../hardware/watchdog-wedge-bench-verify.md)
      — compare the new reset timing against that prior baseline (8.1s) for drift.
- [ ] **ADC A/B** — reflash `esp32dev` (shipping build) on the classic board and capture raw ADC
      dry/wet endpoint readings for one known-good probe (dry air ~3050, submerged wet ~1050 per
      the current `SENSOR_CAL_BOUNDARY` in `config.h`). Compare A (pre-bump baseline) vs B
      (post-bump reading) — the new toolchain's ADC driver/calibration path must not silently
      shift the raw endpoints, or every existing calibration boundary is stale.
- [ ] Record both results in §4-style table, filed as a comment on #283 or #191, referencing this
      sheet.

— Firmware 🔧
