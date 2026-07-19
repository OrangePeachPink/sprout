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
 * Boundaries are DESCENDING raw (higher raw = drier); see moisture_classifier.h
 * for the 7-band semantics. As of the #995 ratification (2026-07-19) boundary[]
 * is a per-BOARD in-soil ladder ([0]=Faint floor .. [5]=Soaked ceiling) shared
 * across all four channels - the air/water RAILS that per-channel #170 measured
 * now live off-ladder in the anchor layer (#1152), so the per-channel divergence
 * collapsed to one board-level set. Per-instance refinement is a later
 * registry+cal job (Data). Kept per-channel in shape for that future seam.
 *
 * CONFIDENCE: provisional. cal-source: #995 dual-envelope band ratification
 * (2026-07-19) - a fresh in-situ peak-summer dry-down (#1174) measured BOTH the
 * classic and C5 envelopes densely; Data derived the seven-bracket sets and they
 * passed the #1153 parameterized cal-suite (#1211). Supersedes the 2026-06-28
 * per-channel #170 rails. Caveat (still provisional): peak-July drying is the
 * fast-transpiration / aggressive end of the range; slower-light months dry more
 * gently, so these edges run a touch dry-biased by design.
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
#define SENSOR_CAL_SRC                                                         \
    "wet_rederive_1236" /* #1236 wet-end re-derivation      */
#define SENSOR_CAL_DATE "2026-07-19"
#define SENSOR_CAL_CONFIDENCE "provisional" /* ADR-0022; Sage's caveat holds  */
#define SENSOR_CAL_SCOPE "channel" /* per-channel override line (#507 parser) */

static const uint16_t
    SENSOR_CAL_BOUNDARY[SENSOR_CAL_CHANNELS][MOISTURE_BOUNDARY_COUNT] = {
        /* #995 ratified the bands to a per-BOARD in-soil ladder (both envelopes
         * measured, 2026-07-19), so all four classic channels now share the same
         * board-level edges; per-channel outer rails moved to the off-ladder
         * anchor layer (#1152). ch0=s3 ch1=s4 ch2=s1 ch3=s2. */
        {2293, 2086, 1879, 1636, 1393, 1150},
        {2293, 2086, 1879, 1636, 1393, 1150},
        {2293, 2086, 1879, 1636, 1393, 1150},
        {2293, 2086, 1879, 1636, 1393, 1150},
};
