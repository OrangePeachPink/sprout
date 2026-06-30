/*
 * commands.h - serial command handler module for the plants controller.
 *
 * Registers all inbound !name[,args]*HH serial commands with the serial_cmd registry
 * and owns the NVS config load (cadence + device identity). Extracted from main.cpp
 * per #292 so that the command surface and persistent config are a reviewable unit,
 * and main.cpp is reduced to identity + setup + loop.
 *
 * Implementation is C++ (commands.cpp) because handlers use Preferences (Arduino NVS).
 * This header is C-compatible so it can be included from mixed C/C++ translation units.
 */
#pragma once
#include <stddef.h>
#include <stdbool.h>
#include "pump_pulse.h"
#include "run_meta.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Mutable controller state that command handlers need to read/write.
 * main.cpp fills this once in setup() and passes it to commands_init().
 * commands.cpp stores a shallow copy — all pointer targets must remain valid
 * for the session lifetime (they are module-level statics in main.cpp).
 *
 * prefs_handle is opaque: commands.cpp casts it to Preferences* internally,
 * keeping this header free of Arduino includes.
 */
typedef struct {
    char *device_id;        /* writable, max device_id_len bytes          */
    size_t device_id_len;
    bool *device_id_custom; /* true when operator set a custom name       */
    unsigned long *cadence_ms; /* current sweep cadence (runtime-settable)   */
    bool *cadence_from_nvs; /* true when the persisted default came from NVS */
    bool *
        cadence_temp; /* true when the live cadence is a session-only !cad,temp — no NVS (#322) */
    void *prefs_handle; /* opaque: Preferences* — the NVS store       */
    pump_pulse_t *pump; /* the manual bounded-pulse actuator (#215)   */
    void (*pump_set)(int ch, bool on); /* energize / de-energize one relay */
    void (*all_relays_off)(void); /* fail-safe: all relays off       */
    /* Project constants — passed in so this module doesn't need config.h          */
    unsigned long
        cadence_floor_ms; /* CADENCE_FLOOR_MS - minimum !cad value      */
    unsigned long
        cadence_ceil_ms; /* CADENCE_CEIL_MS  - maximum !cad value      */
    unsigned long
        cadence_default_ms; /* READ_INTERVAL_MS — used on !cfg,reset    */
    const char *fw_version; /* PLANTS_FW_VERSION — reported by !ver       */
    uint32_t pump_max_ms; /* PUMP_PULSE_MAX_MS — reported in !water ack */
    int num_channels; /* NUM_SENSORS — reported in !water nak       */
    uint32_t wdt_timeout_ms; /* WDT_TIMEOUT_MS — reported in !wedge msg    */
    /* Mutable run metadata (#321): !label / !pos read+write this. Lives in
     * main.cpp; reprint_header re-emits the provenance header after !label. */
    run_meta_t *run_meta;
    void (*reprint_header)(void);
} commands_ctx_t;

/*
 * Load persisted config from NVS (cadence + device identity) and register all
 * serial-command handlers with the serial_cmd registry:
 *   cad, ping, ver, cfg, name, water, stop  (+ wedge if WDT_WEDGE_TEST)
 *
 * Call once from setup(), before printing the provenance header.
 * The ctx pointer is consumed immediately; the struct may be stack-allocated.
 */
void commands_init(commands_ctx_t *ctx);

/*
 * Non-blocking: read one line from Serial and dispatch it through the registry
 * if complete. Prints the handler's (or dispatch's nak) reply to Serial.
 * Call from every loop() iteration.
 */
void commands_poll(void);

#ifdef __cplusplus
} /* extern "C" */
#endif
