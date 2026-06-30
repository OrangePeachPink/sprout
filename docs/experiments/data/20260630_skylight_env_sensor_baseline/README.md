# 2026-06-30 Skylight Env Sensor Baseline

Sage recovery bundle for the first live SHT45 + AS7263 bench session.

This promotes ignored monitor logs into tracked evidence so Data can analyze the
skylight/thermal confound and the new `plants.env` stream without mining chat.

Fast path for Data:

- `channel_summary.csv` - per sensor/channel min, max, median, first/last,
  quality flags, and AS7263 rail counts.
- `time_bin_summary.csv` - 5-minute channel summaries for quick plotting.
- `operator_events.csv` - exact and qualitative bench events from the thread.
- `source_logs_index.csv` - source sessions, row counts, and logger gaps.
- `raw_slices/*.csv` - original tidy rows plus source and phase hints.
- `manifest.json` - provenance, issue routing, and honest-gap policy.

Bench conditions:

- No plant, soil, water, or cup was present for this run.
- Four soil probes were air-dry on the bench in the skylight path.
- S2/S3 were silkscreen-side up; S1/S4 were silkscreen-side down.
- SHT45 and AS7263 were on the breadboard near the ESP32.
- AS7263 was aimed at the skylight beam; it is context, not plant truth.

Important observations:

- SHT45 rose from the high-20s C into the mid-30s C during direct sun.
- AS7263 `nir_680` and `nir_860` frequently railed at raw `51201`.
- The rail behavior is evidence for #416 gain/headroom provenance.
- Soil-probe raw outliers during the long run are handling artifacts, not water.
- Logger gaps/restarts are surfaced in `source_logs_index.csv`.

Boundaries:

Sage provides raw slices, observed bench conditions, and event/provenance notes.
Data owns correlation analysis and any normalized skylight/thermal features.
Firmware owns any follow-up emission change, including ESP32 die temperature.

Refs #345 and #416. Supports #170 and #380.

— Sage
