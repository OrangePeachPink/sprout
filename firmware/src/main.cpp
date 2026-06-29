/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * schema v1 - FOUR soil sensors, supervisor-driven (#94/#227, ADR-0016). The
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
#include <Preferences.h>
#include <string.h>
#include "config.h"
#include "moisture_classifier.h"
#include "serial_cmd.h"
#include "irrigation.h"
#include "telemetry.h"
#include "commands.h"
#include "run_meta.h"

#ifdef ENABLE_ENV_SENSORS
#include <Wire.h>
#include "env_i2c.h"
#include "sht45.h"
#include "as7263.h"
#endif

#ifndef GIT_REV
#define GIT_REV "nogit"  /* overridden by scripts/git_rev.py at build */
#endif

/* Per-boot identity (#188): friendly name, never a hardware fingerprint. */
static char g_device_id[32]    = "Sprout ESP32";
static bool g_device_id_custom = false;
static char g_session_id[12]   = "000000";

/* Sweep cadence is owned by the supervisor (g_sys.sample_period_ms, #227);
 * runtime-settable via !cad (#63), persisted to NVS (#90). This flag only tracks
 * whether the live value came from NVS, for the header. */
static bool g_cadence_from_nvs = false;
/* true when the live cadence is a session-only !cad,temp override — not persisted,
 * reverts to the saved/compiled default on reset (#322). */
static bool g_cadence_temp = false;

/* NVS store: opened once in commands_init(), kept open for the session (#90). */
static Preferences g_prefs;

/* Run metadata (#321): run_label + per-channel sensor_position, seeded from the
 * config.h defaults and updated at runtime via !label / !pos so the bench can
 * move probes between plants without reflashing (stale metadata = join hazard). */
static run_meta_t g_run_meta;

/* Shared classifier config template — same boundaries all channels for now; copied
 * into g_mcfg[] at setup (C1/#170 will diverge per channel). Kept as the canonical
 * copy the header prints. */
static moisture_cfg_t cfg = {
    SAMPLES_PER_READ,
    SAMPLES_TRIM,
    60,     /* deadband_raw */
    3000,   /* confirm_ms_soil (TESTING; prod 8000) */
    3000,   /* confirm_ms_dry  (TESTING; prod 8000) */
    2000,   /* confirm_ms_wet  (TESTING; prod 3500) */
    READ_INTERVAL_MS,
    250,    /* spread_warn_raw */
    /* boundary (descending raw): 7-band scheme (#3). ENDPOINTS RATIFIED against the
     * #248 common-cup anchors (ADR-0006 §6). Interior [1..3] still interpolated —
     * pending the controlled dry-down. See lib/moisture_classifier for semantics. */
    {3050, 2140, 1830, 1520, 1150, 1050},
};

/* Per-channel classifier state — owned here, used by the supervisor as its mstate. */
static moisture_state_t state[NUM_SENSORS];

/* --- The watering supervisor (#94/#227, ADR-0016) -------------------------- */
/* The supervisor is the single sample & actuation authority. It owns the ADC
 * sweep and the relays; main.cpp supplies the I/O callbacks + cfg and ticks it
 * every loop. Autonomous dosing ships DISARMED (see setup) — the bench arms it
 * with !auto only after the dry-safety chain (#93/#191/#2/#215) passes. */
static irrig_ctrl_t   g_irrig;
static moisture_cfg_t g_mcfg[NUM_SENSORS];      /* per-channel (all = cfg for now) */
static irrig_chan_cfg_t g_chan_cfg[NUM_SENSORS]; /* per-channel dose policy (provisional) */
static uint16_t       g_scratch[SAMPLES_PER_READ]; /* FSM burst buffer (>= sample_count) */

/* Idle sweep cadence + dose/soak/fault policy (PROVISIONAL, config.h). sample_period_ms
 * is the !cad / NVS target, so this struct is mutable and main.cpp owns it. */
static irrig_sys_cfg_t g_sys = {
    READ_INTERVAL_MS,           /* sample_period_ms (runtime-settable via !cad)   */
    ADC_DISCARD,                /* adc_discard                                    */
    IRRIG_SETTLE_MS,            /* post_pump_settle_ms                            */
    PUMP_PULSE_MAX_MS,          /* pump_max_ms (hard ceiling, < WDT_TIMEOUT_MS)   */
    IRRIG_MAX_DOSES,            /* max_doses                                      */
    IRRIG_MIN_IMPROVEMENT_RAW,  /* min_improvement_raw                            */
    IRRIG_MAX_HEALTH_WARN,      /* max_health_warn                                */
};

/* ---- hardware helpers --------------------------------------------------- */

/* Fail-safe: drive every relay to its de-energized level.
 * Called FIRST in setup() and passed as a callback to the commands module. */
static void allRelaysOff() {
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        pinMode(RELAY_PINS[ch], OUTPUT);
        digitalWrite(RELAY_PINS[ch], RELAY_OFF_LEVEL);
    }
}

/* Drive ONE channel's relay on/off — the single relay-control point (#215). */
static void pumpSet(int ch, bool on) {
    if (ch < 0 || ch >= NUM_SENSORS) return;
    digitalWrite(RELAY_PINS[ch], on ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
}

/* ---- supervisor I/O callbacks (#227, ADR-0016) -------------------------- */
/* The supervisor is the sole sampler: read_raw returns ONE ADC sample (the FSM
 * does the discard + burst + trimmed mean itself). */
static uint16_t readRaw(int ch, void *user) {
    (void)user;
    return (uint16_t)analogRead(SENSOR_PINS[ch]);
}

/* The supervisor is the sole actuator: set_pump drives one relay (active-low
 * handled in pumpSet). This is the single relay driver in ship builds. */
static void setPump(int ch, bool on, void *user) {
    (void)user;
    pumpSet(ch, on);
}

/* Structured event sink. INTERIM diagnostic line (#-comment, not a data row) —
 * the full schema-conformant `plants.pump` records are #18 (Data-coordinated). */
static void onIrrigEvent(const irrig_event_t *ev, void *user) {
    (void)user;
    char buf[120];
    snprintf(buf, sizeof(buf),
             "# irrig ev=%s ch=%d level=%s raw=%u spread=%u t=%lu",
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

/* Deployment config (env build only — kept out of config.h so config.h's manual
 * alignment stays off the changed-files clang-format gate, #343). */
constexpr int ENV_I2C_SDA = 21; /* ESP32 default I2C/Qwiic SDA */
constexpr int ENV_I2C_SCL = 22; /* ESP32 default I2C/Qwiic SCL */
constexpr uint32_t ENV_I2C_HZ = 100000; /* standard-mode I2C */
constexpr uint8_t AS7263_CFG_GAIN = AS7263_GAIN_64X; /* low indoor NIR */
constexpr uint8_t AS7263_CFG_ITIME = 50; /* INT_TIME reg x2.8ms ~140 ms */
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

static void emitEnvLine(const telemetry_env_row_t *row)
{
    char line[256];
    if (telemetry_format_env_row(line, sizeof(line), row) >= 0) {
        char crc[6];
        snprintf(crc, sizeof(crc), "*%02X", telemetry_checksum(line));
        Serial.print(line);
        Serial.println(crc);
    }
}

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
    static const char *const gain_mult[4] = {"1", "3.7", "16", "64"};
    as7263_reading_t a;
    if (g_as7263_ok && as7263_read(&g_env_i2c, &a) == AS7263_OK) {
        const uint16_t nir[6] = {a.nm610, a.nm680, a.nm730,
                                 a.nm760, a.nm810, a.nm860};
        char payload[80];
        snprintf(payload, sizeof(payload),
                 "gain=%s;itime_ms=%u;aim=skylight_beam;not_canopy",
                 gain_mult[AS7263_CFG_GAIN & 3],
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

static void printHeader() {
    char buf[256];  /* per-channel name@position can run long on the sensors line */
    int  n;
    Serial.println();
    Serial.println(
        "# plants telemetry  schema_version=1  contract=docs/TELEMETRY_SCHEMA.md@v1");
#ifdef WDT_WEDGE_TEST
    Serial.println(
        "# *** WDT WEDGE-TEST BUILD (esp32dev_wdttest) *** "
        "!wedge strands ch0 + hangs the loop -> watchdog must reset. NOT a ship build.");
#endif
    snprintf(buf, sizeof(buf), "# fw=%s  git=%s  built=%s  run=%s",
             PLANTS_FW_VERSION, GIT_REV, __DATE__ " " __TIME__,
             run_meta_label(&g_run_meta));
    Serial.println(buf);
    snprintf(buf, sizeof(buf),
             "# device_id=%s (%s)  chip=%s  adc=ADC1,12bit,11dB,eFuseCal=off",
             g_device_id, g_device_id_custom ? "custom" : "default",
             ESP.getChipModel());
    Serial.println(buf);
    snprintf(buf, sizeof(buf), "# session_id=%s  cadence_ms=%lu  cadence_src=%s",
             g_session_id, (unsigned long)g_sys.sample_period_ms,
             g_cadence_temp ? "temp"
                            : (g_cadence_from_nvs ? "nvs" : "default"));
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# sensors:");
    for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " ch%d=GPIO%d/%s@%s",
                      i, SENSOR_PINS[i], SENSOR_NAMES[i],
                      run_meta_position(&g_run_meta, i));
    if (n < (int)sizeof(buf))
        snprintf(buf + n, sizeof(buf) - n, "  (model=%s)", SENSOR_MODEL);
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# health:");
    for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " ch%d=%s",
                      i, telemetry_quality_flag(&state[i]));
    if (n < (int)sizeof(buf))
        snprintf(buf + n, sizeof(buf) - n,
                 "  (NO_SIGNAL/SUSPECT = probe fault; supervisor won't water it, "
                 "latch x%u)", (unsigned)IRRIG_MAX_HEALTH_WARN);
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# cal bounds(dry>wet):");
    for (int i = 0; i < MOISTURE_BOUNDARY_COUNT && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " %u", (unsigned)cfg.boundary[i]);
    Serial.println(buf);
    snprintf(buf, sizeof(buf),
             "# cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu spr=%u discard=%u",
             (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side,
             (unsigned)cfg.deadband_raw,
             (unsigned long)cfg.confirm_ms_soil, (unsigned long)cfg.confirm_ms_dry,
             (unsigned long)cfg.confirm_ms_wet,
             (unsigned)cfg.spread_warn_raw, (unsigned)ADC_DISCARD);
    Serial.println(buf);
    snprintf(buf, sizeof(buf),
             "# safety: fail-safe OFF (4ch CW-022 active-low, off=HIGH)  task-wdt=%lums  "
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
#endif
    Serial.println("# device_cols: "
                   "record_type,session_id,device_id,fw,millis_ms,sensor_model,"
                   "sensor_id,sensor_position,channel,raw_value,value,unit,"
                   "quality_flag,payload");
    Serial.println(
        "# authoritative: raw_value (ADC counts) + band (payload 'level'); "
        "value/unit are NULL - reserved for a future calibrated VWC, never an "
        "uncalibrated %.");
}

/* ---- Arduino lifecycle -------------------------------------------------- */

void setup() {
    allRelaysOff();  /* FIRST: actuators de-energized before anything else (#93) */

    Serial.begin(SERIAL_BAUD);
    delay(200);

    /* Per-boot session nonce (#188): fresh RNG, not a hardware id. */
    snprintf(g_session_id, sizeof(g_session_id), "%06x",
             (unsigned)(esp_random() & 0xFFFFFF));

    Serial.println();
    Serial.print("# boot plants controller fw=");
    Serial.print(PLANTS_FW_VERSION);
    Serial.println(
        " - schema v1, 4 soil sensors, supervisor-driven "
        "(autonomous dosing DISARMED; manual !water; fail-safe OFF)");

    pinMode(LED_PIN, OUTPUT);

    /* Seed run metadata from the config defaults before !label/!pos are registered. */
    run_meta_init(&g_run_meta, RUN_LABEL, SENSOR_POSITION, NUM_SENSORS);

    /* Build the supervisor's per-channel config (shared template for now; C1/#170
     * diverges it later) and bring up the engine. irrig_init seeds every classifier
     * from one burst with all pumps OFF — it replaces the old standalone seed loop. */
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        g_mcfg[ch] = cfg;
        g_chan_cfg[ch].dose_ms           = IRRIG_DOSE_MS;
        g_chan_cfg[ch].soak_ms           = IRRIG_SOAK_MS;
        g_chan_cfg[ch].water_at_or_below = MOIST_NEEDS_WATER;
        g_chan_cfg[ch].target_level      = MOIST_OK;
    }
    irrig_io_t io = {readRaw, setPump, onIrrigEvent, NULL};
    irrig_init(&g_irrig, &g_sys, g_chan_cfg, g_mcfg, state, g_scratch, io, millis());
    /* SHIP DISARMED (#227): the loop is fully wired but autonomous dosing is OFF
     * until the bench arms it with !auto — and only after the dry-safety chain
     * (#93/#191/#2/#215) passes. irrig_init defaults this off; set it explicitly so
     * the safety intent is visible at the call site. */
    irrig_set_autonomous(&g_irrig, false);

    /* Wire command module: load NVS config (cadence + identity) + register handlers.
     * The supervisor owns the cadence now, so !cad/!cfg retune g_sys.sample_period_ms;
     * !water/!stop/!auto act on g_irrig. */
    commands_ctx_t cmd_ctx = {
        g_device_id, sizeof(g_device_id), &g_device_id_custom,
        &g_sys.sample_period_ms, &g_cadence_from_nvs, &g_cadence_temp,
        &g_prefs, &g_irrig, pumpSet, allRelaysOff,
        CADENCE_FLOOR_MS, CADENCE_CEIL_MS, READ_INTERVAL_MS,
        PLANTS_FW_VERSION, PUMP_PULSE_MAX_MS, NUM_SENSORS, WDT_TIMEOUT_MS,
        &g_run_meta, printHeader,
    };
    commands_init(&cmd_ctx);

#ifdef ENABLE_ENV_SENSORS
    /* Bring up the I2C/Qwiic contextual sensors (#373/#374). SHT45 is single-shot
     * (no init); AS7263 needs reset + config. Bench instrumentation, not plant-truth. */
    Wire.begin(ENV_I2C_SDA, ENV_I2C_SCL, ENV_I2C_HZ);
    g_as7263_ok = (as7263_init(&g_env_i2c, AS7263_CFG_GAIN, AS7263_CFG_ITIME) ==
                   AS7263_OK);
#endif

    printHeader();

    /* Task watchdog LAST: setup's own work won't trip it; loop() feeds it every
     * iteration.  A hung loop resets the chip → reboot re-runs allRelaysOff() (#93).
     * Classic esp_task_wdt API (IDF 4.4 / Arduino-ESP32 2.x): timeout in seconds. */
    esp_task_wdt_init(WDT_TIMEOUT_MS / 1000UL, true);
    esp_task_wdt_add(NULL);
}

void loop() {
    esp_task_wdt_reset();  /* feed the watchdog; a stalled loop -> reset (#93) */

    commands_poll();  /* non-blocking: read one line + dispatch if complete */

    unsigned long now = millis();  /* shared timestamp for all loop schedulers */

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
            for (int d = 0; d < ADC_DISCARD; d++) (void)analogRead(pin);
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
        unsigned long long up_ms = (unsigned long long)esp_timer_get_time() / 1000ULL;

        Serial.println();  /* B6.2 sacrificial sync: absorbs a post-idle framing glitch */
        for (int ch = 0; ch < NUM_SENSORS; ch++) {
            /* Format the CSV row via lib/telemetry; values come from FSM state. */
            char line[200];
            telemetry_soil_row_t row = {
                RECORD_TYPE_SOIL, g_session_id, g_device_id, PLANTS_FW_VERSION,
                up_ms, SENSOR_MODEL, SENSOR_NAMES[ch],
                run_meta_position(&g_run_meta, ch), SOIL_CHANNEL, SENSOR_PINS[ch],
                state[ch].last_raw, irrig_level(&g_irrig, ch), &state[ch],
            };
            if (telemetry_format_soil_row(line, sizeof(line), &row) >= 0) {
                char crc[6];
                snprintf(crc, sizeof(crc), "*%02X", telemetry_checksum(line));
                Serial.print(line);
                Serial.println(crc);
            }
        }

        /* Reprint header every 20 emissions so a long scroll stays self-describing. */
        static unsigned int hdr = 0;
        if (++hdr % 20 == 0) printHeader();

        /* Heartbeat blink — loop alive; doesn't affect cadence. */
        digitalWrite(LED_PIN, HIGH);
        delay(20);
        digitalWrite(LED_PIN, LOW);
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
}
