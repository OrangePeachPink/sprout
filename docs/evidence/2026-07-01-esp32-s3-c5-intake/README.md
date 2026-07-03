# ESP32-S3/C5 Intake Evidence Packet - 2026-07-01

<!-- cspell:words CP210x DevKitC ESPC esptool KITC N8R2 N8R8 USERPROFILE wch WROOM -->

This packet is the curated bench evidence for #443: board identity, visible
silkscreen, USB-path identity, and the current resume point for bring-up.

Provenance: curated 28 of 66 source media (63 phone photos plus 3 Device
Manager screenshots), scaled, EXIF stripped, originals local at the maintainer
shared-root untracked archive
`docs/evidence/2026-07-01-esp32-s3-c5-intake/`.

## Board Identities

| Bench ID | Visible identity | Board / module evidence | USB evidence so far | Status |
|---|---|---|---|---|
| `c5-official-01` | Official Espressif ESP32-C5-DevKitC-1-N8R8 | Box label says `ESP32-C5-DevKitC-1-N8R8`; board silkscreen says `ESP32-C5-DevKitC-1 V1.2`; module can says `ESP32-C5-WROOM-1`, `MDN8R8`. | `UART` port enumerated as Silicon Labs CP210x USB to UART Bridge (COM11); `USB` port enumerated as USB Serial Device (COM12). | Identity resolved; `flash_id` pending. |
| `c5-yellow-01` | Yellow-header ESP32-C5-KITC-A clone/variant | Bottom silkscreen says `ESP32-C5-KITC-A V1.2`; module can says `MODEL: ESPC5-32`, `H4`. | One tested USB path enumerated as USB-SERIAL CH340 (COM10), manufacturer `wch.cn`; physical port and second-port identity still need confirmation. | Identity resolved enough for bench tracking; USB split partially pending. |
| `s3-n8r2-01` | ESP32-S3-N8R2 dual-USB dev board | Module can says `ESP32-S3-N8R2`; board bottom says `ESP32-S3`; ports labelled `COM` and `USB`. | `COM` path observed as USB VID:PID `303A:4001`, USB Serial Device (COM7), consistent with Espressif native USB serial/JTAG. | Identity resolved; `flash_id` blocked until manual bootloader entry succeeds. |

## Evidence Map For #443

| Checklist item | Evidence status | Notes |
|---|---|---|
| Module marking photos | Done | Curated module-marking macros for all three bench boards. |
| Silkscreen to GPIO inventory | Done from photos | Pin-label rows are covered by top/bottom overview and close-up shots. Electrical continuity is still pending. |
| USB bridge / serial path decision | Partial | C5 official has CP210x on `UART` and native Microsoft USB serial on `USB`; yellow C5 has CH340 on one tested path; S3 COM path appears native Espressif USB serial/JTAG. |
| `esptool.py flash_id` | Pending / blocked | S3 clean probe on COM7 failed with `No serial data received`; next step is manual bootloader entry and retry. C5 `flash_id` probes remain pending. |
| Pin selection | Pending | Do after continuity and flash/boot identity checks. |
| Serial-path decision | Partial | Enough evidence to distinguish likely native-vs-bridge paths; final choice should wait for successful bootloader/flash probes per board. |
| WiFi | Out of scope for this packet | No WiFi bring-up is claimed. Existing firmware command path is `!wifi,<ssid>,<password>` over serial after firmware is running; do not commit credentials. |

## Bring-Up Resume Point

1. For `s3-n8r2-01`, plug the `COM` port and confirm COM7 or the current enumerated port.
2. Enter bootloader manually: hold `BOOT`, tap/release `RST`, keep holding `BOOT` for about 1 second, then release `BOOT`.
3. Re-run the clean flash-ID probe:

   ```powershell
   %USERPROFILE%\.platformio\penv\Scripts\python.exe -m esptool --chip esp32s3 --port COM7 flash-id
   ```

4. For `c5-official-01`, test both labelled ports separately: `UART` should
   map to CP210x; `USB` should map to native USB serial. Then run the C5
   flash-ID probe on the chosen port.
5. For `c5-yellow-01`, record which physical port produced CH340 COM10, test the other port, then run the C5 flash-ID probe.
6. After flash-ID is captured, continue #443 with continuity checks and pin selection.

## Package Verification

Generated files are listed in `manifest.csv`. The packaging check verified:

- all curated files exist and match the manifest SHA-256 values;
- no committed image has EXIF metadata;
- every committed image is below 1 MB;
- total committed image payload is below 15 MB.

— Sage
