#ifndef SPROUT_OTA_RELEASE_KEY_H
#define SPROUT_OTA_RELEASE_KEY_H

#include <stdint.h>

/*
 * ota_release_key.h — the release SIGNING public key, embedded (ADR-0026 D2).
 *
 * This is the ed25519 PUBLIC key the device verifies OTA images against (S1
 * fw_verify / S2 ota_gate). It is public by design — the same key lives in the
 * committed PEM and is what the web-flasher verifies with. A public key in the
 * binary authorises nothing; it only lets the device REJECT anything not signed
 * by the matching private key (which never leaves the signing ceremony).
 *
 * PROVENANCE — the 32 raw bytes below are the ed25519 point extracted from:
 *     firmware/keys/sprout-signing-ed25519.pub.pem
 * Regenerate on a key rotation with (both forms agree):
 *     openssl pkey -pubin -in keys/sprout-signing-ed25519.pub.pem \
 *         -outform DER | tail -c 32 | xxd -i
 * The 12-byte SubjectPublicKeyInfo prefix is dropped; only the raw point is kept
 * (that is exactly what monocypher / fw_verify's pubkey[32] expects). If this
 * array and the PEM ever disagree, every genuine release is rejected on-device —
 * so the extraction command above is the single source, not a hand-typed value.
 */
static const uint8_t SPROUT_OTA_RELEASE_PUBKEY[32] = {
    0x1b, 0xce, 0xab, 0xa2, 0x01, 0x9a, 0xa2, 0xda, 0xf2, 0x67, 0x1c,
    0x94, 0x8c, 0xe8, 0x2c, 0xed, 0xe5, 0xf0, 0x94, 0x05, 0x49, 0xe3,
    0x06, 0xd4, 0x1a, 0x13, 0xd8, 0xb8, 0xad, 0x86, 0x0f, 0x69};

#endif /* SPROUT_OTA_RELEASE_KEY_H */
