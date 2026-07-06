# OTA firmware flash (Phase-0, LAN-only)

Update a deployed Sprout board's firmware **over WiFi** — no USB, no moving the PC to the plant.
This is **Phase 0** (#302): a standard ArduinoOTA receiver, LAN-only, password-gated. It is **not**
the ADR-0026 security fence (signed images + verified-marker + pull-mode); that is Phase 1 (v0.8.0).

## One-liner

```sh
just ota <device_id>        # e.g.  just ota k7m2rt   -> targets sprout-k7m2rt.local
```

Find `<device_id>` on the board's card in the dashboard, the boot banner (`device_id=…`), or any
telemetry row. The board announces itself as `sprout-<device_id>.local` on the LAN (#676 mDNS).

## Password

The OTA upload is password-gated. The **Phase-0 placeholder** is `sprout-phase0`, set in two places
that must match:

- **Firmware:** `OTA_PASSWORD` in `firmware/include/config.h` (override at build with
  `-D OTA_PASSWORD='"…"'`).
- **Uploader:** `--auth=…` in the `esp32dev_ota` env (`firmware/platformio.ini`).

**Phase-1 migration:** when a real password is chosen, it moves to a **gitignored local config**
(the same family as WiFi creds), so no secret is committed. Tracked on #59 (go-public gate) — the
placeholder must be rotated or superseded before the repo goes public.

## Honest limits (when OTA does NOT apply — flash wired)

- **A dead / bricked board** has no running receiver — recover it wired (download mode).
- **A brand-new / unprovisioned board** has no OTA firmware and no WiFi creds yet — its **first**
  flash is always wired; OTA works from then on.
- **A board off WiFi** (no creds, out of range) is unreachable by OTA — reconnect it first.
- Rollback safety: a bad push that boots but crashes reverts to the previous image on its own
  (boot-validation rollback, #302) — but the *transfer* still needs a reachable, healthy receiver.

## What happens on an OTA update

1. `espota` pushes the new image to the board's **inactive** app slot (the running image is untouched).
2. The board verifies the transfer, switches the boot slot, and reboots.
3. On reboot, `allRelaysOff()` runs first (#93) — an OTA reset can never strand a relay.
4. The new image boots **pending-verify**; once WiFi is up and a telemetry sweep emits, it marks
   itself valid. If it crashes before that, the bootloader **reverts** to the previous image.

## Manual fallback (no `just`)

```sh
pio run -d firmware -e esp32dev_ota -t upload --upload-port sprout-<device_id>.local
```
