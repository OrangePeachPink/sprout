/*
 * cal_resolver.c - see cal_resolver.h.
 */
#include "cal_resolver.h"

#include <string.h>

/* Injected Layer-2 table (main.cpp -> cal_class_defaults.h). */
static const cal_class_default_t *s_defaults = NULL;
static size_t s_count = 0;

/* Layer 3: the shared factory fallback - a never-bench-measured placeholder (the
 * historic board_capability.h placeholder rails + shared A2 interior). Any board
 * with no class default lands here: monitor-only, CAL_TIER_FACTORY. */
static const cal_record_t k_factory_fallback = {
    "unknown",
    SENSOR_CLASS_CAPACITIVE_V2,
    {3050, 2140, 1830, 1520, 1150, 1050},
    "factory_placeholder",
    CAL_TIER_FACTORY,
};

void cal_resolver_init(const cal_class_default_t *defaults, size_t count)
{
    s_defaults = defaults;
    s_count = defaults ? count : 0;
}

const cal_record_t *cal_instance_lookup(const char *board_class,
                                        sensor_class_t sensor_class,
                                        int channel)
{
    (void)board_class;
    (void)sensor_class;
    (void)channel;
    return NULL; /* #963: no runtime write-path yet - always empty */
}

static const cal_record_t *class_default_lookup(const char *board_class,
                                                sensor_class_t sensor_class,
                                                int channel)
{
    if (board_class == NULL) return NULL;
    for (size_t i = 0; i < s_count; i++) {
        const cal_class_default_t *d = &s_defaults[i];
        if (d->record.sensor_class != sensor_class) continue;
        if (d->record.board_class == NULL) continue;
        if (strcmp(d->record.board_class, board_class) != 0) continue;
        if (d->channel < 0 || d->channel == channel) return &d->record;
    }
    return NULL;
}

const cal_record_t *cal_resolve(const char *board_class,
                                sensor_class_t sensor_class, int channel)
{
    const cal_record_t *r =
        cal_instance_lookup(board_class, sensor_class, channel); /* Layer 1 */
    if (r) return r;
    r = class_default_lookup(board_class, sensor_class, channel); /* Layer 2 */
    if (r) return r;
    return &k_factory_fallback; /* Layer 3 */
}

const char *cal_tier_label(cal_tier_t tier)
{
    switch (tier) {
    case CAL_TIER_CHANNEL:
        return "channel-cal";
    case CAL_TIER_BOARD:
        return "board-cal";
    case CAL_TIER_FACTORY:
    default:
        return "uncalibrated"; /* the factory floor is never bench-measured */
    }
}
