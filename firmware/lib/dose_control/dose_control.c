/*
 * dose_control.c - see dose_control.h for the design.
 * Bounded re-wetting control + absorbed/ran-through discrimination (#414).
 */
#include "dose_control.h"

dose_decision_t dose_decide(uint16_t raw, const dose_cfg_t *cfg)
{
    /* Capacitive: higher raw = drier. */
    if (raw >= cfg->act_at_raw) return DOSE_ACT;
    if (raw <= cfg->hold_at_raw) return DOSE_HOLD;
    return DOSE_WAIT;
}

bool dose_bands_separable(const dose_cfg_t *cfg)
{
    /* All three bands must be non-empty + correctly ordered, else the system
     * can get stuck in the center forever (#410). WAIT = {raw : hold < raw <
     * act} is non-empty only when act_at_raw >= hold_at_raw + 2. A cycle must
     * also be able to pulse at least once. */
    if (cfg->max_pulses == 0) return false;
    if (cfg->act_at_raw <= cfg->hold_at_raw)
        return false; /* inverted/degenerate */
    if ((uint16_t)(cfg->act_at_raw - cfg->hold_at_raw) < 2)
        return false; /* no WAIT gap */
    return true;
}

dose_outcome_t dose_classify(uint16_t pre_raw, uint16_t post_raw, bool runoff,
                             const dose_cfg_t *cfg)
{
    /* Wet-ward movement = the raw getting SMALLER (capacitive). */
    int drop = (int)pre_raw - (int)post_raw;

    if (drop >= (int)cfg->absorbed_drop)
        return DOSE_ABSORBED; /* soil took water */
    if (runoff)
        return DOSE_RAN_THROUGH; /* runoff but soil didn't move: bypass */
    return DOSE_INCONCLUSIVE;
}

dose_cycle_report_t dose_cycle_run(const dose_cfg_t *cfg, const dose_io_t *io)
{
    dose_cycle_report_t r = {0};
    uint16_t cur = io->read_raw(io->user);
    r.start_raw = cur;
    r.end_raw = cur;

    /* Already at/into WAIT or HOLD -> nothing to do (watered enough). */
    if (dose_decide(cur, cfg) != DOSE_ACT) {
        r.result = DOSE_CYCLE_TARGET;
        return r;
    }

    while (r.pulses < cfg->max_pulses) {
        uint16_t pre = cur;
        io->pulse(cfg->pulse_ms, io->user); /* one bounded pulse         */
        uint16_t post = io->read_raw(io->user); /* settled, post-observe     */
        dose_outcome_t o = dose_classify(pre, post, io->runoff(io->user), cfg);

        r.pulses++;
        if (o == DOSE_ABSORBED)
            r.absorbed++;
        else if (o == DOSE_RAN_THROUGH)
            r.ran_through++;
        if (io->on_event) io->on_event(o, post, io->user);

        cur = post;
        r.end_raw = cur;

        if (o == DOSE_RAN_THROUGH) { /* pass-through: hand to Child B (#413) */
            r.result = DOSE_CYCLE_PASSTHROUGH;
            return r;
        }
        if (dose_decide(cur, cfg) != DOSE_ACT) { /* reached the target band */
            r.result = DOSE_CYCLE_TARGET;
            return r;
        }
    }

    r.result =
        DOSE_CYCLE_BOUND; /* exhausted the bound without target: stop safe */
    return r;
}
