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
 * Level 0 (air-dry) and level 6 (submerged) are out-of-band diagnostics: they
 * bracket the real soil range and are not meant for default UI/log display
 * (see moisture_level_is_display). They are useful for troubleshooting,
 * "probe not in soil" detection at boot, and internal indexing.
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
typedef enum {
    MOIST_AIR_DRY = 0,         /* diagnostic: probe in air / air gap          */
    MOIST_DRY,                 /* display:   soil too dry (top of soil range) */
    MOIST_NEEDS_WATER,         /* display                                     */
    MOIST_OK,                  /* display:   healthy band                     */
    MOIST_WELL_WATERED,        /* display:   field capacity                   */
    MOIST_OVERWATERED,         /* display:   saturated / fresh over-soak      */
    MOIST_SUBMERGED            /* diagnostic: standing water                  */
} moisture_level_t;

/* Confirm-window class. Entering a level uses the window for that level's
 * class, so submersion is recognized fast while soil bands settle slowly. */
typedef enum {
    MCLASS_DRY_DIAG = 0,   /* idx 0    (air-dry)   */
    MCLASS_SOIL,           /* idx 1..5 (soil)      */
    MCLASS_WET_DIAG        /* idx 6    (submerged) */
} moisture_class_t;

typedef struct {
    /* --- acquisition --- */
    uint16_t sample_count;     /* samples per measurement (your 64)            */
    uint8_t  trim_each_side;   /* drop this many high AND low (8 -> 48/64)      */

    /* --- hysteresis --- */
    uint16_t deadband_raw;     /* total dead-band width in raw counts (~60)    */

    /* --- persistence (confirmation), in milliseconds --- */
    uint32_t confirm_ms_soil;  /* display bands idx 1..5  (~8000)              */
    uint32_t confirm_ms_dry;   /* air-dry diagnostic idx 0                     */
    uint32_t confirm_ms_wet;   /* submerged diagnostic idx 6 (~3500)           */
    uint32_t loop_period_ms;   /* measurement cadence; ms->count uses this     */

    /* --- health --- */
    uint16_t spread_warn_raw;  /* trimmed-set range above this flags a fault;
                                  0 disables the check                         */

    /* --- calibration thresholds (DESCENDING) ---
     * boundary[i] separates level i from level i+1.
     *   [0] 0/1   air-dry      | DRY        <- dry potting-mix / air gap
     *   [1] 1/2   dry          | needs water
     *   [2] 2/3   needs water  | OK
     *   [3] 3/4   OK           | well watered
     *   [4] 4/5   well watered | overwatered
     *   [5] 5/6   overwatered  | submerged  <- saturated soil vs standing water
     * Middle bands [1]..[3] are provisional (interpolated); tighten from the
     * dry-down log. Wet end + dry center are anchored to measured readings. */
    uint16_t boundary[MOISTURE_BOUNDARY_COUNT];
} moisture_cfg_t;

/* 7-band defaults. Provisional middle bands; tighten from the dry-down log. */
#define MOISTURE_CFG_DEFAULT {            \
    .sample_count    = 64,                \
    .trim_each_side  = 8,                 \
    .deadband_raw    = 60,                \
    .confirm_ms_soil = 8000,              \
    .confirm_ms_dry  = 8000,              \
    .confirm_ms_wet  = 3500,              \
    .loop_period_ms  = 1000,              \
    .spread_warn_raw = 250,               \
    .boundary = { 2760, 2140, 1830,       \
                  1520, 1260, 1030 }      \
}

typedef struct {
    moisture_level_t committed;     /* the level you act on / display          */
    moisture_level_t pending;       /* candidate awaiting confirmation         */
    uint16_t         confirm_count; /* consecutive measurements on pending     */
    uint16_t         last_raw;      /* last trimmed-mean value                 */
    uint16_t         last_spread;   /* range of the kept (trimmed) samples     */
    bool             health_warn;   /* last measurement exceeded spread_warn   */
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

bool             moisture_level_is_display(moisture_level_t l); /* idx 1..5 */
moisture_class_t moisture_class_of(moisture_level_t l);
const char      *moisture_level_name(moisture_level_t l);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* MOISTURE_CLASSIFIER_H */
