#ifndef SPROUT_OTA_GATE_H
#define SPROUT_OTA_GATE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * ota_gate — #302 S2: verify BEFORE the boot slot switches (ADR-0026 D2/D3).
 *
 * This is the fence. After it, only signed firmware runs over OTA.
 *
 * The design point is that the *effect* is gated, not just the verdict. An
 * incoming image is verified with the S1 primitive, and the commit callback -
 * which on-device performs the boot-slot switch (esp_ota_set_boot_partition) -
 * is invoked ONLY on OTA_ACCEPT. Every other path returns without calling it.
 * A caller therefore cannot switch slots by ignoring a return value, which is
 * the usual way a check like this rots.
 *
 * FAIL-CLOSED: absence is rejection. A missing signature, a wrong-length
 * signature, a missing key, or a missing image are all rejections, never
 * "nothing to check, proceed". The only path to ACCEPT is a cryptographically
 * valid signature over the domain-separated message (see fw_verify.h).
 *
 * Pure logic: no hardware, no partition API, no allocation. The on-device flash
 * path supplies the image pointer (a mapped partition) and a commit callback;
 * the native tests supply a buffer and a counter. Same code either way.
 */

typedef enum {
    OTA_ACCEPT = 0, /* signature valid - and only here does commit run   */
    OTA_REJECT_NO_IMAGE, /* no image, or zero length                          */
    OTA_REJECT_NO_SIG, /* signature absent - fail-closed, never allowed    */
    OTA_REJECT_SIG_LEN, /* signature present but not 64 bytes               */
    OTA_REJECT_NO_KEY, /* no verification key available                    */
    OTA_REJECT_BAD_SIG, /* cryptographic verification failed                */
    OTA_REJECT_COMMIT_FAILED /* verified, but the slot switch itself failed */
} ota_verdict_t;

/* Performs the boot-slot switch. Returns true on success. On-device this wraps
 * esp_ota_set_boot_partition(); in tests it records that it was reached. */
typedef bool (*ota_commit_fn)(void *ctx);

/*
 * Verify `sig` over `image` with `pubkey`, and switch the boot slot ONLY if it
 * verifies. `commit` may be NULL to run a dry verification with no effect.
 *
 * Returns OTA_ACCEPT only when the image is genuinely signed AND (if a commit
 * callback was supplied) the switch succeeded.
 */
ota_verdict_t ota_gate_apply(const uint8_t *image, size_t len,
                             const uint8_t *sig, size_t sig_len,
                             const uint8_t *pubkey, ota_commit_fn commit,
                             void *ctx);

/* Stable short token for logs / the telemetry banner. Never NULL. */
const char *ota_verdict_name(ota_verdict_t v);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* SPROUT_OTA_GATE_H */
