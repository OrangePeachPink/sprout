/*
 * plants - capacitive soil-moisture + pump auto-watering controller
 * Target: classic ESP32 (SoC marked ESP-32D / ESP32-D0WD class)
 *
 * RUNG 3 - single soil sensor, read-only. Reads ONE capacitive sensor on
 * GPIO36 (SVP) and prints the raw 12-bit ADC value to serial once a second.
 * There is still NO pump/relay control - nothing actuates. Use this to read and
 * record the dry (in air) and wet (in water) endpoints for later calibration.
 */

#include <Arduino.h>
#include "config.h"

void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.println();
  Serial.println("plants controller - Rung 3: single soil sensor (read-only)");
  Serial.print("firmware version: ");
  Serial.println(PLANTS_FW_VERSION);
  Serial.print("reading sensor on GPIO");
  Serial.println(SENSOR_PIN);
  Serial.println("raw ADC is 0-4095 (12-bit). Expect dry/air = HIGH, wet/water = LOW.");
  Serial.println();

  pinMode(LED_PIN, OUTPUT);
  // GPIO36 is input-only; analogRead() configures the ADC, so no pinMode needed.
}

void loop() {
  int raw = analogRead(SENSOR_PIN);

  Serial.print("t=");
  Serial.print(millis());
  Serial.print(" ms   raw ADC = ");
  Serial.println(raw);

  // Brief heartbeat blink so we can see at a glance that the loop is alive.
  digitalWrite(LED_PIN, HIGH);
  delay(20);
  digitalWrite(LED_PIN, LOW);

  delay(1000);  // one reading per second
}
