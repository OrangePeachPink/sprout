#pragma once
#include <stdint.h>
#include "moisture_classifier.h" /* MOISTURE_BOUNDARY_COUNT */

/*
 * calibration.h — per-channel raw->band boundaries (C1 / #170).
 *
 * GENERATED ARTIFACT — the authoritative version is emitted by the #192
 * calibration workbench's export_config(); do NOT hand-tune values here, REGEN.
 * (Firmware owns this FORMAT + the g_mcfg[ch].boundary wiring + the pinning
 * native test; Data owns the values + their provenance — see #170.)
 *
 * Per-channel-as-installed: ch0=s3 ch1=s4 ch2=s1 ch3=s2 (config.h SENSOR_NAMES).
 * A probe<->channel swap INVALIDATES this table -> re-measure (run_meta
 * sensor_position, #321, records which probe sits on which channel).
 *
 * Each channel gets its own boundary[] (the raw->band map) so per-sensor
 * personality is removed; the band->action policy (irrig_chan_cfg) stays SHARED.
 * Boundaries are DESCENDING raw (higher raw = drier); see moisture_classifier.h
 * for the 7-band semantics ([0]=air-dry rail ... [5]=submerged rail). This is a
 * refinement ON TOP of board_capability.h's per-BOARD cal_boundary (the shared
 * baseline every channel starts from) - the interior [1..4] below is identical
 * to the classic board's shared A2 values; only the outer rails diverge.
 *
 * CONFIDENCE: provisional. cal-source: 2026-06-28 full-wipe / full-air-dry
 * per-channel characterization (Sage bench session; raw captures under
 * docs/experiments/20260628_23*_*_full_wipe_and_full_air_dry*.json — no
 * consolidated findings write-up exists yet for this specific session). Step 1
 * (#170) sets only the per-channel OUTER rails [0]/[5] from that wet/dry
 * envelope; the interior [1..4] stays at the shared A2 values, so the WATERING
 * decision is unchanged until Step 2 (per-channel field-capacity anchor, gated
 * on Sage's next round). Caveat (Sage, carried verbatim — not sanded off):
 * practical anchors with margins, not absolute physics limits; s1/s4 dry
 * endpoints still drift a little with residual surface film / temperature, and
 * s2 is wet-biased (gain+offset).
 */

/* Calibrated channel count. Must equal NUM_SENSORS (config.h) and IRRIG_CHANNELS
 * (irrigation.h) — all three are the same 4-probe fleet. Defined locally so this
 * header stays pure C (config.h is constexpr/C++-only) and the native test can
 * include it. main.cpp static_asserts the match. */
#define SENSOR_CAL_CHANNELS 4

/* Provenance for the cal_ch header lines (#404, ADR-0022 vocabulary). Shared
 * across all four channels for now — one bench session produced every rail;
 * #192's export_config regenerates these per-channel if sessions ever diverge.
 * Values are space-free (the cal_ch line is space-separated k=v). */
#define SENSOR_CAL_SRC "wipe_airdry_bench" /* the 2026-06-28 characterization */
#define SENSOR_CAL_DATE "2026-06-28"
#define SENSOR_CAL_CONFIDENCE "provisional" /* ADR-0022; Sage's caveat holds  */
#define SENSOR_CAL_SCOPE "channel" /* per-channel override line (#507 parser) */

static const uint16_t
    SENSOR_CAL_BOUNDARY[SENSOR_CAL_CHANNELS][MOISTURE_BOUNDARY_COUNT] = {
        /* ch0 = s3 (GPIO36/SVP): wet ~969, dry ~3123 */
        {3123, 2140, 1830, 1520, 1150, 969},
        /* ch1 = s4 (GPIO39/SVN): wet ~970, dry ~3096 */
        {3096, 2140, 1830, 1520, 1150, 970},
        /* ch2 = s1 (GPIO34/P34): wet ~958, dry ~3086 */
        {3086, 2140, 1830, 1520, 1150, 958},
        /* ch3 = s2 (GPIO35/P35): wet ~900, dry ~3120  (wet-biased; gain+offset) */
        {3120, 2140, 1830, 1520, 1150, 900},
};
