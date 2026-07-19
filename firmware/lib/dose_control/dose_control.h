/*
 * dose_control.h
 * -----------------------------------------------------------------------------
 * Bounded re-wetting control + pass-through discrimination (#414, Epic #410-C).
 *
 * Turns "this plant needs water" into a SAFE, BOUNDED sequence of pulses, and -
 * the load-bearing part - tells two dose outcomes apart:
 *
 *   ABSORBED    the soil wetted; the root zone took the water.
 *   RAN_THROUGH runoff/tray-fill while the soil did NOT move - water bypassed a
 *               hydrophobic / parched root zone straight to the tray.
 *
 * Why it matters (#410, the under-watering fail-safe): a parched pot is
 * pass-through. A big confident dose runs straight through and out the bottom
 * WITHOUT wetting the roots. Naive logic then either
 *   - floods  (soil still reads dry -> keep dosing -> drown the tray), or
 *   - starves (treats the runoff as "done" -> plant stays thirsty).
 * The per-dose ABSORBED / RAN_THROUGH outcome is exactly the signal Child B
 * (#413 remediation) branches on: ABSORBED -> continue the normal bounded cycle;
 * RAN_THROUGH -> hand off to spaced small pulses + absorption windows, never more
 * volume.
 *
 * The three decision bands (#410 "keep all three reachable"):
 *   ACT   dry enough to water
 *   WAIT  measure-monitor-wait (the center)
 *   HOLD  wet enough, stand down
 * If a config collapses these into one another the system gets stuck in the
 * center forever (permanent indecision - the never-confident failure in a third
 * disguise). dose_bands_separable() is the structural guard against that.
 *
 * SAFETY: every cycle is hard-bounded by max_pulses; there is no path that doses
 * without a bound (composes with the fail-safe #93 / ADR-0022 over-water gate).
 *
 * Framework-agnostic C11: no allocation, no floats, no hardware. Capacitive
 * convention throughout: HIGHER raw = DRIER (boundaries descending). This module
 * is the SIM-TUNED policy (validated by the dose_sim tuning harness in the native
 * tests); the real pump wiring (#382, needs:hardware) composes it over pump_pulse
 * + the irrigation engine (#227) later - NOT wired into the shipping loop here.
 * -----------------------------------------------------------------------------
 */
#ifndef DOSE_CONTROL_H
#define DOSE_CONTROL_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The three decision bands. Ordered by wetness: HOLD (wettest) < WAIT < ACT. */
typedef enum {
    DOSE_HOLD = 0, /* don't-act: wet enough, stand down     */
    DOSE_WAIT, /* measure-monitor-wait: the center band */
    DOSE_ACT /* act: dry enough to water              */
} dose_decision_t;

/* Per-dose outcome, judged after a pulse + its observe/absorption window. */
typedef enum {
    DOSE_INCONCLUSIVE = 0, /* window not elapsed, or neither test tripped */
    DOSE_ABSORBED, /* soil moved wet-ward: root zone took water   */
    DOSE_RAN_THROUGH /* runoff AND soil did not move: pass-through   */
} dose_outcome_t;

/* How a bounded cycle ended. */
typedef enum {
    DOSE_CYCLE_TARGET = 0, /* reached WAIT/HOLD: watered, success        */
    DOSE_CYCLE_PASSTHROUGH, /* ran-through: hand to Child B (#413) spaced  */
    DOSE_CYCLE_BOUND /* hit max_pulses without target: stop safe    */
} dose_cycle_result_t;

typedef struct {
    /* --- 3-band decision (confidence-resolved raw edges) --- */
    uint16_t act_at_raw; /* raw >= this  -> ACT  (dry)               */
    uint16_t hold_at_raw; /* raw <= this  -> HOLD (wet)               */
    /* hold_at_raw < raw < act_at_raw -> WAIT   */
    /* --- absorbed vs ran-through discrimination --- */
    uint16_t absorbed_drop; /* min wet-ward raw drop over the observe    */
    /* window to call a dose ABSORBED            */
    /* --- bounds / timing (over-water safety) --- */
    uint8_t max_pulses; /* hard cap on pulses per cycle (>= 1)       */
    uint32_t pulse_ms; /* bounded pulse duration                    */
    uint32_t observe_ms; /* absorption window before judging a dose   */
} dose_cfg_t;

/* Sim/hardware seam: the cycle owns the control logic, these own timing + IO.
 * read_raw MUST return the SETTLED raw after the observe/absorption window (the
 * caller/sim is responsible for having waited observe_ms). */
typedef struct {
    uint16_t (*read_raw)(void *user); /* settled soil raw            */
    void (*pulse)(uint32_t ms, void *user); /* issue one bounded pulse     */
    bool (*runoff)(void *user); /* tray-fill / runoff asserted */
    void (*on_event)(dose_outcome_t o, uint16_t raw,
                     void *user); /* log seam    */
    void *user;
} dose_io_t;

typedef struct {
    dose_cycle_result_t result;
    uint8_t pulses; /* pulses issued this cycle (<= max_pulses)      */
    uint8_t absorbed; /* doses classified ABSORBED                     */
    uint8_t ran_through; /* doses classified RAN_THROUGH                  */
    uint16_t start_raw;
    uint16_t end_raw;
} dose_cycle_report_t;

/* 3-band decision from one resolved raw reading. */
dose_decision_t dose_decide(uint16_t raw, const dose_cfg_t *cfg);

/* Structural separability guard (#410): the three bands are distinct + ordered
 * so the system can always leave the center. Returns false if the config
 * collapses or inverts them (requires act_at_raw > hold_at_raw with a WAIT gap,
 * and max_pulses >= 1). */
bool dose_bands_separable(const dose_cfg_t *cfg);

/* Classify one dose. ABSORBED: soil dropped (wet-ward) by >= absorbed_drop over
 * the window. RAN_THROUGH: runoff asserted AND the soil did not move that far
 * (water bypassed the root zone). Otherwise INCONCLUSIVE. */
dose_outcome_t dose_classify(uint16_t pre_raw, uint16_t post_raw, bool runoff,
                             const dose_cfg_t *cfg);

/* Run one bounded cycle. Reads settled raw; if already WAIT/HOLD returns TARGET.
 * While ACT and pulses < max_pulses: pulse -> observe (read_raw) -> classify.
 * RAN_THROUGH stops immediately with PASSTHROUGH; reaching WAIT/HOLD stops with
 * TARGET; exhausting max_pulses stops with BOUND. Never doses unbounded. */
dose_cycle_report_t dose_cycle_run(const dose_cfg_t *cfg, const dose_io_t *io);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* DOSE_CONTROL_H */
