#pragma once
#include <stdint.h>

/*
 * device_uid - the stable device identity (ADR-0027 §1b / #601).
 *
 * At schema_version >= 3 the `device_id` telemetry column is a 6-char Crockford
 * base32 nonce: lowercase 0-9 a-z with the four lookalikes i / l / o / u removed
 * = 32 symbols. Minted ONCE from the SoC RNG (esp_random(), AFTER RF is up so the
 * generator is seeded - see #601 build notes) and persisted to NVS; it is minted,
 * never derived - no MAC / eFuse / serial is read (ADR-0020). The friendly name
 * moves to a separate `name=` payload field.
 *
 * The alphabet is a power of two, so each 5-bit slice of the random word maps to
 * exactly one character with NO modulo bias (base36 would need rejection-sampling).
 * ~1.07 billion values - collision-free for any home fleet (birthday ~1-in-36M at
 * 11 devices). Human-safe: a person occasionally reads/types it from a raw log.
 *
 * Pure C (no Arduino deps) so the native host tests cover it.
 */
#define DEVICE_UID_LEN 6

#ifdef __cplusplus
extern "C" {
#endif

/* Encode the low 30 bits (6 x 5) of `rnd` into a DEVICE_UID_LEN-char Crockford
 * base32 string. `out` must hold at least DEVICE_UID_LEN + 1 bytes. */
void device_uid_encode(uint32_t rnd, char *out);

#ifdef __cplusplus
}
#endif
