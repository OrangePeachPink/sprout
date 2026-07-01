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
} board_capability_t;

/* --- the capability matrix (add a board = add a #elif) -------------------- */
#if defined(CONFIG_IDF_TARGET_ESP32)
/* the classic baseline - EXACT values, unchanged from config.h's prior literals */
#define BOARD_CAPABILITY                                                       \
    {"esp32-classic",  true, 4,  12, "nvs", {36, 39, 34, 35},                  \
     {25, 26, 27, 32}, 2,    21, 22}
#elif defined(CONFIG_IDF_TARGET_ESP32S3)
/* PROVISIONAL (docs/hardware/BOARDS.md candidate map) - bench-verify at #443.
 * led_pin: BOARDS.md deferred to the framework's LED_BUILTIN (board-dependent on a
 * generic clone) rather than guess a GPIO -> BOARD_LED_NONE skips the blink safely. */
#define BOARD_CAPABILITY                                                       \
    {"esp32-s3",    true,           4, 12, "nvs", {1, 2, 3, 4},                \
     {5, 6, 7, 15}, BOARD_LED_NONE, 8, 9}
#elif defined(CONFIG_IDF_TARGET_ESP32C5)
/* PROVISIONAL: inherits the classic PLACEHOLDER pins (matches the C5 env's own
 * documented stance in platformio.ini - "do NOT flash until bench-verified", #436
 * / #443). Not a new guess: C5's real pin map is intentionally unassigned pending
 * the bench + datasheet pass (docs/hardware/BOARDS.md). */
#define BOARD_CAPABILITY                                                       \
    {"esp32-c5",       true, 4,  12, "nvs", {36, 39, 34, 35},                  \
     {25, 26, 27, 32}, 2,    21, 22}
#else
/* host / native tests / an unknown target: assume the Tier-0 floor - tethered
 * monitor, no WiFi, no persistence. A real no-WiFi board (e.g. an AVR) adds its
 * own #elif with has_wifi=false rather than falling through to this. */
#define BOARD_CAPABILITY                                                       \
    {"host",           false, 4,  12, "none", {36, 39, 34, 35},                \
     {25, 26, 27, 32}, 2,     21, 22}
#endif

static const board_capability_t BOARD_CAP = BOARD_CAPABILITY;

/* Feature gate seam: WiFi/untethered features (#21) check this; Tier-0 runs regardless. */
static inline bool board_has_wifi(void)
{
    return BOARD_CAP.has_wifi;
}
