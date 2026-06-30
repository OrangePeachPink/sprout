/*
 * as7263.c - see as7263.h.
 */
#include "as7263.h"

/* Bounded handshake polling — never busy-wait forever (a missing/wedged sensor
 * times out instead of hanging the loop). ~POLL_MAX * POLL_MS ms per wait. */
#define AS7263_POLL_MS 3
#define AS7263_POLL_MAX 20 /* ~60 ms for the TX/RX handshake               */
#define AS7263_DATA_MAX 120 /* ~360 ms for a conversion at default int-time */
#define AS7263_RESET_MS 1000 /* device reboot after a soft reset            */

static int phys_read(const env_i2c_t *bus, uint8_t reg, uint8_t *val)
{
    if (bus->write(AS7263_I2C_ADDR, &reg, 1, bus->user) != 0) return -1;
    if (bus->read(AS7263_I2C_ADDR, val, 1, bus->user) != 0) return -1;
    return 0;
}

static int phys_write(const env_i2c_t *bus, uint8_t reg, uint8_t val)
{
    uint8_t b[2] = {reg, val};
    return bus->write(AS7263_I2C_ADDR, b, 2, bus->user) ? -1 : 0;
}

/* wait until STATUS TX_VALID is clear (we may queue a byte to the device) */
static int wait_tx_clear(const env_i2c_t *bus)
{
    uint8_t st;
    for (int i = 0; i < AS7263_POLL_MAX; i++) {
        if (phys_read(bus, AS7263_REG_STATUS, &st) != 0) return AS7263_ERR_I2C;
        if (!(st & AS7263_TX_VALID)) return AS7263_OK;
        bus->delay_ms(AS7263_POLL_MS, bus->user);
    }
    return AS7263_ERR_TIMEOUT;
}

static int vreg_read(const env_i2c_t *bus, uint8_t vreg, uint8_t *out)
{
    uint8_t st;
    /* drain any stale pending byte */
    if (phys_read(bus, AS7263_REG_STATUS, &st) != 0) return AS7263_ERR_I2C;
    if (st & AS7263_RX_VALID) {
        uint8_t junk;
        if (phys_read(bus, AS7263_REG_READ, &junk) != 0) return AS7263_ERR_I2C;
    }
    int rc = wait_tx_clear(bus);
    if (rc != AS7263_OK) return rc;
    if (phys_write(bus, AS7263_REG_WRITE, vreg) != 0)
        return AS7263_ERR_I2C; /* read: vreg w/o 0x80 */
    for (int i = 0; i < AS7263_POLL_MAX; i++) {
        if (phys_read(bus, AS7263_REG_STATUS, &st) != 0) return AS7263_ERR_I2C;
        if (st & AS7263_RX_VALID)
            return phys_read(bus, AS7263_REG_READ, out) ? AS7263_ERR_I2C
                                                        : AS7263_OK;
        bus->delay_ms(AS7263_POLL_MS, bus->user);
    }
    return AS7263_ERR_TIMEOUT;
}

static int vreg_write(const env_i2c_t *bus, uint8_t vreg, uint8_t val)
{
    int rc = wait_tx_clear(bus);
    if (rc != AS7263_OK) return rc;
    if (phys_write(bus, AS7263_REG_WRITE, (uint8_t)(vreg | 0x80)) !=
        0) /* write: vreg | 0x80 */
        return AS7263_ERR_I2C;
    rc = wait_tx_clear(bus);
    if (rc != AS7263_OK) return rc;
    return phys_write(bus, AS7263_REG_WRITE, val) ? AS7263_ERR_I2C : AS7263_OK;
}

int as7263_init(const env_i2c_t *bus, uint8_t gain, uint8_t itime)
{
    uint8_t hw;
    if (vreg_read(bus, AS7263_HW_VERSION, &hw) != AS7263_OK)
        return AS7263_ERR_I2C; /* device not responding */

    int rc = vreg_write(bus, AS7263_CONTROL_SETUP, 0x80); /* soft reset (RST) */
    if (rc != AS7263_OK) return rc;
    bus->delay_ms(AS7263_RESET_MS, bus->user);

    rc = vreg_write(bus, AS7263_INT_TIME, itime);
    if (rc != AS7263_OK) return rc;

    /* GAIN (bits 5:4) + MODE 2 = continuous all six channels (bits 3:2 = 0b10) */
    uint8_t setup = (uint8_t)(((gain & 0x03) << 4) | (0x02 << 2));
    return vreg_write(bus, AS7263_CONTROL_SETUP, setup);
}

int as7263_read(const env_i2c_t *bus, as7263_reading_t *out)
{
    /* wait (bounded) for a fresh conversion */
    int ready = 0;
    for (int i = 0; i < AS7263_DATA_MAX; i++) {
        uint8_t cs;
        if (vreg_read(bus, AS7263_CONTROL_SETUP, &cs) != AS7263_OK)
            return AS7263_ERR_I2C;
        if (cs & AS7263_DATA_RDY) {
            ready = 1;
            break;
        }
        bus->delay_ms(AS7263_POLL_MS, bus->user);
    }
    if (!ready) return AS7263_ERR_TIMEOUT;

    uint16_t *ch[6] = {&out->nm610, &out->nm680, &out->nm730,
                       &out->nm760, &out->nm810, &out->nm860};
    for (int i = 0; i < 6; i++) {
        uint8_t hi, lo;
        if (vreg_read(bus, (uint8_t)(AS7263_R_HIGH + i * 2), &hi) != AS7263_OK)
            return AS7263_ERR_I2C;
        if (vreg_read(bus, (uint8_t)(AS7263_R_HIGH + i * 2 + 1), &lo) !=
            AS7263_OK)
            return AS7263_ERR_I2C;
        *ch[i] = (uint16_t)((hi << 8) | lo);
    }
    return AS7263_OK;
}
