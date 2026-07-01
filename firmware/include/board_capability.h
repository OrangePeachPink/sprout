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
 * Pure C (no constexpr) so the native host tests include it. The board's ADC/relay
 * PIN MAP - also part of the ADR-0019 descriptor - is tracked in the board pin map
 * (#436); this record carries the capability fields (what the board CAN do).
 */
typedef struct {
    const char *name; /* short board id, e.g. "esp32-classic"            */
    bool has_wifi; /* WiFi/untethered features gate on this (#21)      */
    uint8_t num_channels; /* soil channels the board wires                   */
    uint8_t adc_bits; /* ADC resolution                                  */
    const char *storage; /* persistence tier: "nvs" | "nvs+sd" | "none"     */
} board_capability_t;

/* --- the capability matrix (add a board = add a #elif) -------------------- */
#if defined(CONFIG_IDF_TARGET_ESP32)
#define BOARD_CAPABILITY {"esp32-classic", true, 4, 12, "nvs"}
#elif defined(CONFIG_IDF_TARGET_ESP32S3)
#define BOARD_CAPABILITY                                                       \
    {"esp32-s3", true, 4, 12, "nvs"} /* PROVISIONAL - bench #443 */
#elif defined(CONFIG_IDF_TARGET_ESP32C5)
#define BOARD_CAPABILITY                                                       \
    {"esp32-c5", true, 4, 12, "nvs"} /* PROVISIONAL - toolchain #283 */
#else
/* host / native tests / an unknown target: assume the Tier-0 floor - tethered
 * monitor, no WiFi, no persistence. A real no-WiFi board (e.g. an AVR) adds its
 * own #elif with has_wifi=false rather than falling through to this. */
#define BOARD_CAPABILITY {"host", false, 4, 12, "none"}
#endif

static const board_capability_t BOARD_CAP = BOARD_CAPABILITY;

/* Feature gate seam: WiFi/untethered features (#21) check this; Tier-0 runs regardless. */
static inline bool board_has_wifi(void)
{
    return BOARD_CAP.has_wifi;
}
