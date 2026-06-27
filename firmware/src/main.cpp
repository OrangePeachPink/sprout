/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 4 / schema v1 (read-only) - FOUR soil sensors. Every READ_INTERVAL_MS it
 * sweeps all NUM_SENSORS channels one at a time (ADC-settle discards on each
 * switch), runs each through its own moisture_classifier instance, and emits one
 * compact CSV row per sensor on the wire (machine-first). The host logger adds
 * the UTC/sequence columns, writes the rotating CSV file, and renders a pretty
 * console - the B2 split (see docs/TELEMETRY_SCHEMA.md).
 *
 * Device CSV columns (host prepends timestamp_utc,timestamp_local,sample_id,logger_version):
 *   record_type,session_id,device_id,fw,millis_ms,sensor_model,sensor_id,
 *   sensor_position,channel,raw_value,value,unit,quality_flag,payload
 * (value/unit are emitted NULL - raw_value + band are authoritative, #38.)
 * A '#'-prefixed provenance header is emitted at boot and reprinted periodically.
 * Relays are now defined and driven to their fail-safe OFF state at boot, and a task
 * watchdog resets a hung loop (the #93 safety scaffold) - but NOTHING actuates yet (no
 * pump logic). The one inbound command is `!cad,<ms>*HH` (set the sweep cadence at
 * runtime, ADR-0011 / #63) - cadence only.
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

#ifndef GIT_REV
#define GIT_REV "nogit"  // overridden by scripts/git_rev.py at build (commit hash + dirty)
#endif

// Per-boot identity - filled in setup() before the first header is printed.
static uint64_t g_mac = 0;
static char g_device_id[24]  = "plants_esp32_unknown";
static char g_session_id[12] = "000000";

// Sweep cadence (ms). Runtime-settable via !cad (ADR-0011 / #63) and now persisted to
// NVS (#90): a reboot restores the last set cadence (validated against the floor/ceil
// on load; an empty/corrupt store falls back to READ_INTERVAL_MS). The loop gate and
// the header read this, not the compile-time constant.
static unsigned long g_cadence_ms = READ_INTERVAL_MS;
static bool          g_cadence_from_nvs = false;  // header provenance: loaded from NVS?

// Persisted runtime config store (#90). Opened once for the session: read on boot,
// written on a successful !cad, cleared by !cfg,reset.
static Preferences g_prefs;
static const char *CFG_NS = "plants";

// Shared classifier tuning - same boundaries for all channels for now. The module
// takes a cfg per call, so this becomes a per-channel array when per-probe
// calibration lands (BACKLOG C1).
static moisture_cfg_t cfg = {
  SAMPLES_PER_READ,                                  // sample_count
  SAMPLES_TRIM,                                      // trim_each_side
  60,                                                // deadband_raw
  3000,                                              // confirm_ms_soil (TESTING; prod 8000)
  3000,                                              // confirm_ms_dry  (TESTING; prod 8000)
  2000,                                              // confirm_ms_wet  (TESTING; prod 3500)
  READ_INTERVAL_MS,                                  // loop_period_ms
  250,                                               // spread_warn_raw (0 disables)
  // boundary (descending raw): 7-band scheme, reconciled 2026-06-25 (issue #3)
  // against the 2026-06-21 anchors (docs/SENSOR_CALIBRATION.md):
  //   [0] air-dry|DRY 3050 - air ~3180 vs bone-dry soil ~2440-2920, so a parched
  //       pot now WATERS instead of misreading "out of soil" (the fail-to-water fix).
  //   [4] ww|over 1150, [5] over|sub 1050 - field capacity ~1140-1435 reads
  //       well-watered; saturated soil / standing water (~970-1065) fire the
  //       "too wet / check probe" diagnostic. The wet split is below the ~60-count
  //       noise floor (saturated soil == standing water to a capacitive probe), so
  //       treat anything < ~1150 as ONE "too wet" condition. [1..3] interpolated.
  {3050, 2140, 1830, 1520, 1150, 1050},
};

static moisture_state_t state[NUM_SENSORS];

// NMEA-style XOR checksum over the row body (B6.4) so the host can
// deterministically detect and drop a byte-corrupted line - not just a
// prefix-garbled one - which matters when the data feeds calibration.
static uint8_t lineChecksum(const char *s) {
  uint8_t c = 0;
  while (*s) c ^= (uint8_t)*s++;
  return c;
}

// Map classifier health -> the shared quality_flag enum (docs/TELEMETRY_SCHEMA.md S4).
static const char *qualityFlag(const moisture_state_t *st) {
  uint16_t raw = st->last_raw;
  if (raw >= 4090 || raw <= 5) return "SATURATED";  // ADC railed
  if (st->last_spread >= 2000) return "NO_SIGNAL";  // floating / disconnected probe
  if (st->health_warn)         return "SUSPECT";    // noisy / poor contact
  return "OK";
}

// '#'-prefixed provenance block. The host folds this into the file header and
// shows a terse version on the console; a raw monitor reads it directly.
static void printHeader() {
  char buf[200];
  int n;
  Serial.println();
  Serial.println("# plants telemetry  schema_version=1  contract=docs/TELEMETRY_SCHEMA.md@v1");
  snprintf(buf, sizeof(buf), "# fw=%s  git=%s  built=%s  run=%s",
           PLANTS_FW_VERSION, GIT_REV, __DATE__ " " __TIME__, RUN_LABEL);
  Serial.println(buf);
  snprintf(buf, sizeof(buf), "# device_id=%s  mac=%012llx  chip=%s  adc=ADC1,12bit,11dB,eFuseCal=off",
           g_device_id, (unsigned long long)g_mac, ESP.getChipModel());
  Serial.println(buf);
  snprintf(buf, sizeof(buf), "# session_id=%s  cadence_ms=%lu (%s)",
           g_session_id, g_cadence_ms, g_cadence_from_nvs ? "nvs" : "default");
  Serial.println(buf);
  n = snprintf(buf, sizeof(buf), "# sensors:");
  for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " ch%d=GPIO%d/%s", i, SENSOR_PINS[i], SENSOR_NAMES[i]);
  if (n < (int)sizeof(buf))
    snprintf(buf + n, sizeof(buf) - n, "  (model=%s pos=%s)", SENSOR_MODEL, SENSOR_POSITION);
  Serial.println(buf);
  n = snprintf(buf, sizeof(buf), "# cal bounds(dry>wet):");
  for (int i = 0; i < MOISTURE_BOUNDARY_COUNT && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " %u", (unsigned)cfg.boundary[i]);
  Serial.println(buf);
  snprintf(buf, sizeof(buf),
           "# cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu spr=%u discard=%u",
           (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side, (unsigned)cfg.deadband_raw,
           (unsigned long)cfg.confirm_ms_soil, (unsigned long)cfg.confirm_ms_dry,
           (unsigned long)cfg.confirm_ms_wet, (unsigned)cfg.spread_warn_raw, (unsigned)ADC_DISCARD);
  Serial.println(buf);
  snprintf(buf, sizeof(buf),
           "# safety: actuators fail-safe OFF (4ch CW-022 active-low, off=HIGH)  task-wdt=%lums",
           (unsigned long)WDT_TIMEOUT_MS);
  Serial.println(buf);
  Serial.println("# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
                 "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload");
  Serial.println("# authoritative: raw_value (ADC counts) + band (payload 'level'); value/unit are "
                 "NULL - reserved for a future calibrated VWC, never an uncalibrated %.");
}

// Sample one channel into buf: select the pin, discard a few for the mux/S&H to
// settle, then fill the burst. (One channel at a time - never concurrent.)
static void sampleChannel(int ch, uint16_t *buf) {
  int pin = SENSOR_PINS[ch];
  for (int d = 0; d < ADC_DISCARD; d++) (void)analogRead(pin);
  for (int i = 0; i < SAMPLES_PER_READ; i++) buf[i] = (uint16_t)analogRead(pin);
}

// Fail-safe: drive every relay to its de-energized level. Called FIRST in setup() so
// any reset/boot lands actuators OFF before anything else runs, and reused by the
// irrigation supervisor on every fault/stop once pumps land. No pump exists yet -
// this just guarantees the safe state from the very first instruction (#93).
static void allRelaysOff() {
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    pinMode(RELAY_PINS[ch], OUTPUT);
    digitalWrite(RELAY_PINS[ch], RELAY_OFF_LEVEL);
  }
}

// Load the persisted runtime config from NVS (#90), validating each value against its
// bounds so a stale/corrupt store can never push the device out of safe range. Called
// in setup() before the header is printed.
static void configLoad() {
  g_prefs.begin(CFG_NS, false);                        // rw namespace, kept open for the session
  uint32_t saved = g_prefs.getULong("cadence_ms", 0);  // 0 = "unset" sentinel
  if (saved >= CADENCE_FLOOR_MS && saved <= CADENCE_CEIL_MS) {
    g_cadence_ms = saved;                              // valid persisted cadence
    g_cadence_from_nvs = true;
  }                                                    // else keep the READ_INTERVAL_MS default
}

// Serial-command handlers (defined below, near pollSerialCommand) - forward-declared
// so setup() can register them with the serial_cmd registry (#92).
static void handleCad(const char *args, char *reply, size_t replen);
static void handlePing(const char *args, char *reply, size_t replen);
static void handleVer(const char *args, char *reply, size_t replen);
static void handleCfg(const char *args, char *reply, size_t replen);

void setup() {
  allRelaysOff();  // FIRST: actuators de-energized before anything else can run (#93)

  Serial.begin(SERIAL_BAUD);
  delay(200);

  // Per-boot identity: device_id from the eFuse MAC (free unique board id),
  // session_id a fresh nonce so a reboot is a clean boundary in the data.
  g_mac = ESP.getEfuseMac();
  snprintf(g_device_id, sizeof(g_device_id), "plants_esp32_%06x", (unsigned)(g_mac & 0xFFFFFF));
  snprintf(g_session_id, sizeof(g_session_id), "%06x", (unsigned)(esp_random() & 0xFFFFFF));

  Serial.println();
  Serial.print("# boot plants controller fw=");
  Serial.print(PLANTS_FW_VERSION);
  Serial.println(" - Rung 4 schema v1, four soil sensors (read-only; actuators fail-safe OFF)");

  pinMode(LED_PIN, OUTPUT);

  // Register the inbound serial commands (#92): one registration each; the registry
  // owns re-sync, the *HH checksum, and dispatch.
  serial_cmd_register("cad", handleCad);
  serial_cmd_register("ping", handlePing);
  serial_cmd_register("ver", handleVer);
  serial_cmd_register("cfg", handleCfg);

  // Load any persisted runtime config (#90) so the header + first sweep reflect it.
  configLoad();

  // Seed every channel from one burst so each boots in the right band.
  uint16_t seed[SAMPLES_PER_READ];
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    sampleChannel(ch, seed);
    uint16_t s0 = moisture_trimmed_mean(seed, SAMPLES_PER_READ, SAMPLES_TRIM, NULL);
    moisture_init(&state[ch], &cfg, s0);
  }
  printHeader();

  // Task watchdog LAST, so setup()'s own work can't trip it; loop() feeds it every
  // iteration. A hung loop now resets the chip - and the reboot re-runs allRelaysOff()
  // - so a fault can never strand a pump on (#93). This platform's Arduino-ESP32 uses
  // the classic esp_task_wdt API (timeout in SECONDS, panic on stall); init is harmless
  // if the framework already started the TWDT, then we subscribe the loop task.
  esp_task_wdt_init(WDT_TIMEOUT_MS / 1000UL, true);
  esp_task_wdt_add(NULL);  // watch this (the Arduino loop) task
}

// --- inbound serial command handlers (#92 registry) -------------------------
// The device is otherwise write-only; this is its one inbound path. Each handler gets
// the comma-args and writes a single '#' reply line; the registry (lib/serial_cmd)
// owns the re-sync, the *HH checksum, and dispatch. No actuation, boundaries, or schema.

// !cad,<ms> - set the sweep cadence at runtime (ADR-0011 / #63). Applied at the next
// sweep boundary (g_cadence_ms is read there), never mid-row.
static void handleCad(const char *args, char *reply, size_t replen) {
  uint32_t ms;
  if (!serial_cmd_parse_u32(args, &ms)) {
    snprintf(reply, replen, "# nak err=parse floor=%lu", (unsigned long)CADENCE_FLOOR_MS);
    return;
  }
  if (ms < CADENCE_FLOOR_MS || ms > CADENCE_CEIL_MS) {
    snprintf(reply, replen, "# nak cad=%lu err=range floor=%lu",
             (unsigned long)ms, (unsigned long)CADENCE_FLOOR_MS);
    return;
  }
  unsigned long prev = g_cadence_ms;
  g_cadence_ms = ms;                     // next sweep uses the new period
  g_prefs.putULong("cadence_ms", ms);    // persist across reboots (#90)
  g_cadence_from_nvs = true;
  snprintf(reply, replen, "# ack cad=%lu prev=%lu floor=%lu",
           (unsigned long)ms, prev, (unsigned long)CADENCE_FLOOR_MS);
}

// !ping - liveness check.
static void handlePing(const char *args, char *reply, size_t replen) {
  (void)args;
  snprintf(reply, replen, "# ack pong");
}

// !ver - identity / provenance (fw + device_id + git rev).
static void handleVer(const char *args, char *reply, size_t replen) {
  (void)args;
  snprintf(reply, replen, "# ack ver fw=%s device_id=%s git=%s",
           PLANTS_FW_VERSION, g_device_id, GIT_REV);
}

// !cfg,reset - clear the persisted config so the next boot uses compile-time defaults,
// and apply the default cadence now (#90). Future !cfg subcommands register alongside.
static void handleCfg(const char *args, char *reply, size_t replen) {
  if (strcmp(args, "reset") == 0) {
    g_prefs.clear();                  // wipe the NVS namespace
    g_cadence_ms = READ_INTERVAL_MS;  // apply the default immediately
    g_cadence_from_nvs = false;
    snprintf(reply, replen, "# ack cfg reset cad=%lu", (unsigned long)READ_INTERVAL_MS);
  } else {
    snprintf(reply, replen, "# nak err=cfg (use: !cfg,reset)");
  }
}

// Non-blocking host->device command RX: read whole lines and dispatch them through
// the registry, printing the handler's (or dispatch's nak) reply.
static void pollSerialCommand() {
  static char cmdbuf[48];
  static uint8_t cmdlen = 0;
  while (Serial.available() > 0) {
    int ci = Serial.read();
    if (ci < 0) break;
    char c = (char)ci;
    if (c == '\n' || c == '\r') {
      if (cmdlen == 0) continue;  // ignore blank lines
      cmdbuf[cmdlen] = '\0';
      char reply[96];
      if (serial_cmd_dispatch(cmdbuf, reply, sizeof(reply)) != SERIAL_CMD_IGNORED) {
        Serial.println(reply);
      }
      cmdlen = 0;
    } else if (cmdlen < sizeof(cmdbuf) - 1) {
      cmdbuf[cmdlen++] = c;
    } else {
      cmdlen = 0;  // oversized line: drop it
    }
  }
}

void loop() {
  esp_task_wdt_reset();  // feed the watchdog every iteration; a wedged loop -> reset (#93)

  // Process any inbound !cad command first, so cadence changes are responsive at
  // any cadence (this runs every loop iteration, not once per sweep).
  pollSerialCommand();

  // Non-blocking scheduler: one sweep of all channels every g_cadence_ms.
  static unsigned long lastRead = 0;
  unsigned long now = millis();
  if (now - lastRead < g_cadence_ms) return;
  lastRead = now;

  // Log uptime from the 64-bit esp_timer (us since boot), not millis(): millis()
  // is uint32 and wraps at ~49.7 days, but this counter stays monotonic for
  // ~292,000 years, so the millis_ms column survives an arbitrarily long run.
  unsigned long long up_ms = (unsigned long long)esp_timer_get_time() / 1000ULL;

  // B6.2 sacrificial sync: a leading newline absorbs the post-idle UART framing
  // glitch, so the first real data byte of the burst isn't the one that mangles.
  Serial.println();

  uint16_t samples[SAMPLES_PER_READ];
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    sampleChannel(ch, samples);
    moisture_level_t level = moisture_process(&state[ch], &cfg, samples, SAMPLES_PER_READ);
    uint16_t raw = state[ch].last_raw;

    // Type-specific fields live in the payload (k=v, ';'-sep, no commas).
    char payload[64];
    snprintf(payload, sizeof(payload), "level=%s;role=%s;spread=%u;gpio=%d",
             moisture_level_name(level),
             moisture_level_is_display(level) ? "disp" : "diag",
             (unsigned)state[ch].last_spread, SENSOR_PINS[ch]);

    // Compact device CSV row - host prepends time/sequence columns (B2).
    // value + unit are emitted NULL (empty fields): raw_value (ADC counts) and the
    // band (payload 'level') are authoritative; value/unit are reserved for a
    // future calibrated VWC, never an uncalibrated moisture % (issue #38).
    char line[200];
    snprintf(line, sizeof(line),
             "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%u,,,%s,%s",
             RECORD_TYPE_SOIL, g_session_id, g_device_id, PLANTS_FW_VERSION,
             up_ms, SENSOR_MODEL, SENSOR_NAMES[ch], SENSOR_POSITION, SOIL_CHANNEL,
             (unsigned)raw, qualityFlag(&state[ch]), payload);
    char crc[6];
    snprintf(crc, sizeof(crc), "*%02X", lineChecksum(line));
    Serial.print(line);
    Serial.println(crc);
  }

  // Reprint the header every 20 sweeps so a long scroll stays self-describing.
  static unsigned int hdr = 0;
  if (++hdr % 20 == 0) printHeader();

  // Heartbeat blink - loop alive (does not affect the read cadence).
  digitalWrite(LED_PIN, HIGH);
  delay(20);
  digitalWrite(LED_PIN, LOW);
}
