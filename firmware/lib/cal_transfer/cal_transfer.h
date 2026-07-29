#ifndef SPROUT_CAL_TRANSFER_H
#define SPROUT_CAL_TRANSFER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * cal_transfer — #1449: the code half of ADR-0027 §6.
 *
 * A probe's calibration is probe-intrinsic ⊕ the board's ADC transfer. Move the
 * probe to a different board class and its anchors are still the right SHAPE but
 * expressed in the wrong board's raw space — #1448 measured ~-17% range
 * compression across the classic↔C5 pair. Applied unremapped, every band edge
 * shifts by the untranslated transfer.
 *
 * Today the chain REFUSES that case: cal_instance_lookup returns NULL on a board
 * mismatch and the channel drops to the destination board's class default. That
 * is conservative and correct, just not per-probe optimal. This module is what
 * lets the chain do better — WITHOUT ever doing worse.
 *
 * ---------------------------------------------------------------------------
 * ABSENCE IS A REFUSAL, NOT AN IDENTITY TRANSFORM
 *
 * The single most important behaviour here: with no ratified model, or with any
 * board's envelope unmeasured, this REFUSES and says why. It does not quietly
 * copy the anchors across (an identity transform), because that would look
 * exactly like a calibration while being precisely the untranslated-transfer bug
 * the module exists to prevent.
 *
 * That is the same rule the build channel encodes (#1614/#1701): never default
 * to the trusted value. "We have not measured this board's transfer" and "this
 * board needs no transfer" are different statements, and only the second one
 * earns a copied anchor. #1449's scope says it outright: a future board class is
 * blocked until its transfer is measured — FAIL LOUD, NEVER GUESS A TRANSFER.
 *
 * Pure logic: no board APIs, no allocation. Data owns the VALUES (the envelopes
 * and which model is ratified); Firmware owns the CHAIN that applies them.
 */

/* Which transfer Data has ratified. Absent is the shipped default and means "no
 * transfer happens", never "transfer by copying". */
typedef enum {
    CAL_TRANSFER_ABSENT = 0,
    /* Span remap between two measured board envelopes: an anchor keeps its
     * FRACTIONAL position between wet rail and air rail, and that fraction is
     * re-expressed in the destination board's span. Derives entirely from rails
     * already landed (#1433 for the C5, #1681 for the S3) - it introduces no new
     * measured constant, which is why it is the proposed starting model. */
    CAL_TRANSFER_RAILS_RATIO
} cal_transfer_model_t;

/* One board class's measured raw envelope. Both rails must be REAL measurements;
 * a placeholder rail is not an envelope and must not be registered as one. */
typedef struct {
    const char *board_class; /* BOARD_CAP.name                              */
    uint16_t wet_rail_raw; /* measured submerged floor                    */
    uint16_t air_dry_raw; /* measured air ceiling                        */
} cal_board_envelope_t;

typedef enum {
    CAL_XFER_OK = 0,
    CAL_XFER_NO_MODEL, /* Data has ratified no model - do not transform  */
    CAL_XFER_NO_ENVELOPE, /* a board's envelope is unknown (fail loud)      */
    CAL_XFER_BAD_ENVELOPE, /* degenerate rails (air <= wet, or a zero rail)  */
    CAL_XFER_NOT_MONOTONIC /* the remap would not stay strictly descending   */
} cal_xfer_result_t;

/*
 * Remap `src_anchors` (n values, DESCENDING raw per the moisture_cfg_t contract)
 * from the source board's raw space into the destination board's, writing `out`.
 *
 * `out` is written ONLY on CAL_XFER_OK. Every other result leaves it untouched,
 * so a caller that ignores the return value cannot accidentally act on a
 * half-transferred ladder.
 */
cal_xfer_result_t cal_transfer_anchors(cal_transfer_model_t model,
                                       const cal_board_envelope_t *src,
                                       const cal_board_envelope_t *dst,
                                       const uint16_t *src_anchors, size_t n,
                                       uint16_t *out);

/* Stable short token for the banner / logs. Never NULL. */
const char *cal_xfer_result_label(cal_xfer_result_t r);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* SPROUT_CAL_TRANSFER_H */
