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

### Multi-homed host? Pin the callback IP (#1227)

If your PC has more than one network interface (LAN + VPN + WSL is the common trio), espota can finish the
upload while the board's UDP result-callback goes to the wrong interface: the flash **succeeds**, but espota
waits and then exits `No response from device after upload completion` — a **false FAILED**. Pass your LAN
IP as the third argument to pin the callback interface:

```sh
just ota <device_id> <board> <host_ip>   # e.g.  just ota n3jhsp esp32c5 192.168.1.42
```

> **Setting `--host_ip` by hand instead? Two traps bite together (#1225).**
> `PLATFORMIO_UPLOAD_FLAGS` **replaces** the ini's `upload_flags` — it does not merge, so you must repeat
> `--auth=…` yourself — and PlatformIO splits multi-value env vars on **newlines, not spaces**, so a
> space-joined value reaches espota as *one* argv token and the board ends up checking the literal password
> `sprout-phase0 --host_ip=…` — flag, space and all. **Fingerprint:** the invitation succeeds, then auth fails
> deterministically on *both* PBKDF2-HMAC-SHA256 and MD5 — which reads like a rejecting board when the
> board is healthy. Correct form, or just use the recipe above:
>
> ```sh
> PLATFORMIO_UPLOAD_FLAGS=$'--auth=sprout-phase0\n--host_ip=192.168.1.42'
> ```

**The recipe trusts the board, not espota's exit code.** After every upload it polls
`http://sprout-<device_id>.local/` for the running `git=` short-sha and reports reality: `VERIFIED on <sha>`
when the board is back on the expected commit (even if espota timed out), or a failure only if the board
never returns. An ack-timeout on a healthy flash therefore reads **VERIFIED**; a genuine half-flash still
reads **FAILED**.

## Password

The OTA upload is password-gated, and the password lives in two places that **must match**:

- **Firmware:** `OTA_PASSWORD` — compiled into the image (what the board will accept).
- **Uploader:** `--auth=…` — what espota presents.

The committed value, `sprout-phase0`, is a **published placeholder — an example, not a secret**. It is
in a public repo on purpose; it is LAN-scoped and interim, and it is *not* the security fence (that's
ADR-0026: signed images + verified-marker + key management).

### Running a real password (#1252)

**Do not edit `config.h` or `platformio.ini`** — that would commit the secret. Use the gitignored local
override, which sets **both sides from one file** so they cannot drift apart:

```sh
cd firmware
cp platformio_local.example.ini platformio_local.ini   # gitignored
# edit platformio_local.ini and replace CHANGE-ME-LOCALLY with your value
```

The file is **optional**: absent, PlatformIO skips it and the build falls back to the placeholder, so a
fresh clone needs zero setup. Present, it supplies the firmware's `-D OTA_PASSWORD` *and* the uploader's
`--auth` together. Never put a real value in this doc, the example file, or any tracked file.

> **Why one file for both:** if the two sides disagree, the flash fails `Authentication Failed` on
> **both** hash schemes while the espota invitation still succeeds — a signature that reads like a
> rejecting board when the board is healthy.

**Rotation is a flash, not an edit.** Changing the local value only affects the *next build*: every board
keeps accepting its **old** password until it is re-flashed with a new image. So rotate by flashing the
whole fleet — ideally in one coordinated bundle (see #1236 / #1152) — then verify each board answers.

**Rotating over OTA is chicken-and-egg.** The new password is *inside the image you are sending*, but the
running board still authenticates with its **old** one — so for the rotation flash only, the two sides must
briefly differ. Either flash over **USB** (no auth at all — simplest), or split the local file for one pass:

```ini
[env:esp32dev]
build_flags = -D OTA_PASSWORD='"NEW"'   ; what goes INTO the image
[env:esp32dev_ota]
upload_flags = --auth=OLD               ; what the RUNNING board still expects
```

Once every board is flashed, set `--auth` to `NEW` as well and the two are back in sync. Any board you miss
keeps the OLD password and will refuse the NEW `--auth` — with the both-hash-schemes-fail signature above.

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
