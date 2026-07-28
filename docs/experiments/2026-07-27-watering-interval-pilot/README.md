# Issue #1646 — one-hour antecedent-interval pilot

## Result

This packet preserves a measured-dose watering session centered on p11, the
subject named by #1646.

**Classification:** reference/pilot evidence only. It is **not** Arm A or Arm B
of the proposed experiment.

- Previous recorded p11 watering: `2026-07-21T14:38:57Z`
- Current p11 watering: `2026-07-27T16:15:00Z`
- Antecedent interval: 145.6008 hours / 6.0667 days
- Proposed Arm A: about 3–4 days
- Proposed Arm B: about 10–12 days

The event is useful for validating the capture protocol and as a middle-interval
reference, but it cannot answer whether the proposed short and long intervals
change uptake.

## One-hour observations

| Plant | Dose | Baseline | Immediate | Capture minimum | One hour | Baseline → 1 h |
|---|---:|---:|---:|---:|---:|---:|
| p11 Corn-plant? (mini) | 177.4 mL / 0.75 cup | 1,823 | 1,713 | 1,336 at 17:07:24Z | 1,368 | −455 |
| p10 Pothos (office) | 177.4 mL / 0.75 cup | 1,727 | 1,030 | 992 at 16:06:53Z | 1,104 | −623 |
| p02 Pothos (XXL) | 354.8 mL journal total / 1.5 cups | 1,807 | 1,400 after first pass | 1,369 at 16:18:36Z | 1,481 | −326 |

The one-hour observations are within 0.7–13.4 seconds of their target times.
All three rows have `quality=OK`.

## Approximately 22-hour follow-up

A current-state pull was captured at `2026-07-28T14:36:58–59Z`. This was before
the three exact 24-hour targets, so the rows retain their actual elapsed times:

| Plant | Elapsed | Current raw | Baseline Δ | Change since 1 h | Full-window minimum |
|---|---:|---:|---:|---:|---:|
| p10 | 22.4703 h | 1,282 | −445 | +178 | 992 near the initial plunge |
| p11 | 22.3663 h | 1,377 | −446 | +9 | 1,321 at 4.2219 h |
| p02 | 22.3108 h | 1,463 | −344 | −18 | 1,369 after pass two |

Higher raw counts are drier. p10 shows a clear rebound/dry-down after its
immediate surface peak. p11 is nearly unchanged from its one-hour value and did
not reach its wettest observed point until about 4.22 hours after watering. For
p11, calling the 30- or 60-minute observation “settled” was therefore premature.
The eventual #1646 arms should retain a later checkpoint or define settlement
from the trajectory rather than assuming a fixed early time.

p02 remains close to its one-hour state. Its −18-count endpoint change is a
small continuation toward wetter readings, not evidence of a new watering
event.

The five simultaneous controls changed by −3, +56, +3, +69, and +126 from the
original capture start. These are varied ordinary trajectories; none has the
treated plants' watering plunge. They provide ambient context but must not be
subtracted directly from a different plant or board.

Follow-up integrity:

- 24,865 appended rows: 19,892 soil and 4,973 environment
- 2,489 complete sweeps from `8gtt1h`; 2,484 from `y9d41p`
- zero partial sweeps
- all 24,865 rows have `quality=OK`
- median gap about 30.4 seconds
- longest surfaced gap 65.517 seconds
- 18 and 23 gaps over 45 seconds respectively; none over 90 seconds
- total packet extent: 26,385 raw rows through
  `2026-07-28T14:36:59.117Z`

See `FOLLOWUP_20260728.md`, `derived/followup-snapshot.csv`, and
`raw/followup-20260728/`.

### p11 — #1646 subject

- Delivery was center-first through the large central stalk system. Only the
  small, unmeasured remainder was distributed more widely over the soil.
- No water was visible in the drip tray.
- The initial response was modest: 1,823 → 1,713 (−110).
- The early 30-minute minimum was 1,372, but p11 later reached 1,336 at about
  52 minutes. The schema therefore records the early reference separately from
  the actual capture-window minimum.
- At one hour p11 was 1,368, still 455 counts below baseline.
- Acute ÷ early-30-minute response was 0.26; acute ÷ one-hour response is about
  0.24. Both describe delayed uptake at probe depth, but neither is a
  cross-interval comparison.

### p10 — same measured dose, matched container history

p10 and p11 use the same 6-inch terracotta pot/tray form and have a long history
of equal care. They are different plant species and are measured by different
ESP32 board classes, so absolute raw values must not be compared across them.
Within-plant deltas and response shapes remain useful.

p10 plunged immediately, then rebounded: 1,727 → 992 → 1,104 at one hour. This
is the surface-peak shape, in contrast to p11's delayed deeper response.

### p02 — two-pass contrast

p02 received two equal 177.4 mL journaled passes, totaling 354.8 mL. The physical
measure was 1.5 cups; the 0.1 mL difference is decimal rounding. The trace
contains two distinct watering elbows. A small, typical-or-less amount reached
the drip tray.

## Simultaneous controls

All five unwatered live channels are present in the lossless time-window slices.
Their first-to-last changes were:

| Plant | Change |
|---|---:|
| p01 | −3 |
| p03 | −1 |
| p07 | 0 |
| p06 | +18 |
| p04 | +31 |

No control shows a simultaneous plunge comparable to the treated channels
(−326 to −623 at the one-hour points). This supports the interpretation that the
treated changes are watering responses, without turning the controls into a
claim about causal differences among plants.

## Evidence quality

- UTC window: `2026-07-27T16:03:00Z` through `2026-07-27T17:20:30Z`
- Rows: 1,520 total; 1,216 soil and 304 environment
- Sweeps: 152 per device
- Partial sweeps: 0
- Longest sweep gap: 32.056 seconds
- Quality flags: 1,520 `OK`
- Transport: Wi-Fi polling at a nominal 30-second cadence
- Firmware: 0.7.3 on both production devices
- Logger: `fleet_logger_0_1`, schema 1
- Running app: 0.8.1, but its server commit predates the checkout; raw logger
  slices are the primary evidence.

Raw rows are complete, byte-preserving slices of both active log files for the
bounded window. Gaps would remain visible; no interpolation or smoothing was
performed.

## Watering-journal reconciliation

Four operator-confirmed measured pours are preserved:

- p02: 177.4 mL at 16:07:32Z
- p10: 177.4 mL at 16:08:46Z
- p11: 177.4 mL at 16:15:00Z
- p02: 177.4 mL at 16:18:20Z

During entry, moving cards and three stale browser-only “logged just now” badges
made the UI appear unreliable. The journal was repaired append-only from
operator ground truth. A forced refresh then showed only the correct p10, p11,
and p02 records; no unintended watering rows existed. Manual UI event times are
ordinary near-event times, typically about ±90 seconds. Raw telemetry provides
the finer response timing.

## Admissibility

- **#1646 hypothesis:** annotate; valid protocol and middle-interval reference,
  but neither planned comparison arm.
- **Dose-response analysis:** annotate; retain p11 delivery geometry and p02
  two-pass/tray-water context.
- **Dashboard:** admit after journal reconciliation and forced-refresh check.
- **Calibration anchors:** exclude; these are in-soil watering responses, not
  controlled wet/dry rail measurements.
- **Model training:** do not treat p11 as an Arm A or Arm B label.

No blind pre-pour prediction was sealed for this pilot. The actual comparison
arms should add one before watering.

## File map

- `manifest.json` — machine-readable provenance, treatment, control, quality,
  and admissibility record
- `raw/*.csv` — lossless bounded slices for both live devices
- `events/watering-events.jsonl` — the four exact measured-pour journal rows
- `derived/one-hour.csv` — nearest observations to each one-hour target
- `derived/followup-snapshot.csv` — actual 22.31–22.47-hour treated and control
  observations
- `derived/channel-window-summary.csv` — treated and control window summary
- `derived/baseline.csv`, `immediate.csv`, `settled.csv` — bench captures made
  during the session
- `figures/*.png` — selected clean dashboard exhibits
- `FILELIST.sha256.tsv` — byte counts and SHA-256 for every packet file
- `ISSUE_COMMENT_DRAFT.md` — concise board update, not yet posted
- `WORKFLOW_HANDOFF.md` — local handoff for triage and evidence landing
- `FOLLOWUP_20260728.md` — human-readable follow-up interpretation and limits

## What this does not prove

- It does not compare the planned 3–4-day and 10–12-day p11 arms.
- It does not establish a plant-independent raw-count response.
- It does not prove one delivery geometry is superior.
- It includes an approximately 22-hour pull, not an exact 24-hour or 48-hour
  horizon.
- It does not close #1646.

The next hypothesis-bearing steps are the same p11 dose at the two planned
antecedent intervals, using the same delivery protocol, with a prediction sealed
before each pour and the longer horizons appended afterward.

## Privacy

The packet contains no personal names, private scheduling context, host
paths, IP/MAC/USB identifiers, credentials, coordinates, or browser chrome.
A full-screen p02 image remains only in the private working folder and is
deliberately excluded from this packet.
