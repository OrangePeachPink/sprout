/*
 * board_variant.c - see board_variant.h.
 */
#include "board_variant.h"

#include <stdio.h>
#include <string.h>

#define MB(n) ((uint32_t)(n) * 1024u * 1024u)

/*
 * The measured table. ONE ROW PER PHYSICALLY MEASURED BOARD - never per board
 * we assume is similar. Adding a row means a probe touched that board at the
 * bench and the numbers are in an evidence packet.
 *
 * s3-n16r8-pinned-01 (2026-07-26, #443 close-out / BOARDS.md row 3b):
 *   silkscreen "1" = GPIO1 = ch0, probe-verified
 *     air        3219 - 3222
 *     submerged  1053 - 1057
 * Rails sit JUST OUTSIDE the measured extremes, using the margins ratified for
 * the C5 in #1433 (+58 above the air max, -14 below the wet min): a normal
 * reading can never false-fire the fault, a real open/short always does.
 *   air_dry_raw  = 3222 + 58 = 3280
 *   wet_rail_raw = 1053 - 14 = 1039
 *
 * PROVISIONAL, and honestly so: this is ONE channel on ONE board (the #1433 C5
 * set was four channels at installed positions). Data owns cal values - these
 * are Firmware's derivation from the bench record, pending ratification, and
 * cal_boundary[] (the seven band edges) is NOT touched here. Rails gate the
 * instrument-fault checks; the bands remain the classic placeholder until an
 * S3 dry-down exists.
 */
typedef struct {
    const char *board_class;
    uint32_t flash_bytes;
    uint32_t psram_bytes;
    uint16_t wet_rail_raw;
    uint16_t air_dry_raw;
    const char *provenance;
} measured_variant_t;

static const measured_variant_t k_measured[] = {
    {"esp32-s3", MB(16), MB(8), 1039u, 3280u, "s3-n16r8@bench_20260726"},
};

board_rails_t board_variant_rails(const char *board_class, uint32_t flash_bytes,
                                  uint32_t psram_bytes, bool psram_known,
                                  uint16_t fallback_wet, uint16_t fallback_air)
{
    board_rails_t out;
    out.wet_rail_raw = fallback_wet;
    out.air_dry_raw = fallback_air;
    out.source = BOARD_CAL_PLACEHOLDER;
    out.provenance = "placeholder";

    if (board_class == NULL) return out;

    /* A board whose flash we could not read cannot be matched - matching on a
     * zero would silently hand one variant's rails to an unknown board, which is
     * the exact inheritance the 2026-07-26 ruling refuses. Unknown keeps the
     * placeholder. */
    if (flash_bytes == 0u) return out;

    for (size_t i = 0; i < sizeof(k_measured) / sizeof(k_measured[0]); i++) {
        const measured_variant_t *m = &k_measured[i];
        /* FLASH SIZE IS THE DISCRIMINATOR WE CAN ACTUALLY READ, and for the two
         * boards we own it is decisive: N16R8 = 16 MB, N8R2 = 8 MB. PSRAM would
         * be the tighter key, but [env:esp32s3] deliberately builds the N8 board
         * def with PSRAM UNMAPPED ("Sprout uses no PSRAM so kept deliberately",
         * platformio.ini) - so ESP.getPsramSize() reports 0 on BOTH variants.
         * That 0 means "we did not look", not "absent", and keying on it would
         * make this whole check never fire.
         *
         * So PSRAM TIGHTENS the match when it is genuinely known, and is ignored
         * when it is not. The day the build maps PSRAM, every row gets stricter
         * with no edit here. The limitation to keep in view: a THIRD S3 variant
         * with 16 MB flash but different analog would match this row - flash is
         * a proxy for the board, not proof of it. That is why cal_verified stays
         * false and the banner names the provenance. */
        if (strcmp(m->board_class, board_class) != 0) continue;
        if (m->flash_bytes != flash_bytes) continue;
        if (psram_known && m->psram_bytes != psram_bytes) continue;

        out.wet_rail_raw = m->wet_rail_raw;
        out.air_dry_raw = m->air_dry_raw;
        out.source = BOARD_CAL_MEASURED;
        out.provenance = m->provenance;
        return out;
    }
    return out;
}

const char *board_variant_memory_label(char *buf, size_t cap,
                                       uint32_t flash_bytes,
                                       uint32_t psram_bytes, bool psram_known)
{
    if (buf == NULL || cap == 0u) return "";
    if (flash_bytes == 0u) {
        snprintf(buf, cap, "unknown");
        return buf;
    }
    /* ADR-0028: absence is FIRST-CLASS. "none" (asked, this board has no PSRAM)
     * and "?" (could not ask) are different statements and must not collapse -
     * a 0 printed for both would make a missing measurement look like a fact. */
    if (!psram_known)
        snprintf(buf, cap, "%luMB/?", (unsigned long)(flash_bytes / MB(1)));
    else if (psram_bytes == 0u)
        snprintf(buf, cap, "%luMB/none", (unsigned long)(flash_bytes / MB(1)));
    else
        snprintf(buf, cap, "%luMB/%luMB", (unsigned long)(flash_bytes / MB(1)),
                 (unsigned long)(psram_bytes / MB(1)));
    return buf;
}
