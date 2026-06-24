/* ARCHIVED REFERENCE - NOT ACTIVE, NOT COMPILED, NOT THE BASELINE.
 * Late-night uncommitted prototype "design C" (2026-06-23). An earlier ancestor
 * of the active irrig_ctrl_t design; uses 9-band enum names and would NOT compile
 * against the committed 7-band classifier. Source of the last_water_ms idea.
 * Canonical module: firmware/lib/irrigation/irrigation.{c,h}. See README.md.
 * --------------------------------------------------------------------------- */
/*
 * irrigation_controller.h
 * -----------------------------------------------------------------------------
 * 4-channel soil irrigation controller for one ESP32 driving 4 relays/pumps,
 * built on top of moisture_classifier.h (one classifier instance per channel).
 *
 * TWO HARD INVARIANTS, enforced structurally:
 *   1. At most ONE pump runs at any time.
 *   2. NO sampling occurs while any pump is running.
 * These hold because the controller is a global state machine with mutually
 * exclusive phases:
 *
 *   SYS_SAMPLING : all pumps OFF. Read all 4 probes, update classifiers, decide.
 *                  At the end, grant the pump to AT MOST ONE channel.
 *   SYS_WATERING : exactly ONE pump ON for a fixed dose. No sampling.
 *   SYS_SETTLE   : all pumps OFF. Wait for motor noise / supply to recover,
 *                  then return to SYS_SAMPLING.
 *
 * Sampling and pump-on never coexist, so a sensor is never read with a motor
 * running and only one relay is ever energized. Watering is open-loop (timed
 * dose), because you cannot close the loop on a probe you cannot read.
 *
 * Safety built in:
 *   - Only in-soil DRY display levels trigger watering. If a probe reads
 *     air-dry ("not in soil"), submerged, or its trimmed-spread health flag
 *     trips, that channel is NOT watered.
 *   - Hard per-pump run ceiling (failsafe) independent of the dose length.
 *   - Post-dose soak lockout so water can migrate to the probe before re-deciding.
 *   - Consecutive-dose-without-improvement latches a fault (dry tank, kinked
 *     tube, dead pump) and stops watering that channel.
 *
 * Framework-agnostic: caller supplies time (now_ms) and three callbacks
 * (read one ADC sample, drive one relay, optional event log). No blocking
 * delays, no analogRead/digitalWrite dependency, no dynamic allocation.
 * -----------------------------------------------------------------------------
 */
#ifndef IRRIGATION_CONTROLLER_H
#define IRRIGATION_CONTROLLER_H

#include <stdint.h>
#include <stdbool.h>
#include "moisture_classifier.h"

#ifdef __cplusplus
extern "C" {
#endif

#define IRRIG_CHANNELS 4

typedef enum {
    SYS_SAMPLING = 0,   /* pumps off, reading probes              */
    SYS_WATERING,       /* exactly one pump on                    */
    SYS_SETTLE          /* pumps off, post-dose recovery wait     */
} irrig_mode_t;

typedef enum {
    CH_OK = 0,          /* eligible: monitoring / may request     */
    CH_SOAKING,         /* recently dosed; locked out until soak  */
    CH_FAULT            /* latched: not watered until cleared     */
} irrig_chan_status_t;

/* Per-channel irrigation policy (separate from the per-probe moisture_cfg_t). */
typedef struct {
    uint32_t         dose_ms;           /* pump run length per pulse           */
    uint32_t         soak_ms;           /* lockout after a dose                 */
    moisture_level_t water_at_or_below; /* water when committed level is a
                                           DISPLAY level <= this (e.g.
                                           MOIST_NEEDS_WATER)                   */
} irrig_chan_cfg_t;

/* Shared system policy. */
typedef struct {
    uint32_t sample_period_ms;     /* idle cadence between sweeps when nothing
                                      needs water (e.g. minutes in deployment)  */
    uint8_t  adc_discard;          /* throwaway reads after a channel switch to
                                      cover S/H settling (e.g. 2). Non-blocking. */
    uint32_t post_pump_settle_ms;  /* SETTLE duration after a pump stops        */
    uint32_t pump_max_ms;          /* HARD ceiling on any single pump run;
                                      hitting it latches a fault                 */
    uint8_t  max_consecutive_doses;/* doses without the probe getting wetter
                                      before latching a fault                    */
} irrig_sys_cfg_t;

/* Caller-supplied I/O. read_raw must select channel `ch` and return one ADC
 * sample. set_pump handles the relay's active-low polarity. on_event may be
 * NULL. `user` is passed back to all three. */
typedef struct {
    uint16_t (*read_raw)(int ch, void *user);
    void     (*set_pump)(int ch, bool on, void *user);
    void     (*on_event)(int ch, const char *ev, void *user);
    void     *user;
} irrig_io_t;

typedef struct {
    /* wiring (all caller-owned, arrays of length IRRIG_CHANNELS) */
    const irrig_sys_cfg_t  *sys;
    const irrig_chan_cfg_t *chan_cfg;
    const moisture_cfg_t   *mcfg;
    moisture_state_t       *mstate;
    uint16_t               *scratch;     /* burst buffer, >= max sample_count   */
    irrig_io_t              io;

    /* global runtime */
    irrig_mode_t mode;
    int          active_ch;              /* -1 = none; the single running pump  */
    uint32_t     phase_start_ms;
    uint32_t     next_sample_ms;
    int          last_served;            /* rotation pointer for fairness       */

    /* per-channel runtime */
    irrig_chan_status_t status[IRRIG_CHANNELS];
    moisture_level_t    level[IRRIG_CHANNELS];
    bool                wants[IRRIG_CHANNELS];
    uint32_t            soak_until_ms[IRRIG_CHANNELS];
    uint32_t            last_water_ms[IRRIG_CHANNELS];
    uint8_t             doses[IRRIG_CHANNELS];   /* consecutive, no improvement */
} irrig_ctrl_t;

/* All pumps are forced OFF and classifiers seeded from one burst each (safe;
 * nothing is pumping at init). Call once after wiring up cfg/state arrays. */
void irrig_init(irrig_ctrl_t *c,
                const irrig_sys_cfg_t  *sys,
                const irrig_chan_cfg_t *chan_cfg,
                const moisture_cfg_t   *mcfg,
                moisture_state_t       *mstate,
                uint16_t               *scratch,
                irrig_io_t              io,
                uint32_t                now_ms);

/* Non-blocking. Call every loop with a millisecond clock (millis() or
 * esp_timer_get_time()/1000). Drives the whole state machine. */
void irrig_tick(irrig_ctrl_t *c, uint32_t now_ms);

/* Clear a latched fault after you've fixed the tube/tank/pump. */
void irrig_clear_fault(irrig_ctrl_t *c, int ch);

/* introspection for logging/UI */
irrig_mode_t        irrig_mode(const irrig_ctrl_t *c);
int                 irrig_active_pump(const irrig_ctrl_t *c);   /* -1 if none */
irrig_chan_status_t irrig_status(const irrig_ctrl_t *c, int ch);
moisture_level_t    irrig_level(const irrig_ctrl_t *c, int ch);

#ifdef __cplusplus
}
#endif

#endif /* IRRIGATION_CONTROLLER_H */
