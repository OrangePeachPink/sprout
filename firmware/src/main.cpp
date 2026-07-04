/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * schema v3 - FOUR soil sensors, supervisor-driven (#94/#227, ADR-0016). The
 * irrigation supervisor (lib/irrigation) is the SINGLE sample & actuation
 * authority: ticked every loop, it owns the ADC sweep (one channel at a time,
 * never while a pump runs), classifies each channel, vetoes on health, and — when
 * ARMED — doses. Telemetry rows are derived from supervisor state and emitted only
 * in SYS_SAMPLING (one compact CSV row per sensor; the host adds UTC/sequence — the
 * B2 split, docs/TELEMETRY_SCHEMA.md).
 *
 * Autonomous dosing ships DISARMED: !auto,on arms it, only after the dry-safety
 * chain (#93/#191/#2/#215) passes on the bench. Manual !water is a forced dose into
 * the supervisor (single authority); !stop is the e-stop.
 *
 * Serial command surface: lib/commands (cad/ping/ver/cfg/name/water/stop/auto/label/pos).
 * Telemetry row formatting: lib/telemetry (checksum/quality_flag/format_soil_row).
 * Run metadata: lib/run_meta (#321). Watchdog: a hung loop -> chip reset ->
 * allRelaysOff() re-runs (#93).
 */

#include <Arduino.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_task_wdt.h>
#include <esp_idf_version.h> /* ESP_IDF_VERSION - the watchdog API split at IDF5 (#499) */
#include <Preferences.h>
#include <string.h>
#include "config.h"
#include "moisture_classifier.h"
#include "serial_cmd.h"
#include "irrigation.h"
#include "telemetry.h"
#include "commands.h"
#include "run_meta.h"
#include "board_capability.h" /* per-board capability descriptor + gate seam (#273) */
#include "device_uid.h" /* #601 stable-id base32 mint (ADR-0027 §1b) */
#include "calibration.h" /* SENSOR_CAL_BOUNDARY[ch] — per-channel raw->band (#170) */

/* The calibration table and the firmware must agree on the channel count. */
static_assert(SENSOR_CAL_CHANNELS == NUM_SENSORS,
              "calibration.h channel count must match NUM_SENSORS");
#include "wifi_net.h" /* connect/retry/portal state machine, pure C (#21/#275) */
#include <WiFi.h>
#include <WebServer.h> /* core-bundled, no lib_deps entry needed */
#include <DNSServer.h> /* captive-portal catch-all DNS (#275, core-bundled) */
#include <time.h> /* NTP-on-connect (#278): configTime/gmtime_r/strftime */
#include <sys/time.h> /* gettimeofday - ms precision for device_timestamp_utc */

#ifdef ENABLE_ENV_SENSORS
#include <Wire.h>
#include "env_i2c.h"
#include "sht45.h"
#include "as7263.h"
#endif

#ifndef GIT_REV
#define GIT_REV "nogit"  /* overridden by scripts/git_rev.py at build */
#endif

/* Identity (ADR-0027 §1b / #601). device_id is the STABLE minted id - a 6-char
 * base32 nonce (device_uid lib), minted once in setup() after RF is up and
 * persisted to NVS; never the friendly name, never MAC/eFuse-derived (ADR-0020).
 * Empty until minted (setup mints before printHeader + the first telemetry row). */
static char g_device_id[32] = "";
/* The friendly, re-nameable label (#188 / #600). Rides telemetry as name= on every
 * row (#601); the registry (#592) is its authoritative home, this is the device's
 * cached copy so the banner / GET-/ show a human name without a lookup (ADR-0027
 * rider 2). Loaded from NVS "device_name" in commands_init; set by !name. */
static char g_device_name[32] = "Sprout ESP32";
static bool g_device_name_custom = false;
static char g_session_id[12] = "000000";

/* Device-owned time provenance (#278, ADR-0018 + schema v2 §11.1/§11.2, ratified
 * 2026-07-01). device_seq: monotonic per emitted telemetry row, survives a
 * store-and-forward reconnect/replay (the dedupe key's device-side half); resets
 * only on reboot, same lifecycle as g_session_id - a fresh `static` already gives
 * this for free. time_source is HONEST about what this firmware can currently
 * prove: no NTP/RTC sync path exists yet (WiFi connect itself isn't wired, #21),
 * so every row correctly reports "device_uptime" with device_timestamp_utc
 * omitted (NULL) - never a guessed/fabricated UTC value. Flips to
 * "device_synced" (+ a real device_timestamp_utc) once #21 lands NTP-on-connect;
 * this counter + field plumbing is ready for that day without a wire change. */
static uint32_t g_device_seq = 0;
constexpr const char *TIME_SOURCE_DEVICE_UPTIME = "device_uptime";
constexpr const char *TIME_SOURCE_DEVICE_SYNCED = "device_synced";

/* NTP-on-connect (#278 tail / ADR-0018 §3): configTime() arms SNTP on each WiFi
 * association (see loop()); rows flip to device_synced only once the clock is
 * REAL. The sanity floor rejects the epoch-zero default - a clock before
 * 2025-01-01 means SNTP hasn't answered yet, so we keep reporting
 * device_uptime rather than stamping rows with 1970. */
static bool timeIsSynced(void)
{
    return time(nullptr) > 1735689600; /* 2025-01-01T00:00:00Z */
}

/* ISO-8601 UTC with millisecond precision, e.g. 2026-07-02T03:15:30.412Z -
 * the device_timestamp_utc format schema v2 §11.1 documents. */
static void isoUtcNow(char *out, size_t n)
{
    struct timeval tv;
    gettimeofday(&tv, nullptr);
    struct tm tmv;
    time_t secs = tv.tv_sec;
    gmtime_r(&secs, &tmv);
    size_t len = strftime(out, n, "%Y-%m-%dT%H:%M:%S", &tmv);
    if (len > 0 && len + 6 <= n)
        snprintf(out + len, n - len, ".%03ldZ", (long)(tv.tv_usec / 1000));
}

/* Sweep cadence is owned by the supervisor (g_sys.sample_period_ms, #227);
 * runtime-settable via !cad (#63), persisted to NVS (#90). This flag only tracks
 * whether the live value came from NVS, for the header. */
static bool g_cadence_from_nvs = false;
/* true when the live cadence is a session-only !cad,temp override — not persisted,
 * reverts to the saved/compiled default on reset (#322). */
static bool g_cadence_temp = false;

/* NVS store: opened once in commands_init(), kept open for the session (#90). */
static Preferences g_prefs;

/* WiFi connect-scaffold (#21 desk-buildable slice). Credentials are NVS-backed
 * via !wifi (lib/commands); the state machine (lib/wifi_net, pure C) owns the
 * connect/retry/reconnect policy, ticked every loop(). WiFi is a convenience/
 * telemetry layer — never a dependency of the safety loop, which runs unchanged
 * whether or not this ever connects. */
static wifi_net_ctx_t g_wifi;
static char g_wifi_ssid[64] = "";
static char g_wifi_pass[64] = "";
static bool g_wifi_creds_dirty = false;

/* Captive portal (#275, ADR-0020 §4): config-only AP + catch-all DNS so a
 * phone's captive-detection probe lands on /setup. The AP name is synthetic
 * (ADR-0020 §2): WIFI_AP_PREFIX + a generated suffix persisted in NVS - never
 * MAC/silicon-derived. Raised/torn down on wifi_net state EDGES in loop(). */
static DNSServer g_dns;
static bool g_portal_up = false;
static char g_ap_name[32] = "";

/* Served-status skeleton (#21): minimal read-only status page. No control
 * endpoints here — manual actuation over the network (with auth + the same
 * safety interlocks as autonomous watering) is this issue's later, separate
 * slice, not this connect-scaffold. */
static WebServer g_http(WIFI_HTTP_PORT);

/* Served-telemetry cache (#276): the latest formatted soil row (+checksum) per
 * channel, written at EMIT time and served on request — an HTTP hit never
 * triggers a sample (the supervisor stays the single sample authority,
 * ADR-0016). Same bytes as the serial wire ("one schema, every transport",
 * ADR-0018 §4), so the future device-served reader adapter parses it with the
 * same parse path as the serial stream. Empty = no row emitted yet. */
static char g_last_row[NUM_SENSORS][320];

/* Served-telemetry env cache (#598): the plants.env rows (die-temp on every build;
 * SHT45/AS7263 on the env build) from the latest emit cycle, cached the same way as
 * g_last_row so an UNTETHERED board serves its ambient context on /telemetry too -
 * #276 served soil only, leaving the skylight-confound sensors invisible off-cable.
 * Reset once per cadence tick in loop() (BEFORE the env + die appends, every build),
 * appended by emitEnvLine. Same wire bytes as serial (ADR-0018 §4). */
#define MAX_ENV_ROWS                                                           \
    10 /* SHT temp+rh (2) + AS7263 NIR (6) + die-temp (1) + margin */
static char g_last_env[MAX_ENV_ROWS][288];
static uint8_t g_last_env_count = 0;

/* Run metadata (#321): run_label + per-channel sensor_position, seeded from the
 * config.h defaults and updated at runtime via !label / !pos so the bench can
 * move probes between plants without reflashing (stale metadata = join hazard). */
static run_meta_t g_run_meta;

/* Shared classifier config template — acquisition / hysteresis / persistence /
 * health are shared across channels. Its boundary[] is the shared-interior
 * reference + default rails; at setup each g_mcfg[ch] takes these shared fields
 * but OVERRIDES boundary[] per-channel from calibration.h (C1/#170). The header
 * prints BOTH tiers: this shared template (`# cal bounds`, the fallback) and
 * each channel's diverged rails (`# cal_ch`, #404). */
static moisture_cfg_t cfg = {
    SAMPLES_PER_READ,
    SAMPLES_TRIM,
    60, /* deadband_raw */
    3000, /* confirm_ms_soil (TESTING; prod 8000) */
    3000, /* confirm_ms_dry  (TESTING; prod 8000) */
    2000, /* confirm_ms_wet  (TESTING; prod 3500) */
    READ_INTERVAL_MS,
    250, /* spread_warn_raw */
    /* boundary (descending raw): 7-band scheme (#3), sourced from the board
     * descriptor (#436) - classic's are ENDPOINT-RATIFIED against the #248
     * common-cup anchors (ADR-0006 §6, cal_verified=true); a non-classic board's
     * are the documented placeholder (cal_verified=false) until #443 bench work.
     * Interior [1..3] still interpolated regardless of board - pending the
     * controlled dry-down. See lib/moisture_classifier for semantics. */
    {BOARD_CAP.cal_boundary[0], BOARD_CAP.cal_boundary[1],
     BOARD_CAP.cal_boundary[2], BOARD_CAP.cal_boundary[3],
     BOARD_CAP.cal_boundary[4], BOARD_CAP.cal_boundary[5]},
    SENSOR_CAPACITIVE, /* committed v1 path (ADR-0019 §3); resistive is a per-channel seam */
};

/* Per-channel classifier state — owned here, used by the supervisor as its mstate. */
static moisture_state_t state[NUM_SENSORS];

/* --- The watering supervisor (#94/#227, ADR-0016) -------------------------- */
/* The supervisor is the single sample & actuation authority. It owns the ADC
 * sweep and the relays; main.cpp supplies the I/O callbacks + cfg and ticks it
 * every loop. Autonomous dosing ships DISARMED (see setup) — the bench arms it
 * with !auto only after the dry-safety chain (#93/#191/#2/#215) passes. */
static irrig_ctrl_t g_irrig;
static moisture_cfg_t g_mcfg
    [NUM_SENSORS]; /* per-channel: shared cfg + per-channel boundary (#170) */
static irrig_chan_cfg_t
    g_chan_cfg[NUM_SENSORS]; /* per-channel dose policy (provisional) */
static uint16_t
    g_scratch[SAMPLES_PER_READ]; /* FSM burst buffer (>= sample_count) */

/* Autonomous irrigation policy (PROVISIONAL, #227 / ADR-0016) — kept in main.cpp,
 * NOT config.h, so config.h's manual alignment stays off the #343 changed-files
 * clang-format gate (move back once git-clang-format lands). Real dose/soak/
 * thresholds come from calibration (#170/#192). SAFETY: dosing ships DISARMED
 * (the arm gate); armed only after the dry-safety chain passes on real hardware.
 * Every dose is bounded by PUMP_PULSE_MAX_MS (hard ceiling, < WDT_TIMEOUT_MS). */
constexpr uint32_t IRRIG_DOSE_MS = 1500; /* pump run per autonomous dose */
constexpr uint32_t IRRIG_SOAK_MS =
    300000UL; /* 5 min lockout before re-deciding */
constexpr uint32_t IRRIG_SETTLE_MS =
    5000; /* post-dose settle before re-sampling */
constexpr uint8_t IRRIG_MAX_DOSES = 3; /* non-improving doses -> latch fault */
constexpr uint16_t IRRIG_MIN_IMPROVEMENT_RAW =
    80; /* min raw drop to count as progress */
static_assert(IRRIG_DOSE_MS <= PUMP_PULSE_MAX_MS,
              "autonomous dose must fit under the hard pump ceiling");

/* Idle sweep cadence + dose/soak/fault policy. sample_period_ms is the !cad / NVS
 * target, so this struct is mutable and main.cpp owns it. */
static irrig_sys_cfg_t g_sys = {
    READ_INTERVAL_MS, /* sample_period_ms (runtime-settable via !cad)   */
    ADC_DISCARD, /* adc_discard                                    */
    IRRIG_SETTLE_MS, /* post_pump_settle_ms                            */
    PUMP_PULSE_MAX_MS, /* pump_max_ms (hard ceiling, < WDT_TIMEOUT_MS)   */
    IRRIG_MAX_DOSES, /* max_doses                                      */
    IRRIG_MIN_IMPROVEMENT_RAW, /* min_improvement_raw                            */
    IRRIG_MAX_HEALTH_WARN, /* max_health_warn                                */
};

/* ---- hardware helpers --------------------------------------------------- */

/* Fail-safe: drive every relay to its de-energized level.
 * Called FIRST in setup() and passed as a callback to the commands module. */
static void allRelaysOff()
{
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        pinMode(RELAY_PINS[ch], OUTPUT);
        digitalWrite(RELAY_PINS[ch], RELAY_OFF_LEVEL);
    }
}

/* Drive ONE channel's relay on/off — the single relay-control point (#215). */
static void pumpSet(int ch, bool on)
{
    if (ch < 0 || ch >= NUM_SENSORS) return;
    digitalWrite(RELAY_PINS[ch], on ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
}

/* ---- supervisor I/O callbacks (#227, ADR-0016) -------------------------- */
/* The supervisor is the sole sampler: read_raw returns ONE ADC sample (the FSM
 * does the discard + burst + trimmed mean itself). */
static uint16_t readRaw(int ch, void *user)
{
    (void)user;
    return (uint16_t)analogRead(SENSOR_PINS[ch]);
}

/* The supervisor is the sole actuator: set_pump drives one relay (active-low
 * handled in pumpSet). This is the single relay driver in ship builds. */
static void setPump(int ch, bool on, void *user)
{
    (void)user;
    pumpSet(ch, on);
}

/* Structured event sink. INTERIM diagnostic line (#-comment, not a data row) —
 * the full schema-conformant `plants.pump` records are #18 (Data-coordinated). */
static void onIrrigEvent(const irrig_event_t *ev, void *user)
{
    (void)user;
    char buf[120];
    snprintf(
        buf, sizeof(buf), "# irrig ev=%s ch=%d level=%s raw=%u spread=%u t=%lu",
        irrig_event_name(ev->code), ev->ch, moisture_level_name(ev->level),
        (unsigned)ev->raw, (unsigned)ev->spread, (unsigned long)ev->now_ms);
    Serial.println(buf);
}

#ifdef ENABLE_ENV_SENSORS
/* ---- bench contextual env sensors (#373/#374) --------------------------- */
/* I2C/Qwiic SHT45 (ambient temp/RH) + AS7263 (NIR spectral). Raw CONTEXT, not
 * plant-truth — breadboard-mounted near the ESP32 (see ENV_PLACEMENT below). The
 * pure-C drivers run over these Arduino Wire-backed callbacks. I2C reads never
 * touch the soil ADC, so there's no "no sampling while pumping" concern. */

/* I2C pins come from the board descriptor (ADR-0019 §1, #436) - one place per board
 * describes it. Deployment config below is env-build-only. */
const int ENV_I2C_SDA =
    BOARD_CAP.i2c_sda; /* classic default: GPIO21 (I2C/Qwiic SDA) */
const int ENV_I2C_SCL =
    BOARD_CAP.i2c_scl; /* classic default: GPIO22 (I2C/Qwiic SCL) */
constexpr uint32_t ENV_I2C_HZ = 100000; /* standard-mode I2C */
/* AS7263 analog gain. Sage-ratified gain=16 for direct-beam headroom (#416): the
 * 2026-06-30 skylight pass railed at 64x (51201/65535 on nir_680 x165 rows) -> ~12800
 * at 16x, off the ceiling. FIXED, never auto-ranged (that would break cross-session
 * comparability); the value is logged per row (payload `gain=`) AND in the boot header,
 * so a gain change is always explicit. Raw counts scale ~4x lower vs older 64x captures. */
constexpr uint8_t AS7263_CFG_GAIN = AS7263_GAIN_16X;
constexpr uint8_t AS7263_CFG_ITIME =
    50; /* INT_TIME reg x2.8ms ~140 ms (Sage: hold) */
/* gain enum -> multiplier string; shared by the per-row payload + the boot header (#416). */
static const char *const AS7263_GAIN_MULT[4] = {"1", "3.7", "16", "64"};
constexpr const char *ENV_PLACEMENT =
    "breadboard_near_esp32"; /* canonical sensor_position (#377) */
constexpr const char *ENV_SHT45_PAYLOAD = "mount=breadboard_near_esp32";

static int envI2cWrite(uint8_t addr, const uint8_t *buf, size_t len, void *user)
{
    (void)user;
    Wire.beginTransmission(addr);
    Wire.write(buf, len);
    return Wire.endTransmission() == 0 ? 0 : -1;
}
static int envI2cRead(uint8_t addr, uint8_t *buf, size_t len, void *user)
{
    (void)user;
    if (Wire.requestFrom((int)addr, (int)len) != (int)len) return -1;
    for (size_t i = 0; i < len; i++)
        buf[i] = (uint8_t)Wire.read();
    return 0;
}
static void envI2cDelay(uint32_t ms, void *user)
{
    (void)user;
    delay(ms);
}
static env_i2c_t g_env_i2c = {envI2cWrite, envI2cRead, envI2cDelay, nullptr};
static bool g_as7263_ok = false;
#endif /* ENABLE_ENV_SENSORS */

/* Format + emit one plants.env row with its checksum. Used by the bench env
 * sensors (env build) AND the always-on die-temp row (#345) - so it lives
 * OUTSIDE the ENABLE_ENV_SENSORS guard. */
static void emitEnvLine(const telemetry_env_row_t *row)
{
    char line[300]; /* #601: name= adds up to ~38 bytes vs the prior 256 */
    /* #601: stamp the friendly name onto every env row (payload name=). The row
     * literals the callers build leave .name NULL (zero-init); set it here at the
     * single choke point rather than in each of the ~6 env-row literals. */
    telemetry_env_row_t r = *row;
    r.name = g_device_name;
    if (telemetry_format_env_row(line, sizeof(line), &r) >= 0) {
        char crc[6];
        snprintf(crc, sizeof(crc), "*%02X", telemetry_checksum(line));
        Serial.print(line);
        Serial.println(crc);
        /* #598: cache the exact emitted bytes (row + *CRC) for /telemetry, so an
         * untethered board serves ambient context, not just soil. Reset per cadence
         * tick in loop(); bounded by MAX_ENV_ROWS (a full env cycle fits). */
        if (g_last_env_count < MAX_ENV_ROWS)
            snprintf(g_last_env[g_last_env_count++], sizeof(g_last_env[0]),
                     "%s%s", line, crc);
    }
}

/* ---- ESP32 die temperature (#345) ---------------------------------------- */
/* Board-proxy diagnostic context - the chip's OWN temperature, NOT ambient/soil/
 * water (ADR-0023 source tag: esp32_die, measured/uncalibrated). Purpose: separate
 * "the electronics/ADC reference environment is heating" from "the soil is
 * changing" in the afternoon-drift analysis. Zero external hardware, so it emits
 * on EVERY build (the multi-board fleet won't all carry an SHT45).
 *
 * temperatureRead() (Arduino core): classic ESP32 reads the legacy undocumented
 * ROM sensor - KNOWN CAVEAT: some classic chips have it fused off and return the
 * constant raw 128 -> exactly (128-32)/1.8 C forever; that exact value is flagged
 * SUSPECT rather than silently trusted. S3/C5 use the real IDF5 driver, which
 * returns NAN on failure -> NO_SIGNAL. */
static void emitDieTempRow(unsigned long long up_ms)
{
    /* the classic fused-off sentinel: raw 128 through (x-32)/1.8, bit-exact */
    const float kFusedOffSentinel = (128.0f - 32.0f) / 1.8f;
    float c = temperatureRead();
    char val[16] = "";
    const char *unit = "";
    const char *q = "NO_SIGNAL";
    if (!isnan(c)) {
        snprintf(val, sizeof(val), "%.2f", (double)c);
        unit = "degC";
        q = (c == kFusedOffSentinel) ? "SUSPECT" : "OK";
    }
    telemetry_env_row_t r = {"plants.env",
                             g_session_id,
                             g_device_id,
                             PLANTS_FW_VERSION,
                             up_ms,
                             "ESP32",
                             "esp32_die",
                             "on_chip",
                             "die_temp",
                             "",
                             val,
                             unit,
                             q,
                             "source=esp32_die;cal=uncalibrated_board_proxy;"
                             "api=temperatureRead"};
    emitEnvLine(&r);
}

#ifdef ENABLE_ENV_SENSORS

/* Read the env sensors + emit plants.env rows (contextual; ratified mapping #377).
 * SHT45 -> ambient_temp/ambient_rh with REAL value+unit (factory-calibrated, so the
 * soil raw-only law does NOT apply). AS7263 -> six TIDY rows (one per NIR band, raw
 * counts). Placement rides sensor_position. A CRC/bus failure surfaces as a
 * quality_flag row, never a silent gap. */
static void emitEnvRows(unsigned long long up_ms)
{
    /* --- SHT45: factory-calibrated ambient temp + RH (value+unit populated) --- */
    sht45_reading_t s;
    int rc = sht45_read(&g_env_i2c, &s);
    if (rc == SHT45_OK) {
        char tval[12], rval[12], traw[8], rraw[8];
        int tc = s.temp_c_centi, ta = tc < 0 ? -tc : tc;
        snprintf(tval, sizeof(tval), "%s%d.%02d", tc < 0 ? "-" : "", ta / 100,
                 ta % 100);
        snprintf(rval, sizeof(rval), "%d.%02d", s.rh_pct_centi / 100,
                 s.rh_pct_centi % 100);
        snprintf(traw, sizeof(traw), "%u", s.temp_raw);
        snprintf(rraw, sizeof(rraw), "%u", s.rh_raw);
        telemetry_env_row_t t = {
            "plants.env", g_session_id, g_device_id,   PLANTS_FW_VERSION, up_ms,
            "SHT45",      "sht45",      ENV_PLACEMENT, "ambient_temp",    traw,
            tval,         "degC",       "OK",          ENV_SHT45_PAYLOAD};
        emitEnvLine(&t);
        telemetry_env_row_t h = {
            "plants.env", g_session_id, g_device_id,   PLANTS_FW_VERSION, up_ms,
            "SHT45",      "sht45",      ENV_PLACEMENT, "ambient_rh",      rraw,
            rval,         "pctRH",      "OK",          ENV_SHT45_PAYLOAD};
        emitEnvLine(&h);
    } else {
        telemetry_env_row_t e = {"plants.env",
                                 g_session_id,
                                 g_device_id,
                                 PLANTS_FW_VERSION,
                                 up_ms,
                                 "SHT45",
                                 "sht45",
                                 ENV_PLACEMENT,
                                 "ambient_temp",
                                 "",
                                 "",
                                 "",
                                 rc == SHT45_ERR_CRC ? "SUSPECT" : "NO_SIGNAL",
                                 ENV_SHT45_PAYLOAD};
        emitEnvLine(&e);
    }

    /* --- AS7263: six tidy NIR rows (one per band, raw counts) --- */
    static const char *const nir_ch[6] = {"nir_610", "nir_680", "nir_730",
                                          "nir_760", "nir_810", "nir_860"};
    as7263_reading_t a;
    if (g_as7263_ok && as7263_read(&g_env_i2c, &a) == AS7263_OK) {
        const uint16_t nir[6] = {a.nm610, a.nm680, a.nm730,
                                 a.nm760, a.nm810, a.nm860};
        char payload[80];
        snprintf(payload, sizeof(payload),
                 "gain=%s;itime_ms=%u;aim=skylight_beam;not_canopy",
                 AS7263_GAIN_MULT[AS7263_CFG_GAIN & 3],
                 (unsigned)(AS7263_CFG_ITIME * 28u / 10u)); /* reg x2.8ms */
        for (int i = 0; i < 6; i++) {
            char raw[8];
            snprintf(raw, sizeof(raw), "%u", nir[i]);
            telemetry_env_row_t r = {
                "plants.env", g_session_id, g_device_id, PLANTS_FW_VERSION,
                up_ms,        "AS7263",     "as7263",    ENV_PLACEMENT,
                nir_ch[i],    raw,          "",          "",
                "OK",         payload};
            emitEnvLine(&r);
        }
    } else if (g_as7263_ok) {
        /* read failed -> one NO_SIGNAL row so the dropout isn't silent */
        telemetry_env_row_t e = {"plants.env", g_session_id,
                                 g_device_id,  PLANTS_FW_VERSION,
                                 up_ms,        "AS7263",
                                 "as7263",     ENV_PLACEMENT,
                                 "nir_610",    "",
                                 "",           "",
                                 "NO_SIGNAL",  "aim=skylight_beam;not_canopy"};
        emitEnvLine(&e);
    }
}
#endif /* ENABLE_ENV_SENSORS */

/* ---- provenance header -------------------------------------------------- */

static void printHeader()
{
    char buf
        [256]; /* per-channel name@position can run long on the sensors line */
    int n;
    Serial.println();
    /* #601 / ADR-0027 §1b: schema_version>=3 declares device_id is the stable minted
     * id (not the friendly name) + name= rides every payload. The host reads THIS
     * banner line for the version (plants_logger.schema_version_from_header) and
     * applies the >=3 rule (parse_v1). Computed from the one PLANTS_SCHEMA_VERSION
     * source of truth (config.h) so no banner line can disagree with another (#601). */
    snprintf(buf, sizeof(buf),
             "# plants telemetry  schema_version=%d  "
             "contract=docs/TELEMETRY_SCHEMA.md@v%d",
             PLANTS_SCHEMA_VERSION, PLANTS_SCHEMA_VERSION);
    Serial.println(buf);
#ifdef WDT_WEDGE_TEST
    Serial.println("# *** WDT WEDGE-TEST BUILD (esp32dev_wdttest) *** "
                   "!wedge strands ch0 + hangs the loop -> watchdog must "
                   "reset. NOT a ship build.");
#endif
    snprintf(buf, sizeof(buf), "# fw=%s  git=%s  built=%s  run=%s",
             PLANTS_FW_VERSION, GIT_REV, __DATE__ " " __TIME__,
             run_meta_label(&g_run_meta));
    Serial.println(buf);
    snprintf(buf, sizeof(buf),
             "# device_id=%s  name=%s (%s)  chip=%s  "
             "adc=ADC1,12bit,11dB,eFuseCal=off",
             g_device_id, g_device_name,
             g_device_name_custom ? "custom" : "default", ESP.getChipModel());
    Serial.println(buf);
    /* Capability provenance (#273 / ADR-0019): the board declares what it CAN do,
     * so multi-board data is self-describing and WiFi features (#21) have a gate. */
    snprintf(buf, sizeof(buf),
             "# board: %s  wifi=%s  channels=%u  adc=%ubit  storage=%s  "
             "tier0=monitor(%s)",
             BOARD_CAP.name, board_has_wifi() ? "yes" : "no",
             (unsigned)BOARD_CAP.num_channels, (unsigned)BOARD_CAP.adc_bits,
             BOARD_CAP.storage,
             board_has_wifi() ? "untethered-ready" : "tethered");
    Serial.println(buf);
    /* Calibration honesty (#436): a non-verified board runs on the CLASSIC
     * placeholder endpoints - never silently presented as this board's own
     * calibration (matches the config-provenance principle, #416/ADR-0025). */
    if (!BOARD_CAP.cal_verified) {
        Serial.println("# board cal: PLACEHOLDER (classic endpoints, not "
                       "bench-verified for this board - #443)");
    }
    snprintf(
        buf, sizeof(buf), "# session_id=%s  cadence_ms=%lu  cadence_src=%s",
        g_session_id, (unsigned long)g_sys.sample_period_ms,
        g_cadence_temp ? "temp" : (g_cadence_from_nvs ? "nvs" : "default"));
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# sensors:");
    for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " ch%d=GPIO%d/%s@%s", i,
                      SENSOR_PINS[i], SENSOR_NAMES[i],
                      run_meta_position(&g_run_meta, i));
    if (n < (int)sizeof(buf))
        snprintf(buf + n, sizeof(buf) - n, "  (model=%s)", SENSOR_MODEL);
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# health:");
    for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " ch%d=%s", i,
                      telemetry_quality_flag(&state[i]));
    if (n < (int)sizeof(buf))
        snprintf(
            buf + n, sizeof(buf) - n,
            "  (NO_SIGNAL/SUSPECT = probe fault; supervisor won't water it, "
            "latch x%u)",
            (unsigned)IRRIG_MAX_HEALTH_WARN);
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# cal bounds(dry>wet):");
    for (int i = 0; i < MOISTURE_BOUNDARY_COUNT && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " %u",
                      (unsigned)cfg.boundary[i]);
    Serial.println(buf);
    /* Per-channel cal provenance (#404) - one cal_ch line per channel, sourced
     * from the LIVE g_mcfg[ch].boundary (what the classifier actually uses, per
     * the #170 seam), never re-read from calibration.h - so a future runtime
     * boundary update stays honest in the header. Format locked with Data's
     * #507 parser; the shared line above remains the fallback tier. */
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        if (telemetry_format_cal_ch(
                buf, sizeof(buf), SENSOR_NAMES[ch], g_mcfg[ch].boundary,
                MOISTURE_BOUNDARY_COUNT, SENSOR_CAL_SRC, SENSOR_CAL_DATE,
                SENSOR_CAL_CONFIDENCE, SENSOR_CAL_SCOPE) > 0)
            Serial.println(buf);
    }
    snprintf(
        buf, sizeof(buf),
        "# cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu spr=%u discard=%u",
        (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side,
        (unsigned)cfg.deadband_raw, (unsigned long)cfg.confirm_ms_soil,
        (unsigned long)cfg.confirm_ms_dry, (unsigned long)cfg.confirm_ms_wet,
        (unsigned)cfg.spread_warn_raw, (unsigned)ADC_DISCARD);
    Serial.println(buf);
    snprintf(buf, sizeof(buf),
             "# safety: fail-safe OFF (4ch CW-022 active-low, off=HIGH)  "
             "task-wdt=%lums  "
             "dose<=%lums  autonomous=%s (!auto,on arms; !water=manual dose)",
             (unsigned long)WDT_TIMEOUT_MS, (unsigned long)PUMP_PULSE_MAX_MS,
             irrig_autonomous(&g_irrig) ? "ARMED" : "disarmed");
    Serial.println(buf);
#ifdef ENABLE_ENV_SENSORS
    snprintf(
        buf, sizeof(buf),
        "# env(bench): SHT45 ambient_temp/rh + AS7263 NIR(610-860nm) on I2C "
        "SDA%d/SCL%d - %s, CONTEXT not plant-truth%s",
        ENV_I2C_SDA, ENV_I2C_SCL, ENV_PLACEMENT,
        g_as7263_ok ? "" : " [AS7263 init FAILED]");
    Serial.println(buf);
    /* Config provenance in the header (#416): the sensor-shaping knobs are FIXED and
     * logged, so any reading is interpretable and cross-session comparability is
     * explicit. Same values ride each AS7263 row's `gain=`/`itime_ms=` payload. */
    snprintf(buf, sizeof(buf),
             "# env cfg: AS7263 gain=%sx itime=%ums I2C=%ukHz - FIXED, no "
             "auto-range "
             "(#416); logged per row + here",
             AS7263_GAIN_MULT[AS7263_CFG_GAIN & 3],
             (unsigned)(AS7263_CFG_ITIME * 28u / 10u),
             (unsigned)(ENV_I2C_HZ / 1000u));
    Serial.println(buf);
#endif
    Serial.println("# device_cols: "
                   "record_type,session_id,device_id,fw,millis_ms,sensor_model,"
                   "sensor_id,sensor_position,channel,raw_value,value,unit,"
                   "quality_flag,payload");
    Serial.println(
        "# authoritative: raw_value (ADC counts) + band (payload 'level'); "
        "value/unit are NULL - reserved for a future calibrated VWC, never an "
        "uncalibrated %.");
    /* Time provenance (#278, ADR-0018/schema §11.1) - LIVE sync state, not a
     * static claim: device_synced only once SNTP has actually answered. */
    snprintf(buf, sizeof(buf),
             "# time: source=%s - device_seq/time_source ride each row's "
             "payload, schema v%d §11.1/§11.2",
             timeIsSynced() ? "device_synced (NTP)"
                            : "device_uptime (unsynced; NTP arms on WiFi "
                              "connect, #278)",
             PLANTS_SCHEMA_VERSION);
    Serial.println(buf);
    /* WiFi connect-scaffold status (#21) - live state, not just capability. Set
     * credentials with !wifi,<ssid>[,<pass>]; the served status page (this same
     * state) comes up at http://<ip>/ once connected. When connected, the LAN
     * IP rides the line (#571) so untethered evidence never starts with a
     * router-page scavenger hunt - an RFC1918 IP is repo-evidence-safe; the
     * SSID stays out per ADR-0020 §1 (the serial stream IS a log). */
    if (board_has_wifi()) {
        char netbuf[96];
        int m = snprintf(netbuf, sizeof(netbuf), "# net: state=%s creds=%s",
                         wifi_net_state_name(g_wifi.state),
                         g_wifi_ssid[0] ? "set" : "unset");
        if (g_wifi.state == WIFI_NET_CONNECTED && m > 0 &&
            (size_t)m < sizeof(netbuf)) {
            snprintf(netbuf + m, sizeof(netbuf) - (size_t)m, " ip=%s",
                     WiFi.localIP().toString().c_str());
        }
        Serial.println(netbuf);
    }
}

/* ---- Served-status skeleton (#21) ---------------------------------------- */

/* GET / - plain-text status snapshot. Read-only, no auth (LAN-local, and the
 * fuller #21 scope adds auth + control endpoints separately - this skeleton is
 * status only, nothing actuates from an HTTP request). Reuses the same per-
 * channel state the boot banner reports, so this never drifts from serial
 * telemetry - both read the same g_irrig/state. */
static void handleRoot()
{
    char buf[512];
    int n = snprintf(
        buf, sizeof(buf),
        "Sprout %s\ndevice_id=%s fw=%s git=%s board=%s\nwifi=%s ip=%s\n"
        "uptime_ms=%lu\n\n",
        g_device_name, g_device_id, PLANTS_FW_VERSION, GIT_REV, BOARD_CAP.name,
        wifi_net_state_name(g_wifi.state), WiFi.localIP().toString().c_str(),
        millis());
    for (int ch = 0; ch < NUM_SENSORS && n > 0 && (size_t)n < sizeof(buf);
         ch++) {
        n += snprintf(buf + n, sizeof(buf) - (size_t)n,
                      "ch%d: level=%s raw=%u quality=%s\n", ch,
                      moisture_level_name(state[ch].committed),
                      (unsigned)state[ch].last_raw,
                      telemetry_quality_flag(&state[ch]));
    }
    g_http.send(200, "text/plain", buf);
}

/* GET /telemetry (#276) - the latest schema-shaped soil row per channel, the
 * SAME bytes (row + *HH checksum) as the serial wire per ADR-0018 §4 ("one
 * schema, every transport") - so a device-served reader adapter reuses the
 * serial parse path unchanged. Served from the emit-time cache; never samples
 * (ADR-0016). The device_cols preamble keeps the payload self-describing. */
static void handleTelemetry()
{
    static char resp[sizeof(g_last_row) + sizeof(g_last_env) +
                     220]; /* BSS, not handler stack */
    int n = snprintf(resp, sizeof(resp),
                     "# device_cols: record_type,session_id,device_id,fw,"
                     "millis_ms,sensor_model,sensor_id,sensor_position,channel,"
                     "raw_value,value,unit,quality_flag,payload\n");
    for (int ch = 0; ch < NUM_SENSORS && n > 0 && (size_t)n < sizeof(resp);
         ch++) {
        if (g_last_row[ch][0] != '\0')
            n += snprintf(resp + n, sizeof(resp) - (size_t)n, "%s\n",
                          g_last_row[ch]);
    }
    /* #598: the plants.env context rows (die-temp + SHT45/AS7263) after the soil
     * rows - same 14 columns, same wire bytes, so the host adapter parses them off
     * WiFi exactly as off serial (ADR-0018 §4). Untethered ambient visibility. */
    for (uint8_t i = 0;
         i < g_last_env_count && n > 0 && (size_t)n < sizeof(resp); i++) {
        if (g_last_env[i][0] != '\0')
            n += snprintf(resp + n, sizeof(resp) - (size_t)n, "%s\n",
                          g_last_env[i]);
    }
    g_http.send(200, "text/plain", resp);
}

/* ---- Captive portal (#275) ----------------------------------------------- */

/* GET /setup - minimal functional onboarding form. Deliberately plain HTML:
 * Design owns the portal screens (#275's Design half); this is the working
 * substrate they restyle. ADR-0020 §4: NEVER reflects stored credentials -
 * the form is always empty. */
static void handleSetupForm()
{
    static const char page[] =
        "<!DOCTYPE html><html><head><meta name=\"viewport\" "
        "content=\"width=device-width,initial-scale=1\">"
        "<title>Sprout setup</title></head><body>"
        "<h1>Sprout WiFi setup</h1>"
        "<p>Join Sprout to your home network. Credentials are stored on the "
        "device only.</p>"
        "<form method=\"POST\" action=\"/setup\">"
        "<label>Network name (SSID)<br><input name=\"ssid\" maxlength=\"63\" "
        "required></label><br><br>"
        "<label>Password<br><input name=\"pass\" type=\"password\" "
        "maxlength=\"63\"></label><br>"
        "<p>Leave the password empty for an open network.</p>"
        "<button type=\"submit\">Save &amp; connect</button></form>"
        "</body></html>";
    g_http.send(200, "text/html", page);
}

/* POST /setup - save credentials to NVS (same store !wifi uses) and trigger
 * an immediate fresh STA attempt via the dirty flag. The reply page never
 * echoes what was submitted (ADR-0020 §1/§4). */
static void handleSetupSave()
{
    String ssid = g_http.arg("ssid");
    String pass = g_http.arg("pass");
    if (ssid.length() == 0 || ssid.length() >= sizeof(g_wifi_ssid)) {
        g_http.send(400, "text/plain", "SSID must be 1-63 characters.");
        return;
    }
    /* same CSV-safety sanitization as !name/!wifi: no commas/control chars */
    strncpy(g_wifi_ssid, ssid.c_str(), sizeof(g_wifi_ssid) - 1);
    g_wifi_ssid[sizeof(g_wifi_ssid) - 1] = '\0';
    for (size_t i = 0; g_wifi_ssid[i]; i++) {
        char c = g_wifi_ssid[i];
        if (c == ',' || c < 0x20 || c == 0x7f) g_wifi_ssid[i] = '_';
    }
    strncpy(g_wifi_pass, pass.c_str(), sizeof(g_wifi_pass) - 1);
    g_wifi_pass[sizeof(g_wifi_pass) - 1] = '\0';
    g_prefs.putString("wifi_ssid", g_wifi_ssid);
    g_prefs.putString("wifi_pass", g_wifi_pass);
    g_wifi_creds_dirty = true; /* loop() forces an immediate fresh attempt */
    g_http.send(200, "text/html",
                "<!DOCTYPE html><html><body><h1>Saved.</h1><p>Sprout is "
                "joining your network now. This setup hotspot turns itself "
                "off once connected.</p></body></html>");
}

/* Catch-all: in portal mode, redirect every unknown URL to /setup so phone/
 * tablet captive-portal detection pops the form; otherwise a plain 404. */
static void handleNotFound()
{
    if (g_portal_up) {
        g_http.sendHeader("Location", String("http://") +
                                          WiFi.softAPIP().toString() +
                                          "/setup");
        g_http.send(302, "text/plain", "");
    } else {
        g_http.send(404, "text/plain", "not found");
    }
}

/* Raise the config AP (idempotent). AP name: WIFI_AP_PREFIX + a 4-hex suffix
 * generated ONCE and persisted to NVS - synthetic identity, never a hardware
 * id (ADR-0020 §2). Open AP: the portal is local-link, short-lived, and
 * config-only per ADR-0020 §4's stated home-hobby threat model. */
static void portalUp()
{
    if (g_portal_up) return;
    if (g_ap_name[0] == '\0') {
        char suffix[8];
        size_t n = g_prefs.getString("ap_suffix", suffix, sizeof(suffix));
        if (n == 0 || suffix[0] == '\0') {
            snprintf(suffix, sizeof(suffix), "%04x",
                     (unsigned)(esp_random() & 0xFFFF));
            g_prefs.putString("ap_suffix", suffix);
        }
        snprintf(g_ap_name, sizeof(g_ap_name), "%s%s", WIFI_AP_PREFIX, suffix);
    }
    WiFi.mode(WIFI_AP_STA); /* AP for the portal + STA for background retries */
    WiFi.softAP(g_ap_name);
    g_dns.start(53, "*", WiFi.softAPIP());
    g_portal_up = true;
    char msg[80];
    snprintf(msg, sizeof(msg), "# portal: up ap=%s (config-only, ADR-0020)",
             g_ap_name);
    Serial.println(msg);
}

/* Tear the config AP down (idempotent) - the CONNECTED edge. */
static void portalDown()
{
    if (!g_portal_up) return;
    g_dns.stop();
    WiFi.softAPdisconnect(true);
    WiFi.mode(WIFI_STA);
    g_portal_up = false;
    Serial.println("# portal: down (joined the network)");
}

/* ---- Arduino lifecycle -------------------------------------------------- */

void setup()
{
    allRelaysOff(); /* FIRST: actuators de-energized before anything else (#93) */

    Serial.begin(SERIAL_BAUD);
    delay(200);

    /* Per-boot session nonce (#188): fresh RNG, not a hardware id. */
    snprintf(g_session_id, sizeof(g_session_id), "%06x",
             (unsigned)(esp_random() & 0xFFFFFF));

    Serial.println();
    Serial.print("# boot plants controller fw=");
    Serial.print(PLANTS_FW_VERSION);
    Serial.print(" - schema v");
    Serial.print(
        PLANTS_SCHEMA_VERSION); /* #601: computed from config.h, not a literal */
    Serial.println(
        ", 4 soil sensors, supervisor-driven "
        "(autonomous dosing DISARMED; manual !water; fail-safe OFF)");

    /* BOARD_LED_NONE (255): no verified heartbeat pin for this board - skip rather
     * than guess (#436; e.g. the S3 clone's LED_BUILTIN is unconfirmed pre-bench). */
    if (LED_PIN != BOARD_LED_NONE) pinMode(LED_PIN, OUTPUT);

    /* Seed run metadata from the config defaults before !label/!pos are registered. */
    run_meta_init(&g_run_meta, RUN_LABEL, SENSOR_POSITION, NUM_SENSORS);

    /* Build the supervisor's per-channel config and bring up the engine. irrig_init
     * seeds every classifier from one burst with all pumps OFF — it replaces the
     * old standalone seed loop. */
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        g_mcfg[ch] =
            cfg; /* shared acquisition / hysteresis / persistence / health */
        /* C1/#170: diverge ONLY the raw->band boundaries per channel (sensor
         * personality removed); the band->action policy (g_chan_cfg) stays shared. */
        memcpy(g_mcfg[ch].boundary, SENSOR_CAL_BOUNDARY[ch],
               sizeof(g_mcfg[ch].boundary));
        g_chan_cfg[ch].dose_ms = IRRIG_DOSE_MS;
        g_chan_cfg[ch].soak_ms = IRRIG_SOAK_MS;
        g_chan_cfg[ch].water_at_or_below = MOIST_NEEDS_WATER;
        g_chan_cfg[ch].target_level = MOIST_OK;
    }
    irrig_io_t io = {readRaw, setPump, onIrrigEvent, NULL};
    irrig_init(&g_irrig, &g_sys, g_chan_cfg, g_mcfg, state, g_scratch, io,
               millis());
    /* SHIP DISARMED (#227): the loop is fully wired but autonomous dosing is OFF
     * until the bench arms it with !auto — and only after the dry-safety chain
     * (#93/#191/#2/#215) passes. irrig_init defaults this off; set it explicitly so
     * the safety intent is visible at the call site. */
    irrig_set_autonomous(&g_irrig, false);

    /* Wire command module: load NVS config (cadence + identity) + register handlers.
     * The supervisor owns the cadence now, so !cad/!cfg retune g_sys.sample_period_ms;
     * !water/!stop/!auto act on g_irrig. */
    commands_ctx_t cmd_ctx = {
        g_device_id, /* device_uid: the minted nonce, read-only for !ver (#601) */
        g_device_name,
        sizeof(g_device_name),
        &g_device_name_custom,
        &g_sys.sample_period_ms,
        &g_cadence_from_nvs,
        &g_cadence_temp,
        &g_prefs,
        &g_irrig,
        pumpSet,
        allRelaysOff,
        CADENCE_FLOOR_MS,
        CADENCE_CEIL_MS,
        READ_INTERVAL_MS,
        PLANTS_FW_VERSION,
        PUMP_PULSE_MAX_MS,
        NUM_SENSORS,
        WDT_TIMEOUT_MS,
        &g_run_meta,
        printHeader,
        g_wifi_ssid,
        sizeof(g_wifi_ssid),
        g_wifi_pass,
        sizeof(g_wifi_pass),
        &g_wifi_creds_dirty,
    };
    commands_init(&cmd_ctx);

#ifdef ENABLE_ENV_SENSORS
    /* Bring up the I2C/Qwiic contextual sensors (#373/#374). SHT45 is single-shot
     * (no init); AS7263 needs reset + config. Bench instrumentation, not plant-truth. */
    Wire.begin(ENV_I2C_SDA, ENV_I2C_SCL, ENV_I2C_HZ);
    g_as7263_ok = (as7263_init(&g_env_i2c, AS7263_CFG_GAIN, AS7263_CFG_ITIME) ==
                   AS7263_OK);
#endif

    /* WiFi connect-scaffold (#21): mode + state machine init. WiFi.begin() itself
     * is deferred to loop()'s wifi_net_tick() - never called from setup(), so a
     * missing/wrong AP can never block or delay bring-up (Tier-0 monitor still
     * boots and runs with zero WiFi involvement). board_has_wifi() gates whether
     * this board is expected to have the radio at all; STA mode is harmless to
     * set even if no credentials are stored yet. */
    if (board_has_wifi()) {
        WiFi.mode(WIFI_STA);
        g_http.on("/", handleRoot);
        g_http.on("/telemetry",
                  handleTelemetry); /* schema-shaped rows (#276) */
        g_http.on("/setup", HTTP_GET, handleSetupForm); /* portal (#275) */
        g_http.on("/setup", HTTP_POST, handleSetupSave);
        g_http.onNotFound(handleNotFound); /* captive-detection redirect */
        g_http.begin();
    }
    wifi_net_init(&g_wifi);

    /* #601 / ADR-0027 §1b: mint-or-load the stable device_id (a base32 nonce).
     * Placed AFTER wifi_net_init so the SoC RNG is seeded - esp_random() is only
     * truly random once RF is up; minting earlier could make two identical
     * fresh-flashed boards mint the SAME id and recreate the collision this closes.
     * Minted once, persisted to NVS, reused forever; a factory flash wipes NVS and
     * yields a new id (correct). Never MAC/eFuse-derived (ADR-0020). Runs before
     * printHeader() + the first telemetry row so device_id is never empty on the wire. */
    g_prefs.getString("device_uid", g_device_id, sizeof(g_device_id));
    if (strlen(g_device_id) != DEVICE_UID_LEN) {
        device_uid_encode(esp_random(), g_device_id);
        g_prefs.putString("device_uid", g_device_id);
    }

    printHeader();

    /* Task watchdog LAST: setup's own work won't trip it; loop() feeds it every
     * iteration.  A hung loop resets the chip → reboot re-runs allRelaysOff() (#93).
     * IDF5 config-struct API only (#529): the whole matrix moved to the one
     * pioarduino/IDF5 pin (ADR-0024 rev), so the pre-IDF5 two-arg branch is
     * retired. The guard below makes a pin regression FAIL LOUDLY at compile
     * rather than silently reviving an API whose timeout unit differed
     * (seconds vs milliseconds) - the safety path never degrades quietly. */
#if ESP_IDF_VERSION < ESP_IDF_VERSION_VAL(5, 0, 0)
#error                                                                         \
    "Watchdog uses the IDF5 esp_task_wdt API; the matrix is pinned to IDF5 (ADR-0024/#529). Re-add the two-arg seconds form ONLY with a bench re-qual (#191)."
#endif
    esp_task_wdt_config_t wdt_cfg = {
        .timeout_ms = WDT_TIMEOUT_MS,
        .idle_core_mask = 0,
        .trigger_panic = true,
    };
    /* #599: arduino-esp32 3.x / IDF5 auto-inits the Task WDT before setup(), so a
     * bare esp_task_wdt_init() returns ESP_ERR_INVALID_STATE ("already initialized")
     * and OUR WDT_TIMEOUT_MS is silently dropped - the framework default (~5 s) stands
     * while printHeader() above already announced WDT_TIMEOUT_MS. Reconfigure in that
     * case so the configured timeout actually applies; the WDT is the autonomous-
     * pumping safety guard (#93 / #94), so a silently-wrong timeout is unacceptable. */
    esp_err_t wdt_err = esp_task_wdt_init(&wdt_cfg);
    if (wdt_err == ESP_ERR_INVALID_STATE) {
        wdt_err = esp_task_wdt_reconfigure(
            &wdt_cfg); /* framework pre-inited; apply ours */
    }
    if (wdt_err != ESP_OK) {
        Serial.printf("# WARN task-wdt not configured (err=%d); timeout may be "
                      "the framework default\n",
                      (int)wdt_err);
    }
    esp_task_wdt_add(NULL);
}

void loop()
{
    esp_task_wdt_reset(); /* feed the watchdog; a stalled loop -> reset (#93) */

    commands_poll(); /* non-blocking: read one line + dispatch if complete */

    unsigned long now = millis(); /* shared timestamp for all loop schedulers */

    /* WiFi connect-scaffold (#21): drive the connect/retry policy every tick.
     * Never blocks - wifi_net_tick is pure logic, and WiFi.begin()/status() don't
     * block the loop either (begin() is async; status() just reads a cached
     * enum). Convenience/telemetry layer only: irrig_tick below runs unchanged
     * whether or not any of this ever connects. */
    if (board_has_wifi()) {
        if (g_wifi_creds_dirty) {
            /* Operator just changed credentials (!wifi) - drop whatever attempt
             * was in flight against the OLD ap and force an immediate fresh
             * attempt rather than waiting out a stale retry-backoff window. */
            WiFi.disconnect();
            wifi_net_init(&g_wifi);
            g_wifi_creds_dirty = false;
        }
        bool has_creds = g_wifi_ssid[0] != '\0';
        const wifi_net_cfg_t net_cfg = {
            WIFI_CONNECT_TIMEOUT_MS,
            WIFI_RETRY_BACKOFF_MS,
            WIFI_PORTAL_AFTER_FAILURES,
            WIFI_PORTAL_RETRY_BACKOFF_MS,
        };
        if (wifi_net_tick(&g_wifi, has_creds, WiFi.status() == WL_CONNECTED,
                          now, &net_cfg)) {
            WiFi.begin(g_wifi_ssid, g_wifi_pass);
        }
        /* State EDGES: NTP-on-connect (#278 tail, ADR-0018 §3) arms SNTP on
         * each fresh association (re-arms after a drop, so a long-offline
         * clock re-syncs; configTime is async, nothing blocks). The captive
         * portal (#275) raises its AP on the PORTAL edge and tears down on
         * the CONNECTED edge. */
        static wifi_net_state_t prevWifiState = WIFI_NET_IDLE;
        if (g_wifi.state == WIFI_NET_CONNECTED &&
            prevWifiState != WIFI_NET_CONNECTED) {
            configTime(0, 0, WIFI_NTP_SERVER); /* UTC: no TZ/DST offsets */
            portalDown();
            /* Print the LAN IP the moment we associate (#571) - the operator
             * shouldn't need a router page or arp -a to find the device. By
             * WL_CONNECTED the core has completed DHCP, so localIP() is real.
             * RFC1918-safe for evidence; no SSID (ADR-0020 §1). */
            char ipbuf[64];
            snprintf(ipbuf, sizeof(ipbuf),
                     "# net: state=connected creds=set "
                     "ip=%s",
                     WiFi.localIP().toString().c_str());
            Serial.println(ipbuf);
        }
        if (g_wifi.state == WIFI_NET_PORTAL &&
            prevWifiState != WIFI_NET_PORTAL) {
            portalUp();
        }
        prevWifiState = g_wifi.state;
        if (g_portal_up)
            g_dns.processNextRequest(); /* captive-detection DNS catch-all */
        g_http
            .handleClient(); /* cheap no-op until a client actually connects */
    }

    /* The supervisor is the single sample & actuation authority (ADR-0016): tick it
     * EVERY iteration so dose / overrun / settle timing is real-time, not cadence-
     * gated (#227 / Trellis CRITICAL-A+B). It owns the ADC sweep, classifies, vetoes,
     * logs events, and — only when ARMED — doses. Disarmed it never grants a pump on
     * its own; manual !water still works as a forced dose. */
    irrig_tick(&g_irrig, now);

    /* Fast health tick (#4): a cheap spread-only refresh between full sweeps, ONLY
     * while pumps are off (SYS_SAMPLING) so it never reads during a dose (invariant
     * 2). Writes the shared classifier state the supervisor's veto reads, so a probe
     * fault surfaces within HEALTH_CADENCE_MS instead of a full sweep period. */
    static unsigned long lastHealth = 0;
    if (irrig_mode(&g_irrig) == SYS_SAMPLING &&
        now - lastHealth >= HEALTH_CADENCE_MS) {
        lastHealth = now;
        uint16_t quick[HEALTH_SAMPLES];
        for (int ch = 0; ch < NUM_SENSORS; ch++) {
            int pin = SENSOR_PINS[ch];
            for (int d = 0; d < ADC_DISCARD; d++)
                (void)analogRead(pin);
            for (int i = 0; i < HEALTH_SAMPLES; i++)
                quick[i] = (uint16_t)analogRead(pin);
            uint16_t sp = 0;
            moisture_trimmed_mean(quick, HEALTH_SAMPLES, 1, &sp);
            state[ch].last_spread = sp;
            state[ch].health_warn = sp >= (uint16_t)cfg.spread_warn_raw;
        }
    }

    /* Telemetry: soil rows DERIVED from supervisor state, emitted only while
     * SYS_SAMPLING (ADR-0016) — the stream has intentional gaps during a dose
     * (SYS_WATERING/SYS_SETTLE emit pump events, not soil rows). Paced off the
     * supervisor's own sample_period so it tracks the sweep. */
    static unsigned long lastTelem = 0;
    if (irrig_mode(&g_irrig) == SYS_SAMPLING &&
        now - lastTelem >= g_sys.sample_period_ms) {
        lastTelem = now;

        /* 64-bit uptime (us -> ms): survives the uint32 millis() rollover (day 49.7). */
        unsigned long long up_ms =
            (unsigned long long)esp_timer_get_time() / 1000ULL;

        /* Time provenance for this sweep (#278): device_synced + a real UTC
         * stamp once NTP has answered; honestly device_uptime + NO stamp until
         * then. One read per sweep - all four rows share the moment. */
        char ts[32] = "";
        bool synced = timeIsSynced();
        if (synced) isoUtcNow(ts, sizeof(ts));

        Serial
            .println(); /* B6.2 sacrificial sync: absorbs a post-idle framing glitch */
        for (int ch = 0; ch < NUM_SENSORS; ch++) {
            /* Format the CSV row via lib/telemetry; values come from FSM state. */
            char line[300];
            telemetry_soil_row_t row = {
                RECORD_TYPE_SOIL,
                g_session_id,
                g_device_id,
                PLANTS_FW_VERSION,
                up_ms,
                SENSOR_MODEL,
                SENSOR_NAMES[ch],
                run_meta_position(&g_run_meta, ch),
                SOIL_CHANNEL,
                SENSOR_PINS[ch],
                state[ch].last_raw,
                irrig_level(&g_irrig, ch),
                &state[ch],
                g_device_seq++, /* #278: one tick per emitted row, every channel */
                synced ? TIME_SOURCE_DEVICE_SYNCED : TIME_SOURCE_DEVICE_UPTIME,
                ts, /* real UTC when synced; "" = honestly NULL (#278) */
                g_device_name, /* #601: friendly name -> payload name= on every row */
            };
            if (telemetry_format_soil_row(line, sizeof(line), &row) >= 0) {
                char crc[6];
                snprintf(crc, sizeof(crc), "*%02X", telemetry_checksum(line));
                Serial.print(line);
                Serial.println(crc);
                /* Cache the exact wire bytes for GET /telemetry (#276). */
                snprintf(g_last_row[ch], sizeof(g_last_row[ch]), "%s%s", line,
                         crc);
            }
        }

        /* Reprint header every 20 emissions so a long scroll stays self-describing. */
        static unsigned int hdr = 0;
        if (++hdr % 20 == 0) printHeader();

        /* Heartbeat blink — loop alive; doesn't affect cadence. Skipped if the board
         * has no verified LED pin (BOARD_LED_NONE, #436). */
        if (LED_PIN != BOARD_LED_NONE) {
            digitalWrite(LED_PIN, HIGH);
            delay(20);
            digitalWrite(LED_PIN, LOW);
        }
    }

    /* #598: rebuild the served env-context cache once per cadence tick, BEFORE the
     * env block (env build) and the always-on die-temp row append into it - so a
     * die-only (non-env) build never grows it without bound. Same pacing as both. */
    static unsigned long lastEnvCache = 0;
    if (now - lastEnvCache >= g_sys.sample_period_ms) {
        lastEnvCache = now;
        g_last_env_count = 0;
    }

#ifdef ENABLE_ENV_SENSORS
    /* Bench env context — pump-INDEPENDENT (I2C, not the soil ADC), emitted OUTSIDE
     * the SYS_SAMPLING gate on its own cadence: ambient/NIR context is valid during a
     * dose, so it isn't dropped while watering (Trellis #348-reconcile call). Paced
     * off the supervisor's sample_period (g_sys), independent of the FSM mode. */
    static unsigned long lastEnv = 0;
    if (now - lastEnv >= g_sys.sample_period_ms) {
        lastEnv = now;
        emitEnvRows((unsigned long long)esp_timer_get_time() / 1000ULL);
    }
#endif

    /* ESP32 die temp (#345) — every build, same pump-independent pacing rationale
     * as the env block above (an on-chip register read, never the soil ADC). */
    static unsigned long lastDieTemp = 0;
    if (now - lastDieTemp >= g_sys.sample_period_ms) {
        lastDieTemp = now;
        emitDieTempRow((unsigned long long)esp_timer_get_time() / 1000ULL);
    }
}
