#pragma once
#include <stdint.h>
#include <stdbool.h>

/*
 * board_capability.h - per-board capability descriptor (ADR-0019 §1-2).
 *
 * Sprout is ONE codebase, capability-gated per build target - not a fork per board.
 * Features gate on this record: the Tier-0 monitor runs on ANYTHING; WiFi /
 * untethered features light up only where `has_wifi`. (The WiFi features themselves
 * are #21 / PRD-0005; until they land this descriptor + `board_has_wifi()` is the
 * gate SEAM they will hang off - so a no-WiFi board never compiles/runs code it
 * can't support.)
 *
 * THE CONTRIBUTOR EXTENSION SEAM (ADR-0019 §2): adding a board = adding a `#elif`
 * entry below (+ a per-channel sensor_type profile, #274, + its pin map, #436 /
 * docs/hardware/BOARDS.md) - no core edit. The starting lanes ship the classic
 * ESP32; S3 is bring-up-ready and C5 is toolchain-blocked (#283); everything else is
 * Contributors-Welcome. Runtime detection (getChipModel, #188) AUGMENTS this explicit
 * descriptor, it doesn't replace it (channel wiring / storage can't be auto-detected).
 *
 * Pure C (no constexpr) so the native host tests include it. Per ADR-0019 §1 the
 * board's ADC/relay PIN MAP is ALSO a descriptor field (not a separate file) -
 * config.h sources SENSOR_PINS/RELAY_PINS/LED_PIN from BOARD_CAP below, so there is
 * one place per board that fully describes it.
 */
#define BOARD_MAX_CHANNELS 4
#define BOARD_LED_NONE                                                         \
    255 /* sentinel: no verified heartbeat-LED pin (skip the blink) */
/* Must equal moisture_classifier.h's MOISTURE_BOUNDARY_COUNT. Not #included here
 * to keep this header dependency-free; the native test pins the match (#436). */
#define BOARD_CAL_BOUNDARY_COUNT 6

typedef struct {
    const char *name; /* short board id, e.g. "esp32-classic"            */
    bool has_wifi; /* WiFi/untethered features gate on this (#21)      */
    uint8_t num_channels; /* soil channels the board wires                   */
    uint8_t adc_bits; /* ADC resolution                                  */
    const char *storage; /* persistence tier: "nvs" | "nvs+sd" | "none"     */
    /* --- pins (ADR-0019 §1) --- */
    uint8_t soil_pins[BOARD_MAX_CHANNELS]; /* ADC1 input pins, ch0..ch3   */
    uint8_t relay_pins[BOARD_MAX_CHANNELS]; /* output pins, ch0..ch3       */
    uint8_t led_pin; /* heartbeat LED, or BOARD_LED_NONE to skip it     */
    uint8_t i2c_sda; /* env-sensor bus (env build only, #376)           */
    uint8_t i2c_scl;
    /* --- per-board classifier calibration (#436) ---
     * Raw ADC characteristics (reference voltage, gain, board/probe-pad parasitics)
     * differ per SILICON even at the same bit-width, so the classic ENDPOINTS don't
     * transfer to a new board even though its ADC resolution happens to match
     * (verified: classic + S3 are both SOC_ADC_MAX_BITWIDTH=12, confirmed against
     * the framework's soc_caps.h - resolution isn't the gap, calibration data is).
     * cal_boundary: DESCENDING raw (dry>wet), same shape as moisture_cfg_t.boundary.
     * cal_verified: true ONLY for a board with real bench endpoints (today: classic,
     * from the #248 common-cup anchors). false means "structurally wired, values are
     * the classic placeholder" - never silently treated as real calibration. */
    uint16_t cal_boundary[BOARD_CAL_BOUNDARY_COUNT];
    bool cal_verified;
} board_capability_t;

/* --- the capability matrix (add a board = add a #elif) -------------------- */
#if defined(CONFIG_IDF_TARGET_ESP32)
/* the classic baseline - EXACT values, unchanged from config.h's prior literals.
 * cal_boundary: the #248 common-cup-anchored endpoints, real bench data. */
#define BOARD_CAPABILITY                                                       \
    {"esp32-classic",                                                          \
     true,                                                                     \
     4,                                                                        \
     12,                                                                       \
     "nvs",                                                                    \
     {36, 39, 34, 35},                                                         \
     {25, 26, 27, 32},                                                         \
     2,                                                                        \
     21,                                                                       \
     22,                                                                       \
     {3050, 2140, 1830, 1520, 1150, 1050},                                     \
     true}
#elif defined(CONFIG_IDF_TARGET_ESP32S3)
/* ANTICIPATED map (docs/hardware/BOARDS.md) - all VALID S3 GPIOs, continuity
 * NOT yet meter-verified (B1) so cal_verified=false. Refined 2026-07-03: the
 * soil set drops strapping GPIO3 (S3 strapping = 0/3/45/46) that the earlier
 * {1,2,3,4} candidate included - a capacitive probe holding a strapping pin at
 * reset can disturb boot, so soil now uses non-strapping ADC1 pins only.
 *   soil : {1,2,4,5} - ADC1 (GPIO1-10), all non-strapping.
 *   relay: {6,7,15,16} - non-strapping outputs, clear of USB-JTAG 19/20.
 *   i2c  : {8,9}. led_pin: BOARD_LED_NONE (generic-clone LED unconfirmed).
 * cal_boundary: classic PLACEHOLDER endpoints - 12-bit width matches but the
 * calibration does not transfer; cal_verified=false until #443 bench-measures. */
#define BOARD_CAPABILITY                                                       \
    {"esp32-s3",                                                               \
     true,                                                                     \
     4,                                                                        \
     12,                                                                       \
     "nvs",                                                                    \
     {1, 2, 4, 5},                                                             \
     {6, 7, 15, 16},                                                           \
     BOARD_LED_NONE,                                                           \
     8,                                                                        \
     9,                                                                        \
     {3050, 2140, 1830, 1520, 1150, 1050},                                     \
     false}
#elif defined(CONFIG_IDF_TARGET_ESP32C5)
/* ANTICIPATED map - C5 datasheet + DevKitC-1 v1.2 user guide (#443 candidates).
 * VALID existent GPIOs (C5 = GPIO0-28). Replaces the classic placeholder
 * {36,39,34,35}/{25,26,27,32} which DO NOT EXIST on the C5 - at the first bench
 * flash (2026-07-03, official C5) those nonexistent pins flooded continuous
 * `Pin 36 is not ADC pin!` / `IO 32 is not set as GPIO` errors that starved the
 * loop before WiFi could come up. Valid pins fix that. Continuity NOT yet
 * meter-verified (B1) and the ADC is NOT calibrated -> cal_verified=false; the
 * do-not-flash-for-SENSORS caution stands until the wired round.
 *   soil : the ONLY four non-strapping ADC1 pins. ADC1 = GPIO1-6; strapping
 *          MTMS(2)/MTDI(3) removed -> {1,4,5,6} is forced, not chosen.
 *   relay: the only four free non-strapping output pins {0,8,9,10} (GPIO0 is a
 *          plain I/O on C5, not strapping - verify it isn't the boot button at B1).
 *   i2c  : NOMINAL - no env sensors planned on the C5 (the single SHT45/AS7263
 *          instance lives on the classic); set to valid pins for completeness. */
#define BOARD_CAPABILITY                                                       \
    {"esp32-c5",                                                               \
     true,                                                                     \
     4,                                                                        \
     12,                                                                       \
     "nvs",                                                                    \
     {1, 4, 5, 6},                                                             \
     {0, 8, 9, 10},                                                            \
     BOARD_LED_NONE,                                                           \
     23,                                                                       \
     24,                                                                       \
     {3050, 2140, 1830, 1520, 1150, 1050},                                     \
     false}
#else
/* host / native tests / an unknown target: assume the Tier-0 floor - tethered
 * monitor, no WiFi, no persistence. A real no-WiFi board (e.g. an AVR) adds its
 * own #elif with has_wifi=false rather than falling through to this. */
#define BOARD_CAPABILITY                                                       \
    {"host",                                                                   \
     false,                                                                    \
     4,                                                                        \
     12,                                                                       \
     "none",                                                                   \
     {36, 39, 34, 35},                                                         \
     {25, 26, 27, 32},                                                         \
     2,                                                                        \
     21,                                                                       \
     22,                                                                       \
     {3050, 2140, 1830, 1520, 1150, 1050},                                     \
     false}
#endif

static const board_capability_t BOARD_CAP = BOARD_CAPABILITY;

/* Feature gate seam: WiFi/untethered features (#21) check this; Tier-0 runs regardless. */
static inline bool board_has_wifi(void)
{
    return BOARD_CAP.has_wifi;
}
