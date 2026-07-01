/*
 * telemetry.h - soil row formatting for the plants controller.
 *
 * Pure C, no Arduino/Serial dependency: the format functions are native-testable
 * and callable from the irrigation supervisor (lib/irrigation) once the autonomous
 * loop (#94) lands. The Arduino-side Serial emit stays in main.cpp as a thin wrapper.
 *
 * Per ADR-0016: when the supervisor takes over as the single sample owner (#227 Slice B),
 * it calls telemetry_format_soil_row() and emits via a registered callback rather than
 * from the main.cpp loop directly.
 */
#pragma once
#include <stddef.h>
#include <stdint.h>
#include "moisture_classifier.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * All fields needed to format one soil telemetry CSV row.
 * Callers fill this from their local state and pass it to telemetry_format_soil_row().
 * Using a struct keeps the function signature stable as fields evolve.
 */
typedef struct {
    const char *record_type;     /* e.g. RECORD_TYPE_SOIL ("plants.soil") */
    const char *session_id;      /* per-boot nonce (6 hex chars)           */
    const char *device_id;       /* friendly name (custom or default)      */
    const char *fw_version;      /* PLANTS_FW_VERSION                      */
    unsigned long long up_ms; /* 64-bit uptime (esp_timer / 1000)       */
    const char *sensor_model; /* e.g. SENSOR_MODEL                      */
    const char *sensor_name; /* per-channel name, e.g. "s3"            */
    const char *sensor_position; /* e.g. SENSOR_POSITION                   */
    const char *channel_str; /* e.g. SOIL_CHANNEL ("soil_moisture")    */
    int gpio_pin; /* SENSOR_PINS[ch]                        */
    uint16_t raw; /* last trimmed-mean ADC value            */
    moisture_level_t level; /* committed classifier level             */
    const moisture_state_t *state; /* full classifier state (spread, health) */
    /* --- device-owned time provenance (#278, schema v2 §11.1/§11.2) ---
     * Rides the existing payload field (additive, doesn't touch the fixed
     * 14-column CSV shape) - reviewable/adjustable without a wire-format
     * coordination round; the schema's ratified field NAMES are used verbatim
     * so Data's future parser can lift them straight out of payload. */
    uint32_t device_seq; /* device-monotonic, survives reconnect, resets on
                            reboot (same semantics as session_id) - the row's
                            true emission order regardless of transport delay */
    const char *time_source; /* "host" | "device_synced" | "device_uptime" -
                                which clock this row's time comes from */
    const char *device_timestamp_utc; /* device's own UTC stamp, or NULL/""
                                         when unsynced - NEVER a guessed value.
                                         Omitted from payload entirely (not
                                         printed as an empty key) when NULL. */
} telemetry_soil_row_t;

/*
 * NMEA-style XOR checksum over the row body (B6.4).
 * Used by the caller to append "*HH" after the formatted row.
 */
uint8_t telemetry_checksum(const char *s);

/*
 * Map classifier health to the shared quality_flag enum (TELEMETRY_SCHEMA.md S4).
 * Returns one of: "OK", "SUSPECT", "NO_SIGNAL", "SATURATED".
 */
const char *telemetry_quality_flag(const moisture_state_t *st);

/*
 * Format one soil telemetry CSV row into buf WITHOUT the trailing "*HH" checksum.
 * value + unit are emitted as empty fields (NULL): raw_value (ADC counts) and band
 * (payload 'level') are authoritative; value/unit are reserved for a future calibrated
 * VWC, never an uncalibrated % (#38).
 *
 * Returns: chars written (not counting NUL), or -1 on truncation.
 * Pure C, no Serial — native-testable, supervisor-callable.
 */
int telemetry_format_soil_row(char *buf, size_t buflen,
                              const telemetry_soil_row_t *r);

/*
 * Generic contextual-environment row (record_type=plants.env) for the bench
 * instrumentation sensors (SHT45 temp/RH, AS7263 spectral — #373/#374). Same
 * 14-column device-row shape as the soil row; the type-specific values ride the
 * string fields so temp/RH (value+unit set) and a spectral row (channels in
 * payload) both fit one formatter. Empty string ("") = a NULL column.
 *
 * Contextual telemetry, NOT plant-truth — the placement note belongs in payload.
 */
typedef struct {
    const char *record_type; /* "plants.env"                         */
    const char *session_id;
    const char *device_id;
    const char *fw_version;
    unsigned long long up_ms;
    const char *sensor_model; /* "SHT45" / "AS7263"                   */
    const char *sensor_id; /* "sht45" / "as7263"                   */
    const char *sensor_position; /* short placement, e.g. "breadboard"   */
    const char *channel; /* "ambient_temp" / "ambient_rh" / "spectral_nir" */
    const char *raw_value; /* "" for NULL                          */
    const char *value; /* "" for NULL                          */
    const char *unit; /* "C" / "%RH" / "" for NULL            */
    const char *quality_flag; /* shared enum (S4)                     */
    const char *payload; /* ";"-sep k=v, incl. the placement note */
} telemetry_env_row_t;

/* Format one plants.env CSV row WITHOUT the trailing "*HH". Returns chars written
 * (not counting NUL), or -1 on truncation. Pure C — native-testable. */
int telemetry_format_env_row(char *buf, size_t buflen,
                             const telemetry_env_row_t *r);

#ifdef __cplusplus
} /* extern "C" */
#endif
