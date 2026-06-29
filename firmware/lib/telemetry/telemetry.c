#include "telemetry.h"
#include "moisture_classifier.h"
#include <stdio.h>
#include <stdint.h>

uint8_t telemetry_checksum(const char *s) {
    uint8_t c = 0;
    while (*s) c ^= (uint8_t)*s++;
    return c;
}

const char *telemetry_quality_flag(const moisture_state_t *st) {
    uint16_t raw = st->last_raw;
    if (raw >= 4090 || raw <= 5) return "SATURATED";  /* ADC railed */
    if (st->last_spread >= 2000) return "NO_SIGNAL";  /* floating / disconnected */
    if (st->health_warn)         return "SUSPECT";    /* noisy / poor contact */
    return "OK";
}

int telemetry_format_soil_row(char *buf, size_t buflen,
                              const telemetry_soil_row_t *r) {
    /* payload: level=X;role=Y;spread=N;gpio=P (k=v, ';'-sep, no commas) */
    char payload[64];
    snprintf(payload, sizeof(payload), "level=%s;role=%s;spread=%u;gpio=%d",
             moisture_level_name(r->level),
             moisture_level_is_display(r->level) ? "disp" : "diag",
             (unsigned)r->state->last_spread, r->gpio_pin);

    /*
     * Compact device CSV row — host prepends time/sequence columns (B2 split).
     * value + unit are emitted NULL (empty fields): raw_value (ADC counts) and
     * the band (payload 'level') are authoritative (#38).
     */
    int n = snprintf(buf, buflen,
                     "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%u,,,%s,%s",
                     r->record_type, r->session_id, r->device_id, r->fw_version,
                     r->up_ms, r->sensor_model, r->sensor_name, r->sensor_position,
                     r->channel_str, (unsigned)r->raw,
                     telemetry_quality_flag(r->state), payload);
    return (n >= 0 && (size_t)n < buflen) ? n : -1;
}
