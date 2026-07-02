# Recovery Index - 2026-07-01 P01-P11 48-Hour Follow-Up

Created by Sage on 2026-07-01 at about 6:19 pm local Chicago time, before any
issue/PR publication, to preserve the bench evidence on disk.

## Thread And Transcript Breadcrumbs

- Active task: recover today's P01-P11 bench evidence before switching to
  ESP32-S3 / ESP32-C5 bring-up.
- Known broken prior thread ID supplied by Veronica:
  `019f0ea6-a148-7a91-bba6-0d07f99b7750`
- Known broken prior thread URI:
  `codex://threads/019f0ea6-a148-7a91-bba6-0d07f99b7750`
- Active replacement thread ID supplied by Veronica during recovery:
  `019f1513-4205-7e70-9769-91fad3980be3`
- Active replacement thread URI:
  `codex://threads/019f1513-4205-7e70-9769-91fad3980be3`
- JSON log file: not directly identified from inside this runtime. If recovery
  is needed, use the active replacement thread URI above, the prior broken
  thread ID above, and Codex's local thread/export storage to locate the raw
  transcript JSON. The runtime safety layer blocked broad environment/session
  probing, so this packet records the IDs Veronica supplied instead of claiming
  an inferred path.
- User-provided transcript/reorientation attachments referenced during recovery:
  - `C:\Users\PV\.codex\attachments\92252922-f24e-424f-9747-776cef351b2f\pasted-text.txt`
  - `C:\Users\PV\.codex\attachments\94b27d18-c9eb-40db-b2f2-eb120538dcdf\pasted-text.txt`
  - `C:\Users\PV\.codex\attachments\d8dca951-2caf-43c8-9581-e8cf1c481e21\pasted-text.txt`
  - `C:\Users\PV\.codex\attachments\f15329a4-5e40-424b-b026-8eb35cc8239e\pasted-text.txt`
- Local-only full recovery transcript parked in this bundle:
  `LOCAL_THREAD_TRANSCRIPT_019f1513-4205-7e70-9769-91fad3980be3.md`
  This is a verbose chat-history dump for disaster recovery only. It is ignored
  by this directory's `.gitignore` and should not be committed unless Veronica
  explicitly requests it.

## Durable Files Created Or Confirmed

Notebook sidecars in `docs/experiments/`:

- `20260701_171140_p1_48_hours_later_baseline_air_to_soil_settle_to.json`
- `20260701_172559_s1s2_P02_-_s3s4_P03.json`
- `20260701_180122_p04_p05_water_halfcup_quartercup.json`
- `20260701_183611_p06_48h_check_2probe_maybe_water.json`
- `20260701_185816_p07_cachepot_retention_check_no_water.json`
- `20260701_191925_p08_p09_48h_measure_only_2probe.json`
- `20260701_194006_p10_48h_4probe_check.json`
- `20260701_210013_p11_48h_4probe_check.json` - recovered by Sage after the
  run from transcript notes and raw capture stats.

Workflow handoff:

- `WORKFLOW_ISSUE_REQUEST.md` - copy-pasteable issue/PR request for routing
  this rescue packet through the GitHub evidence gate.
- Filed GitHub issue: #533
  `https://github.com/OrangePeachPink/plants/issues/533`

Copied raw experiment captures in this bundle:

- `experiment_captures/20260701_171140_p1_48_hours_later_baseline_air_to_soil_settle_to/`
- `experiment_captures/20260701_172559_s1s2_P02_-_s3s4_P03/`
- `experiment_captures/20260701_180122_p04_p05_water_halfcup_quartercup/`
- `experiment_captures/20260701_183611_p06_48h_check_2probe_maybe_water/`
- `experiment_captures/20260701_185816_p07_cachepot_retention_check_no_water/`
- `experiment_captures/20260701_191925_p08_p09_48h_measure_only_2probe/`
- `experiment_captures/20260701_194006_p10_48h_4probe_check/`
- `experiment_captures/20260701_210013_p11_48h_4probe_check/`

Copied supporting monitor logs in this bundle:

- `monitor_logs/Sprout ESP32_20260701_174045.csv` - P04/P05 baseline and
  surrounding monitor evidence.
- `monitor_logs/Sprout ESP32_20260701_184208.csv` - P06 post-run monitor /
  sunlight artifact evidence.
- `monitor_logs/Sprout ESP32_20260701_190444.csv` - P07 post-run and later
  monitor context.
- `monitor_logs/Sprout ESP32_20260701_205851.csv` - pre-P11/P11 adjacent monitor
  context.
- `monitor_logs/Sprout ESP32_20260701_210522.csv` - P11 post-run monitor and
  s3/GPIO36 rail-low fault evidence.

Runtime source folders still present locally:

- `experiments/20260701_171140_p1_48_hours_later_baseline_air_to_soil_settle_to`
- `experiments/20260701_172559_s1s2_P02_-_s3s4_P03`
- `experiments/20260701_180122_p04_p05_water_halfcup_quartercup`
- `experiments/20260701_183611_p06_48h_check_2probe_maybe_water`
- `experiments/20260701_185816_p07_cachepot_retention_check_no_water`
- `experiments/20260701_191925_p08_p09_48h_measure_only_2probe`
- `experiments/20260701_194006_p10_48h_4probe_check`
- `experiments/20260701_210013_p11_48h_4probe_check`

## Plant-By-Plant Bench Notes

P01:
Four-probe 360 s experiment. Began air-to-soil, then Veronica watered between
1/4 and 1/2 cup by hand. No runoff observed. Plant looked well watered and was
returned to its normal windowsill location. Use as a 48-hour post-watering
top-up response.

P02 and P03:
Single 360 s experiment. s1/s2 were in P02; s3/s4 were in P03. Veronica watered
about 1 cup into each larger pothos and intentionally spread water better than
on 2026-06-29. P02 leaked about 1/8 cup into the temporary bowl; P03 leaked a
little less than 1/8 cup. Important method note: this was distributed hand
watering, not a one-hose pump spot-feed proxy.

P04 and P05:
Monitor baseline first, then a 300 s experiment. P04 used s1/s2 and received a
little more than 1/2 cup with tiny leakage. P04 also had dead leaves trimmed
during the capture. P05 used s3/s4 with difficult rootball contact; s3 was the
more meaningful rootball probe, s4 was edge/adjacent and low confidence. P05
received 1/4 cup slowly with no observed leakage. A later off-capture bottom
reservoir dose for P05 was planned as plant-care support, but it is not part of
the measured experiment unless separately confirmed.

P06:
Anthurium, two-probe 300 s experiment with s1/s2. Soil felt spongey and moist
and was difficult to probe. Veronica gave 1/2 cup; small leakage entered the
catch basin. It may not have needed watering, but the amount was chosen to be
safe before return to summer windowsill exposure. Post-run monitor context
contains sunlight artifacts.

P07:
Cachepot-retention plant, two-probe experiment with s1/s2. Difficult sensor
insertion; inner pot had been out of the outer pot and draining/drying for about
48 hours. The experiment name says `no_water`, but Veronica did dose about 1/2
cup, mostly into the central branch/leaf cluster cores so retained water could
feed slowly from inside the plant structure. No leakage observed. Treat the
filename as stale; treat these notes as the method truth.

P08 and P09:
Measure-only 180 s experiment. s1 in P08 cactus, s2 in P09 succulent. No water
was added to either. P09 contact was barely against outer roots because the pot
is too rootbound for meaningful insertion. Both were returned to the ledge
without watering.

P10:
Four-probe 300 s measure-only experiment. Better soil structure than many of
the rescue plants. No watering; Veronica skipped it after readings and soil
context did not justify a dose.

P11:
Four-probe 300 s experiment. Soil felt drier than P10. Veronica watered about
3/4 cup to the soil plus about 1/8 cup into the central plant core/column. s3
reported an impossible minimum around 180 raw during the experiment, then the
post-run monitor showed s3/GPIO36 drifting to 0. Veronica pulled and wiped s3,
saw no obvious wet components, visible damage, or connector issue, and s3 did
not recover. At exactly 5:23 pm local, s1, s2, and s4 were pulled; they returned
to normal dry-air levels while s3 stayed failed. Monitor logging stopped fully
at 5:44 pm local. For plant analysis, exclude s3 after the impossible drop and
preserve it as fault evidence.

## Immediate Data Quality Rules

- Raw ADC values remain truth; bands are provisional per #170.
- P11 s3/GPIO36 rail-low values are fault evidence, not valid soil moisture.
- P07 filename says `no_water`, but method notes say water was added.
- P04/P05 have a monitor baseline with no in-app metadata; use the copied
  monitor log and these notes to recover that baseline.
- Distributed hand watering is not equivalent to a future one-hose pump output.

## Next Recovery Step

After this packet is safe on disk:

1. Validate every sidecar JSON parses.
2. Generate flat indexes (`windows_index.csv`, `plant_followup_table.csv`) for
   Data if time allows.
3. Open a new Sage evidence issue or ask Workflow whether to ride under #379 /
   #170 / #191.
4. Branch, commit, push, and open a PR with `Refs #N`; do not merge or close it.

-- Sage
