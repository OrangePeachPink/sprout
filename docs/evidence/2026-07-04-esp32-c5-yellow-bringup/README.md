# ESP32-C5 "yellow" #1 — first bring-up + #601 mint verify — 2026-07-04

Bench evidence for **`c5-yellow-01`** — the first Sprout firmware flash on the yellow ESP32-C5
*clone* (deferred at the 2026-07-03 capstone, now brought up as a Wave-1 launch-fleet member in
place of the S3, which lacks soldered header pins). Flash + serial over its **CH340** USB bridge
(`COM10`). MAC is redacted (ADR-0015 / ADR-0020, machine-checked by the identifier-guard #573).

Bench arrangement: maintainer connected the board (left USB port → `COM10`, one known-good cable,
power + data, no sensors) and stepped away; Firmware ran the probe → build → flash → serial verify
autonomously. No live capture, no logger, no plants at the bench.

## Board identity (settled — esptool + intake silkscreen photo)

| Field | Value | How |
| --- | --- | --- |
| Bench ID | `c5-yellow-01` | intake packet (2026-07-01) |
| Chip | ESP32-C5 (Wi-Fi 6 dual-band, BT5 LE, 802.15.4, single-core + LP, 240 MHz, 48 MHz XTAL) | `esptool flash-id` |
| Flash | **4 MB** | `esptool flash-id` |
| Board silkscreen | **`ESP32-C5-KITC-A V1.2`** — a KITC *clone*, **not** the official DevKitC-1 | intake photo `c5-yellow-bottom-left-rail.jpg` |
| USB bridge | **CH340** (`COM10`) — contrast the official's CP210x/native-USB | intake photo `c5-yellow-usb-bridge-ch340-com10.jpg` |
| MAC | redacted (#573) | — |

## Divergence from the official C5 (the interesting part)

The yellow is a different physical board from the official DevKitC-1, but the **same C5 silicon**:

- **Silkscreen layout differs** (KITC-A vs DevKitC-1) and it uses a **CH340** bridge, not a CP210x.
- **The `N/15` label is genuinely ambiguous** on the left rail (flagged at intake as
  `c5-yellow-ret-n15-ambiguity.jpg`) — reads as "N/15", i.e. it is unclear whether that pin is GPIO15
  or a no-connect. Resolve at continuity (B1) before trusting it.
- **But every GPIO the `esp32c5` firmware uses is present** — soil `{1,4,5,6}`, relay `{0,8,9,10}`
  all appear on the rails — so **the firmware is byte-identical to the official C5's**; only the
  *physical pin positions* differ (a continuity/wiring concern for install day, not a boot one).

Yellow bottom-rail silkscreen, as read from the intake photo (left edge / right edge):

```text
left : G TX0 RX0 24 23 N/15 27 4 5 NC 28 G 14 13 G NC
right: 3V3 RET 2 3 0 1 6 7 8 9 10 25 26 5V G NC
```

## Flash + clean boot (proven)

- Built `esp32c5` from the merged #601 firmware (fw 0.7.0); factory image **1,262,320 bytes**.
- `esptool` flashed it at `0x0` over the CH340, **hash verified, ~17 s** — reset instantly, no
  download-mode button dance.
- **Boot is clean — NO invalid-pin flood** (the `{1,4,5,6}` pins are valid C5 GPIOs; the yellow's
  own pin positions differ but the *numbers* exist):

```text
# boot plants controller fw=0.7.0 - schema v3, 4 soil sensors, supervisor-driven ...
# plants telemetry  schema_version=3  contract=docs/TELEMETRY_SCHEMA.md@v3
# device_id=yyvvpd  name=Sprout ESP32 (default)  chip=ESP32-C5  adc=ADC1,12bit,11dB,eFuseCal=off
# board: esp32-c5  wifi=yes  channels=4  adc=12bit  storage=nvs  tier0=monitor(untethered-ready)
# sensors: ch0=GPIO1/s3 ch1=GPIO4/s4 ch2=GPIO5/s1 ch3=GPIO6/s2  (model=UMLIFE_v2_TLC555)
# net: state=idle creds=unset
# portal: up ap=Sprout-Setup-2a35 (config-only, ADR-0020)
```

## #601 per-device mint — proven on hardware

The yellow minted **`device_id=yyvvpd`** on first boot — a valid Crockford base32 nonce, and
**different from the classic's `y9d41p`** (verified 2026-07-04). Two fresh boards, two unique
nonces: this is exactly the collision-fix #601 exists for, demonstrated across real silicon rather
than argued. `schema_version=3` and `name=` (default `Sprout ESP32`) are correct on a factory-fresh
NVS; the friendly name will be set at onboarding.

## Honest scope — what is NOT here

No sensors wired (soil rows would be floating noise). No WiFi onboarding yet (the captive portal is
up; creds `unset`). The `N/15` ambiguity and the yellow's full pin map are **NOT continuity-verified
(B1)** — the KITC-A layout differs from the official, so its header-pin → GPIO mapping wants a meter
pass before any probe carries signal. It is a Wave-1 launch candidate pending WiFi onboarding + a
registry entry (`device_id=yyvvpd`).

## Session provenance

Firmware autonomous bench session, 2026-07-04 (maintainer coordinating with Workflow off-bench).
Facts here are esptool-probed / serial-observed at capture time; the MAC is in the maintainer's local
archive only.

Refs: #443 · #436 · #601 · #275 · #278 · #584 · intake `2026-07-01-esp32-s3-c5-intake`.

— Firmware 🔧
