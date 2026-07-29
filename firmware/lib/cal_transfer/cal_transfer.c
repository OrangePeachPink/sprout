/*
 * cal_transfer.c - see cal_transfer.h.
 */
#include "cal_transfer.h"

/* A registered envelope must be two REAL rails with real span between them. A
 * zero rail is the "never measured" sentinel used throughout the descriptors, and
 * air <= wet is not a capacitive envelope at all (higher raw = drier). Either way
 * we do not know this board, and not knowing is a refusal. */
static bool envelope_usable(const cal_board_envelope_t *e)
{
    if (e == NULL) return false;
    if (e->wet_rail_raw == 0u || e->air_dry_raw == 0u) return false;
    return e->air_dry_raw > e->wet_rail_raw;
}

cal_xfer_result_t cal_transfer_anchors(cal_transfer_model_t model,
                                       const cal_board_envelope_t *src,
                                       const cal_board_envelope_t *dst,
                                       const uint16_t *src_anchors, size_t n,
                                       uint16_t *out)
{
    /* NO MODEL -> NO TRANSFORM. Checked first and unconditionally: this is the
     * shipped state, and the whole point is that it does NOT fall through to an
     * anchor copy. An identity transform here would be indistinguishable from a
     * real calibration while carrying none of the evidence. */
    if (model == CAL_TRANSFER_ABSENT) return CAL_XFER_NO_MODEL;

    if (src_anchors == NULL || out == NULL || n == 0u) return CAL_XFER_NO_MODEL;
    if (src == NULL || dst == NULL) return CAL_XFER_NO_ENVELOPE;
    if (!envelope_usable(src) || !envelope_usable(dst))
        return CAL_XFER_BAD_ENVELOPE;

    /* Span remap. An anchor's meaning is its FRACTIONAL position between the
     * board's own rails - that fraction is the probe-intrinsic part (ADR-0027
     * §6) and is what survives the move. Re-express it in the destination span.
     *
     * int32 throughout: the numerator is (anchor - wet) * dst_span, which for
     * 12-bit raws and a ~2400-count span is ~10^7 - comfortably inside int32 and
     * nowhere near it in uint16. Rounded, not truncated, so a transfer and its
     * inverse do not drift by a count per hop.
     *
     * Extrapolation is ALLOWED (an anchor may legitimately sit slightly outside
     * the rails) but the result must still land in raw range - anything else
     * means the two envelopes disagree about the world and we refuse. */
    const int32_t src_lo = (int32_t)src->wet_rail_raw;
    const int32_t src_span = (int32_t)src->air_dry_raw - src_lo;
    const int32_t dst_lo = (int32_t)dst->wet_rail_raw;
    const int32_t dst_span = (int32_t)dst->air_dry_raw - dst_lo;

    uint16_t scratch[16];
    if (n > sizeof(scratch) / sizeof(scratch[0])) return CAL_XFER_NO_MODEL;

    for (size_t i = 0; i < n; i++) {
        int32_t rel = (int32_t)src_anchors[i] - src_lo;
        int32_t num = rel * dst_span;
        /* round-half-away-from-zero without floating point */
        int32_t mapped =
            dst_lo + ((num >= 0) ? (num + src_span / 2) / src_span
                                 : (num - src_span / 2) / src_span);
        if (mapped < 0 || mapped > 4095) return CAL_XFER_BAD_ENVELOPE;
        scratch[i] = (uint16_t)mapped;
    }

    /* STRICTLY DESCENDING is the moisture_cfg_t.boundary contract. A remap that
     * flattened two edges together, or inverted them, would hand the classifier a
     * ladder it cannot walk - so that is a refusal too, not a clamp. Checked on
     * the RESULT rather than assumed from the input, because rounding at a narrow
     * destination span is exactly where two close anchors can collide. */
    for (size_t i = 1; i < n; i++)
        if (scratch[i] >= scratch[i - 1]) return CAL_XFER_NOT_MONOTONIC;

    /* Commit only now: `out` is untouched on every refusal path above. */
    for (size_t i = 0; i < n; i++)
        out[i] = scratch[i];
    return CAL_XFER_OK;
}

const char *cal_xfer_result_label(cal_xfer_result_t r)
{
    switch (r) {
    case CAL_XFER_OK:
        return "ok";
    case CAL_XFER_NO_MODEL:
        return "no-model";
    case CAL_XFER_NO_ENVELOPE:
        return "no-envelope";
    case CAL_XFER_BAD_ENVELOPE:
        return "bad-envelope";
    case CAL_XFER_NOT_MONOTONIC:
        return "not-monotonic";
    }
    return "unknown";
}
