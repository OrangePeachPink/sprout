# Sensor QA (s1–s12) + probe characterization — 2026-07-04

Firmware bench package: raw + summary slices from the Wave-1 probe QA pass and sensor characterization on the
cal-verified classic QA station (`device_id y9d41p`). Narrative packet:
`docs/evidence/2026-07-04-sensor-qa-and-characterization/`.

Fast path for Data:

- `depth_sweep_s12.csv` — the only full **raw** sample stream (131 rows): s12 swept full→empty in 8×12.5%
  pours. Includes pull-out air-dry transients (raw >2000) between levels — filter those for the in-water
  depth curve. Shows the saturation-plateau / lower-50%-is-the-measuring-element finding.
- `qa_summary_s1_s12.csv` — per-probe air / wet-floor / recovery / wiped-dry with PASS verdicts. s1–s4 are
  prior-session (ranges only, in the narrative packet); s5–s12 are this session, exact.
- `s7_drydown.csv` — phase anchors of the unwiped dry-down curve (τ≈2 s, ~95% in ~3–4 s).
- `temp_position_study.csv` — room / 40 °F / 140 °F position-averaged means. Temperature effect (≈0.1
  count/°F) is below the ~55-count position-noise floor (cold→hot z≈0.87) — negligible for irrigation.

Important boundary:

Firmware provides the raw depth samples and per-probe/phase summaries with method notes. Only the depth sweep
is raw; the rest are summaries (full raw serial stayed in the maintainer's local archive). No calibration was
changed — this is characterization input for a future probe-keyed cal (#621), not a ratification.

Refs #476 · #584. Supports #621 · #657 · #170.

— Firmware 🔧
