# ESP32-S3 bring-up + first untethered WiFi session — 2026-07-03

Bench evidence for **`s3-n8r2-01`** (issue #443's S3 portion) and the first live WiFi
onboarding of a non-classic Sprout board (#275 / #278; #276 / #21 partial). Curated from
the maintainer's bench session; raw captures (full serial logs, screenshots, photos)
remain in the maintainer's local archive per the evidence policy — MAC addresses, USB
instance IDs, and network details are redacted here by design (ADR-0015 / ADR-0020).

## Board identity (settled)

| Field | Value | Evidence path |
|---|---|---|
| Bench ID | `s3-n8r2-01` | intake packet (2026-07-01) |
| Chip | ESP32-S3 (QFN56) rev **v0.2** | `esptool flash_id`, both ports |
| Flash / PSRAM | **8 MB flash + 2 MB embedded PSRAM** — N8R2 confirmed | `flash_id` |
| Left USB-C | native USB serial/JTAG — `303A:4001` normal (COM7-class), `303A:1001` in bootloader (re-enumerates) | Device Manager + port census |
| Right USB-C | **CH343 UART bridge** — `1A86:55D3` (wch.cn) | Device Manager |
| Preferred flash path | the CH343 bridge port (no bootloader dance) | this session |

The port **labeled** `COM` on the silkscreen is the *native* controller, not the bridge —
the label is misleading; trust the VID:PID. A failed probe on the native port in normal
mode (`No serial data received`) is expected; manual bootloader entry re-enumerates it.

## Flash + boot (proven)

- `pio run -e esp32s3 -t upload` via the CH343 bridge: **success** (~57 s), firmware `fw=0.7.0`
  from main @ `6b6159c`-era.
- Boot banner (verbatim):

```text
# board: esp32-s3 wifi=yes channels=4 adc=12bit storage=nvs tier0=monitor(untethered-ready)
# net: state=idle creds=unset
```

- The honest-placeholder calibration line printed as designed (`cal_verified=false` — this
  board's ADC is not yet bench-calibrated; see `board_capability.h`).

## WiFi onboarding via captive portal (proven — #275)

With no stored credentials, the setup AP rose as **`Sprout-Setup-8ccd`** (synthetic
identity per ADR-0020 — not MAC-derived). From a phone:

1. Joined the setup SSID; the portal page served.
2. Entered home network credentials (never logged, never recorded — by design).
3. Portal reported success; serial showed `# portal: down (joined the network)`;
   the setup SSID disappeared.
4. Serial then showed `# net: state=connected creds=set`.

This exercised the full no-PC onboarding path end-to-end on real hardware.

## Device-owned time (proven — #278)

After association, telemetry rows carried **`time_source=device_synced`** with a real UTC
`device_timestamp_utc` — NTP-on-connect observed live. Before connection the same rows
honestly carried `device_uptime` with no fabricated stamp.

## Honest scope notes

- **No sensors were wired.** Soil telemetry during this session is floating-input noise on
  the provisional pin map — expected bench noise, not signal, and not usable as data.
- **Still pending** (the board remains deployed on the network): the device LAN IP +
  browser/curl hits of `GET /` and `GET /telemetry` (#276), the dashboard reading the
  device over WiFi (#277/#486 live proof), and a reconnect-resilience check (#21).
- C5 bring-up (both variants) is the next bench session; their identity/probe evidence
  lands as its own packet.

## Session provenance

Maintainer bench session, 2026-07-02 evening → 2026-07-03. Curated and packaged by
Workflow from the local evidence packet; facts stated here are serial-observed and
recorded in the session log at capture time.
