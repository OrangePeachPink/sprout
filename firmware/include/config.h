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

// --- set_cadence runtime serial command (ADR-0011, issue #63) --------------
// The host may retune the sweep cadence at runtime via `!cad,<ms>*HH` (Experiment
// mode). Bounds the device accepts:
//   FLOOR - a sweep must finish before the next is due. At the shipped 4ch / 19200
//     / 100-sample config a sweep is ~330 ms (serial-TX-dominated), so 500 ms keeps
//     headroom for the periodic header reprint while still admitting the PRD v1
//     0.5 s tier. The stretch config (higher baud / smaller burst / single channel)
//     would lower this; v1 ships the constant.
//   CEIL  - 1 h, a sane upper bound.
constexpr unsigned long CADENCE_FLOOR_MS =     500UL;
constexpr unsigned long CADENCE_CEIL_MS  = 3600000UL;

// Per-measurement smoothing (trimmed mean): take SAMPLES_PER_READ raw samples,
// drop the SAMPLES_TRIM highest and lowest, average the rest. Tames the ESP32
// ADC's random jitter while shrugging off the odd spurious single sample.
constexpr int SAMPLES_PER_READ = 100;
constexpr int SAMPLES_TRIM     = 15;  // dropped from EACH end (keeps the middle 70)
static_assert(SAMPLES_PER_READ > 2 * SAMPLES_TRIM, "trimmed mean needs samples left after trimming");

// --- Actuation safety: relays + watchdog + fail-safe-off (#93) --------------
// No pump actuates yet (read-only firmware). This is the safety SCAFFOLD that must
// exist BEFORE any relay toggles (the #94 actuation gate): any reset/boot lands
// every relay de-energized, and a wedged loop resets rather than stranding a pump on.
//
// 4 relay channels - the CW-022 board is active-LOW (driving the pin LOW energizes
// the coil), so de-energized = HIGH. Output-capable GPIOs that avoid the strapping
// pins (0, 2, 12, 15) and the input-only ADC pins (34/35/36/39). Bench-verify the
// polarity before connecting a pump.
constexpr int  RELAY_PINS[NUM_SENSORS] = {25, 26, 27, 32};       // ch0..ch3
constexpr bool RELAY_ACTIVE_LOW = true;                          // CW-022 module
constexpr int  RELAY_OFF_LEVEL  = RELAY_ACTIVE_LOW ? HIGH : LOW; // the de-energized level
constexpr int  RELAY_ON_LEVEL   = RELAY_ACTIVE_LOW ? LOW  : HIGH;// the energized level (#215)

// Task-watchdog timeout (ms): the main loop must feed the WDT within this window or
// the device resets - so a hung loop can't strand a pump on. Generous vs a sweep
// (~330 ms); loop() still spins + feeds between the slow (30 s) sweeps.
constexpr uint32_t WDT_TIMEOUT_MS = 8000;

// --- Manual bounded pump pulse (#215, first actuation slice) ----------------
// Operator-commanded single pulse via !water,<ch>[,<ms>] (#92 registry) - NOT
// autonomous dosing (the irrig_tick engine is the next slice, #94). Every pulse is
// bounded by PUMP_PULSE_MAX_MS, a HARD ceiling kept well under WDT_TIMEOUT_MS so the
// watchdog remains a true independent backstop, and defaults to PUMP_PULSE_DEFAULT_MS
// when no duration is given. Conservative to start; tune both from the #191 bench.
constexpr uint32_t PUMP_PULSE_DEFAULT_MS = 1500;
constexpr uint32_t PUMP_PULSE_MAX_MS     = 5000;
static_assert(PUMP_PULSE_MAX_MS < WDT_TIMEOUT_MS,
              "a pump pulse must finish within the watchdog window (watchdog is the backstop)");

// --- Health veto threshold (#2) ---------------------------------------------
// The autonomous supervisor (#94) refuses to water a channel whose probe reads
// unhealthy (NO_SIGNAL / SUSPECT): a floating or shorted probe can report a plausible
// "dry," so watering on it would trip a pump into unknown soil. The per-read veto is
// immediate; a sustained warning for this many consecutive sweeps latches a HARD fault
// (this is the engine's max_health_warn, BACKLOG A1 - already implemented + native-tested
// in lib/irrigation). The live firmware surfaces per-channel health in the boot banner
// today; the supervisor folds this threshold in when the autonomous loop is wired (#94).
constexpr uint8_t IRRIG_MAX_HEALTH_WARN = 3;
