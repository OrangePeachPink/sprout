/*
 * pump_pulse.h
 * -----------------------------------------------------------------------------
 * Bounded single-pulse manual pump actuator (#215, parent epic #94).
 *
 * Status: legacy - superseded by the irrigation supervisor's operator forced-dose
 * path (irrigation.h forced[]/forced_ms[], ADR-0016). `!water` routes through
 * g_irrig as a forced dose, not through here. ADR-0016 makes the supervisor the
 * SINGLE actuation authority, so this is a second path to a pump rather than inert
 * dead code; Firmware recommends deletion before a relay is wired (#215/#191).
 * Retained pending the maintainer's word - see lib/README.md.
 *
 * This is the FIRST, deliberately minimal actuation rung: an OPERATOR-COMMANDED,
 * bounded, single-channel pump pulse (driven by `!water,<ch>[,<ms>]` over the #92
 * command registry). It is NOT autonomous dosing - the closed-loop irrig_tick engine
 * (irrigation.h) is the next slice and only turns on once the relay path is proven on
 * the #191 bench and the #2 health/spread veto has landed.
 *
 * Like the rest of the firmware's logic, this is framework-agnostic: it tracks the
 * pulse state against a millisecond clock the caller supplies (millis()) and reports
 * when the relay should go OFF; the caller owns the actual GPIO. No Arduino deps, so it
 * unit-tests on the host.
 *
 * Invariants enforced structurally here:
 *   1. DEFAULT OFF - nothing pulses until armed, and every pulse auto-expires.
 *   2. At most ONE pulse active at a time - a second !water while busy is rejected.
 *   3. Every pulse is BOUNDED - the requested duration is clamped to a hard ceiling
 *      on arm, so a bad/oversized request can never run the pump indefinitely. The
 *      task watchdog (#93) is the independent backstop beneath this.
 * -----------------------------------------------------------------------------
 */
#ifndef PUMP_PULSE_H
#define PUMP_PULSE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    PUMP_PULSE_ARMED = 0,    /* armed OK; a pulse is now active                  */
    PUMP_PULSE_ERR_BUSY,     /* a pulse is already active - rejected             */
    PUMP_PULSE_ERR_CHANNEL,  /* ch outside [0, channels)                         */
    PUMP_PULSE_ERR_DURATION  /* resolved duration was 0 ms - nothing to do       */
} pump_pulse_result_t;

typedef struct {
    /* config (caller-owned values, copied in at init) */
    int      channels;       /* number of valid channels                         */
    uint32_t default_ms;     /* pulse length used when a request omits the ms    */
    uint32_t max_ms;         /* HARD ceiling; arm() clamps the request to this   */
    /* runtime */
    bool     active;
    int      ch;             /* the channel currently pulsing, or -1             */
    uint32_t off_at_ms;      /* clock value at which the active pulse expires     */
    uint32_t armed_ms;       /* the (clamped) duration of the active pulse        */
} pump_pulse_t;

/* Initialize to idle (no pulse). default_ms/max_ms come from config (#215). */
void pump_pulse_init(pump_pulse_t *p, int channels, uint32_t default_ms, uint32_t max_ms);

/* Arm a bounded pulse on `ch` for `req_ms` (0 => default_ms), clamped to max_ms.
 * Rejects if a pulse is already active or `ch` is out of range. On PUMP_PULSE_ARMED
 * the pulse is active and will expire at now_ms + the clamped duration. */
pump_pulse_result_t pump_pulse_arm(pump_pulse_t *p, int ch, uint32_t req_ms, uint32_t now_ms);

/* Call every loop. Returns true EXACTLY ONCE, the moment the active pulse expires, so
 * the caller turns the relay OFF; idempotent (false) thereafter. Rollover-safe. */
bool pump_pulse_service(pump_pulse_t *p, uint32_t now_ms);

/* Force the pulse off now (operator !stop or a safety abort). Returns true if one was
 * active (so the caller turns the relay OFF). */
bool pump_pulse_stop(pump_pulse_t *p);

/* introspection */
bool     pump_pulse_active(const pump_pulse_t *p);
int      pump_pulse_channel(const pump_pulse_t *p);   /* -1 if none */
uint32_t pump_pulse_armed_ms(const pump_pulse_t *p);  /* clamped duration of the active pulse */

#ifdef __cplusplus
}
#endif

#endif /* PUMP_PULSE_H */
