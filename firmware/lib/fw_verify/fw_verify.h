#ifndef SPROUT_FW_VERIFY_H
#define SPROUT_FW_VERIFY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * fw_verify — the #302 S1 signature primitive (ADR-0026 Decision 2).
 *
 * Verifies a detached ed25519 signature over a firmware image, with the domain
 * separation Trellis ruled on #1282:
 *
 *     signed message = "sprout-fw\0"  ||  image_bytes
 *
 * The 10-byte tag means a firmware signature can never be replayed as a
 * signature over a different artifact class (a config, a manifest, a future
 * signed asset). The CI signer prepends the identical tag
 * (.github/workflows/sign-release.yml) — signer and verifier MUST agree here or
 * every real release is rejected on-device.
 *
 * SCOPE (S1): the primitive only. It does not gate an OTA apply, touch
 * hardware, fetch anything, or know what a partition is. Verify-before-apply
 * wiring is S2 (#1283).
 *
 * PROPERTIES
 *   - deterministic, no allocation, no hardware, no globals
 *   - the image is read as ONE contiguous const region and never copied, so a
 *     multi-megabyte memory-mapped flash partition is fine (see note below)
 *   - PureEdDSA (RFC 8032 Ed25519), matching `openssl pkeyutl -sign -rawin`.
 *     NOT Ed25519ph — the pre-hash variant is a different scheme and would
 *     reject CI's signatures.
 *
 * WHY NOT crypto_ed25519_check() DIRECTLY: that one-shot call takes a single
 * contiguous message, and the domain tag cannot be prepended to a mapped flash
 * region without copying the whole image. So this composes the SAME
 * construction monocypher uses internally — SHA-512 over R || A || M, reduce,
 * check equation — from monocypher's PUBLIC low-level API, feeding the tag and
 * the image as separate chunks of the M stream. It is not a re-implementation:
 * every cryptographic operation is monocypher's, in monocypher's own order.
 * The native test asserts this agrees with crypto_ed25519_check() on a
 * concatenated buffer, so the equivalence is proven rather than asserted.
 */

/* The domain tag, without its terminator: "sprout-fw" + one NUL = 10 bytes. */
#define SPROUT_FW_DOMAIN_TAG "sprout-fw"
#define SPROUT_FW_DOMAIN_TAG_LEN 10u

/*
 * Returns true only if `sig` is a valid ed25519 signature by `pubkey` over
 * (domain tag || image[0..len)). Any tamper — one image byte, one signature
 * byte, the wrong key, or a signature made over the bare image without the
 * tag — returns false.
 *
 * image may be NULL only when len == 0. sig and pubkey must not be NULL.
 */
bool sprout_fw_verify(const uint8_t *image, size_t len, const uint8_t sig[64],
                      const uint8_t pubkey[32]);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* SPROUT_FW_VERIFY_H */
