/*
 * fw_verify.c — see fw_verify.h for the contract and the design rationale.
 */
#include "fw_verify.h"

#include "monocypher-ed25519.h" /* crypto_sha512_* (incremental)            */
#include "monocypher.h" /* crypto_eddsa_reduce / _check_equation    */

bool sprout_fw_verify(const uint8_t *image, size_t len, const uint8_t sig[64],
                      const uint8_t pubkey[32])
{
    if (sig == NULL || pubkey == NULL) return false;
    if (image == NULL && len != 0u) return false;

    /* Ed25519 verification hashes  R || A || M  and reduces it mod L; the
     * message M is simply the tail of that stream. We supply M in two chunks -
     * the domain tag, then the image - which is what lets a memory-mapped
     * multi-megabyte partition be verified without a copy. This is monocypher's
     * own crypto_ed25519_check() construction, in its order, via its public
     * API (the native test pins the equivalence). */
    crypto_sha512_ctx ctx;
    uint8_t hash[64];
    uint8_t h_ram[32];

    crypto_sha512_init(&ctx);
    crypto_sha512_update(&ctx, sig, 32u); /* R */
    crypto_sha512_update(&ctx, pubkey, 32u); /* A */
    crypto_sha512_update(&ctx, (const uint8_t *)SPROUT_FW_DOMAIN_TAG,
                         SPROUT_FW_DOMAIN_TAG_LEN); /* M part 1: the tag  */
    if (len != 0u) crypto_sha512_update(&ctx, image, len); /* M part 2: image */
    crypto_sha512_final(&ctx, hash);

    crypto_eddsa_reduce(h_ram, hash);

    /* monocypher returns 0 on success. Constant-time inside; the only branch
     * here is on its verdict, which is public information. */
    return crypto_eddsa_check_equation(sig, pubkey, h_ram) == 0;
}
