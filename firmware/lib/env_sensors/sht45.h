/*
 * sht45.h - Adafruit SHT45 (Sensirion SHT4x) ambient temp/RH driver (#373).
 *
 * CONTEXTUAL telemetry, not plant-truth: a local air reference next to the ESP32
 * for the skylight/solar pass (PRD-0002 env layer, part of #200). I2C addr 0x44,
 * high-precision single-shot measure (cmd 0xFD), 6-byte read with CRC-8 on each
 * 16-bit word, Sensirion's linear conversion. Pure C (fixed-point, no floats) over
 * the injected env_i2c bus — fully native-testable.
 */
#pragma once
#include "env_i2c.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SHT45_I2C_ADDR 0x44
#define SHT45_CMD_HIGH 0xFD  /* measure T+RH, high precision (~8.2 ms) */
#define SHT45_MEAS_MS 10    /* conversion wait before the 6-byte read */

typedef struct {
    uint16_t temp_raw; /* 16-bit raw word from the sensor                  */
    uint16_t rh_raw;
    int16_t temp_c_centi; /* temperature ×100  (2345 = 23.45 °C)              */
    int16_t rh_pct_centi; /* relative humidity ×100, clamped 0..10000         */
} sht45_reading_t;

/* read result codes */
enum {
    SHT45_OK = 0,
    SHT45_ERR_I2C = -1, /* bus write/read failed                            */
    SHT45_ERR_CRC = -2 /* a word's CRC-8 did not match                     */
};

/* Sensirion CRC-8: poly 0x31, init 0xFF, over `len` bytes. */
uint8_t sht45_crc8(const uint8_t *data, size_t len);

/* Pure conversions (exposed for tests). Fixed-point, exact integer math.
 *   T[°C] = -45 + 175 * raw/65535      -> centi = -4500 + 17500*raw/65535
 *   RH[%] = -6  + 125 * raw/65535      -> centi =  -600 + 12500*raw/65535 (clamped) */
int16_t sht45_temp_centi(uint16_t raw);
int16_t sht45_rh_centi(uint16_t raw);

/* Full single-shot read over the bus: write 0xFD, wait, read 6 bytes, CRC-check
 * both words, convert. Returns SHT45_OK / SHT45_ERR_*. */
int sht45_read(const env_i2c_t *bus, sht45_reading_t *out);

#ifdef __cplusplus
} /* extern "C" */
#endif
