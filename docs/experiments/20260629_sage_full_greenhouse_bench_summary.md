# 2026-06-29 Sage full greenhouse bench summary

**Date:** 2026-06-29 local CDT
**Lane:** Sage
**Authority:** BENCH EVIDENCE, not calibration-ratified.

This summarizes the full P01-P11 bench suite. The purpose was not to produce a
final moisture calibration; it was to capture real plant behavior, probe
placement limits, runoff/resoak behavior, and automation implications from one
complete greenhouse pass.

## Source evidence

- [`20260629_sage_p01_p07_rescue_survey_recovery.md`](20260629_sage_p01_p07_rescue_survey_recovery.md)
- [`20260629_sage_p01_p07_rescue_survey_recovery.json`](20260629_sage_p01_p07_rescue_survey_recovery.json)
- [`20260629_sage_p08_p11_continuation.md`](20260629_sage_p08_p11_continuation.md)
- [`20260629_sage_p08_p11_continuation.json`](20260629_sage_p08_p11_continuation.json)
- `logs/Sprout ESP32_20260629_180631.csv`

## Executive summary

All 11 plants received at least an initial watering or no-water decision with
sensor/log evidence. The physical work would normally take only a few minutes;
the rigorous bench pass took about 6 hours because each plant had placement,
baseline, watering, runoff, and interpretation notes captured.

The strongest system finding is that one local soil probe, or even four local
probes, cannot be treated as whole-pot truth without context. Probe readings are
true locally, but pot geometry, roots, hydrophobic dry soil, foliage access,
tray water, and sensor contact can dominate the interpretation.

The best autonomous-watering policy implied by this session is conservative:
pulse, observe, stop on runoff or tray fill, and do not chase one dry channel
while another channel or the pot/tray state already shows water has arrived.

## Plant-level findings

| Plant | Main evidence | Bench interpretation |
| --- | --- | --- |
| P01 | Small pothos; about 1 cup from prior evening, no runoff; overnight readings stayed locally heterogeneous. | Useful clean plant microzone evidence; not a uniform calibration endpoint. |
| P02 | Largest parched pothos; about 1.5 cups applied and about 0.5 cup runoff. | Strong hydrophobic/preferential-flow evidence; applied water did not equal retained root-zone water. |
| P03 | Parched pothos; 2 cups applied and about 1/3 cup runoff, with later S3/S4 confounded by targeted pour. | Confirms parched-pothos fast runoff/channeling; use early response and water balance, not late S3/S4 as calibration. |
| P04 | Shallow clear insert showed visible bypass and later wick-back behavior. | Physical bypass can make runoff appear before lower soil is uniformly wetted. |
| P05 | Dracaena marginata; about 1/2 cup produced fast runoff, escaped roots may affect uptake path. | High plant-condition evidence; low calibration confidence. |
| P06 | Anthurium; staged dosing to about 1 2/3 cups, with early seepage reabsorbed before sustained pooling. | Best pulse-and-pause evidence from the rescue group. |
| P07 | Old standing water found in cachepot despite about 3 weeks without watering; no water added; S3 contact invalid. | Hidden standing water overrides generic dry-sensor impulse. Fix drainage/air gap before trusting watering guidance. |
| P08 | Tiny likely moon/grafted cactus; S1/S3 dry before watering; about 1/4 cup caused leakage. | Cactus care must be plant-specific; this is a micro-dose case, not houseplant logic. |
| P09 | Rootbound succulent; probe at rootball/soil interface; less than 1/4 cup flowed out almost immediately. | Strong rootbound/low-retention evidence; useful local response, not a normal in-soil calibration point. |
| P10 | Office-cared pothos; about 1 cup, tray fill about 1/4 inch/1 cm, fully reabsorbed by 17:40; moist soil clumped on probes. | Better soil cohesion than rescue pothos, but still strong microzone differences after watering. |
| P11 | Office-cared plant with center-core watering path; tray filled about 1/2-3/4 inch, about 2/3 reabsorbed by 18:24; still non-uniform. | Tray resoak helps but does not quickly equalize local readings. Stop and observe rather than add more water. |

## Cross-cutting conclusions

- Raw ADC plus band remains the honest data layer. Do not convert these results
  into a real moisture percentage.
- Local disagreement is signal, not noise. Cross-channel spread often described
  real microzones, contact differences, and water pathways.
- Runoff is not a global "fully watered" signal. It can mean saturation,
  bypass, hydrophobic soil, rootbound flow, tray-mediated resoak, or simply pot
  geometry.
- Tray state is part of the plant state for P10 and P11. A tray can be a
  temporary reservoir, not just waste runoff.
- Probe contact must be logged as evidence. P07 S3 and P10 S1 show that a
  plausible-looking number can be locally or mechanically questionable.
- Plant-specific pathways matter. P08 cactus micro-dosing, P09 rootball
  interface, P10 pothos foliage obstruction, and P11 center-core watering cannot
  share one naive trigger rule.

## Lane implications

**Data:** add a first-class event annotation layer around raw logs so watering
start, probe pull, tray fill, contact caveats, and no-water decisions can be
queried beside raw samples. A DuckDB/parquet daily bench view would make this
day much easier to slice.

**Firmware:** autonomous watering should favor bounded pulses and observation
windows. Sensor disagreement should lower confidence and pause the decision,
especially when runoff, tray fill, or a strongly wet local channel is present.

**Trellis:** calibration ADRs should encode confidence stages, contact quality,
microzone disagreement, and plant-specific pathway constraints before any
automation is promoted from plant-deployed toward autonomous-enabled.

**Workflow:** likely follow-up issues belong in event annotation, tray/resoak
modeling, controlled probe-orientation testing, sensor-contact procedure, and
plant profile policy.

**DX/Design:** this is a strong public story for honest instrumentation: Sprout
does not pretend a fake percentage is truth; it explains raw local evidence,
uncertainty, and calm next actions.

## Recommended next work

1. Ask Data for an event-annotated DuckDB/parquet view over the 2026-06-29 bench
   logs, including plant segment, probe event, watering event, tray event, and
   contact caveat fields.
2. Run a controlled Sage front/back orientation test in a cup or test soil where
   depth, contact, soil, water amount, and pot-wall distance can be held fixed.
3. Draft a Firmware policy issue for bounded autonomous watering: pulse,
   observe, stop on runoff/tray fill, and require confidence before repeating.
4. Keep calibration bands provisional until raw endpoints and contact quality
   are reviewed plant by plant.

- Sage
