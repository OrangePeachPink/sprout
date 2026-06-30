/*
 * env_i2c.h - tiny injected I2C interface for the contextual env-sensor drivers.
 *
 * The drivers (sht45, as7263) are pure C and framework-agnostic: they speak the
 * sensor protocol through these three callbacks, so the FULL driver — not just the
 * math — is native-testable with a mock bus (same pattern as lib/irrigation's io).
 * main.cpp supplies the Arduino `Wire`-backed implementation under the env build.
 *
 * Callbacks return 0 on success, non-zero on bus error. addr is the 7-bit I2C
 * address. delay_ms covers sensor conversion/handshake waits without an Arduino dep.
 */
#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int (*write)(uint8_t addr, const uint8_t *buf, size_t len, void *user);
    int (*read)(uint8_t addr, uint8_t *buf, size_t len, void *user);
    void (*delay_ms)(uint32_t ms, void *user);
    void *user;
} env_i2c_t;

#ifdef __cplusplus
} /* extern "C" */
#endif
