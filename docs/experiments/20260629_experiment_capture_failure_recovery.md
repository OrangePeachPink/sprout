# 2026-06-29 Experiment Capture failure recovery

**Date:** 2026-06-29 local CDT

**Lane:** Sage

**Status:** Recovery note for #394 retest evidence, not a fix.

**Related:** #322, #335, #394, PR #378, ADR-0011, ADR-0012, ADR-0017

## Summary

Experiment Capture was attempted during the P02 bench run, but the isolated
capture path failed before any CSV or manifest was written. The bench session
continued using Monitor logging, with manual event notes, so the plant data was
not lost.

The recovered evidence points to a host/firmware cadence-command mismatch:
the host Experiment Capture path sends the session-only command
`!cad,<ms>,temp`, while the firmware flashed during the bench session rejected
that form and only accepted the older persistent `!cad,<ms>` form. Firmware
PR #378 has since merged the session-only `!cad,<ms>,temp` support to `main`.
Workflow routed #394 to Sage as the post-#378 bench retest for #322: reflash
from `main`, free COM6, verify the ACK, and record whether CSV + `manifest.json`
are written.

## Observed failure

- UI showed Experiment Capture in error state for
  `20260629_180412_p2_dry_to_watered_test`.
- The prior Sage transcript recorded the manual diagnostic result:
  `device rejected cadence 1000 ms (nak)`.
- Root `experiments/` contained several P02 attempt folders, but each inspected
  P02 attempt folder was empty: no capture CSV, no `manifest.json`.
- The final P02 attempt folder
  `experiments/20260629_180412_p2_dry_to_watered_test/` existed but had
  zero files.
- The dashboard later still showed the red experiment error while Monitor
  logging owned COM6. `logs/.serial-owner.json` reported
  `{"mode":"monitor","port":"COM6"}` for PID 27732, opened at
  `2026-06-29T18:06:26.332Z`. That later state is expected port ownership,
  not proof of a second root cause by itself.

## Empty P02 attempt folders

| Experiment folder | Files |
| --- | ---: |
| `20260629_173741_P02_large_pothos_dry_baseline_to_rewater` | 0 |
| `20260629_173837_P02_large_pothos_dry_baseline_to_rewater` | 0 |
| `20260629_174059_dry-in-soil-p2-then-water` | 0 |
| `20260629_175604_P02_large_pothos_dry_baseline_to_rewater` | 0 |
| `20260629_175818_p2_in_soil_to_watered` | 0 |
| `20260629_180312_p2_dry_pot_sensors_in_soil_to_watered_baselin` | 0 |
| `20260629_180412_p2_dry_to_watered_test` | 0 |

## Source-code cross-check

At recovery time, this checkout showed:

- Host Experiment Capture sends session-only cadence in
  `tools/capture/experiment_capture.py`: `body = f"cad,{ms},temp"`.
- Firmware command handler in `firmware/lib/commands/commands.cpp` accepted
  `!cad,<ms>` and persisted the value to NVS via `prefs()->putULong`, with no
  local `,temp` branch in this checkout.
- `docs/process/BENCH_PREFLIGHT.md` already records the earlier cadence leak:
  a fast experiment cadence persisted to NVS and affected later monitor logging.

PR #378 is the merged Firmware fix for the missing `,temp` support on `main`.
The expected #394 retest is:

1. Pull `main` containing PR #378 and flash the ESP32.
2. Stop Monitor logging or otherwise free COM6.
3. Start Experiment Capture with source `serial (device)`, port `COM6`, and a
   1 s rate.
4. Confirm the device ACKs `!cad,1000,temp`.
5. Confirm the capture folder receives a CSV and `manifest.json`.
6. Confirm the device banner exposes `cadence_src=temp` during the session.
7. Confirm Monitor logging after reset/reopen returns to the intended monitor
   cadence, not the experiment cadence.

## Current interpretation

Facts:

- The failed P02 isolated-capture attempts created folders but no capture files.
- The recovered transcript captured a device NAK for `cadence 1000 ms`.
- Host code sends `!cad,<ms>,temp`.
- Firmware PR #378 explicitly describes the same mismatch and has merged to
  `main`; #394 is the Sage-owned hardware retest for #322.

Inference:

- The P02 Experiment Capture failure was caused by the host sending the new
  session-only cadence command before the flashed firmware supported it.

Open cautions:

- The dashboard's current red error label may remain visible while Monitor
  logging owns COM6. Per Workflow, do not file a #335 UX follow-up unless the
  error survives a clean PR #378 reflash and a freed COM6 port.
- Empty `experiments/<id>/` folders are useful failure evidence, but they are
  gitignored raw-capture directories. This Markdown/JSON pair is the durable
  tracked record.

## Routing recommendation

- **Sage:** own #394 as the #322 post-PR #378 hardware retest.
- **Firmware:** re-engage only if a clean reflash from `main` still NAKs
  `!cad,1000,temp`.
- **Data/UI:** do not file a #335 UX issue unless the error persists after the
  clean firmware retest with COM6 free.
- **Evidence PR:** because #383 is already merged, land this recovery pair with
  the post-#378 pass/fail retest evidence in a new PR.

-- Sage
