# ESP32-S3 (`zdy5ze`) — onboarding + OTA round-trip over WiFi — 2026-07-08
<!-- cspell:words zdy espota esptool PBKDF -->

Bench evidence for the lab **ESP32-S3 devkit** (`esp32-s3-devkitc-1`, no soldered headers → no probes):
a clean USB flash → healthy boot → WiFi rejoin on saved creds → then a full **Phase-0 OTA round-trip
(#302)** pushed **while the board was on a power brick — no USB at all.** Second board type proven for OTA
after the C5. RFC1918 IPs retained; espota prints no MAC (identifier-guard #573).

## What happened

1. **USB flash (`esp32s3`, COM8, native USB).** Genuine devkit — normal auto-reset, no button dance, unlike
   the flaky C5 clones. `Wrote 1108528 bytes … Hash of data verified … Hard resetting via RTS pin` (the RTS
   reset actually took). It booted v0.7.1 (git `159718c` — the PR #838 merge).
2. **Joined WiFi on saved creds — no captive portal.** Its NVS WiFi creds (from the 2026-07-03 bring-up)
   survived the reflash, so it associated directly and served at `192.168.68.67`:

   ```text
   Sprout s3-1
   device_id=zdy5ze fw=0.7.0 git=159718c board=esp32-s3
   wifi=connected ip=192.168.68.67
   ch0: level=submerged raw=4 quality=SENSOR_FAULT
   ```

   The bare channel honestly reads **SENSOR_FAULT** (no probe) — firmware behaving correctly.
3. **OTA round-trip (`esp32s3_ota`, espota over WiFi, board on the brick).** See
   [`ota-round-trip.txt`](ota-round-trip.txt): `Authenticating … OK → Uploading 100% Done → Result: OK →
   Success` (`[SUCCESS] Took 62 s`). The board rebooted into the OTA'd image (**uptime 289 s → 20 s**),
   reconnected WiFi, and served again — device_id preserved. No USB was connected for the update.

## The env added (this PR)

- **`[env:esp32s3_ota]`** — espota over WiFi for the S3, Phase-0 auth. Mirrors `esp32c5_ota`; the multi-homed
  `--host_ip` gotcha is documented (left un-hardcoded so the env isn't machine-tied). `just ota zdy5ze esp32s3`
  now resolves (the board-aware runner from #838).

## Honest notes

- **`fw` reads `0.7.0`, not `0.7.1`** — the firmware version string (`PLANTS_FW_VERSION`) was never bumped
  during the v0.7.1 slice. Evidence + the policy question (bump-in-slice vs bump-at-release-cut) are on **#831**;
  deliberately NOT patched here. `git=159718c` is the accurate provenance.
- The OTA re-pushed the **same** v0.7.1 image, so the version is unchanged by this round-trip — it proves the
  *transport*, not a version change.

## Files in this packet

| File | Bytes | sha256 | What |
| --- | --- | --- | --- |
| `ota-round-trip.txt` | 927 | `a65b2120e3d6193260a2ec51c0cf8289517bedcdca1296785ebebacfb11b42f7` | Curated espota transcript (success run; progress + compile elided). MAC-clean; RFC1918 IPs retained. |

## Refs

- **#443** — ESP32-S3 + C5 bench bring-up (this is the S3's onboard + OTA)
- **#302 / #824 / #825** — OTA Phase-0
- **#838** — the C5 landing + board-aware `just ota` this rides on
- **#831** — the `fw=0.7.0` version-identity item
- **ADR-0020 / ADR-0026** — OTA identity + security fence
