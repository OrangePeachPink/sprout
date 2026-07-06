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
#include <stdbool.h>
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
    /* #601 / ADR-0027 §1b: the friendly name, emitted as name= at the FRONT of the
     * payload on every row (device_id is now the stable nonce; name= is the
     * pre-mint degrade identifier + human legibility). "" or NULL -> empty value. */
    const char *name;
    /* --- #739 schema v4 additions: ALL ride payload k=v / the header - ZERO new
     * CANONICAL_COLUMNS (Trellis's shared-core byte-identity constraint holds). --- */
    uint16_t
        wet_rail_raw; /* #670: board physical wet rail (BOARD_CAP.wet_rail_raw);
                              a raw below it -> SENSOR_FAULT + payload fault=<reason>.
                              0 disables the check (unknown rail -> never self-flag). */
    const char
        *config_id; /* #576 / ADR-0025: firmware-computed config fingerprint,
                              rides payload config_id= (never a canonical column);
                              parse_v1 reads it, never re-derives. NULL/"" omits it. */
    /* #669 board diagnostics (payload). rssi is WiFi-only: rssi_present=false on a
     * serial/tethered row OMITS rssi= entirely - honest-absent, never a fake 0
     * (ADR-0028). uptime_s/heap ride every row (transport-independent). */
    bool rssi_present; /* true only when associated to WiFi              */
    int rssi_dbm; /* WiFi.RSSI() dBm (negative); ignored when !rssi_present */
    uint32_t uptime_s; /* seconds since boot (up_ms / 1000)             */
    uint32_t heap_free; /* esp_get_free_heap_size() bytes                */
} telemetry_soil_row_t;

/*
 * NMEA-style XOR checksum over the row body (B6.4).
 * Used by the caller to append "*HH" after the formatted row.
 */
uint8_t telemetry_checksum(const char *s);

/*
 * FNV-1a 32-bit hash (incremental) - the config_id fingerprint primitive (#576 /
 * ADR-0025). Seed with TELEMETRY_FNV1A32_INIT, fold each config-snapshot field's
 * canonical string in order, then format the final result as 8 lowercase hex.
 * Pure C, deterministic, no allocation - native-testable against a known vector.
 */
#define TELEMETRY_FNV1A32_INIT 2166136261u
uint32_t telemetry_fnv1a32(uint32_t h, const void *data, size_t len);

/*
 * Map classifier state to the shared quality_flag enum (TELEMETRY_SCHEMA.md S4).
 * Returns one of: "SENSOR_FAULT", "SATURATED", "NO_SIGNAL", "SUSPECT", "OK".
 * #670: a raw STRICTLY BELOW the board's physical wet rail (wet_rail_raw, from the
 * board profile) is physically impossible - flagged SENSOR_FAULT, which takes
 * precedence (raw is preserved per ADR-0006; only the trust flag changes). Callers
 * pass BOARD_CAP.wet_rail_raw; native tests pass the classic 900.
 */
const char *telemetry_quality_flag(const moisture_state_t *st,
                                   uint16_t wet_rail_raw);

/*
 * #670 companion reason for the payload `fault=` key: "dead_adc" when the raw floats
 * at/below TELEMETRY_DEAD_ADC_MAX (disconnected / dead ADC), "stuck_wet" when it is
 * below the wet rail but not near-zero (short / water contamination), NULL when the
 * raw is NOT a fault. The coarse SENSOR_FAULT token stays in quality_flag (the shared
 * enum is kept small); the specific reason rides payload so the enum can't balloon
 * (Trellis's #739 binding). Same wet_rail_raw the flag uses.
 */
#define TELEMETRY_DEAD_ADC_MAX 50
const char *telemetry_fault_reason(uint16_t raw, uint16_t wet_rail_raw);

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
    const char *name; /* #601: friendly name, emitted as name= before payload */
    const char
        *config_id; /* #576 / ADR-0025: same config fingerprint, appended to
                              payload as config_id= (never a canonical column). */
} telemetry_env_row_t;

/* Format one plants.env CSV row WITHOUT the trailing "*HH". Returns chars written
 * (not counting NUL), or -1 on truncation. Pure C — native-testable. */
int telemetry_format_env_row(char *buf, size_t buflen,
                             const telemetry_env_row_t *r);

/*
 * Format one per-channel cal-provenance header line (#404, format locked with
 * Data's #507 parser):
 *   # cal_ch <sensor_id>: bounds=<d1,...,d6> src=<...> [date=<...>]
 *     confidence=<provisional|calibrated|corroborated> scope=<channel|shared>
 * Space-separated k=v (the `# cfg:` convention, NOT the payload's `;` one);
 * bounds are the DESCENDING (dry>wet) raw ints, moisture_classifier order.
 * `date` is omitted entirely (not an empty key) when NULL/"" - same honest-NULL
 * rule as device_timestamp_utc. Returns chars written, or -1 on truncation.
 */
int telemetry_format_cal_ch(char *buf, size_t buflen, const char *sensor_id,
                            const uint16_t *bounds, int bounds_count,
                            const char *src, const char *date,
                            const char *confidence, const char *scope);

#ifdef __cplusplus
} /* extern "C" */
#endif
