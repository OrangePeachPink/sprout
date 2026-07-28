#ifndef SPROUT_BOARD_VARIANT_H
#define SPROUT_BOARD_VARIANT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * board_variant — #1681: two boards of one CLASS are not one piece of hardware.
 *
 * `BOARD_CAP` (board_capability.h) is selected per PlatformIO target, so every
 * ESP32-S3 — an N8R2 and an N16R8 alike — receives the identical descriptor:
 * same pins, same cal_boundary[], SAME RAILS. That is fine for pins (the map is
 * the build's) and wrong for calibration (the rails are the board's).
 *
 * The wrong-number path it creates is the one #1433 just fixed for the C5: the
 * shipped S3 rails are the CLASSIC board's (wet 900 / air 3400), and the S3's
 * measured air rail is ~3222 — BELOW the 3400 threshold. `open_adc`
 * (raw > air_dry_raw) therefore cannot fire on an S3 at all, so a disconnected
 * probe reads as plausibly-dry soil instead of the instrument fault it is.
 *
 * ---------------------------------------------------------------------------
 * WHY THIS IS RUNTIME AND NOT A NEW BOARD CLASS
 *
 * #1681 argues the fix is NOT `esp32-s3-n8r2` / `esp32-s3-gold`: a class name
 * encoding RAM lies the moment a vendor changes a batch, and `board_class`
 * already means "which firmware and pin-map" — overloading it with "which
 * hardware variant" is ADR-0036's lesson one layer up. The identity token stays
 * exactly as it is.
 *
 * Instead the chip answers for itself. Flash and PSRAM sizes are MEASURED at
 * boot, and the rails follow the measurement. A board that reports its own
 * memory cannot be wrong about it and cannot go stale.
 *
 * ---------------------------------------------------------------------------
 * INHERITANCE IS REFUSED, NOT ASSUMED (the ruling this exists to honour)
 *
 * docs/hardware/BOARDS.md, ruled 2026-07-26 on the N8R2 row:
 *     "cal entry pending its own sweep - DO NOT INHERIT the N16R8's anchors"
 *
 * So a variant we have not measured does NOT silently take the measured one's
 * numbers just because they share a class. It keeps the placeholder and says so.
 * "We measured this board" and "we measured a board like it" are different
 * claims, and only the first one earns the rails.
 *
 * Pure logic: no Arduino, no ESP APIs. The caller measures (ESP.getFlashChipSize
 * / ESP.getPsramSize) and passes the numbers in; the native tests pass literals.
 * Same code either way.
 */

/* Which calibration a resolved board is actually running on. Stable tokens -
 * they reach the boot banner, so an operator can read the provenance without a
 * disassembler (the #416/ADR-0025 config-provenance principle). */
typedef enum {
    /* rails measured ON THIS VARIANT at the bench                            */
    BOARD_CAL_MEASURED = 0,
    /* rails are the compile-time placeholder - never measured for this board */
    BOARD_CAL_PLACEHOLDER
} board_cal_source_t;

typedef struct {
    uint16_t wet_rail_raw; /* below this = impossible-wet -> SENSOR_FAULT     */
    uint16_t air_dry_raw; /* above this = impossible-dry -> open_adc         */
    board_cal_source_t source;
    /* Stable short token for the banner, e.g. "s3-n16r8@bench_20260726" or
     * "placeholder". Never NULL, never allocated - a string literal. */
    const char *provenance;
} board_rails_t;

/*
 * Resolve the rails for the board actually running.
 *
 * `board_class`  - BOARD_CAP.name, e.g. "esp32-s3" (never modified; identity
 *                  stays the class token per #1681).
 * `flash_bytes`  - measured flash size, 0 when unknown.
 * `psram_bytes`  - measured PSRAM size. 0 means ABSENT, which is a real answer
 *                  (ADR-0028: absence is first-class, never a missing value);
 *                  pass `psram_known=false` when the platform could not be asked
 *                  at all, so "has none" and "we did not look" stay distinct.
 * `fallback_*`   - the compile-time BOARD_CAP rails, returned unchanged whenever
 *                  no measured entry matches. Fail-safe: an unrecognised board
 *                  keeps exactly today's behaviour, never a guessed number.
 *
 * Returns the fallback with BOARD_CAL_PLACEHOLDER for every board we have not
 * bench-measured — including an S3 variant that is not the measured one.
 */
board_rails_t board_variant_rails(const char *board_class, uint32_t flash_bytes,
                                  uint32_t psram_bytes, bool psram_known,
                                  uint16_t fallback_wet, uint16_t fallback_air);

/* Stable short token for the banner: "16MB/8MB", "8MB/none", "unknown". Writes
 * into `buf` and returns it, so the caller owns the storage (no statics). */
const char *board_variant_memory_label(char *buf, size_t cap,
                                       uint32_t flash_bytes,
                                       uint32_t psram_bytes, bool psram_known);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* SPROUT_BOARD_VARIANT_H */
