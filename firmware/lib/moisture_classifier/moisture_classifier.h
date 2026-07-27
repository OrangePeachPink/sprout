/*
 * moisture_classifier.h
 * -----------------------------------------------------------------------------
 * Capacitive soil-moisture classifier for the plants controller.
 *
 * Pipeline per measurement:
 *   raw samples (e.g. 64)
 *     -> trimmed mean (drop N high + N low)        [intra-measurement denoise]
 *     -> dead-band hysteresis -> candidate band    [kills boundary chatter]
 *     -> N-consecutive persistence -> committed     [kills transients]
 *
 * Raw is INVERTED: higher raw = drier (lower moisture). Boundaries are stored
 * in strictly DESCENDING raw order as the level index increases.
 *
 * #995 (2026-07-19): all 7 levels are IN-SOIL display bands (the Faint..Soaked
 * mood ladder). Level 0 (Faint) and level 6 (Soaked) are the DRY/WET edge bands
 * - shown like any other. The true off-ladder "probe in air / probe in water"
 * exceptions moved to the anchor layer (#1152); until it lands, Faint doubles as
 * the "probe may not be in soil" hint (mood-band-map diagnosticNote).
 *
 * Framework-agnostic: you fill the sample buffer (analogRead / adc1_get_raw),
 * this module does the rest. No dynamic allocation, no floats required.
 * -----------------------------------------------------------------------------
 */
#ifndef MOISTURE_CLASSIFIER_H
#define MOISTURE_CLASSIFIER_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MOISTURE_LEVEL_COUNT     7
#define MOISTURE_BOUNDARY_COUNT  6   /* == MOISTURE_LEVEL_COUNT - 1 */

/* Driest (idx 0) -> wettest (idx 6). 7-band scheme (moisture_classifier_spec). */
/* #995 (2026-07-19): all 7 are IN-SOIL display bands (the mood ladder Faint..
 * Soaked, host mood-band-map.json keys on these fwLevel names - do NOT rename).
 * The old air-dry/submerged "diagnostics" are now the Faint/Soaked edge bands;
 * the true off-ladder probe-in-air / probe-in-water exceptions move to the
 * anchor layer (#1152). Faint doubles as "probe may not be in soil" per the
 * mood-map's diagnosticNote until #1152 lands the precise anchor check. */
typedef enum {
    MOIST_AIR_DRY = 0, /* Faint  - driest in-soil (see #1152 air anchor)*/
    MOIST_DRY, /* Parched                                      */
    MOIST_NEEDS_WATER, /* Thirsty                                      */
    MOIST_OK, /* Content - healthy band                       */
    MOIST_WELL_WATERED, /* Thriving - field capacity                    */
    MOIST_OVERWATERED, /* Refreshed - fresh over-soak                  */
    MOIST_SUBMERGED /* Soaked - wettest in-soil (see #1152 water anc)*/
} moisture_level_t;

/* Confirm-window class - a CONFIRM-SPEED grouping, not a display/diagnostic
 * claim (#995: all 7 levels are in-soil bands). The two edge bands keep distinct
 * timing: a fresh Soaked over-soak is recognized fast, the Faint edge settles at
 * its own pace, the mid soil bands settle slowly. Names retain the _DIAG suffix
 * for history; they mean "edge band" now, not "diagnostic". */
typedef enum {
    MCLASS_DRY_DIAG = 0, /* idx 0    (Faint edge)  */
    MCLASS_SOIL, /* idx 1..5 (mid soil)    */
    MCLASS_WET_DIAG /* idx 6    (Soaked edge) */
} moisture_class_t;

/* Sensor-type profile (ADR-0019 §3). Selects the raw->band DIRECTION (and, when a
 * resistive profile is committed, its curve + read strategy). CAPACITIVE is the
 * committed v1 path (higher raw = drier; boundaries DESCENDING). RESISTIVE is an
 * architecture-ready but UNCOMMITTED seam (inverted: higher raw = wetter; boundaries
 * ASCENDING) — it ships NOTHING calibrated (no probes to baseline), so a channel set
 * RESISTIVE needs a contributor's boundary[] + a power-only-during-read excitation
 * strategy in the sampler. Default 0 = CAPACITIVE keeps existing configs unchanged. */
typedef enum {
    SENSOR_CAPACITIVE =
        0, /* committed: higher raw = drier (descending boundary[]) */
    SENSOR_RESISTIVE /* PROVISIONAL seam: higher raw = wetter (ascending)     */
} moisture_sensor_type_t;

typedef struct {
    /* --- acquisition --- */
    uint16_t sample_count;     /* samples per measurement (your 64)            */
    uint8_t  trim_each_side;   /* drop this many high AND low (8 -> 48/64)      */

    /* --- hysteresis --- */
    uint16_t deadband_raw;     /* total dead-band width in raw counts (~60)    */

    /* --- persistence (confirmation), in milliseconds --- */
    uint32_t confirm_ms_soil; /* mid soil bands idx 1..5 (~8000)             */
    uint32_t confirm_ms_dry; /* Faint edge idx 0 (~8000)                    */
    uint32_t confirm_ms_wet; /* Soaked edge idx 6, fast (~3500)             */
    uint32_t loop_period_ms;   /* measurement cadence; ms->count uses this     */

    /* --- health --- */
    uint16_t spread_warn_raw;  /* trimmed-set range above this flags a fault;
                                  0 disables the check                         */
    /* #1152 kinematics (TELEMETRY_SCHEMA S4, Data-ratified): a single-step
     * |delta| larger than this is faster than soil physically moves at the
     * sampling cadence - the reading may be real but the JUMP is not trustable
     * (probe yanked/reseated, contact break). Emits SUSPECT + fault=rate_spike;
     * raw is preserved either way (ADR-0006). 0 disables the check.
     * PROVISIONAL value - see MOISTURE_CFG_DEFAULT. */
    uint16_t max_delta_raw;

    /* --- calibration thresholds (DESCENDING) ---
     * boundary[i] separates level i from level i+1. #995-ratified in-soil edges
     * (2026-07-19) - ALL six are in-soil dividers now; the air/water rails left
     * boundary[] for the anchor layer (#1152).
     *   [0] 0/1   Faint     | Parched   <- driest in-soil (Faint floor ~2293)
     *   [1] 1/2   Parched   | Thirsty
     *   [2] 2/3   Thirsty   | Content
     *   [3] 3/4   Content   | Thriving
     *   [4] 4/5   Thriving  | Refreshed
     *   [5] 5/6   Refreshed | Soaked    <- wettest in-soil (Soaked ceiling ~1150)
     * Both envelopes measured (#1174 dry-down); passed the #1153 cal-suite. */
    uint16_t boundary[MOISTURE_BOUNDARY_COUNT];

    /* --- sensor type (ADR-0019 §3) --- */
    moisture_sensor_type_t
        sensor_type; /* CAPACITIVE (committed) | RESISTIVE (seam) */
} moisture_cfg_t;

/* 7-band defaults; dry edge + wet floor reconciled to anchors (issue #3). */
#define MOISTURE_CFG_DEFAULT                                                   \
    {.sample_count = 64,                                                       \
     .trim_each_side = 8,                                                      \
     .deadband_raw = 60,                                                       \
     .confirm_ms_soil = 8000,                                                  \
     .confirm_ms_dry = 8000,                                                   \
     .confirm_ms_wet = 3500,                                                   \
     .loop_period_ms = 1000,                                                   \
     .spread_warn_raw = 250,                                                   \
     .max_delta_raw = 1200,                                                    \
     .boundary = {2293, 2086, 1879, 1636, 1393, 1150},                         \
     .sensor_type = SENSOR_CAPACITIVE}

typedef struct {
    moisture_level_t committed;     /* the level you act on / display          */
    moisture_level_t pending;       /* candidate awaiting confirmation         */
    uint16_t         confirm_count; /* consecutive measurements on pending     */
    uint16_t         last_raw;      /* last trimmed-mean value                 */
    uint16_t         last_spread;   /* range of the kept (trimmed) samples     */
    bool             health_warn;   /* last measurement exceeded spread_warn   */
    bool rate_spike; /* #1152: last step exceeded max_delta_raw */
    int16_t last_delta; /* #1434 AC0: SIGNED step from the previous accepted
                         * sample (raw_filtered - prev). This is the exact
                         * quantity rate_spike compares to max_delta_raw, kept so
                         * the check is AUDITABLE from telemetry (step=) rather
                         * than inferred from logged rows - which differ from the
                         * accepted-sample sequence across a dropped row. Signed:
                         * direction (wetter vs drier) is the primary exception
                         * discriminator (#1434 taxonomy). 0 at seed. */
} moisture_state_t;

/* ---- lifecycle ---------------------------------------------------------- */

/* Seed committed state from a current raw reading (no confirmation delay).
 * Call once at boot after taking a first measurement. */
void moisture_init(moisture_state_t *st, const moisture_cfg_t *cfg,
                   uint16_t raw_seed);

/* ---- one-shot full pipeline --------------------------------------------- */

/* Trimmed-mean the buffer, run the two-stage gate, update health, return the
 * committed level. NOTE: sorts `samples` in place (pass a scratch buffer). */
moisture_level_t moisture_process(moisture_state_t *st, const moisture_cfg_t *cfg,
                                  uint16_t *samples, uint16_t n);

/* ---- pieces, if you want them separately -------------------------------- */

/* Sorts s[] in place, returns mean of the middle (n - 2*trim_each) samples.
 * If spread_out != NULL, writes the range (max-min) of the kept set.
 * Falls back to a plain mean if n <= 2*trim_each. */
uint16_t moisture_trimmed_mean(uint16_t *s, uint16_t n, uint8_t trim_each,
                               uint16_t *spread_out);

/* Run dead-band + persistence on an already-filtered raw value. */
moisture_level_t moisture_update(moisture_state_t *st, const moisture_cfg_t *cfg,
                                 uint16_t raw_filtered);

/* ---- helpers ------------------------------------------------------------ */

bool moisture_level_is_display(moisture_level_t l); /* #995: all 7 */
moisture_class_t moisture_class_of(moisture_level_t l);
const char      *moisture_level_name(moisture_level_t l);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* MOISTURE_CLASSIFIER_H */
