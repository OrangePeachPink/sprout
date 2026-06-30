# 2026-06-29 Greenhouse Bench Arc Recovery

Sage recovery bundle for the P01-P11 greenhouse bench session.

This promotes computable evidence out of ignored monitor logs into tracked files so Data can build
the requested one-time bench-day arc view without mining prose.

Fast path for Data:

- `plant_arc_table.csv` - one row per plant with recovered start, wettest, ending checkpoint,
  valid probes, spread, confidence, and completeness notes.
- `plant_arc_observations_long.csv` - the same arc observations in long form for easy plotting.
- `windows/p*_*.csv` - raw monitor rows sliced by plant segment, with Sage probe-inclusion annotations.

Enrichment:

- `windows_index.csv` - index of plant and non-plant slices.
- `manifest.json` - provenance, honest-gap policy, source logs, and Data contract candidates.
- non-plant windows preserve air-reset, sun/reset, and method-check evidence, but they should
  not block the fixed visual.

Important boundary:

Sage provides the recovered readings and probe-quality evidence. Data owns the final
one-read-per-plant aggregation rule for #380. Empty arc cells are honest gaps, not zeroes.

Refs #379. Supports #380.

— Sage
