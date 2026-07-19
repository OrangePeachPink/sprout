/*
 * moisture_classifier.c  — see moisture_classifier.h for the design notes.
 */
#include "moisture_classifier.h"

/* -------------------------------------------------------------------------- */
/* helpers                                                                    */
/* -------------------------------------------------------------------------- */

bool moisture_level_is_display(moisture_level_t l)
{
    /* #995: all 7 are in-soil display bands (Faint..Soaked). The off-ladder
     * probe-in-air/water exceptions are the #1152 anchor layer, not a level. */
    return (l >= MOIST_AIR_DRY) && (l <= MOIST_SUBMERGED);
}

moisture_class_t moisture_class_of(moisture_level_t l)
{
    /* confirm-SPEED grouping (#995): edge bands keep distinct timing. */
    if (l <= MOIST_AIR_DRY) return MCLASS_DRY_DIAG; /* idx 0  Faint edge  */
    if (l >= MOIST_SUBMERGED) return MCLASS_WET_DIAG; /* idx 6  Soaked edge */
    return MCLASS_SOIL; /* idx 1..5 mid soil  */
}

const char *moisture_level_name(moisture_level_t l)
{
    switch (l) {
        case MOIST_AIR_DRY:      return "air-dry";
        case MOIST_DRY:          return "dry";
        case MOIST_NEEDS_WATER:  return "needs water";
        case MOIST_OK:           return "OK";
        case MOIST_WELL_WATERED: return "well watered";
        case MOIST_OVERWATERED:  return "overwatered";
        case MOIST_SUBMERGED:    return "submerged";
        default:                 return "?";
    }
}

/* Number of consecutive in-band measurements required to commit `lvl`.
 * Keyed on the level being entered, so the wet diagnostics latch quickly
 * while soil transitions stay deliberate. */
static uint16_t confirm_samples(moisture_level_t lvl, const moisture_cfg_t *cfg)
{
    uint32_t ms;
    switch (moisture_class_of(lvl)) {
        case MCLASS_WET_DIAG: ms = cfg->confirm_ms_wet;  break;
        case MCLASS_DRY_DIAG: ms = cfg->confirm_ms_dry;  break;
        default:              ms = cfg->confirm_ms_soil; break;
    }
    uint32_t period = cfg->loop_period_ms ? cfg->loop_period_ms : 1u;
    uint32_t n = (ms + period - 1u) / period;            /* ceil */
    return (uint16_t)(n < 1u ? 1u : n);
}

/* Classify a raw value into a band, biased to "stick" to `committed` by
 * deadband/2 on each side. Boundaries drier than the committed band are
 * raised; boundaries at/below it are lowered. The result is a deadband-wide
 * window around the committed band that raw must fully exit to change. */
static moisture_level_t classify_hyst(uint16_t raw, moisture_level_t committed,
                                      const uint16_t *b, uint16_t deadband,
                                      moisture_sensor_type_t type)
{
    int half = (int)deadband / 2;
    int band = 0;
    for (int i = 0; i < MOISTURE_BOUNDARY_COUNT; i++) {
        if (type == SENSOR_RESISTIVE) {
            /* inverted seam (ADR-0019 §3): higher raw = wetter, boundary[] ASCENDING.
             * Hysteresis sign flips with the direction so it stays symmetric. */
            int eff = (int)b[i] + ((i < (int)committed) ? -half : half);
            if ((int)raw > eff) band++; /* each boundary crossed -> 1 wetter */
        } else {
            /* capacitive (committed): higher raw = drier, boundary[] DESCENDING */
            int eff = (int)b[i] + ((i < (int)committed) ? half : -half);
            if ((int)raw < eff) band++; /* each boundary crossed -> 1 wetter */
        }
    }
    return (moisture_level_t)band;
}

/* -------------------------------------------------------------------------- */
/* trimmed mean                                                               */
/* -------------------------------------------------------------------------- */

uint16_t moisture_trimmed_mean(uint16_t *s, uint16_t n, uint8_t trim_each,
                               uint16_t *spread_out)
{
    if (n == 0) { if (spread_out) *spread_out = 0; return 0; }

    /* insertion sort — n is small (~64), avoids qsort/recursion overhead */
    for (uint16_t i = 1; i < n; i++) {
        uint16_t key = s[i];
        int j = (int)i - 1;
        while (j >= 0 && s[j] > key) { s[j + 1] = s[j]; j--; }
        s[j + 1] = key;
    }

    uint16_t lo = trim_each;
    uint16_t hi = (n > 2 * trim_each) ? (uint16_t)(n - trim_each) : n;  /* exclusive */
    if (n <= 2 * trim_each) lo = 0;        /* not enough to trim -> plain mean */

    uint32_t sum = 0;
    for (uint16_t i = lo; i < hi; i++) sum += s[i];
    uint16_t kept = (uint16_t)(hi - lo);

    if (spread_out) *spread_out = (uint16_t)(s[hi - 1] - s[lo]);
    return (uint16_t)(sum / kept);
}

/* -------------------------------------------------------------------------- */
/* two-stage gate                                                             */
/* -------------------------------------------------------------------------- */

moisture_level_t moisture_update(moisture_state_t *st, const moisture_cfg_t *cfg,
                                 uint16_t raw_filtered)
{
    st->last_raw = raw_filtered;

    moisture_level_t candidate =
        classify_hyst(raw_filtered, st->committed, cfg->boundary,
                      cfg->deadband_raw, cfg->sensor_type);

    if (candidate == st->committed) {
        /* back home — cancel any in-progress transition */
        st->pending = candidate;
        st->confirm_count = 0;
    } else if (candidate == st->pending) {
        /* same new candidate as last time — accumulate */
        if (++st->confirm_count >= confirm_samples(candidate, cfg)) {
            st->committed = candidate;
            st->pending = candidate;
            st->confirm_count = 0;
        }
    } else {
        /* candidate changed — (re)start the confirmation clock at 1 */
        st->pending = candidate;
        st->confirm_count = 1;
    }

    return st->committed;
}

/* -------------------------------------------------------------------------- */
/* lifecycle + one-shot                                                       */
/* -------------------------------------------------------------------------- */

void moisture_init(moisture_state_t *st, const moisture_cfg_t *cfg,
                   uint16_t raw_seed)
{
    /* deadband 0 + neutral committed -> plain classification for the seed */
    moisture_level_t lvl =
        classify_hyst(raw_seed, MOIST_OK, cfg->boundary, 0, cfg->sensor_type);
    st->committed     = lvl;
    st->pending       = lvl;
    st->confirm_count = 0;
    st->last_raw      = raw_seed;
    st->last_spread   = 0;
    st->health_warn   = false;
}

moisture_level_t moisture_process(moisture_state_t *st, const moisture_cfg_t *cfg,
                                  uint16_t *samples, uint16_t n)
{
    uint16_t spread = 0;
    uint16_t raw = moisture_trimmed_mean(samples, n, cfg->trim_each_side, &spread);

    st->last_spread = spread;
    st->health_warn = (cfg->spread_warn_raw > 0) && (spread > cfg->spread_warn_raw);

    return moisture_update(st, cfg, raw);
}
