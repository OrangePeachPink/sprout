/* ARCHIVED REFERENCE - NOT ACTIVE, NOT COMPILED, NOT THE BASELINE.
 * Late-night uncommitted prototype "design B" (2026-06-23). Source of the A1
 * health-veto latch + accessor that were grafted into the canonical module at
 * firmware/lib/irrigation/irrigation.{c,h}. See README.md in this folder.
 * --------------------------------------------------------------------------- */
/*
 * irrigation.h
 * -----------------------------------------------------------------------------
 * Supervisory controller for a 4-channel capacitive-soil watering system on a
 * single ESP32: 4 sensors (ADC1) -> 4 classifiers -> arbiter -> 4 relays/pumps.
 *
 * Two hard invariants, enforced structurally by the state machine:
 *   1. AT MOST ONE pump runs at any instant. A pump can only be started from
 *      IRR_IDLE (active_pump == -1), and no other can start until the FSM has
 *      returned through IRR_SETTLE -> IRR_IDLE.
 *   2. NO channel is sampled while ANY pump runs. Sampling happens only in
 *      IRR_IDLE, which is unreachable while a pump is active.
 *
 * Watering is open-loop per dose (you can't sample mid-pump) and closed-loop
 * across doses: dose a fixed amount -> stop -> soak lockout -> resample -> if
 * still dry, dose again. After `max_doses` without reaching target the channel
 * faults (probe out of soil, empty reservoir, dead pump) and stops requesting.
 *
 * The module owns the four classifiers. You provide two hardware hooks:
 * one to read a channel's (already trimmed-mean) raw value, one to drive a
 * relay. Drive logic is yours (handle active-low inversion in the pump hook).
 * -----------------------------------------------------------------------------
 */
#ifndef IRRIGATION_H
#define IRRIGATION_H

#include "moisture_classifier.h"
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define IRR_MAX_CHANNELS 4

/* Return a trimmed-mean raw ADC value for channel `ch` (do your 100-sample
 * burst + trim inside). Called ONLY when no pump is running. */
typedef uint16_t (*irr_sample_fn)(uint8_t ch, void *user);

/* Drive the relay for channel `ch`. on=true -> pump runs. Handle active-low
 * inversion here. Must be safe to call with the same value repeatedly. */
typedef void (*irr_pump_fn)(uint8_t ch, bool on, void *user);

typedef struct {
    uint8_t  num_channels;          /* 1..IRR_MAX_CHANNELS                      */

    uint32_t sample_period_ms;      /* cadence between sample sweeps when idle   */
    uint32_t pump_settle_ms;        /* quiet time after a pump stops before
                                       sampling resumes (motor noise decay)      */
    uint32_t pump_dose_ms;          /* duration of ONE watering dose             */
    uint32_t soak_lockout_ms;       /* after watering, channel can't re-water
                                       for this long (let water reach the probe) */

    uint8_t  max_doses;             /* consecutive doses w/o reaching target
                                       before the channel faults                 */
    uint8_t  max_health_warn;       /* consecutive unhealthy samples (classifier
                                       spread > spread_warn) before the channel is
                                       treated as faulted. 0 disables the latch;
                                       the per-read veto still applies regardless. */
    moisture_level_t water_at_or_below; /* request water when committed level is
                                           in [MOIST_DRY .. this]                 */
    moisture_level_t target_level;      /* reaching this (or wetter) clears the
                                           dose counter and any fault             */

    /* One classifier config per channel - independent per-probe calibration.
     * IMPORTANT: set each mcfg[ch]->loop_period_ms == sample_period_ms so the
     * classifier's confirm windows mean what you intend at this cadence. */
    const moisture_cfg_t *mcfg[IRR_MAX_CHANNELS];
} irrigation_cfg_t;

typedef enum {
    IRR_SETTLE = 0,   /* pumps OFF, waiting out settle (boot or post-pump)       */
    IRR_IDLE,         /* no pump; sampling on cadence; only state that can pump  */
    IRR_WATERING      /* exactly one pump running; no sampling                   */
} irr_phase_t;

typedef struct {
    moisture_state_t m;             /* classifier state                          */
    moisture_level_t level;         /* last committed level                      */
    bool     soaking;               /* in post-water lockout                     */
    uint32_t soak_since_ms;         /* when soak started (wrap-safe timing)      */
    uint8_t  dose_count;            /* consecutive doses since target reached    */
    uint8_t  warn_count;            /* consecutive unhealthy samples; resets on a
                                       healthy read, so a transient glitch self-
                                       heals and only a sustained fault latches   */
    bool     faulted;               /* gave up requesting water                  */
} irr_channel_t;

typedef struct {
    const irrigation_cfg_t *cfg;
    irr_sample_fn sample;
    irr_pump_fn   pump;
    void         *user;

    irr_phase_t phase;
    uint32_t    phase_since_ms;
    uint32_t    last_sample_ms;
    int8_t      active_pump;        /* -1 = none; else 0..num_channels-1         */
    uint8_t     rr_cursor;          /* round-robin start, prevents starvation    */

    irr_channel_t ch[IRR_MAX_CHANNELS];
} irrigation_t;

/* Forces all pumps OFF, then seeds each classifier with one sample (safe: pumps
 * are off). Configure your ADC and relay GPIOs (driven to OFF) before calling. */
void irrigation_init(irrigation_t *irr, const irrigation_cfg_t *cfg,
                     irr_sample_fn sample, irr_pump_fn pump, void *user,
                     uint32_t now_ms);

/* Advance the controller. Call frequently (every loop). Non-blocking. */
void irrigation_tick(irrigation_t *irr, uint32_t now_ms);

/* Introspection for logging / UI. */
int              irrigation_active_pump(const irrigation_t *irr); /* -1 or ch  */
moisture_level_t irrigation_level(const irrigation_t *irr, uint8_t ch);
bool             irrigation_is_soaking(const irrigation_t *irr, uint8_t ch,
                                       uint32_t now_ms);
bool             irrigation_is_faulted(const irrigation_t *irr, uint8_t ch);
bool             irrigation_health_warn(const irrigation_t *irr, uint8_t ch);

#ifdef __cplusplus
}
#endif

#endif /* IRRIGATION_H */
