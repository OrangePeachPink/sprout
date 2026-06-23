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
 * A '#'-prefixed provenance header is emitted at boot and reprinted periodically.
 * Still NO pump/relay control - nothing actuates.
 */

#include <Arduino.h>
#include <esp_system.h>
#include <esp_timer.h>
#include "config.h"
#include "moisture_classifier.h"

#ifndef GIT_REV
#define GIT_REV "nogit"  // overridden by scripts/git_rev.py at build (commit hash + dirty)
#endif

// Per-boot identity - filled in setup() before the first header is printed.
static uint64_t g_mac = 0;
static char g_device_id[24]  = "plants_esp32_unknown";
static char g_session_id[12] = "000000";

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
  // boundary (descending raw): 7-band scheme. Wet end + dry center anchored to
  // measured readings; middle three (needs water/OK) interpolated - tighten from
  // the dry-down log. db=60 uniform. (moisture_classifier_spec baseline.)
  {2760, 2140, 1830, 1520, 1260, 1030},
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
  snprintf(buf, sizeof(buf), "# session_id=%s  cadence_ms=%lu",
           g_session_id, (unsigned long)READ_INTERVAL_MS);
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
  if (n < (int)sizeof(buf))
    snprintf(buf + n, sizeof(buf) - n, "  [moist%% %d..%d]", SENSOR_WET_RAW, SENSOR_DRY_RAW);
  Serial.println(buf);
  snprintf(buf, sizeof(buf),
           "# cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu spr=%u discard=%u",
           (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side, (unsigned)cfg.deadband_raw,
           (unsigned long)cfg.confirm_ms_soil, (unsigned long)cfg.confirm_ms_dry,
           (unsigned long)cfg.confirm_ms_wet, (unsigned)cfg.spread_warn_raw, (unsigned)ADC_DISCARD);
  Serial.println(buf);
  Serial.println("# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
                 "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload");
}

// Sample one channel into buf: select the pin, discard a few for the mux/S&H to
// settle, then fill the burst. (One channel at a time - never concurrent.)
static void sampleChannel(int ch, uint16_t *buf) {
  int pin = SENSOR_PINS[ch];
  for (int d = 0; d < ADC_DISCARD; d++) (void)analogRead(pin);
  for (int i = 0; i < SAMPLES_PER_READ; i++) buf[i] = (uint16_t)analogRead(pin);
}

void setup() {
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
  Serial.println(" - Rung 4 schema v1, four soil sensors (read-only)");

  pinMode(LED_PIN, OUTPUT);

  // Seed every channel from one burst so each boots in the right band.
  uint16_t seed[SAMPLES_PER_READ];
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    sampleChannel(ch, seed);
    uint16_t s0 = moisture_trimmed_mean(seed, SAMPLES_PER_READ, SAMPLES_TRIM, NULL);
    moisture_init(&state[ch], &cfg, s0);
  }
  printHeader();
}

void loop() {
  // Non-blocking scheduler: one sweep of all channels every READ_INTERVAL_MS.
  static unsigned long lastRead = 0;
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL_MS) return;
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

    long pct = (long)(SENSOR_DRY_RAW - (int)raw) * 100 / (SENSOR_DRY_RAW - SENSOR_WET_RAW);
    if (pct < 0)   pct = 0;
    if (pct > 100) pct = 100;

    // Type-specific fields live in the payload (k=v, ';'-sep, no commas).
    char payload[64];
    snprintf(payload, sizeof(payload), "level=%s;role=%s;spread=%u;gpio=%d",
             moisture_level_name(level),
             moisture_level_is_display(level) ? "disp" : "diag",
             (unsigned)state[ch].last_spread, SENSOR_PINS[ch]);

    // Compact device CSV row - host prepends time/sequence columns (B2).
    char line[200];
    snprintf(line, sizeof(line),
             "%s,%s,%s,%s,%llu,%s,%s,%s,%s,%u,%ld,%s,%s,%s",
             RECORD_TYPE_SOIL, g_session_id, g_device_id, PLANTS_FW_VERSION,
             up_ms, SENSOR_MODEL, SENSOR_NAMES[ch], SENSOR_POSITION, SOIL_CHANNEL,
             (unsigned)raw, pct, "pct", qualityFlag(&state[ch]), payload);
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
