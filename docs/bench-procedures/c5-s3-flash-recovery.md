# ESP32-C5 + S3 flash / recovery troubleshooting guide

**When a board won't flash, or flashes but boot-loops.** This is the *recovery* companion to
[`s3-c5-bringup-run-sheet.md`](s3-c5-bringup-run-sheet.md) (the happy-path bring-up). Reach for
this sheet when the bring-up sheet's §2 flash step fails, or its §3 boot check shows a crash-loop.

Refs #1046 · #271 (web-flasher re-verification) · #680 (C5 recovery attempt) · #1034 (S3
boot-loop) · #443 (board bring-up)

> **⚠️ Live-sources-only doc (the whole point).** Both chips are newer than any agent's training
> data — the C5 especially. This guide was assembled entirely from **current** vendor docs and
> **active** issue threads, each cited inline with a retrieved-date. Nothing here is from agent
> memory. **All web sources retrieved 2026-07-12.** When you use this sheet weeks from now,
> re-open the linked threads — the C5 story is moving fast (see §6: the EWT fix landed the same
> day this guide was written). Facts drawn from *our own bench* rather than a vendor page are
> tagged **[bench]** and are provenance, not doctrine.

---

## §0 Orientation — the two chips at a glance

| | ESP32-S3 (our N8R2 DevKitC-style) | ESP32-C5 (our Amazon 3-pack) |
| --- | --- | --- |
| USB bridge | **native USB-Serial/JTAG** (the UART-bridge port died on our lab board — **[bench]** 2026-07-03, #443) | **CH340** UART bridge **[bench]** |
| Ports | two: native-USB + UART-bridge | two USB-C: one USB-Serial/JTAG, one UART |
| Flash defaults | `dio` / 8 MB / 80 m (after #1034 fix; board def *defaulted* `qio`) | `dio` / **2 MB** / **40 m** ([C5 flashing][c5-flash]) |
| Bootloader offset | `0x0` | **`0x2000`** ([C5 flashing][c5-flash]) |
| `--baud` change | works | **cannot be changed** (crystal-detect limit, shared with C2) ([C5 troubleshooting][c5-ts]) |

The offset and flash-default differences matter: a C5 image written with S3 assumptions (bootloader
at `0x0`, 80 m) will not boot.

---

## §1 The download-mode EXIT trap — read this first

This is the single most surprising C5 behavior and the leading suspect whenever a board "goes dead"
after a manual flash. **A board stuck in download mode looks dead but is fully recoverable.**

**Entry** (to flash a board whose auto-reset won't cooperate) — hold **BOOT** (`GPIO28`), tap/press
**EN** (`CHIP_PU`), release BOOT ([C5 boot-mode][c5-boot]). `GPIO27` must be high; the combination
`GPIO27=0 + GPIO28=0` is invalid and triggers undefined behavior ([C5 boot-mode][c5-boot]).

**The trap — verbatim from the vendor** ([C5 troubleshooting][c5-ts], retrieved 2026-07-12):

> If USB-Serial/JTAG is used for communication and the download mode is entered manually (typically
> by pressing the **EN** button while holding the **Boot** button on a DevKit), esptool cannot exit
> download mode using the default reset behavior. Specifically, the USB-Serial/JTAG peripheral can
> only trigger a **core reset**, which does not re-sample the state of the boot strapping pin. As a
> result, the state of the boot pin remains sampled as LOW, even if it is physically released, and
> the chip stays in download mode instead of entering SPI boot mode... To automatically leave the
> download mode, the `--after watchdog-reset` option must be used.

The same statement appears across the per-chip troubleshooting guides (ESP32, S3, C3, C6 …) — it is
a **USB-Serial/JTAG** property, not a C5-only bug ([ESP32 troubleshooting][esp32-ts]).

**Three ways out of a stuck download mode:**

1. `esptool ... --after watchdog-reset` — a full system reset that re-samples the straps. **Not**
   on by default (Espressif's note: enabling it automatically "could introduce issues").
2. **Press EN/RESET by hand** (a real reset button, not the tool's core reset).
3. **Power-cycle** — full unplug/replug.

> A board that flashes "successfully" then shows *no* app output — no banner, seemingly bricked —
> is very often just parked in download mode by exactly this trap. Try an exit before declaring it
> dead (see §5).

---

## §2 Per-chip flash paths (both ports)

### ESP32-S3

```bash
# Native-USB port (our lab board's only working path — [bench], UART bridge dead 2026-07-03):
pio run -d firmware -e esp32s3 -t upload --upload-port <COMx>
# The env carries -D ARDUINO_USB_CDC_ON_BOOT=1 so Serial comes out the native port.
```

S3 flash mode: **`dio`**. The `esp32-s3-devkitc-1` board def *defaults* `qio`, which our N8R2
module cannot read back at boot → the #1034 crash-loop. `board_build.flash_mode = dio` (PR #1055)
fixes it; verify byte 2 of the factory image header is `0x02` (DIO), not `0x00` (QIO). Root cause
is the esptool "boot fails after successful flash" case — *qio writes fine but the chip can't read
flash back to run* ([S3 troubleshooting][s3-ts]).

### ESP32-C5

```bash
# Normal (auto-reset works):
pio run -d firmware -e esp32c5 -t upload --upload-port <COMx>

# RECOVERY profile (auto-reset flaky — latch download mode by hand first, then):
pio run -d firmware -e esp32c5_recover -t upload --upload-port <COMx>
#   esp32c5_recover = --no-stub --before no-reset  ([bench] env, platformio.ini)

# Canonical esptool form (what pio drives underneath) — note C5 offsets/defaults:
esptool --chip esp32c5 -b 460800 --before default-reset --after hard-reset \
  write-flash --flash-mode dio --flash-size 2MB --flash-freq 40m \
  0x2000 bootloader.bin 0x8000 partition-table.bin 0x10000 app.bin   # ([C5 flashing][c5-flash])
```

**Port choice matters on the C5.** Community reports say EWT/web-flash works **only via the UART
port, not the USB-Serial/JTAG port** ([EWT #687][ewt687], @Alexxdal). For command-line esptool,
either port can work; the two-port setup lets you **flash on one and monitor on the other**
simultaneously.

**`--baud` caveat:** you cannot raise the baud with `--baud` on the C5 (or C2) — esptool must read
crystal-frequency registers to compute baud, which Secure Download Mode blocks ([C5
troubleshooting][c5-ts]). Don't chase "baud" errors; drop to `-b 9600` only for *noise*, not speed.

**SPI-pin wiring conflict (flash-comms failures):** GPIO 6 & 11 always access SPI flash; in `dio`
mode GPIO 7–8 must be disconnected (in `qio`, 7–10) ([C5 troubleshooting][c5-ts]). Our C5 relay map
uses GPIO 8/9/10 — **disconnect anything on those pins before flashing** or the flash write can
fail. Cross-ref [`docs/hardware/BOARDS.md`](../hardware/BOARDS.md).

---

## §3 Boot-loop triage tree — match the log signature

Capture the **full** boot log first (reset the board while the monitor is attached). Then match the
signature — each failure mode has a distinct fingerprint:

### A. Flash-mode mismatch (our #1034 S3 case)

```text
rst:0x7 (TG0WDT_SYS_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)
mode:QIO, clock div:1          ← QIO here on a module that can't read-back in QIO
load:0x...,len:0x...
ets_loader.c 78                ← dies in the 2nd-stage loader, before any app output
```

…repeating, alternating `TG0WDT_SYS_RST` / `RTCWDT_RTC_RST`.
**Fix:** flash mode → `dio` ([S3 troubleshooting][s3-ts]). Our fix: `board_build.flash_mode = dio`
(#1034 / PR #1055).

### B. Empty / partial flash — wrong offset or missing bootloader

```text
rst:0x7 (TG0_WDT_HPSYS),boot:0x18 (SPI_FAST_FLASH_BOOT)
invalid header: 0xffffffff     ← 0xffffffff = erased/unwritten flash at the boot offset
invalid header: 0xffffffff
assertion "result == ETS_OK" failed: file "ets_main.c"
```

(real C5 log, [EWT #687][ewt687], @EmileSpecialProducts). **Fix:** the image never landed, or the
bootloader is at the wrong offset. `erase-flash` then re-flash the **full** set with the C5
bootloader at **`0x2000`** (not `0x0`) ([C5 flashing][c5-flash]). This is the signature of a
web-flash that "completed" but only wrote part of the set.

### C. Stuck in download mode (the §1 trap)

No app banner at all after a "successful" flash, or the boot-mode line reads
`DOWNLOAD(USB/UART0)` instead of `SPI_FAST_FLASH_BOOT` ([C5 boot-mode][c5-boot]). **Fix:** exit per
§1 — `--after watchdog-reset`, EN press, or power cycle. **This is not a dead board.**

### D. Brownout / insufficient power

Random repeated resets, `Brownout detector was triggered`, or a flash that fails partway. The C5
needs ~70 mA continuous, 200–300 mA peak; **FTDI FT232R adapters and Arduino boards cannot power it
reliably** ([C5 troubleshooting][c5-ts]). **Fix:** a good cable (data-verified — **[bench]** the
Treedix TRX5-0816 checks pin-map; the FNIRSI FNB58 checks load), a powered hub, or a stronger USB
source. Retry the flash at a lower baud if it fails mid-write ([C5 troubleshooting][c5-ts]).

### E. Wrong silicon revision (C5 ECO1 vs ECO2)

The C5 shipped in two silicon revisions and the toolchain support differs. The **boot ROM string
names the revision**:

```text
ESP-ROM:esp32c5-eco2-20250121   ← "eco2" = ECO2 (rev v1.2)
```

arduino-esp32 support: **ECO1** works *only* with the 3.3.0-alpha1 board package; **ECO2** was "not
officially supported yet" as of that thread, though users report ECO2 flashing successfully on
current toolchains ([arduino-esp32 #11386][ard11386], @me-no-dev / @OyczE). **Triage step:** read
the ROM string on the first boot line; if flashing fails on a devkit, confirm your board-package /
platform version actually supports that revision. Our fleet flashes on the pinned pioarduino
platform (#529) — **[bench]** record each board's ROM string in the §5 table if you hit trouble.

---

## §4 The CH340 / clone-board specifics (our C5 3-pack, "KITC-A")

Our C5s are generic Amazon 3-pack boards with a **CH340** UART bridge (**[bench]**, platformio.ini),
*not* the CP2102 (`VID 0x10c4 / PID 0xea60`) seen on the official DevKitC in
[esptool-js #217][ejs217]. Consequences:

- **Flaky auto-reset.** CH340 clones frequently fail to hold download mode via DTR/RTS. When
  `pio upload` reports "Wrong boot mode detected" or "Failed to connect," the autoreset circuit
  didn't latch — enter download mode by hand (§1) and use the **`esp32c5_recover`** env
  (`--no-stub --before no-reset`), which skips the stub loader (sidesteps the USB-Serial/JTAG "start
  stub flasher" failure) and doesn't reset the latched chip ([bench] env; corroborated by the
  "manually enter download mode" fix in [IDF C5 flashing][idf-c5]).
- **Cable first.** "Invalid head of packet" / "No serial data received" is usually a charge-only
  cable or noise, not a dead board — swap to a data-verified cable and retry, drop to `-b 9600` for
  noise ([C5 troubleshooting][c5-ts]).
- **Driver.** CH340 needs its vendor driver on Windows; confirm the COM port enumerates in Device
  Manager / `pio device list` before blaming the board.

---

## §5 c5yellow#1 recovery attempt procedure

**Context [bench]:** "c5yellow#1" is the yellow C5 that appeared dead after a reflash attempt. Given
§1, the leading hypothesis is **stuck in download mode, not bricked** — the manual-download-mode
exit trap fits the symptom exactly. Work this ladder in order; stop at the first that yields a clean
boot banner:

1. **Power-cycle** — full unplug, wait 5 s, replug. If it now prints a normal banner, it was parked
   in download mode (§1-C). Done.
2. **Watchdog-reset exit** — `esptool --chip esp32c5 --port <COMx> --after watchdog-reset chip-id`
   (a read-only command; the point is the `--after` exit). Re-open the monitor and reset.
3. **Read the ROM string** — note `esp32c5-ecoN-…` for the §3-E revision check.
4. **erase-flash, then full re-flash** — `esptool --chip esp32c5 --port <COMx> erase-flash`, then
   the `esp32c5_recover` env (§2). Bootloader must land at **`0x2000`** (§3-B).
5. **Swap the port** — try the *other* USB-C port (UART vs USB-Serial/JTAG); per [EWT #687][ewt687]
   the UART port is the more reliable C5 path.
6. **Swap the cable** — data-verified only (§4). **[bench]** confirm on the Treedix/FNIRSI bench.
7. **Only after 1–6 fail** on both ports + a known-good cable + a known-good power source is a
   "dead" verdict defensible. Record the ROM string, the exact failing command, and the full log on
   #680 before retiring the board.

---

## §6 ESP Web Tools (EWT) C5 re-add checklist

`esp32c5` is **not** in `WEB_FLASH_VERIFIED` today (ADR-0026 D6) — web-flash of the C5 has been
failing upstream. The picture is **actively changing**:

- [EWT #687][ewt687] (OPEN): "Is ESP32-C5 really supported?" — flashing fails via EWT; works via
  pio; multiple reporters say **UART port only**.
- [esptool-js #217][ejs217] (OPEN): C5 flash-**size** auto-detect fails in the browser (`Flash ID:
  0` → defaults to 4 MB) while native esptool detects it — so even a connecting C5 may write with
  the wrong size.
- **[EWT #706][ewt706] — MERGED 2026-07-12** (the day this guide was written): updates the bundled
  **esptool-js to 0.6.0**, which reportedly fixes the C5 path. **This is the re-add trigger.**

**Checklist before adding `esp32c5` to `WEB_FLASH_VERIFIED`:**

1. Confirm our flasher bundles **esptool-js ≥ 0.6.0** (i.e. an EWT release that includes #706).
   Record the exact EWT/esptool-js version our Pages flasher ships.
2. Re-test a full C5 web-flash **on the UART port first** ([EWT #687][ewt687]) — erase → write →
   "Installation complete!".
3. Watch flash-size detection ([esptool-js #217][ejs217]); if it misdetects, pin `--flash-size`
   explicitly in the manifest/build and re-test.
4. **Confirm the board boots** (banner + health line), not just "flash complete" — the #1034 lesson:
   flashes-but-bootloops is worse UX than not offered.
5. Only then open a PR adding `esp32c5` to `WEB_FLASH_VERIFIED`, citing this run's evidence (mirrors
   the S3 gate in #1034 / PR #1055).

---

## Sources (all retrieved 2026-07-12)

| # | Source | State | Used for |
| --- | --- | --- | --- |
| 1 | [esptool ESP32-C5 troubleshooting][c5-ts] | latest | exit trap, DIO fix, `--baud` limit, power, SPI-pin conflicts, error messages |
| 2 | [esptool ESP32-C5 boot-mode selection][c5-boot] | latest | download-mode entry, GPIO27/28, boot-mode values |
| 3 | [esptool ESP32-C5 flashing firmware][c5-flash] | latest | canonical command, C5 defaults (dio/2 MB/40 m), bootloader @ 0x2000 |
| 4 | [ESP-IDF ESP32-C5 flashing troubleshooting][idf-c5] | stable | failed-to-connect, DTR/RTS, manual download mode |
| 5 | [esptool ESP32-S3 troubleshooting][s3-ts] | latest | qio-can't-read-back → dio (the #1034 root cause) |
| 6 | [esptool ESP32 troubleshooting (cross-chip)][esp32-ts] | latest | watchdog-reset exit is a USB-Serial/JTAG property, not C5-only |
| 7 | [esp-web-tools #687][ewt687] | OPEN | C5 EWT fails; UART-only; empty-flash boot-loop log |
| 8 | [esp-web-tools #706][ewt706] | **MERGED 2026-07-12** | esptool-js → 0.6.0; the EWT re-add trigger |
| 9 | [esptool-js #217][ejs217] | OPEN | C5 flash-size misdetect in the browser |
| 10 | [arduino-esp32 #11386][ard11386] | CLOSED | C5 ECO1 vs ECO2 gating; ROM string reveals revision |

**[bench]** items (our fleet, not vendor docs): CH340 bridge on the C5 3-pack; S3 native-USB-only
(UART bridge died 2026-07-03, #443); `esp32c5_recover` env; Treedix/FNIRSI cable bench; c5yellow#1
symptom history (#680).

[c5-ts]: https://docs.espressif.com/projects/esptool/en/latest/esp32c5/troubleshooting.html
[c5-boot]: https://docs.espressif.com/projects/esptool/en/latest/esp32c5/advanced-topics/boot-mode-selection.html
[c5-flash]: https://docs.espressif.com/projects/esptool/en/latest/esp32c5/esptool/flashing-firmware.html
[idf-c5]: https://docs.espressif.com/projects/esp-idf/en/stable/esp32c5/get-started/flashing-troubleshooting.html
[s3-ts]: https://docs.espressif.com/projects/esptool/en/latest/esp32s3/troubleshooting.html
[esp32-ts]: https://docs.espressif.com/projects/esptool/en/latest/esp32/troubleshooting.html
[ewt687]: https://github.com/esphome/esp-web-tools/issues/687
[ewt706]: https://github.com/esphome/esp-web-tools/pull/706
[ejs217]: https://github.com/espressif/esptool-js/issues/217
[ard11386]: https://github.com/espressif/arduino-esp32/issues/11386

— Firmware 🔧
