/*
 * as7263.h - SparkFun AS7263 6-channel NIR spectral sensor driver (#374).
 *
 * LIGHT-CONTEXT telemetry, not plant data: marks the skylight transit + direct-
 * beam-vs-shaded state for the solar pass (PRD-0002 env layer, part of #200). Six
 * NIR channels: 610 / 680 / 730 / 760 / 810 / 860 nm. Aim it at the beam path, not
 * the plant. RAW counts (uint16) — no floats, no calibration claims.
 *
 * I2C addr 0x49 via the AS726x "virtual register" protocol: physical STATUS/WRITE/
 * READ registers with a TX/RX handshake. Pure C over the injected env_i2c bus —
 * the protocol flow is native-testable with a mock. Polls are bounded (timeout),
 * never busy-wait forever.
 */
#pragma once
#include "env_i2c.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define AS7263_I2C_ADDR 0x49

/* physical registers */
#define AS7263_REG_STATUS 0x00
#define AS7263_REG_WRITE 0x01
#define AS7263_REG_READ 0x02
#define AS7263_TX_VALID 0x02 /* STATUS: a byte is queued to the device     */
#define AS7263_RX_VALID 0x01 /* STATUS: a byte is ready to read back       */

/* virtual registers */
#define AS7263_HW_VERSION 0x01
#define AS7263_CONTROL_SETUP                                                   \
    0x04 /* [7]=RST [5:4]=GAIN [3:2]=MODE [1]=DATA_RDY  */
#define AS7263_INT_TIME 0x05 /* integration time, value x 2.8 ms           */
#define AS7263_R_HIGH 0x08 /* first of six 16-bit raw channels (R..W)    */
#define AS7263_DATA_RDY 0x02 /* CONTROL_SETUP bit 1                         */

/* gain settings (CONTROL_SETUP bits 5:4) */
enum {
    AS7263_GAIN_1X = 0,
    AS7263_GAIN_3X7 = 1,
    AS7263_GAIN_16X = 2,
    AS7263_GAIN_64X = 3
};

enum {
    AS7263_OK = 0,
    AS7263_ERR_I2C = -1,
    AS7263_ERR_TIMEOUT =
        -2 /* handshake / DATA_RDY poll exceeded the bound     */
};

typedef struct {
    uint16_t nm610, nm680, nm730, nm760, nm810, nm860; /* raw counts, R..W */
} as7263_reading_t;

/* Verify presence, soft-reset, then set integration time + gain + continuous
 * all-6-channel mode. `gain` is an AS7263_GAIN_*; `itime` is the INT_TIME register
 * (x2.8 ms). Returns AS7263_OK / AS7263_ERR_*. */
int as7263_init(const env_i2c_t *bus, uint8_t gain, uint8_t itime);

/* Wait (bounded) for DATA_RDY, then read all six raw channels into out. */
int as7263_read(const env_i2c_t *bus, as7263_reading_t *out);

#ifdef __cplusplus
} /* extern "C" */
#endif
