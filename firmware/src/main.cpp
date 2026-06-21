/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 3 - single soil sensor, read-only. Every READ_INTERVAL_MS (non-blocking,
 * drift-free) it samples GPIO36 (SVP) as a trimmed mean of SAMPLES_PER_READ reads
 * and prints a human-readable table:
 *   uptime (+h:mm:ss since boot) | raw ADC | moisture % | state word
 * Moisture % and the state word come from the calibration constants in config.h.
 * There is still NO pump/relay control - nothing actuates.
 */

#include <Arduino.h>
#include "config.h"

// Column header for the table (printed at boot and every 20 rows).
static void printHeader() {
  char h[64];
  snprintf(h, sizeof(h), "%-16s  %4s  %5s  %s", "uptime(+h:mm:ss)", "raw", "moist", "state");
  Serial.println();
  Serial.println(h);
}

// Read the sensor as a trimmed mean: take SAMPLES_PER_READ raw samples, sort, drop
// the SAMPLES_TRIM highest and lowest, and average what remains. Smooths the ESP32
// ADC's random jitter and rejects the occasional spurious single sample.
static int readSensorRaw() {
  int s[SAMPLES_PER_READ];
  for (int i = 0; i < SAMPLES_PER_READ; i++) s[i] = analogRead(SENSOR_PIN);

  // Insertion sort - SAMPLES_PER_READ is small, so this is plenty fast.
  for (int i = 1; i < SAMPLES_PER_READ; i++) {
    int v = s[i], j = i - 1;
    while (j >= 0 && s[j] > v) { s[j + 1] = s[j]; j--; }
    s[j + 1] = v;
  }

  long sum = 0;
  for (int i = SAMPLES_TRIM; i < SAMPLES_PER_READ - SAMPLES_TRIM; i++) sum += s[i];
  return (int)(sum / (SAMPLES_PER_READ - 2 * SAMPLES_TRIM));
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println();
  Serial.println("plants controller - Rung 3: single soil sensor (read-only)");
  Serial.print("firmware version: ");
  Serial.println(PLANTS_FW_VERSION);
  Serial.print("sensor on GPIO");
  Serial.print(SENSOR_PIN);
  Serial.print("   cal: 100% wet <= ");
  Serial.print(SENSOR_WET_RAW);
  Serial.print(" raw, 0% dry >= ");
  Serial.print(SENSOR_DRY_RAW);
  Serial.println(" raw");
  Serial.print("sampling: trimmed mean of ");
  Serial.print(SAMPLES_PER_READ);
  Serial.print(" (drop ");
  Serial.print(SAMPLES_TRIM);
  Serial.println("/side)");

  pinMode(LED_PIN, OUTPUT);
  printHeader();
}

void loop() {
  // Non-blocking scheduler: fire exactly READ_INTERVAL_MS after the last read.
  // lastRead is stamped at the moment we fire (not after the print/blink work
  // below), so that work never adds to the interval - no drift, no skipped seconds.
  static unsigned long lastRead = 0;
  unsigned long now = millis();
  if (now - lastRead < READ_INTERVAL_MS) return;
  lastRead = now;

  int raw = readSensorRaw();

  // Uptime since boot as +h:mm:ss (days dropped for now; hours keep counting up).
  unsigned long s = now / 1000UL;
  unsigned long hours = s / 3600UL;
  unsigned long mins  = (s % 3600UL) / 60UL;
  unsigned long secs  =  s % 60UL;

  // Moisture %: linear map, clamped. WET_RAW -> 100%, DRY_RAW -> 0%.
  long pct = (long)(SENSOR_DRY_RAW - raw) * 100 / (SENSOR_DRY_RAW - SENSOR_WET_RAW);
  if (pct < 0)   pct = 0;
  if (pct > 100) pct = 100;

  // Human-readable state from raw thresholds.
  const char *state;
  if (raw <= STATE_SUBMERGED_MAX)      state = "submerged";
  else if (raw >= STATE_DRY_MIN)       state = "dry";
  else                                 state = "wet";

  char uptime[20];
  snprintf(uptime, sizeof(uptime), "+%lu:%02lu:%02lu", hours, mins, secs);

  char line[64];
  snprintf(line, sizeof(line), "%-16s  %4d  %4ld%%  %s", uptime, raw, pct, state);
  Serial.println(line);

  // Reprint the header every 20 rows so a long scroll stays readable.
  static unsigned int rows = 0;
  if (++rows % 20 == 0) printHeader();

  // Heartbeat blink - loop is alive (does not affect the read cadence).
  digitalWrite(LED_PIN, HIGH);
  delay(20);
  digitalWrite(LED_PIN, LOW);
}
