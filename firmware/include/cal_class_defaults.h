/*
 * cal_class_defaults.h
 * -----------------------------------------------------------------------------
 * Layer-2 per board-type x sensor-class calibration defaults (#952). The classic's
 * table is now ONE entry, not THE table.
 *
 * GENERATED ARTIFACT (future): the #192 cal workbench, board-aware, emits per-board
 * tables from each board's bench data. TODAY hand-preserved from calibration.h
 * (classic per-channel, #170/#248) + board_capability.h (C5 board envelope,
 * #898/#899) so classic + C5 resolve BYTE-IDENTICALLY to the pre-#952 seam - the
 * #899 AC pattern. Data owns the values/regen; Firmware owns the chain.
 *
 *   channel >= 0 : a per-CHANNEL record (CAL_TIER_CHANNEL).
 *   channel == -1: a per-BOARD record (CAL_TIER_BOARD), returned for any channel.
 *
 * A board absent here resolves to the factory fallback (cal_resolver.c) - which is
 * exactly the historic board_capability placeholder, so an unverified board (e.g.
 * S3) is byte-preserved too. Adding a bench-verified board = add its rows here.
 * -----------------------------------------------------------------------------
 */
#ifndef CAL_CLASS_DEFAULTS_H
#define CAL_CLASS_DEFAULTS_H

#include "cal_resolver.h"

static const cal_class_default_t CAL_CLASS_DEFAULTS[] = {
    /* esp32-classic x capacitive-v2 - #995 dual-envelope band ratification
     * (2026-07-19). All four channels now share the per-BOARD in-soil ladder;
     * per-channel outer rails moved to the off-ladder anchor layer (#1152).
     * Byte-identical to calibration.h SENSOR_CAL_BOUNDARY[ch0..ch3]. */
    {0,
     {"esp32-classic",
      SENSOR_CLASS_CAPACITIVE_V2,
      {2293, 2086, 1879, 1673, 1466, 1259},
      "band_ratified_995_20260719",
      CAL_TIER_CHANNEL}},
    {1,
     {"esp32-classic",
      SENSOR_CLASS_CAPACITIVE_V2,
      {2293, 2086, 1879, 1673, 1466, 1259},
      "band_ratified_995_20260719",
      CAL_TIER_CHANNEL}},
    {2,
     {"esp32-classic",
      SENSOR_CLASS_CAPACITIVE_V2,
      {2293, 2086, 1879, 1673, 1466, 1259},
      "band_ratified_995_20260719",
      CAL_TIER_CHANNEL}},
    {3,
     {"esp32-classic",
      SENSOR_CLASS_CAPACITIVE_V2,
      {2293, 2086, 1879, 1673, 1466, 1259},
      "band_ratified_995_20260719",
      CAL_TIER_CHANNEL}},

    /* esp32-c5 x capacitive-v2 - #995 ratification, 8gtt1h envelope MEASURED
     * directly (2026-07-19; no longer #898-derived).
     * Byte-identical to board_capability.h's C5 cal_boundary. */
    {-1,
     {"esp32-c5",
      SENSOR_CLASS_CAPACITIVE_V2,
      {2037, 1861, 1685, 1510, 1334, 1158},
      "band_ratified_995_20260719",
      CAL_TIER_BOARD}},
};

#define CAL_CLASS_DEFAULTS_COUNT                                               \
    (sizeof(CAL_CLASS_DEFAULTS) / sizeof(CAL_CLASS_DEFAULTS[0]))

#endif /* CAL_CLASS_DEFAULTS_H */
