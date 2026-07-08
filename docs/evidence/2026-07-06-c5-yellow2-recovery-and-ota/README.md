# ESP32-C5 "yellow #2" (`n3jhsp`) — bench recovery + OTA round-trip — 2026-07-06
<!-- cspell:words jhsp espota esptool PBKDF -->

Bench evidence for **`c5-yellow-02`** (device_id `n3jhsp`) — a spare yellow ESP32-C5 *clone* (KITC-A,
CH340 bridge) recovered from a non-flashing state, brought up on v0.7.1 firmware, and then used to
prove the **Phase-0 OTA path (#302)** end-to-end over WiFi. Maintainer on hands (USB latch + button
taps), Firmware on brains (probe → flash → validate). RFC1918 IPs are retained; espota prints no MAC
(no chip-serial connect), machine-checked by the identifier-guard (#573).

> **In-progress record (filed 2026-07-06).** Landed now because the recovery + OTA methods are
> *proven and self-contained*; the wider fleet reflash that will exercise them further is still
> pending the #739 log-watch (both deployed boards were at fw 0.7.0 / no v4 markers at last check).
> Expect updates as the reflash lands.

## What happened

1. **Recovery (USB, `esp32c5_recover`)** — `n3jhsp` would not enter/hold download mode via its normal
   auto-reset; the flash was recovered with a hand-latched download mode + a no-reset/no-stub esptool
   profile. It came up on the current firmware (v0.7.1, git `981d102`).
2. **OTA round-trip (WiFi, `esp32c5_ota`)** — a build was then pushed to the running board over espota,
   verified, and it rebooted into the new image — the first end-to-end proof of the Phase-0 OTA path
   on hardware. Full method + narrative on **#680**.

## 1. Recovery method — flaky-C5 download mode (`esp32c5_recover`)

The KITC-A yellow clones have a flaky CH340 auto-reset that won't hold download mode, and esptool's
own reset kicks a latched board back out. Winning recipe:

1. Plug the board's **native "USB"** port (VID 303A, USB-Serial/JTAG) into a **good (non-wedged)** host port.
2. **Latch download mode by hand:** hold BOOT → tap RESET → release. No sustained hold.
3. Flash: `pio run -d firmware -e esp32c5_recover -t upload --upload-port COMx`
   — `upload_flags = --no-stub --before no-reset` (esptool v5 wants **hyphens**: `no-reset`).
   `--before no-reset` keeps the latched bootloader; `--no-stub` uses the ROM loader, sidestepping the
   USB-Serial/JTAG "Failed to start stub flasher" bug.
4. Tap RESET by hand afterward to boot (the final RTS hard-reset often doesn't take).

**Root-cause note:** a *wedged host USB port* (a descriptor-fail latched it) failed identically for
every board + cable and initially made a healthy board look dead — try a **different port first**.

## 2. OTA round-trip — proven (`esp32c5_ota`)

`espota` pushed the build to the running board over WiFi, it verified + switched slots + rebooted
into the image (uptime reset), device_id preserved. Evidence: [`ota-round-trip.txt`](ota-round-trip.txt)
— `Authenticating … OK → Uploading 100% Done → Result: OK → Success` (`[SUCCESS] Took 46.6 s`).

**First attempt failed** with "No response from device" *after* a successful auth — the multi-homed
host advertised the wrong callback interface. Fixed by **pinning the host LAN IP** (`--host_ip`), which
is now documented as a gotcha in the env (left un-hardcoded so the env isn't tied to one machine).

## Envs + runner added (this PR)

- **`[env:esp32c5_recover]`** — the recovery flash profile above.
- **`[env:esp32c5_ota]`** — espota over WiFi, Phase-0 auth; multi-homed `--host_ip` gotcha documented.
- **`just ota` is now board-aware** — optional 2nd arg selects `<board>_ota` (default `esp32dev`):
  `just ota n3jhsp esp32c5`.

## Honest limits

- **0.7.0 has no OTA receiver** (it shipped *in* v4) → a board's **first** hop to v4 is always **wired**;
  OTA works from then on.
- The OTA password is the **Phase-0 placeholder** (`sprout-phase0`) — must be rotated/superseded before
  the repo goes public (#59); the real fence is Phase-1 (ADR-0026: signed + pull-only + verified-marker).

## Files in this packet

| File | Bytes | sha256 | What |
| --- | --- | --- | --- |
| `ota-round-trip.txt` | 1356 | `43d738983eabc403ee6f3a97d67ef79f84eb698d8708bdb1a3b4f8afdae0b426` | Curated espota transcript (success run; progress elided). MAC-clean; RFC1918 IPs retained. |

## Refs

- **#680** — recovery method + narrative
- **#302 / #824 / #825** — OTA Phase-0
- **#826** — WiFi command parity
- **#830** — this landing
- **#667** — C5 per-board anchors
- **#739** — fleet-reflash log-watch
- **ADR-0020 / ADR-0026** — OTA identity + security fence
