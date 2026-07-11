/*
 * cal_resolver.h
 * -----------------------------------------------------------------------------
 * Per-board-type calibration resolution CHAIN (#952). Removes the single-table
 * ceiling: the #899 boolean seam ("cal_verified ? classic-per-channel : board")
 * generalizes into a layered resolver so ANY board-type can graduate to its own
 * cal without inheriting the classic's numbers.
 *
 * The chain, first hit wins:
 *   1. INSTANCE override - runtime-writable owner slot. EMPTY today; the NVS/
 *      registry write-path is #963 (0.8.0). Schema'd + wired now so the chain and
 *      its tests exist before the write-path (signed prebuilt binaries, #271/#302,
 *      mean an owner can never bake cal into headers - the override slot is the
 *      product's field-cal future).
 *   2. CLASS default  - header-generated, per board-type x sensor-class (Layer 2,
 *      cal_class_defaults.h). Data owns the values; Firmware owns the chain.
 *   3. FACTORY fallback - a shared, never-bench-measured placeholder. Guarantees
 *      cal_resolve() always returns a valid record.
 *
 * tier maps to ADR-0022 confidence: FACTORY/BOARD -> `provisional` (monitor only,
 * never auto-doses); CHANNEL -> `calibrated` (per-channel #170; necessary, not
 * sufficient, for autonomy).
 *
 * Framework-agnostic (no Arduino deps) - host-unit-tested. main.cpp injects the
 * class-default table via cal_resolver_init(); the lib stays pure logic.
 * -----------------------------------------------------------------------------
 */
#ifndef CAL_RESOLVER_H
#define CAL_RESOLVER_H

#include <stddef.h>
#include <stdint.h>

#include "moisture_classifier.h" /* MOISTURE_BOUNDARY_COUNT, boundary contract */

#ifdef __cplusplus
extern "C" {
#endif

/* The cal-source ladder (#952 promotion path) - how a channel's raw->band anchors
 * were derived. Ascending trust: FACTORY < BOARD < CHANNEL. */
typedef enum {
    CAL_TIER_FACTORY =
        0, /* shared placeholder - never bench-measured           */
    CAL_TIER_BOARD, /* measured board-type envelope (e.g. C5 #898)          */
    CAL_TIER_CHANNEL /* per-channel bench (e.g. classic #170/#248)           */
} cal_tier_t;

/* Sensor class (#952 STUB, ADR-0019 direction). Only CAPACITIVE_V2 is populated
 * today; the enum is schema'd so a future class slots in without a table reshape. */
typedef enum {
    SENSOR_CLASS_CAPACITIVE_V2 =
        0 /* committed v1 capacitive probe (UMLIFE_v2) */
} sensor_class_t;

/* One resolved calibration record. anchors[] are DESCENDING raw (dry>wet) - the
 * moisture_cfg_t.boundary contract (moisture_classifier.h). */
typedef struct {
    const char
        *board_class; /* BOARD_CAP.name, e.g. "esp32-classic"/"esp32-c5" */
    sensor_class_t
        sensor_class; /* SENSOR_CLASS_CAPACITIVE_V2 (stub)               */
    uint16_t anchors[MOISTURE_BOUNDARY_COUNT];
    const char
        *provenance; /* cal_source (ADR-0022): how these were derived   */
    cal_tier_t tier;
} cal_record_t;

/* A Layer-2 class-default entry: a record keyed additionally by channel.
 * channel >= 0 -> an exact per-CHANNEL record; channel == -1 -> a per-BOARD record
 * (returned for any channel). */
typedef struct {
    int channel;
    cal_record_t record;
} cal_class_default_t;

/* Install the Layer-2 class-default table (cal_class_defaults.h). Call once at
 * boot before cal_resolve(). Passing NULL/0 leaves only the factory fallback. */
void cal_resolver_init(const cal_class_default_t *defaults, size_t count);

/* Resolve (board_class, sensor_class, channel) down the chain. Always non-NULL
 * (the factory fallback is the guaranteed floor). */
const cal_record_t *cal_resolve(const char *board_class,
                                sensor_class_t sensor_class, int channel);

/* Layer 1: instance override. STUB - always NULL today (write-path = #963, 0.8.0),
 * so the chain falls through to the class default. Exposed now so the ordering is
 * real + tested before the write-path exists. */
const cal_record_t *cal_instance_lookup(const char *board_class,
                                        sensor_class_t sensor_class,
                                        int channel);

#ifdef __cplusplus
}
#endif

#endif /* CAL_RESOLVER_H */
