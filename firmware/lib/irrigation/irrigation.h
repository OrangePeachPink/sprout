/*
 * irrigation.h
 * -----------------------------------------------------------------------------
 * 4-channel capacitive-soil watering control engine for one ESP32 driving 4
 * relays/pumps, built on moisture_classifier.h (one classifier per channel).
 *
 * Merged from two prototypes: the richer controller (the module owns the ADC
 * burst, with channel-switch discards, a pump-overrun failsafe, a sensor-health
 * fault, and an event log) PLUS dose-to-target hysteresis (separate request and
 * target levels). Two enhancements added on top:
 *   - TRUE no-improvement fault: a channel only counts a "wasted dose" when the
 *     trimmed-mean raw fails to FALL by min_improvement_raw between doses, not
 *     merely because it took several doses. A slowly-wetting pot won't
 * false-fault.
 *   - A structured logging seam (irrig_event_t) carrying everything a log
 * record needs, so you can back it with Serial now and a file / WiFi sink
 * later.
 *
 * TWO HARD INVARIANTS, enforced structurally by the global state machine:
 *   1. At most ONE pump runs at any instant.
 *   2. NO probe is sampled while any pump runs.
 *
 *   SYS_SAMPLING : all pumps OFF. Read every probe, update classifiers, decide.
 *                  Grant the single pump to AT MOST ONE channel.
 *   SYS_WATERING : exactly ONE pump ON for a fixed dose. No sampling.
 *   SYS_SETTLE   : all pumps OFF. Wait out motor/supply recovery, then
 * resample.
 *
 * Watering is open-loop per dose (you cannot read a probe with its pump
 * running) and closed-loop across doses: dose -> soak lockout -> resample ->
 * re-decide.
 *
 * Safety:
 *   - Only in-soil DRY *display* levels trigger watering. air-dry (probe not in
 *     soil), submerged, water-contact, or a tripped spread/health flag NEVER
 * water.
 *   - Hard per-pump run ceiling (failsafe) independent of the dose length.
 *   - Post-dose soak lockout so water can migrate to the probe before
 * re-deciding.
 *   - No-improvement latch (dry tank / kinked tube / dead pump) stops a
 * channel.
 *   - Sensor-health veto (BACKLOG A1): a per-read spread/health flag suppresses
 *     watering immediately (auto-recovers), and a sustained flag for
 *     max_health_warn consecutive sweeps latches a HARD fault - a floating or
 *     disconnected probe reading a plausible "dry" can never trip the pump.
 *
 * Framework-agnostic: caller supplies now_ms and three callbacks (read ONE ADC
 * sample, drive one relay [handle active-low here], optional event sink). No
 * blocking delays, no analogRead/digitalWrite dependency, no dynamic
 * allocation.
 *
 * --- LOGGING SEAM -----------------------------------------------------------
 * io.on_event(&irrig_event_t, user) fires at every decision/action. The event
 * carries {now_ms, ch, code, level, raw, spread} - everything a log record
 * needs. Wire it to Serial now for debugging; later back it with LittleFS/SD or
 * push it over WiFi/MQTT to a local server. Pass NULL to disable. Example stub:
 *
 *     static void log_event(const irrig_event_t *e, void *user) {
 *         // TODO(logging): replace Serial with file/WiFi sink later.
 *         Serial.printf("[%lu] ch%d %-18s level=%d raw=%u spr=%u\n",
 *             (unsigned long)e->now_ms, e->ch, irrig_event_name(e->code),
 *             e->level, e->raw, e->spread);
 *     }
 * -----------------------------------------------------------------------------
 */
#ifndef IRRIGATION_H
#define IRRIGATION_H

#include <stdint.h>
#include <stdbool.h>
#include "moisture_classifier.h"

#ifdef __cplusplus
extern "C" {
#endif

#define IRRIG_CHANNELS 4

/* -------------------------------------------------------------------------- */
/* logging seam                                                               */
/* -------------------------------------------------------------------------- */

typedef enum {
    IRRIG_EV_LEVEL_CHANGE = 0, /* committed moisture level changed           */
    IRRIG_EV_PUMP_ON, /* a dose started on this channel             */
    IRRIG_EV_PUMP_OFF, /* the dose ended                             */
    IRRIG_EV_TARGET_REACHED, /* channel reached target_level after dosing  */
    IRRIG_EV_PROBE_NOT_IN_SOIL, /* read air-dry: probe likely out of soil     */
    IRRIG_EV_SENSOR_FAULT, /* trimmed-spread health flag tripped         */
    IRRIG_EV_PUMP_OVERRUN_FAULT, /* pump hit the hard run ceiling (latched)   */
    IRRIG_EV_NO_IMPROVEMENT_FAULT, /* doses not wetting the soil (latched) */
    IRRIG_EV_HEALTH_FAULT, /* sustained health warning latched (A1)      */
    IRRIG_EV_FAULT_CLEARED /* a latched fault was manually cleared        */
} irrig_event_code_t;

typedef struct {
    uint32_t now_ms;
    int ch;
    irrig_event_code_t code;
    moisture_level_t level; /* committed level at the time                */
    uint16_t raw; /* last trimmed-mean raw                       */
    uint16_t spread; /* last trimmed-set spread (health)           */
} irrig_event_t;

const char *irrig_event_name(irrig_event_code_t code);

/* -------------------------------------------------------------------------- */
/* configuration                                                              */
/* -------------------------------------------------------------------------- */

/* Shared system policy. */
typedef struct {
    uint32_t sample_period_ms; /* idle cadence between sweeps when nothing
                                     needs water (minutes in deployment)       */
    uint8_t adc_discard; /* throwaway reads after a channel switch to
                                     cover S/H settling (e.g. 2). Non-blocking. */
    uint32_t post_pump_settle_ms; /* SETTLE duration after a pump stops */
    uint32_t pump_max_ms; /* HARD ceiling on any single pump run; hitting
                             it latches a fault                         */
    uint8_t max_doses; /* consecutive non-improving doses before
                             latching a no-improvement fault            */
    uint16_t min_improvement_raw; /* a dose must drop the trimmed-mean raw by at
                                     least this (wetter) to count as progress */
    uint8_t max_health_warn; /* consecutive unhealthy sweeps (classifier
                                     spread > spread_warn_raw) before a channel
                                     latches a HARD sensor fault (BACKLOG A1).
                                     0 disables the latch; the per-read health
                                     veto still applies regardless.             */
} irrig_sys_cfg_t;

/* Per-channel irrigation policy (separate from the per-probe moisture_cfg_t).
 * Dose-to-target hysteresis: request water while the committed display level is
 * in [MOIST_DRY .. water_at_or_below]; consider the channel recovered once it
 * is at or wetter than target_level. Set target_level a notch or two wetter
 * than water_at_or_below for a clean hysteresis gap (no dosing chatter). */
typedef struct {
    uint32_t dose_ms; /* pump run length per pulse             */
    uint32_t soak_ms; /* lockout after a dose                   */
    moisture_level_t
        water_at_or_below; /* request when level <= this (& >= DRY)  */
    moisture_level_t target_level; /* recovered when level >= this          */
} irrig_chan_cfg_t;

/* Caller-supplied I/O. read_raw must select channel `ch` and return ONE ADC
 * sample (the engine does the burst + trimmed mean). set_pump handles the
 * relay's active-low polarity. on_event may be NULL. `user` is passed back to
 * all. */
typedef struct {
    uint16_t (*read_raw)(int ch, void *user);
    void (*set_pump)(int ch, bool on, void *user);
    void (*on_event)(const irrig_event_t *ev, void *user);
    void *user;
} irrig_io_t;

/* -------------------------------------------------------------------------- */
/* runtime state                                                              */
/* -------------------------------------------------------------------------- */

typedef enum {
    SYS_SAMPLING = 0, /* pumps off, reading probes              */
    SYS_WATERING, /* exactly one pump on                    */
    SYS_SETTLE /* pumps off, post-dose recovery wait     */
} irrig_mode_t;

typedef enum {
    CH_OK = 0, /* eligible: monitoring / may request     */
    CH_SOAKING, /* recently dosed; locked out until soak  */
    CH_FAULT /* not watered (latched hard fault OR a
                   non-latching sensor-health warning)    */
} irrig_chan_status_t;

typedef struct {
    /* wiring (all caller-owned; arrays of length IRRIG_CHANNELS) */
    const irrig_sys_cfg_t *sys;
    const irrig_chan_cfg_t *chan_cfg;
    const moisture_cfg_t *mcfg;
    moisture_state_t *mstate;
    uint16_t *scratch; /* burst buffer, >= max sample_count   */
    irrig_io_t io;

    /* global runtime */
    irrig_mode_t mode;
    int active_ch; /* -1 = none; the single running pump  */
    uint32_t phase_start_ms;
    uint32_t next_sample_ms;
    int last_served; /* rotation pointer for fairness       */
    uint32_t active_dose_ms; /* length of the in-flight dose, resolved at
                                grant: forced_ms (clamped) or chan dose_ms */

    /* per-channel runtime */
    irrig_chan_status_t status[IRRIG_CHANNELS];
    moisture_level_t level[IRRIG_CHANNELS];
    bool wants[IRRIG_CHANNELS];
    bool faulted[IRRIG_CHANNELS]; /* HARD latch (manual clear) */
    uint32_t soak_until_ms[IRRIG_CHANNELS];
    uint16_t raw_at_dose[IRRIG_CHANNELS]; /* raw when last dose granted */
    uint8_t dose_count[IRRIG_CHANNELS]; /* consecutive non-improving  */
    bool dosed_once[IRRIG_CHANNELS]; /* dosed since last reset      */
    moisture_level_t prev_level[IRRIG_CHANNELS]; /* for level-change events */
    bool prev_health_warn[IRRIG_CHANNELS];
    uint8_t warn_count[IRRIG_CHANNELS]; /* consecutive unhealthy reads;
                                               self-heals on a clean read,
                                               latches at max_health_warn (A1) */
    uint32_t last_water_ms[IRRIG_CHANNELS]; /* millis() at the last dose-off;
                                               interval telemetry (D1/E3)  */
    bool forced[IRRIG_CHANNELS]; /* operator forced-dose pending (ADR-0016) */
    uint32_t forced_ms[IRRIG_CHANNELS]; /* requested dose length; 0 = use chan
                                           dose_ms */
} irrig_ctrl_t;

/* -------------------------------------------------------------------------- */
/* API                                                                        */
/* -------------------------------------------------------------------------- */

/* All pumps forced OFF and classifiers seeded from one burst each (safe;
 * nothing is pumping at init). Call once after wiring up the cfg/state arrays.
 */
void irrig_init(irrig_ctrl_t *c, const irrig_sys_cfg_t *sys,
                const irrig_chan_cfg_t *chan_cfg, const moisture_cfg_t *mcfg,
                moisture_state_t *mstate, uint16_t *scratch, irrig_io_t io,
                uint32_t now_ms);

/* Non-blocking. Call every loop with a millisecond clock (millis()). Drives the
 * whole state machine. */
void irrig_tick(irrig_ctrl_t *c, uint32_t now_ms);

/* Clear a latched HARD fault after you've fixed the tube/tank/pump. */
void irrig_clear_fault(irrig_ctrl_t *c, int ch);

/* Operator-forced dose (ADR-0016): express a manual !water as a request INTO
 * the supervisor, not a second relay driver. Queues a one-shot dose on `ch` for
 * `ms` (0 = the channel's configured dose_ms), granted on the next SYS_SAMPLING
 * tick with priority over autonomous wants. Bypasses the moisture-level
 * decision, the per-read health veto, and the soak lockout (operator intent)
 * but still honors the hard invariants: at most one pump at a time, the
 * pump_max_ms ceiling (the request is clamped to it), and the HARD fault latch
 * (a faulted channel is refused - clear it first). One-shot: the request is
 * consumed when the dose is granted. */
typedef enum {
    IRRIG_DOSE_QUEUED = 0, /* accepted; granted on the next SYS_SAMPLING tick */
    IRRIG_DOSE_BAD_CHANNEL, /* ch out of [0, IRRIG_CHANNELS) */
    IRRIG_DOSE_FAULTED /* channel hard-faulted - clear it first            */
} irrig_dose_result_t;

irrig_dose_result_t irrig_request_dose(irrig_ctrl_t *c, int ch, uint32_t ms);

/* introspection for logging / UI */
irrig_mode_t irrig_mode(const irrig_ctrl_t *c);
int irrig_active_pump(const irrig_ctrl_t *c); /* -1 if none */
irrig_chan_status_t irrig_status(const irrig_ctrl_t *c, int ch);
moisture_level_t irrig_level(const irrig_ctrl_t *c, int ch);
bool irrig_health_warn(const irrig_ctrl_t *c,
                       int ch); /* per-read OR latched (A1) */
uint8_t irrig_warn_count(const irrig_ctrl_t *c,
                         int ch); /* consecutive unhealthy reads */
uint32_t irrig_last_water_ms(const irrig_ctrl_t *c,
                             int ch); /* millis() of last dose-off  */

#ifdef __cplusplus
}
#endif

#endif /* IRRIGATION_H */
