/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 4 / schema v1 (read-only) - FOUR soil sensors. Every g_cadence_ms it
 * sweeps all NUM_SENSORS channels one at a time (ADC-settle discards on each
 * switch), runs each through its own moisture_classifier instance, and emits
 * one compact CSV row per sensor on the wire (machine-first). The host logger
 * adds the UTC/sequence columns, writes the rotating CSV file, and renders a
 * pretty console — the B2 split (see docs/TELEMETRY_SCHEMA.md).
 *
 * Serial command surface: lib/commands (cad/ping/ver/cfg/name/water/stop).
 * Telemetry row formatting: lib/telemetry (checksum/quality_flag/format_soil_row).
 * Manual bounded pump pulse: lib/pump_pulse (#215). No autonomous dosing yet (#94).
 * Watchdog: hangs the loop -> chip reset -> allRelaysOff() re-runs (#93).
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
#include "pump_pulse.h"
#include "telemetry.h"
#include "commands.h"

#ifndef GIT_REV
#define GIT_REV "nogit"  /* overridden by scripts/git_rev.py at build */
#endif

/* Per-boot identity (#188): friendly name, never a hardware fingerprint. */
static char g_device_id[32]    = "Sprout ESP32";
static bool g_device_id_custom = false;
static char g_session_id[12]   = "000000";

/* Sweep cadence (ms): runtime-settable via !cad (#63), persisted to NVS (#90). */
static unsigned long g_cadence_ms     = READ_INTERVAL_MS;
static bool          g_cadence_from_nvs = false;

/* NVS store: opened once in commands_init(), kept open for the session (#90). */
static Preferences g_prefs;

/* Manual bounded pump-pulse actuator (#215): one channel at a time, default OFF. */
static pump_pulse_t g_pump;

/* Shared classifier config — same boundaries all channels for now (C1/#170 later). */
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

static moisture_state_t state[NUM_SENSORS];

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

/* Sample one channel into buf: discard for mux/S&H settle, then fill burst. */
static void sampleChannel(int ch, uint16_t *buf) {
    int pin = SENSOR_PINS[ch];
    for (int d = 0; d < ADC_DISCARD; d++) (void)analogRead(pin);
    for (int i = 0; i < SAMPLES_PER_READ; i++) buf[i] = (uint16_t)analogRead(pin);
}

/* ---- provenance header -------------------------------------------------- */

static void printHeader() {
    char buf[200];
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
             PLANTS_FW_VERSION, GIT_REV, __DATE__ " " __TIME__, RUN_LABEL);
    Serial.println(buf);
    snprintf(buf, sizeof(buf),
             "# device_id=%s (%s)  chip=%s  adc=ADC1,12bit,11dB,eFuseCal=off",
             g_device_id, g_device_id_custom ? "custom" : "default",
             ESP.getChipModel());
    Serial.println(buf);
    snprintf(buf, sizeof(buf), "# session_id=%s  cadence_ms=%lu (%s)",
             g_session_id, g_cadence_ms, g_cadence_from_nvs ? "nvs" : "default");
    Serial.println(buf);
    n = snprintf(buf, sizeof(buf), "# sensors:");
    for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
        n += snprintf(buf + n, sizeof(buf) - n, " ch%d=GPIO%d/%s",
                      i, SENSOR_PINS[i], SENSOR_NAMES[i]);
    if (n < (int)sizeof(buf))
        snprintf(buf + n, sizeof(buf) - n, "  (model=%s pos=%s)",
                 SENSOR_MODEL, SENSOR_POSITION);
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
             "# safety: actuators fail-safe OFF (4ch CW-022 active-low, off=HIGH)  "
             "task-wdt=%lums  pump=manual(!water) bounded<=%lums",
             (unsigned long)WDT_TIMEOUT_MS, (unsigned long)PUMP_PULSE_MAX_MS);
    Serial.println(buf);
    Serial.println(
        "# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
        "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload");
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
        " - Rung 4 schema v1, four soil sensors "
        "(manual bounded pump pulse; fail-safe OFF)");

    pinMode(LED_PIN, OUTPUT);

    /* Prime the pump-pulse FSM before commands_init so !water is immediately safe. */
    pump_pulse_init(&g_pump, NUM_SENSORS, PUMP_PULSE_DEFAULT_MS, PUMP_PULSE_MAX_MS);

    /* Wire command module: load NVS config (cadence + identity) + register handlers. */
    commands_ctx_t cmd_ctx = {
        g_device_id, sizeof(g_device_id), &g_device_id_custom,
        &g_cadence_ms, &g_cadence_from_nvs,
        &g_prefs, &g_pump, pumpSet, allRelaysOff,
        CADENCE_FLOOR_MS, CADENCE_CEIL_MS, READ_INTERVAL_MS,
        PLANTS_FW_VERSION, PUMP_PULSE_MAX_MS, NUM_SENSORS, WDT_TIMEOUT_MS,
    };
    commands_init(&cmd_ctx);

    /* Seed every channel so the first header shows real health. */
    uint16_t seed[SAMPLES_PER_READ];
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        sampleChannel(ch, seed);
        uint16_t s0 = moisture_trimmed_mean(seed, SAMPLES_PER_READ, SAMPLES_TRIM, NULL);
        moisture_init(&state[ch], &cfg, s0);
    }
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

    /* Service the manual pump pulse: turn relay off the instant the bounded pulse
     * expires (#215). Capture the channel before service() clears it. */
    int pulse_ch = pump_pulse_channel(&g_pump);
    if (pump_pulse_service(&g_pump, now)) pumpSet(pulse_ch, false);

    /* Fast health tick (#4): cheap HEALTH_SAMPLES-burst spread check per channel.
     * Refreshes last_spread + health_warn so probe faults show up quickly in the
     * health banner and future status indicators (D3) / served page (D4).
     * Does NOT update the classifier - committed band + last_raw are unchanged.
     * Skips ADC when a pump is active (relay switching injects noise onto ADC bus). */
    static unsigned long lastHealth = 0;
    if (now - lastHealth >= HEALTH_CADENCE_MS) {
        lastHealth = now;
        if (!pump_pulse_active(&g_pump)) {
            uint16_t quick[HEALTH_SAMPLES];
            for (int ch = 0; ch < NUM_SENSORS; ch++) {
                int pin = SENSOR_PINS[ch];
                for (int d = 0; d < ADC_DISCARD; d++) (void)analogRead(pin);
                for (int i = 0; i < HEALTH_SAMPLES; i++) quick[i] = (uint16_t)analogRead(pin);
                uint16_t sp = 0;
                moisture_trimmed_mean(quick, HEALTH_SAMPLES, 1, &sp);
                state[ch].last_spread = sp;
                state[ch].health_warn = sp >= (uint16_t)cfg.spread_warn_raw;
            }
        }
    }

    /* HARD INVARIANT: never sample while a pump runs — keeps noise off the ADC. */
    if (pump_pulse_active(&g_pump)) return;

    /* Non-blocking scheduler: one sweep every g_cadence_ms. */
    static unsigned long lastRead = 0;
    if (now - lastRead < g_cadence_ms) return;
    lastRead = now;

    /* 64-bit uptime (us -> ms): survives the uint32 millis() rollover at day 49.7. */
    unsigned long long up_ms = (unsigned long long)esp_timer_get_time() / 1000ULL;

    /* B6.2 sacrificial sync: leading newline absorbs post-idle UART framing glitch. */
    Serial.println();

    uint16_t samples[SAMPLES_PER_READ];
    for (int ch = 0; ch < NUM_SENSORS; ch++) {
        sampleChannel(ch, samples);
        moisture_level_t level =
            moisture_process(&state[ch], &cfg, samples, SAMPLES_PER_READ);

        /* Format the CSV row via lib/telemetry (no Serial there — supervisor-safe). */
        char line[200];
        telemetry_soil_row_t row = {
            RECORD_TYPE_SOIL, g_session_id, g_device_id, PLANTS_FW_VERSION,
            up_ms, SENSOR_MODEL, SENSOR_NAMES[ch], SENSOR_POSITION, SOIL_CHANNEL,
            SENSOR_PINS[ch], state[ch].last_raw, level, &state[ch],
        };
        if (telemetry_format_soil_row(line, sizeof(line), &row) >= 0) {
            char crc[6];
            snprintf(crc, sizeof(crc), "*%02X", telemetry_checksum(line));
            Serial.print(line);
            Serial.println(crc);
        }
    }

    /* Reprint header every 20 sweeps so a long scroll stays self-describing. */
    static unsigned int hdr = 0;
    if (++hdr % 20 == 0) printHeader();

    /* Heartbeat blink — loop alive; doesn't affect read cadence. */
    digitalWrite(LED_PIN, HIGH);
    delay(20);
    digitalWrite(LED_PIN, LOW);
}
