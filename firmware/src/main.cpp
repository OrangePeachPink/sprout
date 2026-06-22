/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 3 - single soil sensor, read-only. Every READ_INTERVAL_MS it samples
 * GPIO36 (SVP) SAMPLES_PER_READ times and runs the moisture_classifier module:
 *   trimmed mean -> dead-band hysteresis -> N-consecutive persistence gate.
 * Prints: uptime | raw (trimmed mean) | moisture % | level | role | spread | health.
 * Moisture % is a separate linear readout (config.h); level/role/health come from
 * the classifier. There is still NO pump/relay control - nothing actuates.
 */

#include <Arduino.h>
#include "config.h"
#include "moisture_classifier.h"

// Classifier tuning. Shared acquisition values come from config.h; the classifier-
// specific knobs (hysteresis, confirm windows, spread, boundaries) live here.
// NOTE: the confirm windows are SHORTENED for bench testing/tuning. Production
// values are soil 8000 / dry 8000 / wet 3500 ms - raise them when deploying to a
// real plant so brief transients don't flip the committed level.
static moisture_cfg_t cfg = {
  SAMPLES_PER_READ,                                  // sample_count
  SAMPLES_TRIM,                                      // trim_each_side
  60,                                                // deadband_raw
  3000,                                              // confirm_ms_soil (TESTING; prod 8000)
  3000,                                              // confirm_ms_dry  (TESTING; prod 8000)
  2000,                                              // confirm_ms_wet  (TESTING; prod 3500)
  READ_INTERVAL_MS,                                  // loop_period_ms
  250,                                               // spread_warn_raw (0 disables)
  // boundary (descending raw). Calibrated to real soil (2026-06-21, PROVISIONAL,
  // cross-sensor): air ~3175; bone-dry distressed ~2440 -> "dry"; drained field
  // capacity ~1165-1435 across probes -> "well watered"; saturated ~970 -> "overwatered".
  // The ~270-count field-capacity spread is placement/contact variance -> each probe
  // ultimately needs its OWN in-place cal. "needs water"/"OK" mid bands are interpolated
  // (no measured point yet) and will tighten on the dry-down. water-contact/submerged
  // sit BELOW the ~950 water rail: to a capacitive probe saturated soil == standing
  // water, so those diagnostics are effectively unreachable by an in-soil probe.
  {3300, 3050, 2200, 1750, 1450, 1080, 900, 800},
};

static moisture_state_t state;

// Header block (printed at boot and every 20 rows). Three lines so any pasted
// snippet records the calibration + settings in effect: anchors, then config,
// then the column names (kept directly above the data rows).
static void printHeader() {
  // Each line is built in one buffer and printed with a single write - shorter
  // (so the monitor doesn't wrap+merge them) and more atomic on the serial link.
  char buf[160];
  int n;

  Serial.println();

  // Line 1 - calibration: the 8 level boundaries (dry->wet) + the moist% endpoints.
  n = snprintf(buf, sizeof(buf), "cal bounds(dry>wet):");
  for (int i = 0; i < MOISTURE_BOUNDARY_COUNT && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " %u", (unsigned)cfg.boundary[i]);
  snprintf(buf + n, sizeof(buf) - n, "  [moist%% %d..%d]", SENSOR_WET_RAW, SENSOR_DRY_RAW);
  Serial.println(buf);

  // Line 2 - other configurable settings in effect.
  snprintf(buf, sizeof(buf),
           "cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu period=%lu spr=%u",
           (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side, (unsigned)cfg.deadband_raw,
           (unsigned long)cfg.confirm_ms_soil, (unsigned long)cfg.confirm_ms_dry,
           (unsigned long)cfg.confirm_ms_wet, (unsigned long)cfg.loop_period_ms,
           (unsigned)cfg.spread_warn_raw);
  Serial.println(buf);

  // Line 3 - column names.
  snprintf(buf, sizeof(buf), "%6s  %-18s  %4s  %5s  %-16s  %-4s  %4s  %s",
           "#", "uptime(+d h:mm:ss)", "raw", "moist", "level", "role", "spr", "health");
  Serial.println(buf);
}

// Fill a buffer with SAMPLES_PER_READ raw ADC samples from the sensor.
static void sampleSensor(uint16_t *buf) {
  for (int i = 0; i < SAMPLES_PER_READ; i++) buf[i] = (uint16_t)analogRead(SENSOR_PIN);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println();
  Serial.println("plants controller - Rung 3: single soil sensor (read-only)");
  Serial.print("firmware version: ");
  Serial.println(PLANTS_FW_VERSION);
  Serial.print("sensor on GPIO");
  Serial.println(SENSOR_PIN);

  pinMode(LED_PIN, OUTPUT);

  // Seed the classifier from a first measurement so it boots in the right band
  // (no confirmation delay on the very first reading).
  uint16_t seed[SAMPLES_PER_READ];
  sampleSensor(seed);
  uint16_t seed_raw = moisture_trimmed_mean(seed, SAMPLES_PER_READ, SAMPLES_TRIM, NULL);
  moisture_init(&state, &cfg, seed_raw);

  printHeader();
}

void loop() {
  // Non-blocking scheduler: fire exactly READ_INTERVAL_MS after the last read.
  static unsigned long lastRead = 0;
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL_MS) return;
  lastRead = now;

  static unsigned long sample_no = 0;
  sample_no++;

  uint16_t samples[SAMPLES_PER_READ];
  sampleSensor(samples);
  moisture_level_t level = moisture_process(&state, &cfg, samples, SAMPLES_PER_READ);
  uint16_t raw = state.last_raw;

  // Moisture %: separate linear readout. WET_RAW -> 100%, DRY_RAW -> 0%, clamped.
  long pct = (long)(SENSOR_DRY_RAW - (int)raw) * 100 / (SENSOR_DRY_RAW - SENSOR_WET_RAW);
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;

  // Uptime since boot as +Dd HH:MM:SS (days shown again for long runs).
  unsigned long s = now / 1000UL;
  unsigned long days  =  s / 86400UL;
  unsigned long hours = (s % 86400UL) / 3600UL;
  unsigned long mins  = (s % 3600UL) / 60UL;
  unsigned long secs  =  s % 60UL;

  char uptime[24];
  snprintf(uptime, sizeof(uptime), "+%lud %02lu:%02lu:%02lu", days, hours, mins, secs);

  char line[96];
  snprintf(line, sizeof(line), "%6lu  %-18s  %4u  %4ld%%  %-16s  %-4s  %4u  %s",
           sample_no, uptime, (unsigned)raw, pct,
           moisture_level_name(level),
           moisture_level_is_display(level) ? "disp" : "diag",
           (unsigned)state.last_spread,
           state.health_warn ? "WARN" : "ok");
  Serial.println(line);

  // Reprint the header every 20 rows so a long scroll stays readable.
  static unsigned int rows = 0;
  if (++rows % 20 == 0) printHeader();

  // Heartbeat blink - loop is alive (does not affect the read cadence).
  digitalWrite(LED_PIN, HIGH);
  delay(20);
  digitalWrite(LED_PIN, LOW);
}
