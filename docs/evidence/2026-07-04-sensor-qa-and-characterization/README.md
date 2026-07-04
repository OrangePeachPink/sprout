# Sensor QA (s1–s12) + probe characterization — 2026-07-04
<!-- cspell:words drydown immersion TLC UMLIFE esptool submerged overwatered reinsertion dielectric deasserted -->
<!-- cspell:words Crockford nonce RFC KITC wetted microsite untethered pours repositioned deadband cad -->

Bench evidence for the Wave-1 **probe QA pass** (all twelve capacitive probes s1–s12 validated
air→wet→recovery) plus a short **sensor-characterization** block: dry-down dynamics, immersion-depth
sensitivity, and a water-temperature-vs-position-noise study. MAC / USB instance IDs are redacted where
they would appear (ADR-0015 / ADR-0020, machine-checked by the identifier-guard, issue #573). This is a
serial-only bench session on the cal-verified QA station — no networked capture.

Bench arrangement: maintainer = hands (probes, water cups, wiping, cadence); Firmware lane = brains-on-call
(serial commands, watched output, verdicts). The QA station is the **classic** (`device_id y9d41p`,
ESP32-D0WD, `esp32dev`) — the only cal-ratified board — read over serial at a session-only fast cadence
(`!cad`, temp). No-reset serial opens (DTR/RTS deasserted) kept the session cadence alive across reads. Raw
per-sample serial streams stay in the maintainer's local archive; the computable slices land as a bench
package (`docs/experiments/data/20260704_sensor_qa_characterization/`).

## QA station (settled)

| Field | Value | How |
| --- | --- | --- |
| Board | classic — `device_id y9d41p`, ESP32-D0WD, `esp32dev` | boot banner / #632 mint |
| Role | cal-verified QA station (per-channel A2 endpoints ratified) | `calibration.h` (#170) |
| Probe model | UMLIFE v2 capacitive (TLC555 oscillator) | silkscreen |
| Port map | ch0=GPIO36=s3 · ch1=GPIO39=s4 · ch2=GPIO34=s1 · ch3=GPIO35=s2 | `config.h` SENSOR_NAMES |
| Read method | serial @ 19200, DTR/RTS deasserted (no reset), `!cad` session cadence | this session |

Note — **channel ≠ probe.** The four sockets are fixed to the board; the twelve physical probes (stickers
s1–s12) are mobile. This QA cycles probes through the four sockets in batches, so a reading is reported by
the **physical probe**, mapped to the socket it occupied (batch offsets: s1–s4 direct, s5–s8 = socket+4,
s9–s12 = socket+8). That probe↔socket independence is exactly the ADR-0027 identity distinction, and it is
why the current per-channel calibration is not yet portable (see Findings, #621).

## QA pass — all twelve probes (air → wet → recovery)

Each probe was read air-dry, submerged in a water cup (wet floor), then pulled, wiped, and re-read
(recovery). Pass = a clean ~2000-count wet swing into the saturated band and recovery to the air-dry
baseline with no sticking. **Result: 12 / 12 PASS — the ≥11 Wave-1 launch bar is cleared with a spare.**

Batch s5–s8 (this session):

| Probe | Air | Wet floor | Recovery | Wiped-dry | Verdict |
| --- | --- | --- | --- | --- | --- |
| s5 | 3083 | 938 | 3069 | 2989 | PASS |
| s6 | 3112 | 977 | 3108 | 3040 | PASS |
| s7 | 3069 | 871 | 3076 | 3022 | PASS |
| s8 | 3077 | 890 | 3078 | 3013 | PASS |

Batch s9–s12 (this session):

| Probe | Air | Wet floor | Recovery | Wiped-dry | Verdict |
| --- | --- | --- | --- | --- | --- |
| s9 | 3079 | 873 | 3082 | 3076 | PASS |
| s10 | 3082 | 871 | 3098 | 3095 | PASS |
| s11 | 3105 | 848 | 3102 | 3103 | PASS |
| s12 | 3082 | 1026\* | 3089 | 3099 | PASS |

Batch s1–s4 (prior bench session, summarized — full per-probe rows in the maintainer's archive): all four
PASS; air ~3057–3113, wet floor ~943–1017, recovery ~2969–3086. s3, previously water-contaminated,
recovered cleanly (dropped 3085→1017, cleanest spread of the batch, recovered →3054).

\*s12's 1026 wet floor was a **batch position artifact**, not a weak probe — see the depth sweep below.

## Characterization

### Dry-down dynamics (s7)

Pulled from full submersion and left to drip **unwiped**, s7's raw climbed back to air-dry very fast:

| Phase | Raw | Time from pull |
| --- | --- | --- |
| Submerged floor | 829 | — |
| Climbing | 1264 | +1.5 s |
| ~95% recovered | 2985 | +3.5 s |
| Settled (plateau) | ~3040 | +6 s |

Time constant **τ ≈ 2 s; ~95% recovery in ~3–4 s; fully settled ~6 s.** Sensor lag is negligible against
soil-moisture dynamics (which move over hours) — the probe is effectively instantaneous for irrigation.

### Immersion-depth sensitivity (s12)

s12 was swept full→empty in **8 × 12.5% water-level increments** (drain direction chosen to avoid splashing
the connector — the #657 corrosion lesson applied as procedure). In-water raw at each level:

| Water level | In-water raw | Band |
| --- | --- | --- |
| Full (to mark) | 885 | submerged |
| −1 pour | 920 | submerged |
| −2 pours | 965 | overwatered |
| −3 pours | 1040 | overwatered |
| −4 pours | 1042 | overwatered |
| −5 pours | 1158 | well-watered |
| −6 pours | 1450 | well-watered |
| Emptied | ~3080 | air-dry |

**Headline: sensitivity is bottom-heavy.** The upper ~50% of the water column is a saturation plateau
(full→−4 pours moved raw only ~150 counts); the lower ~50% carries ~90% of the dynamic range (~2000 counts).
**The bottom half of the blade is the real measuring element.** The 95%-wet point (raw ≈ 999) held until
about a third of the water was drained. Full raw curve (131 samples): `depth_sweep_s12.csv` in the package.

### Water temperature vs position noise

Tested at full immersion, cup #1 = 40°F ice water, cup #2 = 140°F (a **100°F / ~55°C span**, ~23% dielectric
swing). Position-averaged means (multi-reposition):

| Condition | Mean raw | n | sd |
| --- | --- | --- | --- |
| Room (ambient control) | 896 | 4 | — |
| 40°F cold (cup #1) | 902.5 | 10 | 32.1 |
| 140°F hot (cup #2) | 912.8 | 22 | 28.6 |

Cold→hot Δ = **+10 counts, z ≈ 0.87 — not a statistically significant separation.** Re-seating the *same*
cup at a slightly different position swung the reading **~55 counts** — larger than the temperature
difference across the entire ice-to-near-boiling range. The +10 is in the physically-correct direction
(hot = lower dielectric = drier), but it is buried under position noise.

**Conclusion: water temperature ≈ 0.1 count/°F at saturation — negligible for irrigation.** A realistic
windowsill soil-temp swing (~10–20°F) would move the reading 1–2 counts, sub-noise. No temperature
compensation needed; position/immersion is the only variable that matters. s12 returned to a clean air-dry
baseline (3078) after hot exposure with zero thermal drift.

## Findings & relay notes

- **Classifier `level` label lags raw by ~1 sample (~2 s) on fast transients** — e.g. raw 888 still labeled
  `dry`, raw 2985 still `submerged` for one cadence tick. Deadband/debounce hysteresis (correct anti-flap
  behavior in soil); a relay note for the Data/classifier lane, not a defect.
- **Calibration is per-*channel*, not per-*probe* (#621).** `calibration.h` keys the raw→band endpoints to
  the socket (`SENSOR_CAL_SCOPE "channel"`) and warns a probe↔channel swap invalidates the table. With mobile
  probes (ADR-0027) the cal should ride *with* the probe; today's depth/position data is the kind of input a
  probe-keyed calibration would need. Note added to #621.
- **Corrosion survey → #657.** The four deployed probes all show onboard-connector corrosion by degree
  (s1 minimal, s2 notable, s3 minor, s4 minimal); the eight never-deployed spares (s5–s12) are pristine. The
  cause is deployment watering (leaf-dispersed water wicking into the unsealed JST), not storage — so a
  waterproofing cycle belongs before the pumps (#94) install, and spares need nothing.
- **s12 is normal.** Its 1026 batch wet-floor was position / neighbor-coupling (shallower seating plus
  flat-probe hydro-suction masking sensing area); a solo full-depth read floored at 889, in the fleet pack.

## Honest scope — what is NOT here

- The temperature study was run **only at full saturation** — the least-sensitive point per the depth sweep.
  A proportionally larger temp effect could exist mid-range; it was not measured (and stays small scaled to
  real soil-temp swings).
- QA / temperature / dry-down numbers are **per-probe or phase summaries**; only the depth sweep is a full
  raw sample stream. Full raw serial stayed in the maintainer's local archive per convention.
- **No calibration was changed** and no per-probe cal was created — this is characterization input, not a cal
  ratification. s5–s12 still fall back to the shared board baseline until characterized on their sockets.
- **No plant assignments** — probe↔plant mapping is install-day (Block E) work. Block B (C5 continuity) is
  still pending before probes carry signal on the C5 boards.

## Future work

- **Stainless waterproof in-soil temperature probes** (maintainer-owned; maker / voltage / driver unknown) →
  a future bring-up + characterization session; would give the telemetry schema a real soil-temp channel.
- **Fixed-position jig** to isolate a sub-50-count temperature (or mid-range) effect if ever wanted —
  hand-dipping cannot resolve it.
- **Finer depth curve** (syringe the water without pulling the probe) to fill the 1500–3000 mid-band the
  coarse final pour skipped.

## Session provenance

Firmware bench session, 2026-07-04 (maintainer coordinating with other lanes off-bench). Facts here are
serial-observed at capture time on the classic QA station; raw per-sample streams and any photos kept in the
maintainer's local archive. Statistics (means, sd, z) computed from the session's captured samples.

Refs: #476 · #584 · #621 · #657 · #170 · #573 · #381 · #601 · ADR-0027 · ADR-0022.

— Firmware 🔧
