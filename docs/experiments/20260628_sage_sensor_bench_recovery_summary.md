# 2026-06-28 Sage sensor bench recovery summary

**Date:** 2026-06-28 local CDT
**Lane:** Sage
**Authority:** BENCH EVIDENCE, not calibration-ratified.

This file indexes the recovered 2026-06-28 small experiment sidecars that were
left untracked after the earlier Sage thread crash. The JSON sidecars remain the
machine-readable evidence. This summary makes the sequence durable and
discoverable for calibration review.

## Source sidecars

- [`20260628_180203_control-water-board-shade-1302.json`](20260628_180203_control-water-board-shade-1302.json)
- [`20260628_180802_subject_control-water-board-shade-recov.json`](20260628_180802_subject_control-water-board-shade-recov.json)
- [`20260628_181446_shaded_esp32.json`](20260628_181446_shaded_esp32.json)
- [`20260628_221707_post-firmware-flash-test.json`](20260628_221707_post-firmware-flash-test.json)
- [`20260628_224652_wet-dry-speed-transition-settle-test.json`](20260628_224652_wet-dry-speed-transition-settle-test.json)
- [`20260628_230230_filled-to-max-level-test.json`](20260628_230230_filled-to-max-level-test.json)
- [`20260628_230734_wet-to-dry-sequential-pull-to-platepaper.json`](20260628_230734_wet-to-dry-sequential-pull-to-platepaper.json)
- [`20260628_231615_s4_dry_to_wet_test.json`](20260628_231615_s4_dry_to_wet_test.json)
- [`20260628_231914_s3_dry_to_wet_test.json`](20260628_231914_s3_dry_to_wet_test.json)
- [`20260628_232404_s2_dry_to_wet_test.json`](20260628_232404_s2_dry_to_wet_test.json)
- [`20260628_232650_s1_dry_to_wet_test.json`](20260628_232650_s1_dry_to_wet_test.json)
- [`20260628_232948_all_4_full_wipe_and_full_air_dry.json`](20260628_232948_all_4_full_wipe_and_full_air_dry.json)
- [`20260628_233604_2nd_4_full_wipe_and_full_air_dry_chk_s2.json`](20260628_233604_2nd_4_full_wipe_and_full_air_dry_chk_s2.json)
- [`20260628_234134_3rd_4_full_wipe_and_full_air_dry_chk_s1.json`](20260628_234134_3rd_4_full_wipe_and_full_air_dry_chk_s1.json)
- [`20260628_234458_4th_4_full_wipe_and_full_air_dry_chk_s1.json`](20260628_234458_4th_4_full_wipe_and_full_air_dry_chk_s1.json)
- [`20260628_234715_resetting_logging_to_5_sec_via_exp.json`](20260628_234715_resetting_logging_to_5_sec_via_exp.json)

## Executive summary

The recovered sidecars cover a sequence of sensor-bench experiments before the
full plant survey. They are useful for calibration and procedure design, but
they should remain provisional until reviewed against raw logs and any available
capture manifests.

Main findings:

- Water-reference readings were stable around the saturated/submerged region
  during the sun/shade checks; no large immediate sunlight step was observed.
- A slower thermal explanation remains plausible because board, water, and
  ambient temperatures were not captured as independent sidecar metadata.
- The post-firmware-flash capture verified the firmware/logger/app capture path
  after restart.
- Wet-to-dry and dry-to-wet transitions were large and fast enough for Sprout's
  watering use case.
- One-at-a-time dry-to-wet tests showed strong channel-local response on all
  four probes, with limited immediate cross-channel contamination.
- Repeated wipe/air-dry captures placed practical open-air dry endpoints near
  3090-3130 raw ADC, while still showing per-channel offset and wipe/dry-state
  sensitivity.

## Evidence table

| Time / file | Purpose | Key result | Use with |
| --- | --- | --- | --- |
| 18:02 board shade | Check immediate ADC artifact after shading board while probes stayed in water. | Stable wet-reference medians: s1 997, s2 941, s3 1034, s4 992; no CRC failures; 16 dropped rows. | Sun/heat artifact discussion; not final thermal proof. |
| 18:08 shade recovery / sun tail | Check direct sun step during water-cup run. | Small first-to-last movement only: s1 +6, s2 +7, s3 +1, s4 +6; 1 CRC failure. | Weakens fast direct-sun artifact hypothesis. |
| 18:14 shaded ESP32 | Keep board shaded through later skylight interval. | Water-reference medians stayed near s1 999, s2 942, s3 1035, s4 994; small downward drift. | Supports adding board/water temperature metadata later. |
| 22:17 post-firmware flash | Verify capture path after firmware/app restart. | 114 sweeps / 456 soil rows, 0 CRC failures, stable water medians s1 977, s2 922, s3 1007, s4 977. | Operational validation, not a new anchor. |
| 22:46 wet-to-dry settle | Lift wet probes from water to air/drying condition. | First-to-last deltas about +1843 to +1946 for s1/s2/s3/s4, with handling caveats. | Demonstrates fast wet-to-dry detectability. |
| 23:02 filled-to-max level | Test deeper water reference at marked insertion line. | Medians s1 958, s2 900, s3 969, s4 970; depth/angle affected values. | Shows wet anchors need consistent depth/fixture. |
| 23:07 sequential pull to plate/paper | Pull wet probes one by one to drying surface. | Sequential deltas visible; s1 +1816, s2 +1920, s3 +1460, s4 +1173. | Useful transition evidence; not per-channel timing calibration. |
| 23:16 s4 dry-to-wet | Place only s4 into water after wiping dry. | s4 dropped 2795 to 965, delta -1830; other probes stayed dry with small deltas. | Channel-local dry-to-wet response. |
| 23:19 s3 dry-to-wet | Place only s3 into water after wiping dry. | s3 dropped 2927 to 1004, delta -1923; other probes had small dry drift. | Channel-local dry-to-wet response. |
| 23:24 s2 dry-to-wet | Place only s2 into water after wiping dry. | s2 dropped 3095 to 941, delta -2154; s1/s3 stable, s4 drifted dryward. | Strongest observed span; reinforces per-channel calibration. |
| 23:26 s1 dry-to-wet | Place only s1 into water after wiping dry. | s1 dropped 3006 to 987, delta -2019; other probes mostly dry/static. | Completes one-by-one channel response set. |
| 23:29 full wipe/air dry | First all-probe wipe and air-dry endpoint check. | Medians s1 2975, s2 3119, s3 3121, s4 3058; narrow ranges. | Initial dry-air endpoint, but s1 remained lower. |
| 23:36 second full wipe | Repeat dry-air check, especially s2. | Medians s1 2942, s2 3120, s3 3123, s4 3051. | Shows s2/s3 dry endpoint stability. |
| 23:41 third full wipe | Check whether s1 can reach higher dry-air region. | Medians s1 3120, s2 3120, s3 3123, s4 3099. | Shows s1 lower reading was not fixed limitation. |
| 23:44 fourth full wipe | Final vigorous wipe/dry check. | Medians s1 3089, s2 3123, s3 3125, s4 3131; 1 CRC failure. | Practical dry-air endpoint region around 3090-3130. |
| 23:47 return to 5 s capture | Operational sanity check after 0.5 s captures. | 5 sweeps / 20 rows, no dropped rows, no CRC failures; dry medians s1 3175, s2 3124, s3 3123, s4 3134. | Confirms slower experiment capture path after fast tests. |

## Calibration implications

- Per-channel calibration is required. The single-probe dry-to-wet spans were
  all large, but not identical: s4 -1830, s3 -1923, s2 -2154, and s1 -2019 raw
  counts.
- Wet endpoints depend on immersion depth, probe angle, and handling. The
  filled-to-max test should not be mixed with lower-depth water-cup captures as
  if both are the same endpoint.
- Dry endpoints depend on wipe quality and remaining surface moisture. Later
  full-wipe runs are better endpoint candidates than the first wipe pass.
- Sun/shade data does not support a large immediate direct-light ADC artifact,
  but it does support adding temperature/light sidecar metadata before making
  stronger claims about drift causes.

## Follow-ups

1. Tie these sidecars to the calibration issue as recovered Sage bench evidence.
2. Ask Data to include sidecar provenance fields when building bench-log views:
   capture cadence, subject/reference, event timing, CRC failures, dropped rows,
   and operator handling caveats.
3. For future calibration anchors, use a simple probe holder so depth and angle
   are controlled.
4. Add board/environment temperature sidecar capture before revisiting sunlight
   or thermal-drift explanations.

- Sage
