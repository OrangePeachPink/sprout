# P01-P07 rescue survey recovery - findings

**Date:** 2026-06-29 local CDT
**Lane:** Sage
**Authority:** BENCH EVIDENCE, recovered from monitor logs and transcript markers.
This is not A2/C1 calibration-ratified evidence.
Machine sidecar: [`20260629_sage_p01_p07_rescue_survey_recovery.json`](20260629_sage_p01_p07_rescue_survey_recovery.json).

## Scope

This report recovers the bench notebook for a broken Sage thread during the
P01-P07 plant survey. Experiment Capture was not reliable for P02-P07, so those
segments are documented as a single continuous monitor-log survey with transcript
event markers.

Primary sources:

- P01 morning monitor logs:
  `logs/Sprout ESP32_20260629_121817.csv`,
  `logs/Sprout ESP32_20260629_135003.csv`
- P02-P07 continuous monitor log:
  `logs/Sprout ESP32_20260629_180631.csv`
- Existing P01 experiment sidecars:
  `docs/experiments/20260629_030551_p1_post_dry_rewatering.json`,
  `docs/experiments/20260629_032448_overnight_water_soil_equilib_test.json`
- Recovered Sage thread line markers from thread
  `019f0ea6-a148-7a91-bba6-0d07f99b7750`

## Device and logging provenance

The P02-P07 rescue survey used monitor logging, not isolated Experiment Capture.
The active rescue log header reports:

- Firmware: `0.7.0`
- Git revision: `8e5d73c`
- Logger: `plants_logger_0_4`
- Session: `706a34`
- Cadence: `5000 ms`
- Sensor mapping:
  - `s3` = GPIO36
  - `s4` = GPIO39
  - `s1` = GPIO34
  - `s2` = GPIO35

Experiment Capture was blocked because the host path expected session-only
cadence command form `!cad,<ms>,temp`, while the flashed firmware still appeared
to accept only `!cad,<ms>`. The recovery therefore treats P02-P07 as bounded
monitor-log evidence.

## Key findings

- P01 accepted about 1 cup by slow distributed top watering with no observed
  runoff, but the four probe locations did not converge overnight.
- P02 and P03, both very parched pothos plants, showed fast runoff/channeling
  despite slow distributed watering.
- P04 showed visible bypass in a shallow clear insert: water reached the bowl
  while parts of the soil still did not visibly soak.
- P05 was not calibration-grade because the tight rootball allowed only `s1`
  and `s4` insertion; about 1/2 cup produced fast runoff, and escaped roots in
  the bowl may have been the main uptake path.
- P06, an Anthurium "Lovable Hearts", behaved differently: early seepage was
  reabsorbed after a pause, then sustained pooling appeared only after about
  1 2/3 cups total. This is the best pulse-and-pause case in the survey.
- P07 had old standing water in the decorative/cachepot despite about 3 weeks
  without watering. It was held in measure-only mode, no water was added, and
  probes were pulled at 15:57 local.

## Timeline

| Plant | Segment | Key times, local CDT | Water / action | Evidence quality |
|---|---|---|---|---|
| P01 | Morning continuation after overnight equilibration | 07:18:17-12:16:24; pre-pull at ~12:16 | Prior dose about 1 cup, no runoff | Useful plant microzone evidence; not uniform calibration |
| P02 | Largest home pothos, parched | Watering start ~13:11:12; runoff by 13:14:25 | About 1.5 cups applied; about 0.5 cup runoff estimated | Good runoff/water-balance evidence; weak four-probe calibration |
| P03 | Other large pothos, parched | Probes 13:25:22; water 13:28:08; runoff 13:30:08; pull 13:40:20 | 2 cups total; 1/3 cup runoff measured | Good runoff evidence; S3/S4 confounded after targeted pour |
| P04 | Likely dracaena/cane-type, shallow clear insert | Probes 13:48:38; pooling/runoff 13:52:30; pull 14:06:17 | Up to 1 cup; some runoff wicked back | Strong physical bypass evidence; low calibration confidence |
| P05 | Confirmed 6 inch Dracaena marginata braided | Water 14:18:26; runoff 14:20:19; pull 14:26:35 | About 1/2 cup caused fast runoff | High plant-condition evidence; low calibration confidence |
| P06 | Anthurium "Lovable Hearts" | Setup 14:37:27; water 14:38:44; pool 14:43:59; pull 14:59 | About 1 2/3 cups total; remaining runoff >50 mL and <1/4 cup | Strong staged-dosing evidence; recovery-state confounded |
| P07 | Bromeliad/rosette-like, ID uncertain | Prep ~15:10; probes in 15:19:30; measure-only through 15:57 pull | No water added | Important cachepot/standing-water evidence; no-water decision recorded |

## P01 notes

P01 was the small home pothos. The prior evening P01 received about 1 US cup
(about 237 mL) by slow distributed top watering. No visible runoff was observed
and the paper towel under the inner pot stayed dry.

The overnight experiment
`20260629_032448_overnight_water_soil_equilib_test` found that the four probe
locations did not equalize into one shared soil value. During the morning
monitor continuation, the bounded logs contain 14,302 rows from 07:18:17 to
12:16:24 local. End-of-window values were:

| Sensor | Median raw | Last raw | Last band |
|---|---:|---:|---|
| s1 | 1272 | 1280 | well watered |
| s2 | 1431 | 1437 | well watered |
| s3 | 1244 | 1251 | well watered |
| s4 | 1126 | 1138 | overwatered |

Evidence interpretation: P01 stayed locally heterogeneous. `s2` remained the
higher/drier channel and `s4` remained the lowest/wettest channel. Because no
runoff was observed, the `overwatered` band label for `s4` should remain
provisional, not treated as proof the plant was globally overwatered.

## P02 notes

P02 was the largest home pothos and was described as very dry. The isolated
experiment path was abandoned for this plant because Experiment Capture was
blocked, so the continuous monitor log is the evidence source.

Thread markers:

- Start fallback monitor evidence: line 3638
- User stated sensors were in soil and settled before watering: line 3644
- Watering lower-bound timestamp: 13:11:11.95, line 3657
- Runoff observed by: 13:14:25.56, line 3671
- Water balance correction: 1.5 cups applied, about 0.5 cup runoff, line 3716

The P02 water balance is the strongest evidence: despite being far larger than
P01, P02 appeared to retain only about 1 cup from a 1.5 cup pour, with about
0.5 cup escaping into the bowl/paper towels. This supports hydrophobic dry
soil, preferential flow, and the distinction between water applied and water
actually retained by the root zone.

Calibration caveat: `s4` stayed air-dry through the P02 segment while the other
channels showed much wetter local response. This makes P02 useful for runoff
and channeling behavior, but not a clean four-probe calibration record.

## P03 notes

P03 was the other large pothos, slightly smaller than P02, and also very
parched.

Thread markers:

- Probes inserted: 13:25:22.78, line 3696
- Watering started: 13:28:08.09, line 3726
- First runoff / initial stop: 13:30:08.05, line 3740
- Targeted S4 diagnostic pour: 13:31:58.18, line 3757
- Segment end / probes pulled: 13:40:20.22, line 3786
- Runoff measured: about 1/3 cup, line 3800

P03 repeated the P02 parched-pothos pattern: careful distributed watering still
hit runoff quickly. The first clean response showed `s1`, `s2`, and `s3` in
well-watered ranges while `s4` stayed air-dry. After `s4` stayed anomalously
dry, a wiring check and targeted pour near S4/S3 contaminated the later S3/S4
readings. Treat the initial runoff behavior and S1/S2/S3 wet response as useful;
treat later S3/S4 readings as contact/handling-confounded.

Approximate water balance:

- Total poured: 2 cups
- Captured runoff: about 1/3 cup
- Not captured / retained / otherwise held: about 1 2/3 cups
- Caveat: retained does not imply uniformly absorbed.

## P04 notes

P04 was an unknown plant, likely dracaena/cane-type, in a wide shallow
transparent insert. The probes may not have reached their normal maximum
insertion line.

Thread markers:

- Between-plant air-dry/skylight check ended: 13:47:05.74, line 3814
- P04 probes inserted / settling started: 13:48:38.52, line 3828
- Watering/runoff observed: 13:52:30.18, line 3850
- Visual bypass notes: lines 3859 and 3869
- Segment end / probes pulled: 14:06:17.94, line 3898

P04 received up to about 1 cup in small sips across the surface. Significant
pooling appeared in the temporary bowl. The clear insert showed water passing
through while lower soil still did not visibly soak evenly. Some runoff later
appeared to wick back from the bowl.

This is strong physical evidence for bypass flow and shallow-pot limitations,
but low-confidence calibration evidence because the pot geometry and insertion
depth were not controlled.

## P05 notes

P05 was confirmed from its label as a 6 inch Dracaena marginata, braided.
Only two probes were inserted because the rootball was very tight and forcing
four probes risked damage and bad contact.

Thread markers:

- Two-probe setup note: 14:16:24.94, line 3946
- Watering start: 14:18:26.02, line 3968
- Confirmed plant ID: line 3977
- First runoff / bypass marker: 14:20:19.36, line 3987
- User corrected inserted probes to `s1` and `s4`: line 4002
- Probe pull / transition: 14:26:35.78, line 4010
- Escaped-root and bowl-water observation: lines 4016 and 4029

P05 received about 1/2 cup and already had water pouring out the bottom. The
surface visibly beaded/balled water and sent it down the sides. Afterward,
about 1/8 cup remained in the bowl, and roots were visibly extending beyond the
pot into that bowl water. Veronica estimated at least 1/4 cup bypassed the
tight rootball into the bowl, with roughly half of that possibly reabsorbed by
escaped roots.

This is not a clean soil-moisture calibration case. It is high-value evidence
that rootbound plants can bypass from top watering while still taking up some
water from escaped roots below the pot.

## P06 notes

P06 was Anthurium "Lovable Hearts", drought-stressed with lost hearts/blooms
from underwatering. Four probes were inserted radially because insertion across
the expected root plane was difficult.

Thread markers:

- Setup: 14:37:27, line 4044
- Watering start: 14:38:44, line 4054
- First dose marker: 14:41:18, line 4072
- Second-dose start after reabsorption: 14:42:44, line 4082
- Stop / sustained pooling: 14:43:59, line 4095
- S1 response visible: 14:46:57, line 4109
- S2 response visible: 14:48:24, line 4122
- Probe pull: 14:59, line 4167
- Remaining bowl water: >50 mL and <1/4 cup, line 4182

P06 received about 1.0 to 1.25 cups first, causing minor seepage. That seepage
was reabsorbed within roughly 1 to 2 minutes. Continued small doses brought the
total to about 1 2/3 cups, at which point sustained bowl pooling appeared.
After pooling, `s1` showed the clearest wetward response first, followed by
`s2`; the pot did not respond uniformly across all four probes.

This is the clearest evidence in the survey that pulse-and-pause watering can
work better than one continuous pour for at least some plants/pots. It is still
not calibration-grade because P06 was in a rescue/recovery state.

## P07 notes

P07 looked bromeliad/rosette-like, but the exact ID was uncertain. The main
finding was not soil dryness; it was hidden standing water.

Thread markers:

- P7 prep / photo context: lines 4196 and 4199
- Standing-water cachepot observation: line 4211
- Do-not-water-yet decision rule: line 4217
- Probes in: line 4226
- Restart / hold, no watering: line 4230
- Measure-only baseline after restart: line 4248
- Continuation update: probes pulled at 15:57 local with no water added; dashboard
  screenshot captured current readings before/at pull.
- Post-pull contact correction: `s3` had virtually no soil contact. It was
  barely inserted, shallow, and not meaningfully coupled to the soil. Treat
  P07 `s3` as contact-invalid for soil interpretation.

Despite about 3 weeks without watering, P07 had standing water in the outer
decorative/cachepot from an older watering. The inner pot fit tightly in the
tall narrow outer pot, making it hard to see whether water was too much or too
little. P07 was therefore held in measure-only mode: probes inserted, S2
adjusted, and no watering added. The probes were pulled at 15:57 local so the
sensors could be wiped and returned to open-air dry state before the next plant.

Dashboard screenshot at pull showed current readings:

| Sensor | Dashboard raw | Dashboard band |
|---|---:|---|
| s1 | 1773 | OK / Ideal |
| s2 | 2175 | dry |
| s3* | 2824 | dry |
| s4 | 2517 | dry |

Monitor-log window 15:19:30-15:57:12 local, excluding immediate pull artifacts:

| Sensor | Median raw | Last raw | Last band |
|---|---:|---:|---|
| s1 | 1863.5 | 1777 | OK |
| s2 | 2238 | 2186 | dry |
| s3* | 2898 | 2836 | dry |
| s4 | 2435 | 2473 | dry |

`*` P07 `s3` is contact-invalid because post-pull inspection found it was only
barely sitting in the pot with no real depth or soil contact.

Interpretation: the measured probe zones looked dry to needs-water, but the
standing-water cachepot history means lower roots may have been wet or oxygen
limited. Do not treat the local dry readings as proof that immediate watering
was safe; also exclude `s3` from soil interpretation because it lacked contact.
The standing-water finding overrides the generic soil-sensor watering impulse
for this plant. P07 was closed as no-water-added and needs a cachepot
spacing/drainage correction before normal watering guidance can be trusted.

## Survey-level implications

1. Applied water volume is not retained water volume.
2. Runoff is not a reliable "fully watered" signal in parched or rootbound pots.
3. Probe readings are local. They can be true locally while misleading for the
   whole pot, especially with channeling, shallow insertion, tight rootballs,
   or standing-water cachepots.
4. Pump logic should prefer small pulses plus settle/soak pauses over one large
   continuous dose.
5. Rescue-state plants are valuable for field behavior, but they should not be
   used as calibration authorities without controlled follow-up.

## Open follow-ups

- For P07, keep the standing-water/cachepot issue as the primary care finding:
  dry outside the cachepot, add a riser/pebbles or other air gap, and only
  consider a later measured micro-dose after lower-root condition is checked.
- Continue with P08, described before measurement as a very small cactus with a
  green triangular base and pink round top/side domes; likely a grafted cactus
  form, but ID is not confirmed.
- Create separate future calibration runs for non-rescue plants P10/P11 after
  they are measured.
- File or link the Firmware/Data contract issue for Experiment Capture command
  mismatch: host `!cad,<ms>,temp` vs firmware `!cad,<ms>`.
- Preserve the recovered line markers and log-window summary until the issue
  notes/PR evidence map are written.

- Sage
