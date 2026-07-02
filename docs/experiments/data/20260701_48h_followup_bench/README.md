# 2026-07-01 P01-P11 48-Hour Follow-Up Bench

A 48-hour follow-up bench pass for plants P01-P11, after the 2026-06-29
greenhouse characterization session. Short per-plant Experiment Capture runs
(air -> soil settle -> optional small watering) plus the surrounding monitor
logs, promoted into tracked, computable evidence so Data can work from the raw
readings without mining prose.

## Fast Path For Data

- `manifest.json` - provenance, per-plant windows (plant, phase, valid/excluded
  probes, row counts, slice files), analysis-surface refs, honest-gap policy,
  and the reconstitution table for split files.
- `experiment_captures/<id>/` - the raw Experiment Capture for each run: the
  app `manifest.json` plus the capture CSV (whole, or `*_partNN.csv` slices).
- `monitor_logs/` - monitor logs carrying baseline, post-run, sunlight-artifact,
  and P11 fault context not represented by Experiment Capture metadata.
- `docs/experiments/20260701_*.json` - the notebook sidecars for each run.

## Reconstitution Of Split Files

Capture CSVs and monitor logs above the repo's 1024 KB file limit are stored as
line-boundary parts (`<name>_partNN.csv`). Concatenating a file's parts in order
reproduces the original bytes exactly; `manifest.json -> reconstitution` records
each original's SHA-256 and byte size. To rebuild and verify one:

```sh
cat <name>_part*.csv > <name>.csv        # parts are ordered
sha256sum <name>.csv                     # matches reconstitution.original_sha256
```

Files under the limit are stored whole.

## Bench Method, Plant By Plant

- **P01** - four-probe 360 s. Air -> soil settle, then 1/4-1/2 cup by hand; no
  runoff. A 48-hour post-watering top-up response.
- **P02 / P03** - one 360 s run; s1/s2 in P02, s3/s4 in P03. ~1 cup each,
  distributed hand watering (deliberately better spread than 06-29). Minor
  leakage. This is distributed hand watering, not a one-hose pump spot-feed.
- **P04 / P05** - monitor baseline first, then 300 s. P04 on s1/s2 (>1/2 cup;
  dead leaves trimmed mid-capture). P05 on s3 (rootball, meaningful); s4 was
  edge/adjacent and low-confidence. 1/4 cup to P05, no leak.
- **P06** - anthurium, two-probe 300 s (s1/s2). Spongey/moist soil; 1/2 cup with
  small leakage. Post-run monitor contains sunlight artifacts.
- **P07** - cachepot-retention, two-probe (s1/s2). The experiment name says
  `no_water`, but ~1/2 cup was added into the central leaf/branch cores. Treat
  the filename as stale; the method note is the truth.
- **P08 / P09** - measure-only 180 s. s1 in P08 cactus, s2 in P09 succulent
  (barely contacting outer roots; rootbound). No water added.
- **P10** - four-probe 300 s, measure-only. Better soil structure; no watering,
  the readings did not justify a dose.
- **P11** - four-probe 300 s. Drier than P10; ~3/4 cup to soil plus ~1/8 cup to
  the core. s3/GPIO36 read an impossible ~180 raw during the run, then drifted
  to 0 in post-run monitoring. It did not recover after a pull-and-wipe. Exclude
  s3 after the impossible drop; it is preserved as fault evidence. s1/s2/s4
  returned to normal dry-air levels on pull.

## Data-Quality Caveats

- Raw ADC counts remain truth; bands remain provisional pending #170.
- P11 s3/GPIO36 rail-low values are a sensor-path fault, not moisture.
- P07's `no_water` filename is stale; ~1/2 cup was added.
- P04/P05 have a monitor-log baseline with no in-app metadata; use the monitor
  slice plus these notes to recover that baseline.
- Hand-distributed watering is not equivalent to a future one-hose pump output.

## Boundaries

Sage provides the raw slices, observed bench conditions, and probe-validity
notes. Data owns aggregation and any normalized features. Firmware owns any
follow-up on the P11 s3/GPIO36 sensor-path fault.

Refs #379, #170, #191. Supports Data follow-up on #380.

-- Sage
