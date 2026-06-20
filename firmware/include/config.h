/*
 * config.h - central hardware/config constants for the plants controller.
 *
 * The sensor and relay pin assignments below are PLACEHOLDERS and are commented
 * out on purpose. We enable them during bring-up, after the physical wiring plan
 * is settled (see docs/).
 */
#pragma once

// Firmware version (keep in sync with README as it changes)
constexpr char PLANTS_FW_VERSION[] = "0.0.1";

// Serial
constexpr unsigned long SERIAL_BAUD = 115200;

// Onboard LED - most classic ESP32 dev boards use GPIO2
constexpr int LED_PIN = 2;

// --- Placeholders, finalized during wiring/bring-up -------------------------
// 4 soil sensors on ADC1 (ADC2 is unusable while WiFi is on). Good ADC1 pins,
// all input-only and ideal for analog input:
//   GPIO 36 (VP), 39 (VN), 34, 35
// constexpr int SENSOR_PINS[4] = {36, 39, 34, 35};
//
// 4 relay channels - the CW-022 board is active-LOW. Output-capable GPIOs that
// avoid the strapping pins (0, 2, 12, 15):
//   GPIO 25, 26, 27, 32
// constexpr int RELAY_PINS[4] = {25, 26, 27, 32};
