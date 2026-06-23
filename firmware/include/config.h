/*
 * config.h - central hardware/config constants for the plants controller.
 *
 * The sensor and relay pin assignments below are PLACEHOLDERS and are commented
 * out on purpose. We enable them during bring-up, after the physical wiring plan
 * is settled (see docs/).
 */
#pragma once

// Firmware version (keep in sync with README as it changes)
constexpr char PLANTS_FW_VERSION[] = "0.7.0";

// Serial - dropped 115200 -> 19200 for noise margin on the USB-serial link
// (the prefix-corruption framing errors); throughput is irrelevant at this cadence.
constexpr unsigned long SERIAL_BAUD = 19200;

// Onboard LED - most classic ESP32 dev boards use GPIO2
constexpr int LED_PIN = 2;

// --- Sensing: 4 soil sensors on ADC1 ---------------------------------------
// ADC2 is unusable while WiFi is on, so all sensors live on ADC1. These four are
// input-only pins, ideal for analog. Fixed pin map (see docs/WIRING.md).
constexpr int NUM_SENSORS = 4;
constexpr int SENSOR_PINS[NUM_SENSORS] = {36, 39, 34, 35};  // ch0..ch3 = SVP, SVN, P34, P35
// Channel -> physical sensor -> pin/silkscreen -> stress history (2026-06-23):
//   ch0 = GPIO36 / SVP = sensor #3  (clean; was the solo dry-down reference probe)
//   ch1 = GPIO39 / SVN = sensor #4  (clean)
//   ch2 = GPIO34 / P34 = sensor #1  (recovered: water-on-board contamination)
//   ch3 = GPIO35 / P35 = sensor #2  (recovered: reverse-polarity hot-swap)
// All four go in the ONE original recovering plant for now -> a cross-probe
// agreement test (how much do 4 probes in the same soil disagree over a run).
// Per-channel name = the physical sensor id (short, space-free).
constexpr const char *SENSOR_NAMES[NUM_SENSORS] = {"s3", "s4", "s1", "s2"};
// Throwaway reads after switching the ADC mux to a channel (S/H settle).
constexpr int ADC_DISCARD = 4;
// Free-text run label for the log header - set per deployment.
constexpr const char *RUN_LABEL = "4probe-coloc-origplant";

// --- Cross-project telemetry identity (docs/TELEMETRY_SCHEMA.md) ------------
// These populate the namespaced, joinable row schema shared with HotBoxAQ.
constexpr const char *RECORD_TYPE_SOIL = "plants.soil";       // namespaced record_type
constexpr const char *SENSOR_MODEL     = "UMLIFE_v2_TLC555";  // probe family
constexpr const char *SENSOR_POSITION  = "origplant";        // all four co-located now; per-channel at repot
constexpr const char *SOIL_CHANNEL     = "soil_moisture";    // the measured quantity
// Observed raw endpoints (sensor #3, Rung 3): dry/air ~3266 max, wet/submerged ~947 min
// (damp-but-out-of-water ~2700). Per-channel calibration to come (BACKLOG C1).

// --- Calibration: raw ADC -> moisture % (shared across channels for now) ---
// Linear map, clamped: raw <= SENSOR_WET_RAW => 100%, raw >= SENSOR_DRY_RAW => 0%.
// Endpoints are set a little OUTSIDE the observed range on purpose, for headroom:
//   WET_RAW 900  sits just below the observed submerged floor (~947).
//   DRY_RAW 3400 sits above the observed in-air ceiling (~3266), leaving room for very
//                dry winter air. Tighten later from logged data. Each sensor can differ.
constexpr int SENSOR_WET_RAW = 900;   // raw at/below this reads 100% moisture
constexpr int SENSOR_DRY_RAW = 3400;  // raw at/above this reads 0% moisture

// Moisture level classification now lives in the moisture_classifier module
// (lib/moisture_classifier). Its levels, boundaries, hysteresis, and confirmation
// windows are configured via the moisture_cfg_t in main.cpp. Boundaries are
// PROVISIONAL pending real potted-soil readings.

// Sampling cadence - non-blocking and drift-free (exact ms between reads).
// 30 s for a long unattended dry-down (keeps the log manageable, ~2880 rows/day);
// set back to 1000 for interactive bench testing. NOTE: the classifier confirm
// windows are in ms, so at 30 s they round down to ~1 sample (debounce effectively
// immediate) - fine for slow drying, not ideal for poking the probe by hand.
constexpr unsigned long READ_INTERVAL_MS = 30000;

// Per-measurement smoothing (trimmed mean): take SAMPLES_PER_READ raw samples,
// drop the SAMPLES_TRIM highest and lowest, average the rest. Tames the ESP32
// ADC's random jitter while shrugging off the odd spurious single sample.
constexpr int SAMPLES_PER_READ = 100;
constexpr int SAMPLES_TRIM     = 15;  // dropped from EACH end (keeps the middle 70)
static_assert(SAMPLES_PER_READ > 2 * SAMPLES_TRIM, "trimmed mean needs samples left after trimming");

// 4 relay channels - the CW-022 board is active-LOW. Output-capable GPIOs that
// avoid the strapping pins (0, 2, 12, 15):
//   GPIO 25, 26, 27, 32
// constexpr int RELAY_PINS[4] = {25, 26, 27, 32};
