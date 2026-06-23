/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 4 (read-only) - FOUR soil sensors. Every READ_INTERVAL_MS it sweeps all
 * NUM_SENSORS channels one at a time (ADC-settle discards on each switch), runs
 * each through its own moisture_classifier instance, and logs one self-contained
 * row per sensor (long/tidy):
 *   rec sweep ms uptime ch name raw moist% level role spread health
 * A self-describing header (schema + per-sensor map + cal/cfg) is emitted at boot
 * and reprinted periodically. Data rows begin with the record type ("soil");
 * every other line starts with '#' or is the column header. Still NO pump/relay
 * control - nothing actuates.
 */

#include <Arduino.h>
#include "config.h"
#include "moisture_classifier.h"

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
  // boundary (descending raw): real-soil cal 2026-06-21 (provisional, cross-sensor #1/#3)
  {3300, 3050, 2200, 1750, 1450, 1080, 900, 800},
};

static moisture_state_t state[NUM_SENSORS];

// Self-describing header: schema + per-sensor map + cal/cfg + human column row.
// All metadata lines start with '#'; the column row is for eyeballing. Parsers
// take data rows as those whose first token is a record type ("soil").
static void printHeader() {
  char buf[200];
  int n;
  Serial.println();
  snprintf(buf, sizeof(buf), "# log_schema=1 fw=%s run=%s cadence_ms=%lu",
           PLANTS_FW_VERSION, RUN_LABEL, (unsigned long)READ_INTERVAL_MS);
  Serial.println(buf);
  Serial.println("# record_type=soil cols: rec sweep ms uptime ch name raw moist level role spread health");
  n = snprintf(buf, sizeof(buf), "# sensors:");
  for (int i = 0; i < NUM_SENSORS && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " ch%d=GPIO%d/%s", i, SENSOR_PINS[i], SENSOR_NAMES[i]);
  Serial.println(buf);
  n = snprintf(buf, sizeof(buf), "# cal bounds(dry>wet):");
  for (int i = 0; i < MOISTURE_BOUNDARY_COUNT && n < (int)sizeof(buf); i++)
    n += snprintf(buf + n, sizeof(buf) - n, " %u", (unsigned)cfg.boundary[i]);
  snprintf(buf + n, sizeof(buf) - n, "  [moist%% %d..%d]", SENSOR_WET_RAW, SENSOR_DRY_RAW);
  Serial.println(buf);
  snprintf(buf, sizeof(buf),
           "# cfg: smp=%u trim=%u db=%u confirm_ms=%lu/%lu/%lu spr=%u discard=%u",
           (unsigned)cfg.sample_count, (unsigned)cfg.trim_each_side, (unsigned)cfg.deadband_raw,
           (unsigned long)cfg.confirm_ms_soil, (unsigned long)cfg.confirm_ms_dry,
           (unsigned long)cfg.confirm_ms_wet, (unsigned)cfg.spread_warn_raw, (unsigned)ADC_DISCARD);
  Serial.println(buf);
  snprintf(buf, sizeof(buf), "%-4s %5s %9s  %-14s  %2s  %-11s  %4s  %5s  %-16s  %-4s  %4s  %s",
           "rec", "sweep", "ms", "uptime(+d h:mm:ss)", "ch", "name",
           "raw", "moist", "level", "role", "spr", "health");
  Serial.println(buf);
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
  Serial.println();
  Serial.println("plants controller - Rung 4: four soil sensors (read-only)");
  Serial.print("firmware version: ");
  Serial.println(PLANTS_FW_VERSION);

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

  static unsigned long sweep = 0;
  sweep++;

  // Uptime since boot as +Dd HH:MM:SS (shared by every row in this sweep).
  unsigned long s = now / 1000UL;
  unsigned long days  =  s / 86400UL;
  unsigned long hours = (s % 86400UL) / 3600UL;
  unsigned long mins  = (s % 3600UL) / 60UL;
  unsigned long secs  =  s % 60UL;
  char uptime[24];
  snprintf(uptime, sizeof(uptime), "+%lud %02lu:%02lu:%02lu", days, hours, mins, secs);

  uint16_t samples[SAMPLES_PER_READ];
  for (int ch = 0; ch < NUM_SENSORS; ch++) {
    sampleChannel(ch, samples);
    moisture_level_t level = moisture_process(&state[ch], &cfg, samples, SAMPLES_PER_READ);
    uint16_t raw = state[ch].last_raw;

    long pct = (long)(SENSOR_DRY_RAW - (int)raw) * 100 / (SENSOR_DRY_RAW - SENSOR_WET_RAW);
    if (pct < 0)   pct = 0;
    if (pct > 100) pct = 100;

    char line[128];
    snprintf(line, sizeof(line),
             "%-4s %5lu %9lu  %-14s  %2d  %-11s  %4u  %4ld%%  %-16s  %-4s  %4u  %s",
             "soil", sweep, now, uptime, ch, SENSOR_NAMES[ch],
             (unsigned)raw, pct,
             moisture_level_name(level),
             moisture_level_is_display(level) ? "disp" : "diag",
             (unsigned)state[ch].last_spread,
             state[ch].health_warn ? "WARN" : "ok");
    Serial.println(line);
  }

  // Reprint the header every 20 sweeps so a long scroll stays self-describing.
  static unsigned int hdr = 0;
  if (++hdr % 20 == 0) printHeader();

  // Heartbeat blink - loop alive (does not affect the read cadence).
  digitalWrite(LED_PIN, HIGH);
  delay(20);
  digitalWrite(LED_PIN, LOW);
}
