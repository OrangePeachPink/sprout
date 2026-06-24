/* ARCHIVED REFERENCE - NOT ACTIVE, NOT COMPILED, NOT THE BASELINE.
 * Late-night uncommitted prototype "design C" (2026-06-23). An earlier ancestor
 * of the active irrig_ctrl_t design; uses 9-band enum names and would NOT compile
 * against the committed 7-band classifier. Source of the last_water_ms idea.
 * Canonical module: firmware/lib/irrigation/irrigation.{c,h}. See README.md.
 * --------------------------------------------------------------------------- */
/*
 * irrigation_controller.c  - see header for the design + invariants.
 */
#include "irrigation_controller.h"

/* -------------------------------------------------------------------------- */
/* small helpers                                                              */
/* -------------------------------------------------------------------------- */

static void all_pumps_off(irrig_ctrl_t *c)
{
    for (int ch = 0; ch < IRRIG_CHANNELS; ch++)
        c->io.set_pump(ch, false, c->io.user);
    c->active_ch = -1;
}

static void emit(irrig_ctrl_t *c, int ch, const char *ev)
{
    if (c->io.on_event) c->io.on_event(ch, ev, c->io.user);
}

/* One denoised measurement for a channel: discard a few reads to cover the
 * S/H switch, fill the burst, trimmed-mean it through the classifier. */
static moisture_level_t sample_channel(irrig_ctrl_t *c, int ch)
{
    const moisture_cfg_t *mc = &c->mcfg[ch];
    for (uint8_t d = 0; d < c->sys->adc_discard; d++)
        (void)c->io.read_raw(ch, c->io.user);
    for (uint16_t i = 0; i < mc->sample_count; i++)
        c->scratch[i] = c->io.read_raw(ch, c->io.user);
    return moisture_process(&c->mstate[ch], mc, c->scratch, mc->sample_count);
}

/* Pick the channel to water: only eligible ones, driest first, with a rotating
 * start index so ties don't always favor channel 0 (anti-starvation). */
static int choose_channel(irrig_ctrl_t *c)
{
    int best = -1;
    for (int k = 0; k < IRRIG_CHANNELS; k++) {
        int ch = (c->last_served + 1 + k) % IRRIG_CHANNELS;
        if (!c->wants[ch]) continue;
        if (best < 0 || c->level[ch] < c->level[best]) best = ch;
    }
    return best;
}

/* -------------------------------------------------------------------------- */
/* the sweep: evaluate every channel (called only with all pumps OFF)         */
/* -------------------------------------------------------------------------- */

static void do_sweep(irrig_ctrl_t *c, uint32_t now)
{
    all_pumps_off(c);   /* defensive: guarantee invariant 2 before any read */

    for (int ch = 0; ch < IRRIG_CHANNELS; ch++) {
        moisture_level_t lvl = sample_channel(c, ch);
        c->level[ch] = lvl;
        c->wants[ch] = false;

        const irrig_chan_cfg_t *cc = &c->chan_cfg[ch];

        if (c->mstate[ch].health_warn) {
            /* trimmed-spread blew up -> probe/wiring fault. Never water. */
            if (c->status[ch] != CH_FAULT) emit(c, ch, "sensor_fault");
            c->status[ch] = CH_FAULT;
            continue;
        }

        if (!moisture_level_is_display(lvl)) {
            /* out of the real soil range: air-dry (probe not in soil) or
             * submerged/water-contact. Abnormal -> never water. */
            if (lvl <= MOIST_AIR_DRY_SUMMER) emit(c, ch, "probe_not_in_soil");
            continue;
        }

        if (lvl > cc->water_at_or_below) {
            /* wet enough: success. Clear soft state + dose counter. */
            if (c->status[ch] != CH_FAULT) c->status[ch] = CH_OK;
            c->doses[ch] = 0;
            continue;
        }

        /* in-soil and dry enough to want water */
        if (c->status[ch] == CH_FAULT) {
            continue;                       /* latched: ignore until cleared */
        }
        if (now < c->soak_until_ms[ch]) {
            c->status[ch] = CH_SOAKING;     /* still soaking from last dose */
            continue;
        }
        c->status[ch] = CH_OK;
        c->wants[ch]  = true;
    }
}

/* -------------------------------------------------------------------------- */
/* lifecycle                                                                  */
/* -------------------------------------------------------------------------- */

void irrig_init(irrig_ctrl_t *c,
                const irrig_sys_cfg_t  *sys,
                const irrig_chan_cfg_t *chan_cfg,
                const moisture_cfg_t   *mcfg,
                moisture_state_t       *mstate,
                uint16_t               *scratch,
                irrig_io_t              io,
                uint32_t                now_ms)
{
    c->sys = sys; c->chan_cfg = chan_cfg; c->mcfg = mcfg;
    c->mstate = mstate; c->scratch = scratch; c->io = io;

    all_pumps_off(c);                       /* relays OFF before anything else */

    for (int ch = 0; ch < IRRIG_CHANNELS; ch++) {
        /* seed each classifier from one burst (safe: no pump running) */
        const moisture_cfg_t *mc = &mcfg[ch];
        for (uint8_t d = 0; d < sys->adc_discard; d++) (void)io.read_raw(ch, io.user);
        for (uint16_t i = 0; i < mc->sample_count; i++) scratch[i] = io.read_raw(ch, io.user);
        uint16_t seed = moisture_trimmed_mean(scratch, mc->sample_count, mc->trim_each_side, NULL);
        moisture_init(&mstate[ch], mc, seed);

        c->status[ch]        = CH_OK;
        c->level[ch]         = mstate[ch].committed;
        c->wants[ch]         = false;
        c->soak_until_ms[ch] = now_ms;
        c->last_water_ms[ch] = now_ms;
        c->doses[ch]         = 0;
    }

    c->mode           = SYS_SAMPLING;
    c->active_ch      = -1;
    c->phase_start_ms = now_ms;
    c->next_sample_ms = now_ms;             /* sample on the first tick */
    c->last_served    = IRRIG_CHANNELS - 1; /* so rotation starts at ch 0 */
}

/* -------------------------------------------------------------------------- */
/* state machine                                                              */
/* -------------------------------------------------------------------------- */

void irrig_tick(irrig_ctrl_t *c, uint32_t now)
{
    switch (c->mode) {

    case SYS_SAMPLING: {
        if ((int32_t)(now - c->next_sample_ms) < 0) return;   /* not due yet */

        do_sweep(c, now);

        int ch = choose_channel(c);
        if (ch >= 0) {
            /* grant the single pump token */
            c->active_ch      = ch;
            c->last_served    = ch;
            c->io.set_pump(ch, true, c->io.user);
            c->mode           = SYS_WATERING;
            c->phase_start_ms = now;
            emit(c, ch, "pump_on");
        } else {
            /* nothing needs water -> relax to idle cadence */
            c->next_sample_ms = now + c->sys->sample_period_ms;
        }
        return;
    }

    case SYS_WATERING: {
        int ch = c->active_ch;
        uint32_t run = now - c->phase_start_ms;
        bool dose_done = run >= c->chan_cfg[ch].dose_ms;
        bool overrun   = run >= c->sys->pump_max_ms;

        if (dose_done || overrun) {
            c->io.set_pump(ch, false, c->io.user);
            c->active_ch = -1;
            emit(c, ch, "pump_off");

            c->doses[ch]++;
            c->last_water_ms[ch] = now;
            c->soak_until_ms[ch] = now + c->chan_cfg[ch].soak_ms;
            c->status[ch]        = CH_SOAKING;

            if (overrun && !dose_done) {
                c->status[ch] = CH_FAULT;
                emit(c, ch, "pump_overrun_fault");
            } else if (c->doses[ch] >= c->sys->max_consecutive_doses) {
                c->status[ch] = CH_FAULT;
                emit(c, ch, "no_improvement_fault");
            }

            c->mode           = SYS_SETTLE;
            c->phase_start_ms = now;
        }
        return;
    }

    case SYS_SETTLE: {
        if (now - c->phase_start_ms >= c->sys->post_pump_settle_ms) {
            all_pumps_off(c);               /* belt and suspenders */
            c->mode           = SYS_SAMPLING;
            c->next_sample_ms = now;        /* re-sample promptly to service the
                                               next dry channel, if any */
        }
        return;
    }
    }
}

/* -------------------------------------------------------------------------- */
/* introspection                                                              */
/* -------------------------------------------------------------------------- */

void irrig_clear_fault(irrig_ctrl_t *c, int ch)
{
    if (ch < 0 || ch >= IRRIG_CHANNELS) return;
    c->status[ch] = CH_OK;
    c->doses[ch]  = 0;
}

irrig_mode_t        irrig_mode(const irrig_ctrl_t *c)            { return c->mode; }
int                 irrig_active_pump(const irrig_ctrl_t *c)     { return c->active_ch; }
irrig_chan_status_t irrig_status(const irrig_ctrl_t *c, int ch)  { return c->status[ch]; }
moisture_level_t    irrig_level(const irrig_ctrl_t *c, int ch)   { return c->level[ch]; }
