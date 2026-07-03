# ESP32-S3 native-USB bring-up + untethered WiFi captures — 2026-07-03 (session 2)

Bench evidence for **`s3-n8r2-01`** covering the full untethered WiFi path on current
`main` (Block A of the #584 close-out plan). This is the **second** S3 session of the day;
it **supersedes the flash-path facts** in
[`../2026-07-03-esp32-s3-bringup-wifi/`](../2026-07-03-esp32-s3-bringup-wifi/README.md)
(session 1 used the CH343 bridge port, which has since failed — see Finding 1). Raw serial
logs and screenshots remain in the maintainer's local untracked archive per the evidence
policy; MAC / USB instance IDs are redacted here (ADR-0015 / ADR-0020, machine-checked by
the #573 identifier-guard). Private RFC1918 IPs are evidence-safe and kept.

Bench arrangement: maintainer = hands (cables, phone, power); Firmware lane = brains-on-call
(diagnosis, exact commands, serial/curl capture, verdicts). One power/data cable, native USB.

## Board identity (settled — esptool, this session)

| Field | Value | How |
| --- | --- | --- |
| Bench ID | `s3-n8r2-01` | intake packet (2026-07-01) |
| Chip | ESP32-S3 (QFN56) rev **v0.2** | `esptool flash-id` |
| Flash / PSRAM | **8 MB flash + 2 MB embedded PSRAM** — N8R2 confirmed at the silicon level | `esptool` feature line |
| Working USB path | **native USB-Serial/JTAG** (`303A:1001`), enumerates as `COM8` | Device Manager + esptool |
| MAC | redacted (#573) | — |

The 2 MB PSRAM confirms the module is physically an **N8R2**. The PlatformIO board def
(`esp32-s3-devkitc-1`) is the N8 variant (PSRAM unmapped); Sprout allocates no PSRAM, so it
is kept deliberately — revisit only if a feature needs PSRAM (recorded on #443).

## Finding 1 — the CH343 bridge port is hardware-dead → native-USB path adopted

The right USB-C port (the CH343 UART bridge, session 1's flash path) delivers **no power and
does not enumerate** on a known-good data cable that works on the native port. A full cold
power-drain did not revive it. Because the CH343 is an independent USB chip that would
enumerate on its own regardless of the ESP32's boot state, total silence indicates a
compromised connector/solder — not a firmware state, and not fixable by any BOOT/RST
sequence (those act on the ESP32 chip, not the bridge). Verdict: **connector-level hardware
failure.** Deeper recovery is deferred post-Wave-1; the maintainer has two spare S3s from the
same batch for dual-USB experiments later.

Consequence: this board's only working serial path is the **native USB-Serial/JTAG** port.
Firmware moved to it by adding `-D ARDUINO_USB_CDC_ON_BOOT=1` to `[env:esp32s3]` (the board
default is already `ARDUINO_USB_MODE=1` = HW CDC/JTAG), so Arduino `Serial` comes out the
native port. This is also the **simpler untethered path** — one fewer chip in the chain. The
`platformio.ini` change ships **with this packet**.

## Flash + boot (native USB, proven)

- Chip was found stuck in ROM **download mode** (invalid app from a prior failed session);
  `esptool flash-id` connected cleanly, confirming healthy silicon.
- Flashed the merged factory image at `0x0` over `COM8` — **1,111,920 bytes, hash verified,
  9.1 s**. (The PlatformIO upload wrapper hung on its reset dance; a direct `esptool
  write-flash` succeeded — recorded for the run sheet.)
- Boot banner (verbatim, current `main`):

```text
# boot plants controller fw=0.7.0 - schema v1, 4 soil sensors, supervisor-driven ...
# fw=0.7.0  git=6570f72+dirty  built=Jul  3 2026 13:35:00  run=4probe-coloc-origplant
# board: esp32-s3  wifi=yes  channels=4  adc=12bit  storage=nvs  tier0=monitor(untethered-ready)
# board cal: PLACEHOLDER (classic endpoints, not bench-verified for this board - #443)
# sensors: ch0=GPIO1/s3 ch1=GPIO2/s4 ch2=GPIO3/s1 ch3=GPIO4/s2  (model=UMLIFE_v2_TLC555)
```

(`git=…+dirty` = the uncommitted `platformio.ini` CDC flag, now committed with this packet.)

## WiFi onboarding via captive portal (proven — #275)

Fresh flash left NVS empty → banner showed `creds=unset` and the board raised its config AP
`Sprout-Setup-XXXX` (synthetic name per ADR-0020, not MAC-derived). From a phone:

1. Joined the open setup SSID; the captive page served the setup form.
2. Entered home-network credentials (never logged, never recorded — by design).
3. On save: `# portal: down (joined the network)`, the setup SSID disappeared, and the board
   associated with the home network.

Full no-PC onboarding path, end-to-end on real hardware.

## Device-owned time (proven — #278)

After association, telemetry rows carried `time_source=device_synced` with a real UTC
`device_timestamp_utc` (e.g. `2026-07-03T18:58:26.089Z`) — NTP-on-connect observed live.
Pre-connection rows honestly carried `device_uptime` with no fabricated stamp.

## IP-on-connect (#579) + RST auto-rejoin (#21) (proven)

On a reset with credentials stored, serial showed a clean auto-rejoin with **no portal**:

```text
0.4s  # net: state=idle creds=set
2.1s  # net: state=connected creds=set ip=192.168.68.62
```

Association in ~2.1 s, IP printed on the connect edge (the #579 quality-of-life line that
removes the router-page IP hunt). This is also the #21 reconnect-resilience check: reset →
rejoin without human action.

## Served endpoints over WiFi (proven — #276)

Both served from the device's own IP with no data cable attached.

`GET http://192.168.68.62/` — human status page:

```text
Sprout Sprout ESP32
fw=0.7.0 git=6570f72+dirty board=esp32-s3
wifi=connected ip=192.168.68.62
uptime_ms=19552
ch0: level=submerged raw=2 quality=SATURATED
...
```

`GET http://192.168.68.62/telemetry` — the same schema-shaped rows as the serial wire
(ADR-0018 §4, "one schema, every transport"):

```text
# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload
plants.soil,e09672,Sprout ESP32,0.7.0,60004,UMLIFE_v2_TLC555,s3,origplant,soil_moisture,5,,,SATURATED,level=submerged;role=diag;spread=169;gpio=1;device_seq=4;time_source=device_synced;device_timestamp_utc=2026-07-03T18:58:26.089Z*03
```

Note: `/telemetry` serves an emit-time cache (populated once per sweep), so it returns the
`# device_cols` preamble with no rows until the first post-boot sweep completes — expected,
and consistent with the "latest-reading-only while the host runs" honesty bound on #584.

## Finding 2 — flashing the merged factory image clears NVS

The `sprout-esp32-factory.bin` at `0x0` spans the NVS region, so a factory-image flash
**erases stored WiFi credentials + device name** (why re-onboarding was needed here). An
app-only `-t upload` (app at `0x10000`) preserves NVS. Relevant for install day: prefer
app-only reflash on already-onboarded boards.

## Honest scope — what is NOT in this packet (the wired round)

No sensors were wired. Soil telemetry this session is floating-input noise on the provisional
pin map (`SATURATED`/random raw) — expected, not data. Deferred to the wired round:

- **B1** — unpowered continuity of the S3 pin map (header pin → GPIO, meter).
- **B2** — one validated probe on a soil pin: dry-air vs wet-cup direction/range sanity
  (#276's independent real-value verification, and #170 endpoint data).

Those become `board_capability.h` verdicts (still `cal_verified=false` until then) in the
Block B3 gate PR.

## Sensor-batch note (Block C pre-check)

The maintainer opened the newly-received capacitive batch and confirms the units are
**visually identical to the validated first batch, with 8 additional available** — not yet
wired. The 3-flaw screen (`SENSOR_QA`) and dry/wet endpoint capture (#170) are the wired
round (#476 / Block C).

## Firmware change shipped with this packet

`firmware/platformio.ini` — `[env:esp32s3]` gains `-D ARDUINO_USB_CDC_ON_BOOT=1` (native-USB
serial path, Finding 1) and an N8R2 board-def note. Compile-verified (`pio run -e esp32s3`
SUCCESS) and flash+run+serve verified live above. The `board_capability.h` C5 entries + the
do-not-flash-C5 guard lift remain the Block B3 PR after C5 continuity.

## Session provenance

Maintainer bench session, 2026-07-03. Facts here are serial-observed / curl-captured at
capture time; raw logs kept in the maintainer's local archive.

Refs: #443 · #275 · #276 · #278 · #21 · #579 · #584.

— Firmware 🔧
