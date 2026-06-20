/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * STATUS: scaffold placeholder. It only proves the toolchain flashes and the
 * board boots - it prints a serial banner and blinks the onboard LED. There is
 * NO sensor reading or pump/relay control yet; those are added deliberately
 * during bring-up so nothing actuates by accident.
 */

#include <Arduino.h>
#include "config.h"

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println();
  Serial.println("plants controller - scaffold placeholder");
  Serial.print("firmware version: ");
  Serial.println(PLANTS_FW_VERSION);

  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  // Heartbeat - proves the board is alive. Replaced during bring-up.
  digitalWrite(LED_PIN, HIGH);
  delay(500);
  digitalWrite(LED_PIN, LOW);
  delay(500);
}
