/*
 * config.h - central hardware/config constants for the plants controller.
 *
 * The sensor and relay pin assignments below are PLACEHOLDERS and are commented
 * out on purpose. We enable them during bring-up, after the physical wiring plan
 * is settled (see docs/).
 */
#pragma once

// Firmware version (keep in sync with README as it changes)
constexpr char PLANTS_FW_VERSION[] = "0.2.0";

// Serial
constexpr unsigned long SERIAL_BAUD = 115200;

// Onboard LED - most classic ESP32 dev boards use GPIO2
constexpr int LED_PIN = 2;

// --- Sensing ---------------------------------------------------------------
// Rung 3: ONE soil sensor on ADC1. GPIO36 = the SVP pin (input-only, ideal for
// analog). Bench-verified at the breadboard (3V3 / true GND / AOUT). ADC2 is
// unusable while WiFi is on, so all sensors live on ADC1.
constexpr int SENSOR_PIN = 36;  // Sensor 1 AOUT -> GPIO36 (SVP)
// Observed raw endpoints (Rung 3, this sensor): dry/air ~3150, wet/submerged ~1000
// (damp-but-out-of-water ~2700). Per-sensor calibration constants come at Rung 4.
//
// Later (Rung 4) - the full bank on ADC1:
//   GPIO 36 (VP), 39 (VN), 34, 35
// constexpr int SENSOR_PINS[4] = {36, 39, 34, 35};
//
// 4 relay channels - the CW-022 board is active-LOW. Output-capable GPIOs that
// avoid the strapping pins (0, 2, 12, 15):
//   GPIO 25, 26, 27, 32
// constexpr int RELAY_PINS[4] = {25, 26, 27, 32};
