/*
 * sht45.c - see sht45.h.
 */
#include "sht45.h"

uint8_t sht45_crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0xFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x31)
                               : (uint8_t)(crc << 1);
    }
    return crc;
}

int16_t sht45_temp_centi(uint16_t raw)
{
    /* -4500 + 17500*raw/65535, round-to-nearest; 17500*65535 ~ 1.15e9 fits int32 */
    return (int16_t)(-4500 +
                     (int32_t)((17500L * (int32_t)raw + 32767L) / 65535L));
}

int16_t sht45_rh_centi(uint16_t raw)
{
    int32_t rh = -600 + (int32_t)((12500L * (int32_t)raw + 32767L) / 65535L);
    if (rh < 0) rh = 0; /* physical RH clamps to [0, 100] */
    if (rh > 10000) rh = 10000;
    return (int16_t)rh;
}

int sht45_read(const env_i2c_t *bus, sht45_reading_t *out)
{
    uint8_t cmd = SHT45_CMD_HIGH;
    if (bus->write(SHT45_I2C_ADDR, &cmd, 1, bus->user) != 0)
        return SHT45_ERR_I2C;

    bus->delay_ms(SHT45_MEAS_MS, bus->user);

    uint8_t b[6];
    if (bus->read(SHT45_I2C_ADDR, b, 6, bus->user) != 0) return SHT45_ERR_I2C;

    /* word layout: [T_msb, T_lsb, T_crc, RH_msb, RH_lsb, RH_crc] */
    if (sht45_crc8(&b[0], 2) != b[2] || sht45_crc8(&b[3], 2) != b[5])
        return SHT45_ERR_CRC;

    uint16_t t_raw = (uint16_t)((b[0] << 8) | b[1]);
    uint16_t rh_raw = (uint16_t)((b[3] << 8) | b[4]);

    out->temp_raw = t_raw;
    out->rh_raw = rh_raw;
    out->temp_c_centi = sht45_temp_centi(t_raw);
    out->rh_pct_centi = sht45_rh_centi(rh_raw);
    return SHT45_OK;
}
