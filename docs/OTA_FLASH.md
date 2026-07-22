# OTA firmware flash — RETIRED (#1340)

> **This page documented the Phase-0 espota PUSH receiver, which no longer exists.**
> It is kept as a pointer rather than deleted, because `just ota` and this filename are
> in a year of commit messages, issues, and bench notes — a dead link is worse than a
> short page that says what happened.

## What was retired

The board no longer runs a WiFi update **listener**. Removed in full:

- the `ArduinoOTA` receiver (gone from the binary, not merely disabled)
- `OTA_PASSWORD` and the build-time provisioning that armed it
- the `*_ota` PlatformIO upload environments
- the `just ota` recipe

**Why:** a listening receiver guarded by a build-time shared secret was always an interim
(ADR-0026 named it as one). Signed **pull** removes both the listener and the secret rather
than hardening them — there is nothing to authenticate *to*, because nothing is listening.

## How to update a board now

| Situation | Path |
| --- | --- |
| Normal WiFi update | **signed pull** — the device fetches, verifies the signature, then switches slots (#302 S3) |
| New, dead, or off-WiFi board | **USB** — `just flash`. The maker door is always open (ADR-0026) |
| Web flasher | the Pages flasher, same signed artifact |

## One thing worth carrying forward

The retired `just ota` recipe did **not** trust espota's exit code. On a multi-homed host the
UDP ack can time out after a perfectly healthy flash, so it polled the board's own status page
for `git=` and reported what the **board** said (#1227).

That distinction outlives the mechanism: *what you sent* and *what is running* are different
claims. Whatever verifies a pull update should verify from the **device**, not from the transfer.

## History

The bench evidence from the push era stays where it is — `docs/evidence/2026-07-06-…` and
`2026-07-08-…` are records of what happened and are not rewritten (ADR-0006). The multi-homed
`--host_ip` finding (#1227) and the `PLATFORMIO_UPLOAD_FLAGS` newline-splitting trap (#1225)
are preserved there.
