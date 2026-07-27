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

uint32_t telemetry_fnv1a32(uint32_t h, const void *data, size_t len)
{
    const uint8_t *p = (const uint8_t *)data;
    for (size_t i = 0; i < len; i++) {
        h ^= p[i];
        h *= 16777619u; /* FNV-1a 32-bit prime */
    }
    return h;
}

const char *telemetry_quality_flag(const moisture_state_t *st,
                                   uint16_t wet_rail_raw, uint16_t air_dry_raw)
{
    uint16_t raw = st->last_raw;
    /* #670: a raw below the physical wet rail is impossible - a fault (short /
     * water contamination) or a dead ADC floating low, never real moisture. Takes
     * precedence; raw is preserved (ADR-0006). This replaces the old
     * `raw <= 5 -> SATURATED`, which masked dead boards as drowning plants (the
     * live s3-1 0/7/4/1 case). wet_rail_raw==0 disables the check (unknown rail). */
    if (wet_rail_raw > 0 && raw < wet_rail_raw) return "SENSOR_FAULT";
    if (raw >= 4090) return "SATURATED"; /* dry-rail: ADC railed high (clamp) */
    /* #1152: the SYMMETRIC MIRROR of the sub-wet-rail fault. Above the board's
     * air rail (but not pegged) is impossibly dry for soil - an open circuit or
     * a disconnected lead, not a very thirsty plant. Ordered AFTER the peg check
     * so the pegged-clamp condition keeps its own distinct SATURATED value. */
    if (air_dry_raw > 0 && raw > air_dry_raw) return "SENSOR_FAULT";
    if (st->last_spread >= 2000)
        return "NO_SIGNAL"; /* floating / disconnected */
    if (st->rate_spike)
        return "SUSPECT"; /* #1152 kinematics: implausible step */
    if (st->health_warn) return "SUSPECT"; /* noisy / poor contact */
    return "OK";
}

const char *telemetry_fault_reason(const moisture_state_t *st,
                                   uint16_t wet_rail_raw, uint16_t air_dry_raw)
{
    uint16_t raw = st->last_raw;
    /* Hard (physically impossible) faults first - they outrank a kinematics
     * hint, which only says the STEP was implausible, not the reading. */
    if (wet_rail_raw > 0 && raw < wet_rail_raw) {
        if (raw <= TELEMETRY_DEAD_ADC_MAX)
            return "dead_adc"; /* floating to ~0: disconnected / dead ADC */
        return "stuck_wet"; /* below rail, not near-zero: short / contamination */
    }
    /* #1152 physics mirror: impossibly dry -> open circuit / disconnected lead */
    if (air_dry_raw > 0 && raw > air_dry_raw && raw < 4090) return "open_adc";
    /* #1152 kinematics: the reading may be real but the jump is not trustable */
    if (st->rate_spike) return "rate_spike";
    return NULL; /* not a fault */
}

int telemetry_format_soil_row(char *buf, size_t buflen,
                              const telemetry_soil_row_t *r)
{
    /* payload: name=L;level=X;role=Y;spread=N;gpio=P;device_seq=N;time_source=S
     * [;device_timestamp_utc=T] (k=v, ';'-sep, no commas). name= (#601 / ADR-0027
     * §1b) LEADS - device_id is now the stable nonce, so name= carries the friendly
     * label + is the pre-mint degrade identifier. Time-provenance fields (#278,
     * schema §11) ride the payload too - additive, doesn't touch the 14-column CSV
     * shape. device_timestamp_utc is OMITTED (not an empty key) when NULL/unsynced -
     * absence, not a guessed value, is what NULL means here. */
    char payload
        [384]; /* #601 name= + #739 v4 keys + #952/#997 cal_tier/cal_src on WiFi
                  rows. Sized for the worst-case field combo (WiFi + SNTP-synced
                  device_timestamp_utc + a fault reason + cal provenance) so no
                  additive key is ever silently dropped from a full row. */
    /* #1434 AC0: step= is the SIGNED raw delta from the previous accepted sample -
     * the exact quantity rate_spike compares to max_delta_raw. It rides the base
     * payload (always present, never a dropped tail key) next to its sibling
     * spread=, so the kinematics check is auditable from the wire: a reader can
     * verify (|step| > threshold) <=> fault=rate_spike, and read direction
     * (wetter vs drier) for the exception taxonomy. Emitting it here - not
     * reconstructing it from logged rows - is the point: logged rows differ from
     * the classifier's accepted-sample sequence across any dropped row. */
    int len =
        snprintf(payload, sizeof(payload),
                 "name=%s;level=%s;role=%s;spread=%u;step=%d;gpio=%d;"
                 "device_seq=%lu;time_source=%s",
                 r->name ? r->name : "", moisture_level_name(r->level),
                 moisture_level_is_display(r->level) ? "disp" : "diag",
                 (unsigned)r->state->last_spread, (int)r->state->last_delta,
                 r->gpio_pin, (unsigned long)r->device_seq, r->time_source);
    /* Each append is bounds-guarded; a would-be overflow just drops the tail key
     * (snprintf still NUL-terminates - never a partial-but-unterminated payload). */
    if (r->device_timestamp_utc && r->device_timestamp_utc[0] != '\0' &&
        len > 0 && (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";device_timestamp_utc=%s", r->device_timestamp_utc);
    }
    /* #576 / ADR-0025: per-row config-provenance ref (firmware-computed hash). */
    if (r->config_id && r->config_id[0] != '\0' && len > 0 &&
        (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";config_id=%s", r->config_id);
    }
    /* #670: the specific fault reason rides payload; the coarse SENSOR_FAULT token
     * is in quality_flag (below). NULL when the raw is not a fault. */
    const char *fault =
        telemetry_fault_reason(r->state, r->wet_rail_raw, r->air_dry_raw);
    if (fault && len > 0 && (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";fault=%s", fault);
    }
    /* #669: rssi is absent off WiFi (omit, never a placeholder 0); uptime_s/heap
     * ride every row (transport-independent board diagnostics). */
    if (r->rssi_present && len > 0 && (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";rssi=%d", r->rssi_dbm);
    }
    if (len > 0 && (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";uptime_s=%lu;heap=%lu", (unsigned long)r->uptime_s,
                        (unsigned long)r->heap_free);
    }
    /* #952/#957/#997: cal provenance rides the WiFi soil rows (same gate as rssi -
     * rssi_present == WiFi-associated). The header cal signals are tethered-only, so
     * this wire token is the off-tether supplement; a tethered row omits it and the
     * header derivation governs (Data #997 fallback). Omitted (not an empty key)
     * when the value is NULL/"" - absent, never a guessed token. */
    if (r->rssi_present && r->cal_tier && r->cal_tier[0] != '\0' && len > 0 &&
        (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";cal_tier=%s", r->cal_tier);
    }
    if (r->rssi_present && r->cal_src && r->cal_src[0] != '\0' && len > 0 &&
        (size_t)len < sizeof(payload)) {
        len += snprintf(payload + len, sizeof(payload) - (size_t)len,
                        ";cal_src=%s", r->cal_src);
    }
    (void)len;

    /*
     * Compact device CSV row — host prepends time/sequence columns (B2 split).
     * value + unit are emitted NULL (empty fields): raw_value (ADC counts) and
     * the band (payload 'level') are authoritative (#38).
     */
    int n = snprintf(
        buf, buflen, "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%u,,,%s,%s", r->record_type,
        r->session_id, r->device_id, r->fw_version, r->up_ms, r->sensor_model,
        r->sensor_name, r->sensor_position, r->channel_str, (unsigned)r->raw,
        telemetry_quality_flag(r->state, r->wet_rail_raw, r->air_dry_raw),
        payload);
    return (n >= 0 && (size_t)n < buflen) ? n : -1;
}

int telemetry_format_env_row(char *buf, size_t buflen,
                             const telemetry_env_row_t *r)
{
    /* Same 14 device columns as the soil row; value/unit/raw are pre-formatted
     * strings ("" = NULL). The host loader expands both row types identically.
     * #601: name= leads the payload here too, so every row (soil AND env) carries
     * the friendly label + the pre-mint degrade identifier (ADR-0027 §1b). */
    int n = snprintf(
        buf, buflen, "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%s,%s,%s,%s,name=%s;%s",
        r->record_type, r->session_id, r->device_id, r->fw_version, r->up_ms,
        r->sensor_model, r->sensor_id, r->sensor_position, r->channel,
        r->raw_value, r->value, r->unit, r->quality_flag,
        r->name ? r->name : "", r->payload);
    /* #576 / ADR-0025: append the config-provenance ref to the payload column (the
     * last field) so env rows are as self-interpreting as soil rows. */
    if (r->config_id && r->config_id[0] != '\0' && n > 0 &&
        (size_t)n < buflen) {
        n += snprintf(buf + n, buflen - (size_t)n, ";config_id=%s",
                      r->config_id);
    }
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
