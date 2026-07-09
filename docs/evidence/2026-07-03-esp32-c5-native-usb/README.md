# ESP32-C5 first bring-up + untethered WiFi captures — 2026-07-03

Bench evidence for **`c5-official-01`** (Espressif ESP32-C5-DevKitC-1-N8R8) — the **first-ever
Sprout firmware flash on ESP32-C5 silicon** and its full untethered WiFi path (Block A5 of
close-out #584). Raw serial logs / screenshots stay in the maintainer's local untracked
archive; MAC / USB instance IDs are redacted here (ADR-0015 / ADR-0020, machine-checked by the
identifier-guard #573). Private RFC1918 IPs are evidence-safe and kept.

Bench arrangement: maintainer = hands (cables, phone, power); Firmware lane = brains-on-call.
Flash + telemetry both over the CP210x UART port (`COM11`) at 19200 — classic-like, no native-
USB puzzle (contrast the S3).

## Board identity (settled — esptool, this session)

| Field | Value | How |
| --- | --- | --- |
| Bench ID | `c5-official-01` | intake packet (2026-07-01) |
| Chip | ESP32-C5 **rev v1.2** (matches the DevKitC-1 V1.2 silkscreen) | `esptool flash-id` |
| Radio | **Wi-Fi 6 dual-band (2.4 + 5 GHz)**, BT 5 LE, IEEE 802.15.4 | esptool feature line |
| Core | Single RISC-V + LP core, 240 MHz, 48 MHz XTAL | esptool |
| Flash | **8 MB** (the N8R8) | `esptool flash-id` |
| USB path | CP210x UART bridge (`10C4:EA60`), `COM11` | Device Manager + esptool |
| MAC | redacted (#573) | — |

Note: the `esp32c5` board def conservatively assumes 4 MB flash — a harmless floor, since the
~1.26 MB app fits easily and the partition table simply doesn't use the upper 4 MB. An 8 MB
board def + PSRAM flag is a future nicety, not needed for bring-up.

## Finding — the classic placeholder pins are INVALID on C5 (fixed this session)

First flash used the pre-existing `board_capability.h` C5 entry, which inherited the **classic**
placeholder pins (`soil {36,39,34,35}`, `relay {25,26,27,32}`). The C5 only has **GPIO0–28**, so
those pins **do not exist** — the firmware flooded continuous
`Pin 36 is not ADC pin!` / `IO 32 is not set as GPIO` / `adc_io_to_channel: invalid gpio`
errors that starved the loop before WiFi could come up. (The S3 dodged this only because its
placeholder `{1,2,3,4}` happen to be valid S3 pins.) This **validates the whole per-board
`board_capability` design** — the abstraction exists precisely for this.

Fix (this session): the C5 entry now uses the **datasheet-derived candidate map** (#443):

| Role | GPIO | Rationale |
| --- | --- | --- |
| soil (ADC1) | **1, 4, 5, 6** | the ONLY four non-strapping ADC1 pins (ADC1 = GPIO1–6; strapping 2/3 removed) — forced, not chosen |
| relays | **0, 8, 9, 10** | the only four free non-strapping output pins (verify GPIO0 isn't the boot button at continuity) |
| I²C | 23 / 24 | **nominal — no env sensors planned on the C5**; the single SHT45/AS7263 lives on the classic |

These are **valid existent GPIOs** but **NOT continuity-verified (B1)** and **NOT calibrated** →
`cal_verified=false`. The do-not-flash-for-**sensors** caution stands until the wired round.

## Flash + clean boot (native, proven)

- `esptool` connected instantly over the CP210x (no reset hang — classic-like). `flash-id`
  confirmed the identity above.
- Flashed the merged factory image at `0x0`, `COM11`: **1,260,048 bytes, hash verified, ~65 s**
  (the CP210x bridge caps ~155 kbit/s vs the S3's native ~980 — slower, flawless).
- After the valid-pin reflash, boot is **clean** (no invalid-pin flood):

```text
# board: esp32-c5  wifi=yes  channels=4  adc=12bit  storage=nvs  tier0=monitor(untethered-ready)
# sensors: ch0=GPIO1/s3 ch1=GPIO4/s4 ch2=GPIO5/s1 ch3=GPIO6/s2  (model=UMLIFE_v2_TLC555)
# time: source=device_uptime (unsynced; NTP arms on WiFi connect, #278)
# net: state=idle creds=unset
# portal: up ap=Sprout-Setup-XXXX (config-only, ADR-0020)
```

(The C5 honestly reports `device_uptime` at cold boot — no retained RTC, unlike the warm-reset
S3 — so it does not claim a synced clock it doesn't have.)

## WiFi onboarding + device time + serve (proven — #275 / #278 / #579 / #21 / #276)

Captive-portal onboarding from a phone (`Sprout-Setup-XXXX` → home creds → save):

```text
# portal: down (joined the network)
# net: state=connected creds=set ip=192.168.x.85
```

After association, telemetry carried `time_source=device_synced` with real UTC
(`2026-07-03T19:55:34.503Z`) — NTP-on-connect on C5. Both served endpoints work over WiFi, no
cable:

`GET http://192.168.x.85/` → `board=esp32-c5  wifi=connected  ip=192.168.x.85` + per-channel
readings. `GET http://192.168.x.85/telemetry` → schema-shaped rows (ADR-0018 §4), e.g.:

```text
plants.soil,98ad36,Sprout ESP32,0.7.0,240001,UMLIFE_v2_TLC555,s3,origplant,soil_moisture,0,,,SATURATED,level=submerged;role=diag;spread=92;gpio=1;device_seq=28;time_source=device_synced;device_timestamp_utc=2026-07-03T19:55:34.503Z*6E
```

The C5 is dual-band, so it can join a 2.4 **or** 5 GHz home network; the setup AP itself is
2.4 GHz.

## Honest scope — what is NOT in this packet (the wired round)

No sensors wired — soil rows are floating noise on now-**valid** pins (`SATURATED`/near-zero).
Deferred to the wired round: **B1** unpowered continuity of the C5 map (header pin → GPIO,
meter — the KITC clones lie; even this official board's pins want confirming), and **B2** a real
probe dry/wet sanity read. Those finalize the `board_capability.h` C5 verdict (still
`cal_verified=false` until then) and the do-not-flash-for-sensors guard lift (Block B3).

## Firmware change shipped with this packet

`firmware/include/board_capability.h` — C5 entry to the valid candidate map (above); the S3 entry
also refined to drop strapping GPIO3 from its soil set (`{1,2,3,4}` → `{1,2,4,5}`, relays
`{5,6,7,15}` → `{6,7,15,16}`). `docs/hardware/BOARDS.md` updated to match. Both remain
`cal_verified=false` pending continuity. Compile-verified (`pio run -e esp32c5` / `-e esp32s3`
SUCCESS), native 22/22, and the C5 flash+run+serve verified live above.

## Session provenance

Maintainer bench session, 2026-07-03. Facts here are serial-observed / curl-captured at capture
time; raw logs kept in the maintainer's local archive.

Refs: #443 · #436 · #275 · #276 · #278 · #21 · #579 · #584.

— Firmware 🔧
