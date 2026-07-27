# 2026-06-28 Bench Session Log

<!-- markdownlint-disable MD024 -->
<!-- Session log structure intentionally repeats Hypothesis/Method/Findings/Conclusion per experiment -->

Manual bench log for sensor controls and plant dry/wet baseline captures.

This log is the bench-session ground truth when the Lab Notes UI cannot save notes.
Raw captures remain in the experiment capture folders; this file records the
human-observed setup, interventions, and interpretation.

## Session Context

- Date: 2026-06-28
- Bench role: Sage / Bench lane
- Hardware state:
  - ESP32 + four capacitive soil probes are bench-wired.
  - Pumps and relay board are not connected for this session.
  - Probes initially in a shared cup of water.
- Environmental note:
  - Around 13:00 local, direct skylight was hitting the ESP32/breadboard.
  - The ESP32/breadboard was shaded at exactly 13:00 local.
  - The cup of water and probes were not shaded or moved for the first control.
- Measurement caution:
  - Shading the board changes direct light exposure, but it does not instantly
    reset board temperature. A short shaded capture can only test for a large
    immediate artifact, not slower thermal lag.
  - The running experiment CSV still includes processed `value,pct` columns.
    For this session, `raw_value` is the evidence column; the processed value
    and unit fields are ignored.

## Capture: control-water-board-shade-1302

- Capture id: `20260628_180203_control-water-board-shade-1302`
- Subject: `control-water-board-shade-1302`
- Start time: 2026-06-28 13:02 local / 18:02 UTC
- Duration: 60 s
- Sample rate: 1.0 s
- Source: serial device
- Condition:
  - All four probes remained in the same cup of water.
  - ESP32/breadboard shaded after being in direct skylight.
  - Cup of water and probes were not shaded or moved.
- Rows: 236
- Samples per channel: 59
- Dropped rows: 16
- CRC failures: 0

### Hypothesis

If direct skylight on the ESP32/breadboard was causing a large immediate ADC
artifact, then shading the ESP32 while leaving the water cup and probes unchanged
should produce a visible step change or strong drift in raw water readings.

### Method

At 13:00 local, the ESP32/breadboard was shaded after being in direct skylight.
The water cup and probes were not shaded or moved. After about 2 minutes, a
60 second experiment capture was recorded at 1 second cadence.

### Findings

All four probes remained in the saturated/submerged wet-reference band.

| Probe | GPIO | Median Raw | Range | Slope |
|---|---:|---:|---:|---:|
| s1 | 34 | 997 | 993-1000 | +71.73/h |
| s2 | 35 | 941 | 938-944 | -16.84/h |
| s3 | 36 | 1034 | 1031-1037 | +75.51/h |
| s4 | 39 | 992 | 988-996 | +48.61/h |

The one-minute slopes should be treated as short-window indicators only, not a
long-run trend estimate.

### Conclusion

This run does not show a large immediate measurement shift within the first few
minutes after shading the ESP32/breadboard while the probes stayed in water.
It does not rule out board heating or thermal-lag effects, because the
ESP32/breadboard may still have been at elevated temperature during the capture.
Longer shaded recovery captures are needed to evaluate return-to-baseline
behavior.

## Capture: subject_control-water-board-shade-recov

- Capture id: `20260628_180802_subject_control-water-board-shade-recov`
- Subject: `subject_control-water-board-shade-recov`
- Start time: 2026-06-28 13:08 local / 18:08 UTC
- Duration: 300 s
- Sample rate: 1.0 s
- Source: serial device
- Condition:
  - All four probes remained in the same cup of water.
  - ESP32/breadboard was shaded at the beginning of the capture.
  - At 180 s elapsed, direct skylight was allowed back onto the
    ESP32/breadboard.
  - Cup of water and probes were not moved.
- Rows: 1195
- Sweeps: 299
- Dropped rows: 112
- CRC failures: 1
- Idle noise: 4

### Hypothesis

If direct skylight on the ESP32/breadboard causes a fast ADC artifact, then
removing shade during a stable water-reference capture should produce a visible
step change shortly after the 180 s intervention.

### Method

A 5 minute capture was run with all four probes in a shared water cup. The
ESP32/breadboard was shaded for the first 180 seconds. At 180 seconds elapsed,
shade was removed so direct skylight reached the ESP32/breadboard for the final
120 seconds. The water cup and probes were held constant.

### Findings

The raw readings remained in the saturated/submerged wet-reference band. A
small upward drift was present after direct skylight was restored, but no large
step response was visible in the raw split.

| Probe | Shaded 0-180 s Mean | Sun 180-300 s Mean | Sun - Shaded | First Sun 60 s - Last Shaded 60 s |
|---|---:|---:|---:|---:|
| s1 | 997.57 | 999.70 | +2.13 | +1.53 |
| s2 | 940.59 | 942.82 | +2.23 | +1.45 |
| s3 | 1035.48 | 1037.07 | +1.59 | +1.13 |
| s4 | 992.95 | 994.94 | +1.99 | +1.27 |

Full-capture summary:

| Probe | GPIO | Median Raw | Range | Slope |
|---|---:|---:|---:|---:|
| s1 | 34 | 998 | 993-1003 | +41.80/h |
| s2 | 35 | 941 | 937-948 | +44.36/h |
| s3 | 36 | 1036 | 1032-1040 | +34.44/h |
| s4 | 39 | 994 | 989-999 | +40.59/h |

### Conclusion

This capture does not support a large immediate direct-light artifact on the
ESP32/breadboard while probes are submerged in water. It does support a small
upward drift during the sunlit tail, on the order of 1-2 raw counts at the
intervention boundary and about 2 raw counts across the broader shaded-vs-sunlit
split. This remains compatible with thermal lag, slow board warming, or normal
short-window ADC noise. It does not test dry soil or plant media behavior.

## Capture: shaded_esp32

- Capture id: `20260628_181446_shaded_esp32`
- Subject: `shaded_esp32`
- Start time: 2026-06-28 13:14 local / 18:14 UTC
- Duration: 900 s
- Sample rate: 1.0 s
- Source: serial device
- Condition:
  - All four probes remained in the same cup of water.
  - ESP32/breadboard was actively shaded for the capture.
  - The table/bench/cardboard box remained in the skylight beam during at
    least the final portion of the run.
  - Cup of water and wires were exposed to direct or partial skylight.
  - Sensor faces were mostly vertical in the cup; direct photon exposure on the
    sensing faces was not verified.
  - Water temperature was not measured.
- Rows: 3594
- Sweeps: 899
- Dropped rows: 352
- CRC failures: 2
- Idle noise: 4

### Hypothesis

If the ESP32/breadboard was heated by skylight and the measurement system has a
slow thermal response, then actively shading the ESP32 during the later part of
the skylight period should cause raw readings to recover downward over minutes,
not as an immediate step.

### Method

A 15 minute capture was run with all four probes in a shared water cup. The
ESP32/breadboard remained shaded. The wider bench area and water cup still had
skylight exposure, so this is a partial environmental control rather than a
full-shade control.

### Findings

All four probes showed a shared downward trend over the 15 minute shaded
recovery capture.

| Probe | Early 0-300 s Mean | Middle 300-600 s Mean | Late 600-900 s Mean | Late - Early | Last 120 s - First 120 s |
|---|---:|---:|---:|---:|---:|
| s1 | 1000.49 | 998.83 | 995.46 | -5.04 | -7.05 |
| s2 | 943.57 | 942.05 | 939.17 | -4.40 | -5.88 |
| s3 | 1036.37 | 1035.42 | 1030.61 | -5.75 | -8.76 |
| s4 | 996.11 | 994.68 | 991.39 | -4.72 | -5.89 |

Full-capture summary:

| Probe | GPIO | Median Raw | Range | Slope |
|---|---:|---:|---:|---:|
| s1 | 34 | 999 | 989-1005 | -30.86/h |
| s2 | 35 | 942 | 934-948 | -27.01/h |
| s3 | 36 | 1035 | 1022-1041 | -35.80/h |
| s4 | 39 | 994 | 986-1000 | -27.96/h |

Rolling 60 second windows put the lowest means near the end of the run for all
channels, around t+838 s.

### Conclusion

This run supports the hypothesis that the water-reference readings can recover
downward over minutes after active shading of the ESP32/breadboard. The effect
is shared across all four channels and is larger than the short one-minute
water-reference noise observed earlier in the session. It does not isolate the
ESP32/breadboard completely, because water, wires, and the surrounding bench
remained at least partially exposed to skylight and water temperature was not
measured.

### Same-Clock Historical Check

The 13:20-13:30 local window was compared against available monitor logs. The
same window was unavailable for 2026-06-26 and unavailable in the 2026-06-28
monitor log because the isolated experiment was running.

| Date / Source | s1 Slope | s2 Slope | s3 Slope | s4 Slope | Notes |
|---|---:|---:|---:|---:|---|
| 2026-06-24 monitor | +3.07/h | +3.79/h | -1.44/h | +8.66/h | Mostly flat |
| 2026-06-25 monitor | -17.23/h | -10.10/h | -54.22/h | -17.77/h | Mixed downward |
| 2026-06-27 monitor | -46.01/h | -58.55/h | -51.16/h | -39.85/h | Downward across all channels |
| 2026-06-28 shaded experiment | -43.85/h | -36.78/h | -63.32/h | -40.51/h | Downward across all channels |

The same-clock comparison shows today's shaded recovery is real, but it is not
uniquely faster than the available 2026-06-27 same-clock window. This supports
continued investigation of board/wet-reference recovery, but it does not yet
prove active ESP32 shading accelerated recovery relative to prior days.

## Passive Monitor Observation: long shaded water hold

- Log file: `logs/plants_esp32_f4e9d4_20260628_183018.csv` — **slice unavailable**
  (maintainer ruling A, #1330, 2026-07-20): this file is present in neither `logs/`
  nor the archive, so the citation cannot be resolved. It predates the production
  epoch (`2026-07-06T00:00:06Z`, ADR-0037) and therefore predates the archive
  boundary this record was written against. The observations below stand on their
  own narrative; the raw slice behind them is not recoverable.
- Log type: monitor log, not isolated experiment capture
- Local time covered so far: 2026-06-28 13:30:18 to 17:02:18 CDT
- Human context:
  - Veronica had company visit for several hours.
  - Probes remained in the shared water cup.
  - ESP32/breadboard remained covered by the cardboard shade.
  - The skylight beam passed the bench area around 13:30 local.
- Data caution:
  - This post-restart monitor log still populated `value,pct`.
  - `raw_value` remains the evidence column for this session.

### Findings

After the sharper 15 minute shaded recovery run, the longer water hold continued
to drift downward slowly while the probes stayed submerged.

| Probe | 13:30-14:00 Mean | 14:00-15:00 Mean | 15:00-16:00 Mean | 16:00-17:00 Mean | Full Delta |
|---|---:|---:|---:|---:|---:|
| s1 | 992.15 | 986.71 | 981.75 | 978.76 | -15 |
| s2 | 936.98 | 932.58 | 927.84 | 923.97 | -13 |
| s3 | 1021.08 | 1015.13 | 1011.27 | 1009.29 | -13 |
| s4 | 988.93 | 985.47 | 981.42 | 978.62 | -9 |

Full-window slopes from 13:30 to 17:02 local were modest: s1 -4.49/h,
s2 -4.55/h, s3 -3.76/h, and s4 -3.61/h.

### Conclusion

The long passive water hold supports a two-phase recovery shape: a faster
initial downward recovery during the 15 minute shaded experiment, followed by a
much slower downward drift over the next several hours. Because the probes
remained submerged, the effect is not plant water uptake. Possible contributors
include board thermal recovery, water temperature change, sensor-body/wire
thermal effects, ADC behavior, or a combination of those factors.

## Post-Flash Acceptance Check

- Firmware build/upload: successful via PlatformIO
- Flashed git rev reported by build: `e012f21`
- Capture id: `20260628_221707_post-firmware-flash-test`
- Subject: `post-firmware-flash-test`
- Start time: 2026-06-28 17:17 local / 22:17 UTC
- Duration: 60 s
- Requested sample rate: 0.5 s
- Source: serial device
- Condition:
  - All four probes remained in the shared water cup.
  - Sprout app/server was restarted before the capture.
  - Firmware was rebuilt and uploaded before the capture.
- Rows: 456
- Sweeps: 114
- Dropped rows: 55
- CRC failures: 0
- Idle noise: 0

### Contract Check

The experiment CSV rows obeyed the raw-only value/unit contract:

- `value`: empty in 456/456 rows
- `unit`: empty in 456/456 rows
- `quality_flag`: `OK` in 456/456 rows
- `firmware_version`: `0.7.0` in 456/456 rows
- `logger_version`: `experiment_capture_0_1` in 456/456 rows

The lab-notes save path also worked after restart. Notes were written to
`docs/experiments/20260628_221707_post-firmware-flash-test.json` with
`saved_at=2026-06-28T22:23:18Z`.

### Firmware / Banner Check

The fresh monitor logs captured the firmware boot/provenance banner after
flashing:

- `fw=0.7.0`
- `git=e012f21`
- `built=Jun 28 2026 17:09:06`
- `health: ch0=OK ch1=OK ch2=OK ch3=OK`
- `safety: actuators fail-safe OFF ... pump=manual(!water) bounded<=5000ms`
- `device_cols` includes `value,unit`
- The following banner line states that `raw_value` plus payload band are
  authoritative and `value/unit` are NULL/reserved.

The experiment CSV itself does not include the firmware git rev; it only carries
`firmware_version=0.7.0`. Monitor logs are therefore the current source for
post-flash git provenance.

### Sub-Second Sampling Check

The 0.5 s experiment did run below 1 s cadence. Expected output for a 60 s run
is about 120 sweeps / 480 rows. Observed output was 114 complete four-channel
sweeps / 456 rows.

- Unique sweep timestamps by device `millis_ms`: 114
- Sweep deltas: 108 intervals at 500 ms, 5 intervals at 856 ms
- First-to-last host timestamp duration: 58.501 s
- Device millis span: 58.280 s
- Per-channel samples: 114 each for s1, s2, s3, and s4

The capture supports 0.5 s sampling as operational for short bench tests, with
some missed/long intervals. It should be treated as usable but not lossless.

### Cadence Caution

The fresh monitor banner after the experiment reported `cadence_ms=500 (nvs)`.
This means the 0.5 s cadence was persisted on-device. Before long monitor
logging, choose an intentional cadence so the logger does not accidentally
produce very dense files.

### Follow-Up: monitor cadence after 0.5 s experiment

Veronica stopped the monitor log that was started after the 0.5 s experiment.
The latest monitor file was `logs/Sprout ESP32_20260628_222533.csv`.

- Banner cadence: `cadence_ms=500 (nvs)`
- Local time span: 2026-06-28 17:25:33 to 17:41:16 CDT
- Rows: 7286
- Unique sweeps: 1822
- Rows per minute: 463.5
- Sweep deltas: 1730 intervals at 500 ms, 91 intervals at 856 ms
- `value`: empty in 7286/7286 rows
- `unit`: empty in 7286/7286 rows

This confirms monitor logging inherited the persisted 0.5 s device cadence.
The experiment UI does not currently behave as a purely per-experiment cadence
setting; it changes the firmware cadence until changed again.

## Capture: wet-dry-speed-transition-settle-test

- Capture id: `20260628_224652_wet-dry-speed-transition-settle-test`
- Subject: `wet-dry-speed-transition-settle-test`
- Start time: 2026-06-28 17:46 local / 22:46 UTC
- Duration: 120 s
- Requested sample rate: 0.5 s
- Source: serial device
- Condition:
  - All four probes started in the shared water cup.
  - Veronica lifted and held the probes in air over the cup for the capture.
  - s1 and s2 initially stuck together face-to-face because of the water film;
    their delayed response is a handling artifact.
  - The probes were hand-held, so wire strain, angle, dripping, and water-film
    thickness were not controlled.
- Rows: 919
- Sweeps: 230
- Dropped rows: 121
- CRC failures: 1
- Idle noise: 0

### Contract Check

The experiment CSV obeyed the raw-only value/unit contract:

- `value`: empty in 919/919 rows
- `unit`: empty in 919/919 rows
- Unique sweep timestamps: 230
- Sweep deltas: 218 intervals at 500 ms, 11 intervals at 856 ms

This supports 0.5 s sampling as useful for short transition tests, but still
not lossless.

### Hypothesis

If the probes have a measurable wet-to-air response after being removed from a
water reference, then a 0.5 s capture should show a fast raw-value rise from
the submerged band toward dry-air readings, followed by a slower settling tail.

### Method

The four probes were lifted from the shared water cup into air at the start of
the capture and held over the cup for 120 seconds. This was a fast exploratory
method, not a controlled fixture. A follow-up should place probes on a plate or
paper towel fixture so they separate cleanly and remain at a stable angle.

### Findings

Using the first captured sweep as the wet endpoint and the 90-120 s median as
the dry-air endpoint, all four probes moved from wet-reference readings near
900-1050 raw counts to dry-air readings around 2860-2924 raw counts.

| Probe | First Wet Raw | Dry Median 90-120 s | Amplitude | t10 | t50 | t90 | t10 to t90 | t99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| s1 | 1025 | 2859 | 1834 | 5.14 s | 5.14 s | 16.99 s | 11.86 s | 79.63 s |
| s2 | 935 | 2863 | 1928 | 4.72 s | 5.22 s | 27.92 s | 23.20 s | 92.56 s |
| s3 | 1006 | 2924 | 1918 | 0.48 s | 0.48 s | 16.35 s | 15.87 s | 79.99 s |
| s4 | 983 | 2875 | 1892 | 0.57 s | 1.07 s | 25.78 s | 25.21 s | 84.92 s |

s1 and s2 should not be used to infer natural probe response timing in the
first 5 seconds because they were physically stuck together. s3 and s4 show the
cleaner immediate response: both crossed 50 percent of the wet-to-dry-air span
within about 1 second, then took roughly 16-26 seconds to reach 90 percent and
about 80-85 seconds to reach 99 percent.

### Conclusion

This first wet-to-air transition run supports a two-phase sensor response:
an immediate large raw-value rise after leaving water, followed by a slower
settling tail that continues for roughly 1-1.5 minutes. It is useful evidence
that 0.5 s capture can resolve fast physical transitions. It does not measure
soil drying, plant behavior, or a clean per-probe response time because the
probes were hand-held and two probes stuck together at the start.

## Capture: filled-to-max-level-test

- Capture id: `20260628_230230_filled-to-max-level-test`
- Subject: `filled-to-max-level-test`
- Start time: 2026-06-28 18:02 local / 23:02 UTC
- Duration: 60 s
- Requested sample rate: 0.5 s
- Source: serial device
- Condition:
  - The shared water cup was refilled so the probes reached the marked maximum
    insertion line.
  - Refill was done by pouring from another cup, so splashing and turbulence
    were possible.
  - Refill water was colder than the water already in the cup.
  - Veronica adjusted probe verticality during the capture; the narrow cup made
    equal probe angle and equal submersion difficult.
- Rows: 455
- Sweeps: 114
- Dropped rows: 55
- CRC failures: 1
- Idle noise: 0

### Hypothesis

If the earlier water cup was too shallow, then filling to the probe max line may
produce a deeper-wet reference reading. If refill splashing reached electronics,
the capture may show resets, quality failures, large cross-channel glitches, or
other abnormal artifacts. Colder refill water may also create a temperature
variant.

### Method

The probes remained in the common water cup while the cup was refilled to the
probe max line. A 60 second capture was recorded at 0.5 s cadence after refill.
The method was not fully controlled because water temperature, splash height,
probe angle, and exact insertion depth varied during the run.

### Findings

The CSV contract and serial stream were healthy during the capture.

- `value`: empty in 455/455 rows
- `unit`: empty in 455/455 rows
- `quality_flag`: `OK` in 455/455 rows
- Sweep deltas: 108 intervals at 500 ms, 5 intervals at 856 ms

No obvious wet-electronics signature was observed in the data: there was no
device reset signature in `millis_ms`, no quality-flag burst, and no large
all-channel glitch. This does not replace visual inspection of the board.

Compared with the last 60 seconds of the immediately prior monitor water log,
the filled-to-max medians changed only modestly.

| Probe | Prior Water Median | Filled-to-Max Median | Delta | Filled Range | Notes |
|---|---:|---:|---:|---:|---|
| s1 | 963 | 958 | -5 | 955-964 | Slight wetter/lower |
| s2 | 897 | 900 | +3 | 893-922 | Nudge/angle artifact visible |
| s3 | 966 | 969 | +3 | 965-977 | Slight drier/higher |
| s4 | 979 | 970 | -9 | 945-982 | Nudge/angle artifact visible |

### Conclusion

This run does not show a strong, uniform deeper-wet step from filling the cup to
the max insertion line. It does show small channel-specific shifts that are
plausibly dominated by probe angle, insertion depth, turbulence, and water
temperature. The data also does not show an obvious electronics-wet artifact,
though that conclusion is limited to serial/ADC behavior and does not prove the
board physically stayed dry.

Temperature should become an explicit future control: cold, room-temperature,
and warm water cups could separate temperature effects from insertion-depth
effects.

## Capture: wet-to-dry-sequential-pull-to-platepaper

- Capture id: `20260628_230734_wet-to-dry-sequential-pull-to-platepaper`
- Subject: `wet-to-dry-sequential-pull-to-platepaper`
- Start time: 2026-06-28 18:07 local / 23:07 UTC
- Duration: 180 s
- Requested sample rate: 0.5 s
- Source: serial device
- Condition:
  - All four probes started in the shared water cup.
  - Veronica pulled the probes one by one, then laid them on a plate with a
    paper towel.
  - Pull timing was intentionally sequential, so each channel has its own
    transition start time.
  - Paper towel contact, sensor face orientation, and remaining water film were
    not controlled.
- Rows: 1381
- Sweeps: 346
- Dropped rows: 187
- CRC failures: 2
- Idle noise: 0

### Contract Check

The experiment CSV obeyed the raw-only value/unit contract:

- `value`: empty in 1381/1381 rows
- `unit`: empty in 1381/1381 rows
- `quality_flag`: `OK` in 1381/1381 rows
- Sweep deltas: 328 intervals at 500 ms, 17 intervals at 856 ms

### Hypothesis

If probes are removed from water one at a time and placed onto a paper towel,
the 0.5 s capture should show distinct per-probe transition starts. The final
raw values may differ if paper towel contact or residual water film keeps some
sensor faces wetter than others.

### Method

The capture ran for 180 seconds. Probes were removed sequentially from the
shared water cup and placed onto a plate with a paper towel. Each probe's
transition timing was analyzed independently, using the first 5 seconds as the
wet baseline and the last 30 seconds as the plate/paper-towel endpoint.

### Findings

The transition order inferred from the first 10 percent threshold was s4, s2,
s1, then s3.

| Probe | Wet Baseline | Last 30 s Median | Amplitude | t10 | t50 | t90 | t10 to t90 | t99 | Last 30 s Slope |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| s4 | 968.0 | 2130.0 | 1162.0 | 3.07 s | 3.07 s | 7.07 s | 4.00 s | 15.43 s | +1258/h |
| s2 | 900.5 | 2809.0 | 1908.5 | 6.72 s | 7.72 s | 32.79 s | 26.06 s | 132.00 s | +2036/h |
| s1 | 956.5 | 2771.0 | 1814.5 | 8.64 s | 15.50 s | 25.35 s | 16.71 s | 117.57 s | +1179/h |
| s3 | 970.0 | 2430.0 | 1460.0 | 10.86 s | 10.86 s | 15.84 s | 4.99 s | 109.06 s | +1129/h |

s1 and s2 reached dry-air-like endpoints near 2770-2810 raw counts. s3 and s4
ended much lower, especially s4, which remained near the "needs water" band on
the dashboard. That difference is strong evidence that paper towel contact,
probe face orientation, retained water film, or placement geometry can dominate
the final endpoint.

### Conclusion

This sequential pull run is better than the prior hand-held all-at-once run for
identifying per-probe transition starts. It confirms that 0.5 s sampling can
resolve probe removal events and shows clear channel-specific transition
timing. It does not provide a clean universal wet-to-dry response curve because
the paper towel became part of the measurement system: some probes dried toward
air-like values while others stayed materially wetter.

Follow-up tests should use a simple fixture or spacer so all probes leave water
at a known time, avoid face-to-face sticking, and land with consistent contact
geometry. Run separate endpoint tests for free-air drying, paper-towel contact,
and towel blot-then-air.

## Calibration Envelope: max-line wet to aggressive wipe-dry

- Time window: 2026-06-28 18:02-18:47 local / 23:02-23:47 UTC
- Capture families:
  - Max-line water reference: `20260628_230230_filled-to-max-level-test`
  - Dry-to-wet insertion checks:
    - `20260628_231615_s4_dry_to_wet_test`
    - `20260628_231914_s3_dry_to_wet_test`
    - `20260628_232404_s2_dry_to_wet_test`
    - `20260628_232650_s1_dry_to_wet_test`
  - Aggressive wipe / air-dry checks:
    - `20260628_232948_all_4_full_wipe_and_full_air_dry`
    - `20260628_233604_2nd_4_full_wipe_and_full_air_dry_chk_s2`
    - `20260628_234134_3rd_4_full_wipe_and_full_air_dry_chk_s1`
    - `20260628_234458_4th_4_full_wipe_and_full_air_dry_chk_s1`
    - `20260628_234715_resetting_logging_to_5_sec_via_exp`
- Excluded from endpoint evidence:
  - `20260628_230159_common-cup` because it had non-empty `value/unit` fields
    and only 3 sweeps.
  - Several aborted `3rd_4_full_wipe...` folders because they had no manifest.

### Hypothesis

If aggressive towel/shirt wiping removes nearly all retained water film from
the probes, then repeated wipe-dry checks should reveal the practical dry
headroom available on these four sensors. Combined with the max-line water
reference, this gives the current practical wet-to-dry calibration envelope for
the installed probe set.

### Method

The filled-to-max water reference was used as the wet endpoint evidence. The
subsequent one-by-one dry-to-wet insertions confirmed that each probe responds
quickly enough for Sprout's plant-care use case, but they were not used as the
primary endpoint because they are transition runs. Repeated full wipe / air-dry
captures were used as the dry endpoint evidence.

Veronica returned the device cadence to 5 seconds with
`20260628_234715_resetting_logging_to_5_sec_via_exp`. The subsequent monitor
log `logs/Sprout ESP32_20260628_234758.csv` confirmed
`cadence_ms=5000 (nvs)`.

### Findings

The completed raw-only captures were internally consistent: `value/unit` were
empty and `quality_flag=OK` for all included rows. The 0.5 s experiment captures
continued to show occasional 856 ms sweep gaps, but they were adequate for the
transition and endpoint checks.

Practical endpoint envelope from max-line water to aggressive wipe-dry:

| Probe | Wet Evidence Range | Wet Median | Driest Observed Raw | Dry Median Across Wipe Checks | Practical Span |
|---|---:|---:|---:|---:|---:|
| s1 | 955-964 | 958 | 3177 | 3086 | 2222 |
| s2 | 893-922 | 900 | 3127 | 3120 | 2234 |
| s3 | 965-977 | 969 | 3134 | 3123 | 2169 |
| s4 | 945-982 | 970 | 3136 | 3096 | 2191 |

The practical spans are tightly clustered, about 2169-2234 raw counts across
the four probes. This is strong evidence that the current sensor set has enough
usable ADC range for per-channel calibration.

Dry endpoint behavior is not perfectly identical across channels. s1 and s4
showed meaningful movement across repeated wipe-dry checks, which may reflect
remaining water film, probe surface wetting, towel contact, temperature, board
thermal state, or a combination. s2 and s3 were more stable near 3120-3125 once
fully wiped.

### Conclusion

From a wipe-it-dry bench perspective, this session likely captured the useful
wettest-wet to driest-dry headroom for these four installed sensors. It should
be treated as the current practical calibration envelope, not an absolute
physics limit. Further endpoint mapping may be scientifically interesting, but
it is unlikely to change Sprout's plant-care decisions unless we intentionally
study temperature, fixture geometry, or long dry-air settling.

For Sprout's north star, the key result is that per-channel calibration should
use these observed wet/dry anchors with sensible margins rather than relying on
a shared classifier. Dry-to-wet and wet-to-dry response times are fast enough
for normal watering and placement workflows; the main remaining value is
calibration accuracy, not faster response modeling.

### Follow-Up Note

The fresh 5 second monitor log showed `cadence_ms=5000 (nvs)`, confirming the
device cadence was reset after sub-second testing. The same banner also showed a
corrupted-looking `cal bounds(...)` line; that should be investigated separately
because calibration provenance needs to remain readable.

## Plant Capture Template

Copy this section for each plant.

### Plant P__

- Plant id: `P__`
- Plant type, if known:
- Pot size / pot notes:
- Visible plant state: ok / wilted / stressed / other
- Soil surface: dry / damp / wet / mixed
- Room for four probes: yes / no
- Probe placement:
  - s1:
  - s2:
  - s3:
  - s4:
- Sun/skylight on board: none / partial / direct
- Sun/skylight on plant: none / partial / direct
- Capture id:
- Subject:
- Start time:
- Duration:
- Sample rate:
- Pre-water or post-water:
- Watering action, if any:
- Notes:

#### Hypothesis

#### Method

#### Findings

#### Conclusion
