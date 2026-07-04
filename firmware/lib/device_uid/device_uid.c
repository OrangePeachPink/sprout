#include "device_uid.h"

/* Crockford base32, lowercase, i / l / o / u removed (0-9 a-z minus those four) =
 * 32 symbols. Index 0..31 = one 5-bit slice; a power-of-two alphabet, so the
 * mapping is uniform (unbiased) straight from random bits (ADR-0027 §1b). */
static const char DEVICE_UID_ALPHABET[33] = "0123456789abcdefghjkmnpqrstvwxyz";

void device_uid_encode(uint32_t rnd, char *out)
{
    for (unsigned i = 0; i < DEVICE_UID_LEN; i++)
        out[i] = DEVICE_UID_ALPHABET[(rnd >> (5u * i)) & 0x1Fu];
    out[DEVICE_UID_LEN] = '\0';
}
