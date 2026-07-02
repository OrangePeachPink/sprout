#include "telemetry.h"
#include "moisture_classifier.h"
#include <stdio.h>
#include <stdint.h>

uint8_t telemetry_checksum(const char *s)
{
    uint8_t c = 0;
    while (*s)
        c ^= (uint8_t)*s++;
    return c;
}

const char *telemetry_quality_flag(const moisture_state_t *st)
{
    uint16_t raw = st->last_raw;
    if (raw >= 4090 || raw <= 5) return "SATURATED";  /* ADC railed */
    if (st->last_spread >= 2000)
        return "NO_SIGNAL";  /* floating / disconnected */
    if (st->health_warn) return "SUSPECT";    /* noisy / poor contact */
    return "OK";
}

int telemetry_format_soil_row(char *buf, size_t buflen,
                              const telemetry_soil_row_t *r)
{
    /* payload: level=X;role=Y;spread=N;gpio=P;device_seq=N;time_source=S
     * [;device_timestamp_utc=T] (k=v, ';'-sep, no commas). Time-provenance
     * fields (#278, schema v2 §11.1/§11.2) ride the existing payload field -
     * additive, doesn't touch the fixed 14-column CSV shape. Field NAMES match
     * the ratified schema verbatim. device_timestamp_utc is OMITTED (not an
     * empty key) when NULL/unsynced - absence, not a guessed value, is the
     * honest NULL here. */
    char payload[160];
    int len = snprintf(payload, sizeof(payload),
                       "level=%s;role=%s;spread=%u;gpio=%d;device_seq=%lu;"
                       "time_source=%s",
                       moisture_level_name(r->level),
                       moisture_level_is_display(r->level) ? "disp" : "diag",
                       (unsigned)r->state->last_spread, r->gpio_pin,
                       (unsigned long)r->device_seq, r->time_source);
    if (r->device_timestamp_utc && r->device_timestamp_utc[0] != '\0' &&
        len > 0 && (size_t)len < sizeof(payload)) {
        snprintf(payload + len, sizeof(payload) - (size_t)len,
                 ";device_timestamp_utc=%s", r->device_timestamp_utc);
    }

    /*
     * Compact device CSV row — host prepends time/sequence columns (B2 split).
     * value + unit are emitted NULL (empty fields): raw_value (ADC counts) and
     * the band (payload 'level') are authoritative (#38).
     */
    int n = snprintf(buf, buflen, "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%u,,,%s,%s",
                     r->record_type, r->session_id, r->device_id, r->fw_version,
                     r->up_ms, r->sensor_model, r->sensor_name,
                     r->sensor_position, r->channel_str, (unsigned)r->raw,
                     telemetry_quality_flag(r->state), payload);
    return (n >= 0 && (size_t)n < buflen) ? n : -1;
}

int telemetry_format_env_row(char *buf, size_t buflen,
                             const telemetry_env_row_t *r)
{
    /* Same 14 device columns as the soil row; value/unit/raw are pre-formatted
     * strings ("" = NULL). The host loader expands both row types identically. */
    int n = snprintf(buf, buflen, "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%s,%s,%s,%s,%s",
                     r->record_type, r->session_id, r->device_id, r->fw_version,
                     r->up_ms, r->sensor_model, r->sensor_id,
                     r->sensor_position, r->channel, r->raw_value, r->value,
                     r->unit, r->quality_flag, r->payload);
    return (n >= 0 && (size_t)n < buflen) ? n : -1;
}

int telemetry_format_cal_ch(char *buf, size_t buflen, const char *sensor_id,
                            const uint16_t *bounds, int bounds_count,
                            const char *src, const char *date,
                            const char *confidence, const char *scope)
{
    /* # cal_ch s3: bounds=3123,2140,1830,1520,1150,969 src=... date=...
     * confidence=provisional scope=channel  - format locked with Data's #507
     * parser (_parse_cal_channel / ChannelCal). date omitted when NULL/"". */
    int n = snprintf(buf, buflen, "# cal_ch %s: bounds=", sensor_id);
    if (n < 0 || (size_t)n >= buflen) return -1;
    for (int i = 0; i < bounds_count; i++) {
        int w = snprintf(buf + n, buflen - (size_t)n, "%s%u", i ? "," : "",
                         (unsigned)bounds[i]);
        if (w < 0 || (size_t)(n + w) >= buflen) return -1;
        n += w;
    }
    int w;
    if (date && date[0] != '\0')
        w = snprintf(buf + n, buflen - (size_t)n,
                     " src=%s date=%s confidence=%s scope=%s", src, date,
                     confidence, scope);
    else
        w = snprintf(buf + n, buflen - (size_t)n,
                     " src=%s confidence=%s scope=%s", src, confidence, scope);
    if (w < 0 || (size_t)(n + w) >= buflen) return -1;
    return n + w;
}
