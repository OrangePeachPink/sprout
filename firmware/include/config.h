/*
 * config.h - central hardware/config constants for the plants controller.
 *
 * The sensor and relay pin assignments below are PLACEHOLDERS and are commented
 * out on purpose. We enable them during bring-up, after the physical wiring plan
 * is settled (see docs/).
 */
#pragma once

// Firmware version (keep in sync with README as it changes)
constexpr char PLANTS_FW_VERSION[] = "0.2.2";

// Serial
constexpr unsigned long SERIAL_BAUD = 115200;

// Onboard LED - most classic ESP32 dev boards use GPIO2
constexpr int LED_PIN = 2;

// --- Sensing ---------------------------------------------------------------
// Rung 3: ONE soil sensor on ADC1. GPIO36 = the SVP pin (input-only, ideal for
// analog). Bench-verified at the breadboard (3V3 / true GND / AOUT). ADC2 is
// unusable while WiFi is on, so all sensors live on ADC1.
constexpr int SENSOR_PIN = 36;  // Sensor 1 AOUT -> GPIO36 (SVP)
// Observed raw endpoints (Rung 3, this sensor): dry/air ~3266 max, wet/submerged ~947 min
// (damp-but-out-of-water ~2700).

// --- Calibration: raw ADC -> moisture % (one sensor for now; per-sensor arrays at Rung 4) ---
// Linear map, clamped: raw <= SENSOR_WET_RAW => 100%, raw >= SENSOR_DRY_RAW => 0%.
// Endpoints are set a little OUTSIDE the observed range on purpose, for headroom:
//   WET_RAW 900  sits just below the observed submerged floor (~947).
//   DRY_RAW 3400 sits above the observed in-air ceiling (~3266), leaving room for very
//                dry winter air. Tighten later from logged data. Each sensor can differ.
constexpr int SENSOR_WET_RAW = 900;   // raw at/below this reads 100% moisture
constexpr int SENSOR_DRY_RAW = 3400;  // raw at/above this reads 0% moisture

// State-word thresholds (raw ADC) for the human-readable column:
//   raw <= STATE_SUBMERGED_MAX -> "submerged" (near 100% wet)
//   raw >= STATE_DRY_MIN       -> "dry" (in air)
//   in between                 -> "wet" (e.g. pulled from water, not yet wiped down)
constexpr int STATE_SUBMERGED_MAX = 1150;  // below true-submerged ceiling (~1100);
                                           // a hand (~1350+) reads "wet", not "submerged"
constexpr int STATE_DRY_MIN       = 3000;

// Sampling cadence - non-blocking and drift-free (exact ms between reads).
constexpr unsigned long READ_INTERVAL_MS = 1000;
//
// Later (Rung 4) - the full bank on ADC1:
//   GPIO 36 (VP), 39 (VN), 34, 35
// constexpr int SENSOR_PINS[4] = {36, 39, 34, 35};
//
// 4 relay channels - the CW-022 board is active-LOW. Output-capable GPIOs that
// avoid the strapping pins (0, 2, 12, 15):
//   GPIO 25, 26, 27, 32
// constexpr int RELAY_PINS[4] = {25, 26, 27, 32};
