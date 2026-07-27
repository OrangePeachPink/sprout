/*
 * ota_gate.c — see ota_gate.h for the contract and the fail-closed rationale.
 */
#include "ota_gate.h"

#include "fw_verify.h"

ota_verdict_t ota_gate_apply(const uint8_t *image, size_t len,
                             const uint8_t *sig, size_t sig_len,
                             const uint8_t *pubkey, ota_commit_fn commit,
                             void *ctx)
{
    /* Fail-closed, in order. Every one of these returns WITHOUT touching the
     * commit callback - absence of a check is never permission to proceed. */
    if (image == NULL || len == 0u) return OTA_REJECT_NO_IMAGE;
    if (sig == NULL) return OTA_REJECT_NO_SIG;
    if (sig_len != 64u) return OTA_REJECT_SIG_LEN;
    if (pubkey == NULL) return OTA_REJECT_NO_KEY;

    if (!sprout_fw_verify(image, len, sig, pubkey)) return OTA_REJECT_BAD_SIG;

    /* Verified. This is the ONLY path that may switch the boot slot. */
    if (commit != NULL && !commit(ctx)) return OTA_REJECT_COMMIT_FAILED;

    return OTA_ACCEPT;
}

const char *ota_verdict_name(ota_verdict_t v)
{
    switch (v) {
    case OTA_ACCEPT:
        return "accept";
    case OTA_REJECT_NO_IMAGE:
        return "reject_no_image";
    case OTA_REJECT_NO_SIG:
        return "reject_no_sig";
    case OTA_REJECT_SIG_LEN:
        return "reject_sig_len";
    case OTA_REJECT_NO_KEY:
        return "reject_no_key";
    case OTA_REJECT_BAD_SIG:
        return "reject_bad_sig";
    case OTA_REJECT_COMMIT_FAILED:
        return "reject_commit_failed";
    default:
        return "reject_unknown";
    }
}
