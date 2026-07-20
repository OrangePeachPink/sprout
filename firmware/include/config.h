/*
 * config.h - central hardware/config constants for the plants controller.
 */
#pragma once
#include "board_capability.h" // BOARD_CAP - per-board pins are a descriptor field (ADR-0019 §1, #436)

// Firmware version (keep in sync with README as it changes)
constexpr char PLANTS_FW_VERSION[] = "0.7.3";

// Serial - dropped 115200 -> 19200 for noise margin on the USB-serial link
// (the prefix-corruption framing errors); throughput is irrelevant at this cadence.
constexpr unsigned long SERIAL_BAUD = 19200;

// Onboard heartbeat LED, from the board descriptor. BOARD_LED_NONE (255) means no
// verified pin for this board - loop()'s blink is skipped rather than guessing.
const int LED_PIN = BOARD_CAP.led_pin;

// --- Sensing: 4 soil sensors on ADC1 ---------------------------------------
// ADC2 is unusable while WiFi is on, so all sensors live on ADC1 on every board.
// Pin values come from BOARD_CAP (board_capability.h) - the classic map below is
// EXACT / unchanged; other boards' maps are PROVISIONAL, bench-verify before flashing
// (docs/hardware/BOARDS.md). `const`, not `constexpr`: BOARD_CAP is a runtime-const
// struct, not a compile-time constant expression - fine, since these are only ever
// used at runtime (pinMode/analogRead), never in another constexpr/static_assert.
constexpr int NUM_SENSORS = 4;
const int SENSOR_PINS[NUM_SENSORS] = {
    BOARD_CAP.soil_pins[0], BOARD_CAP.soil_pins[1], BOARD_CAP.soil_pins[2],
    BOARD_CAP.soil_pins[3]};
// classic ch0..ch3 = GPIO36/39/34/35 = SVP, SVN, P34, P35
// Channel -> physical sensor -> pin/silkscreen -> stress history (2026-06-23):
//   ch0 = GPIO36 / SVP = sensor #3  (clean; was the solo dry-down reference probe)
//   ch1 = GPIO39 / SVN = sensor #4  (clean)
//   ch2 = GPIO34 / P34 = sensor #1  (recovered: water-on-board contamination)
//   ch3 = GPIO35 / P35 = sensor #2  (recovered: reverse-polarity hot-swap)
// All four go in the ONE original recovering plant for now -> a cross-probe
// agreement test (how much do 4 probes in the same soil disagree over a run).
// Per-channel name = the physical sensor id (short, space-free).
// ADR-0036 (ratified 2026-07-19, Fork A): these are the FIRMWARE CHANNEL layer -
// a board port / ADC lane - and they are what the wire `sensor_id` carries. They
// are NOT probe stickers. The old {s3,s4,s1,s2} encoded a MUTABLE probe<->channel
// binding in an IMMUTABLE flashed constant, so moving a probe silently mislabelled
// the wire until reflash, and per-board s1..s4 collided fleet-wide. Probe identity
// now lives in the registry (a probe move is a registry event); a reading stays
// unique as (device_id, sensor_id), exactly as before.
constexpr const char *SENSOR_NAMES[NUM_SENSORS] = {"ch0", "ch1", "ch2", "ch3"};
// Throwaway reads after switching the ADC mux to a channel (S/H settle).
constexpr int ADC_DISCARD = 4;
// Free-text run label for the log header - set per deployment.
constexpr const char *RUN_LABEL = "4probe-coloc-origplant";

// --- Cross-project telemetry identity (docs/TELEMETRY_SCHEMA.md) ------------
// These populate the namespaced, joinable row schema shared with the
// companion air-quality project.
// The telemetry SCHEMA version this firmware emits (ADR-0027 §1b). SINGLE SOURCE
// OF TRUTH: every banner mention (the boot line, the telemetry-header line the
// host parses, the contract @vN tag, the time-provenance line) computes from this
// one constant, so they can NEVER drift out of sync - they did exactly once (#601:
// boot line said v1 while the header said v3). Bump here and everywhere follows.
// >= 3 => device_id is the stable minted id + name= rides the payload.
// >= 4 => the v4 bundle (#739, one wire revision): config_id= per-row provenance
//   ref (#576/ADR-0025), rssi=/uptime_s=/heap= board diagnostics (#669), and the
//   SENSOR_FAULT quality_flag value + fault= reason (#670). v4 is a strict superset
//   of v3 - all additive payload/header, ZERO new CANONICAL_COLUMNS (the companion
//   shared-core stays byte-identical); parse_v1 branches once at >=4, never stitches.
// v5 (#1042 / ADR-0036): the `sensor_id` rename is a SCHEMA BOUNDARY, not an
// in-place edit (never-stitch, ADR-0006 / ADR-0021). v4 rows carry the old
// port-as-sticker token; v5 rows carry the channel. Old rows are never rewritten,
// and a parser can tell from the version which contract a row was written under.
constexpr int PLANTS_SCHEMA_VERSION = 5;
constexpr const char *RECORD_TYPE_SOIL = "plants.soil";       // namespaced record_type
constexpr const char *SENSOR_MODEL     = "UMLIFE_v2_TLC555";  // probe family
constexpr const char *SENSOR_POSITION  = "origplant";        // all four co-located now; per-channel at repot
constexpr const char *SOIL_CHANNEL     = "soil_moisture";    // the measured quantity
// Observed raw endpoints (sensor #3, Rung 3): dry/air ~3266 max, wet/submerged ~947 min
// (damp-but-out-of-water ~2700). Per-channel calibration to come (BACKLOG C1).

// --- Calibration: raw ADC -> moisture % (shared across channels for now) ---
// Linear map, clamped: raw <= SENSOR_WET_RAW => 100%, raw >= SENSOR_DRY_RAW => 0%.
// Endpoints sit a little OUTSIDE the observed range for headroom, confirmed by the #248
// common-cup anchors (4-probe): WET_RAW 900 stays below the saturated anchors (center 978,
// min probe 926); DRY_RAW 3400 stays above the air-dry anchors (center 3170, max probe
// 3191), leaving room for very dry winter air. NOTE: value/unit (the moist%) are emitted
// NULL (#38) - this linear map is reserved, never analysed; raw + band is the reading.
// #1152 kinematics (TELEMETRY_SCHEMA S4, Data-ratified wire row): a single-step
// |delta| bigger than this is faster than soil moves at READ_INTERVAL_MS - the
// reading may be real but the JUMP is not trustable (probe yanked/reseated,
// contact break). Emits SUSPECT + fault=rate_spike; raw is preserved (ADR-0006).
// PROVISIONAL: derived with margin from the #1174 dry-down, where a FULL watering
// moved a channel ~900 counts across MANY 30 s steps - so a single step this big
// is instrument motion, not soil. Data owns cal values; ratify or retune there.
// 0 disables the check.
constexpr uint16_t SENSOR_MAX_DELTA_RAW = 1200;

constexpr int SENSOR_WET_RAW = 900;   // raw at/below this would read 100% (reserved)
constexpr int SENSOR_DRY_RAW = 3400;  // raw at/above this would read 0% (reserved)

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
const int RELAY_PINS[NUM_SENSORS] = {
    BOARD_CAP.relay_pins[0], BOARD_CAP.relay_pins[1], BOARD_CAP.relay_pins[2],
    BOARD_CAP.relay_pins[3]};
// classic ch0..ch3 = GPIO25/26/27/32
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

// --- Fast health tick (#4) --------------------------------------------------
// A cheap spread-only check runs every HEALTH_CADENCE_MS — much faster than
// the slow data cadence — so probe faults (floating probe, near-rail raw)
// appear in the health banner and future status indicators (D3) / served page
// (D4) with minimal lag. Uses HEALTH_SAMPLES per channel (trim_each=1).
// Skips ADC while a pump is active (avoids relay-switching noise on the ADC).
// Does NOT feed the classifier — committed band and last_raw are untouched.
constexpr unsigned long HEALTH_CADENCE_MS = 2000UL; // 2 s between checks
constexpr int           HEALTH_SAMPLES    = 8;       // cheap burst; trim_each=1 keeps 6

// --- Health veto threshold (#2) ---------------------------------------------
// The autonomous supervisor (#94) refuses to water a channel whose probe reads
// unhealthy (NO_SIGNAL / SUSPECT): a floating or shorted probe can report a plausible
// "dry," so watering on it would trip a pump into unknown soil. The per-read veto is
// immediate; a sustained warning for this many consecutive sweeps latches a HARD fault
// (this is the engine's max_health_warn, BACKLOG A1 - already implemented + native-tested
// in lib/irrigation). The live firmware surfaces per-channel health in the boot banner
// today; the supervisor folds this threshold in when the autonomous loop is wired (#94).
constexpr uint8_t IRRIG_MAX_HEALTH_WARN = 3;

// --- WiFi connect-scaffold (#21 desk-buildable slice) -----------------------
// Policy constants for lib/wifi_net's connect/retry state machine. WiFi is a
// convenience/telemetry layer, never a dependency of the safety loop - these
// only govern how eagerly the device tries to reach the AP, not anything
// actuation-related.
constexpr uint32_t WIFI_CONNECT_TIMEOUT_MS =
    15000UL; // give one attempt this long
constexpr uint32_t WIFI_RETRY_BACKOFF_MS =
    30000UL; // wait this long after a failed attempt
constexpr int WIFI_HTTP_PORT = 80; // served-status skeleton (#21)
// --- Phase-0 OTA (#302, maintainer-ruled interim; NOT the ADR-0026 fence) -----
// ArduinoOTA is LAN-only (espota over the local net, mDNS-advertised) and armed only
// while WiFi-connected. It is PASSWORD-gated: the espota password below. This is a
// deliberately weak Phase-0 interim - a shared, LAN-scoped default. The real posture
// (signed images + a verified-marker + key management) is ADR-0026, staged as a
// follow-up amendment; do NOT treat this as the security fence.
//
// PROVISIONED-OR-OFF (#1333, maintainer-approved). There is NO default password,
// and that absence is the whole mechanism: the push receiver arms only when a
// password was provisioned AT BUILD TIME.
//
// The retired placeholder ("sprout-phase0") was published on purpose as an example -
// but a published credential compiled into every PUBLIC build (CI, release,
// web-flasher) is a known-password receiver listening on a stranger's LAN, on a
// board they flashed from our own front door. "You still have to be on the LAN"
// is a real mitigation for a maintainer's own bench and a much weaker one for a
// household that has guests, roommates, or a shared flat's WiFi. The person who
// clicks Flash on the Pages site never opted into that, and cannot see it.
//
// So: no local override file -> no OTA_PASSWORD -> receiver never begins (see
// OTA_PUSH_ARMED). Public builds are dark by construction, not by remembering to
// set something. Bench builds are UNCHANGED - they already provision by copying
// firmware/platformio_local.example.ini -> platformio_local.ini (gitignored), and
// that one file supplies BOTH the -D OTA_PASSWORD compiled in here AND the
// uploader's --auth, which must match. See docs/OTA_FLASH.md § Password.
//
// Do NOT reintroduce a default here to "make bench easier" - a default re-arms
// every public build, which is the exact defect this closes.
// A board keeps accepting its OLD password until it is re-flashed.
//
// TEMPORARY BY DESIGN: the push mechanism retires in v0.8.1 (#1340) once signed
// pull (#302) is proven on the live fleet. This latch dies with the receiver -
// there is nothing to unwind later.
#ifdef OTA_PASSWORD
#define OTA_PUSH_ARMED 1
#else
#define OTA_PUSH_ARMED 0
#endif
// NTP-on-connect (#278/#276, ADR-0018 §3): SNTP arms on WiFi association; rows
// flip time_source=device_uptime -> device_synced once the clock is real.
constexpr const char *WIFI_NTP_SERVER = "pool.ntp.org";
// Captive portal (#275, ADR-0020 §4): the config AP opens on a fresh board (no
// creds) or after this many consecutive STA failures; while up, background STA
// retries continue on the LONG backoff so a transient router outage self-heals
// without human action. AP name = prefix + a generated NVS-stored suffix -
// synthetic identity, never MAC/silicon-derived (ADR-0020 §2).
constexpr uint32_t WIFI_PORTAL_AFTER_FAILURES = 3;
constexpr uint32_t WIFI_PORTAL_RETRY_BACKOFF_MS = 300000UL; // 5 min
constexpr const char *WIFI_AP_PREFIX = "Sprout-Setup-";
