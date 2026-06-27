/*
 * irrigation.c  — see irrigation.h for the design + invariants.
 *
 * All time comparisons use the (now - since) form so they are safe across the
 * ~49.7-day millis() wrap.
 */
#include "irrigation.h"

/* -------------------------------------------------------------------------- */
/* small helpers                                                              */
/* -------------------------------------------------------------------------- */

const char *irrig_event_name(irrig_event_code_t code)
{
    switch (code) {
        case IRRIG_EV_LEVEL_CHANGE:         return "level_change";
        case IRRIG_EV_PUMP_ON:              return "pump_on";
        case IRRIG_EV_PUMP_OFF:             return "pump_off";
        case IRRIG_EV_TARGET_REACHED:       return "target_reached";
        case IRRIG_EV_PROBE_NOT_IN_SOIL:    return "probe_not_in_soil";
        case IRRIG_EV_SENSOR_FAULT:         return "sensor_fault";
        case IRRIG_EV_PUMP_OVERRUN_FAULT:   return "pump_overrun_fault";
        case IRRIG_EV_NO_IMPROVEMENT_FAULT: return "no_improvement_fault";
        case IRRIG_EV_HEALTH_FAULT:         return "health_fault";
        case IRRIG_EV_FAULT_CLEARED:        return "fault_cleared";
        default:                            return "?";
    }
}

static void emit(irrig_ctrl_t *c, int ch, irrig_event_code_t code, uint32_t now)
{
    if (!c->io.on_event) return;
    irrig_event_t e;
    e.now_ms = now;
    e.ch     = ch;
    e.code   = code;
    e.level  = c->level[ch];
    e.raw    = c->mstate[ch].last_raw;
    e.spread = c->mstate[ch].last_spread;
    c->io.on_event(&e, c->io.user);
}

static void all_pumps_off(irrig_ctrl_t *c)
{
    for (int ch = 0; ch < IRRIG_CHANNELS; ch++)
        c->io.set_pump(ch, false, c->io.user);
    c->active_ch = -1;
}

/* One denoised measurement for a channel: discard a few reads to cover the S/H
 * switch, fill the burst, trimmed-mean it through the classifier. */
static moisture_level_t sample_channel(irrig_ctrl_t *c, int ch)
{
    const moisture_cfg_t *mc = &c->mcfg[ch];
    for (uint8_t d = 0; d < c->sys->adc_discard; d++)
        (void)c->io.read_raw(ch, c->io.user);
    for (uint16_t i = 0; i < mc->sample_count; i++)
        c->scratch[i] = c->io.read_raw(ch, c->io.user);
    return moisture_process(&c->mstate[ch], mc, c->scratch, mc->sample_count);
}

/* Pick the channel to water: only eligible (wants) ones, driest first, with a
 * rotating start index so ties don't always favor channel 0 (anti-starvation). */
static int choose_channel(irrig_ctrl_t *c)
{
    /* Operator forced doses (ADR-0016) take priority over autonomous wants; a
     * hard-faulted channel is never granted (clear it first). Rotate for fairness. */
    for (int k = 0; k < IRRIG_CHANNELS; k++) {
        int ch = (c->last_served + 1 + k) % IRRIG_CHANNELS;
        if (c->forced[ch] && !c->faulted[ch]) return ch;
    }
    int best = -1;
    for (int k = 0; k < IRRIG_CHANNELS; k++) {
        int ch = (c->last_served + 1 + k) % IRRIG_CHANNELS;
        if (!c->wants[ch]) continue;
        if (best < 0 || c->level[ch] < c->level[best]) best = ch;  /* lower idx = drier */
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

        /* edge-triggered telemetry: committed level changed since last sweep */
        if (lvl != c->prev_level[ch]) {
            emit(c, ch, IRRIG_EV_LEVEL_CHANGE, now);
            c->prev_level[ch] = lvl;
        }

        /* hard latched fault: never water until manually cleared */
        if (c->faulted[ch]) { c->status[ch] = CH_FAULT; continue; }

        /* sensor-health (spread) veto - BACKLOG A1. A floating/disconnected probe
         * can report a plausible "dry" with a huge sample spread; never act on it.
         * The per-read veto suppresses watering immediately and auto-recovers when
         * the spread settles (a transient glitch). A SUSTAINED warning - health_warn
         * for max_health_warn consecutive sweeps - escalates to a HARD latched fault
         * (manual clear), because a probe unhealthy that long is real hardware
         * trouble a human should look at. warn_count self-heals to 0 on any clean
         * read, so only a persistent fault reaches the threshold. max_health_warn
         * == 0 disables the latch; the per-read veto still applies. */
        if (c->mstate[ch].health_warn) {
            if (!c->prev_health_warn[ch]) emit(c, ch, IRRIG_EV_SENSOR_FAULT, now);
            c->prev_health_warn[ch] = true;
            if (c->warn_count[ch] < 0xFF) c->warn_count[ch]++;
            if (c->sys->max_health_warn &&
                c->warn_count[ch] >= c->sys->max_health_warn) {
                if (!c->faulted[ch]) emit(c, ch, IRRIG_EV_HEALTH_FAULT, now);
                c->faulted[ch] = true;                  /* HARD latch */
            }
            c->status[ch] = CH_FAULT;
            continue;
        }
        c->prev_health_warn[ch] = false;
        c->warn_count[ch] = 0;          /* clean read -> self-heal the soft counter */

        /* out of the real soil range: never water */
        if (!moisture_level_is_display(lvl)) {
            if (lvl <= MOIST_AIR_DRY) emit(c, ch, IRRIG_EV_PROBE_NOT_IN_SOIL, now);
            c->status[ch] = CH_OK;   /* not soil, but not a hard fault either */
            continue;
        }

        /* recovered: at or wetter than the target level */
        if (lvl >= cc->target_level) {
            if (c->dosed_once[ch]) emit(c, ch, IRRIG_EV_TARGET_REACHED, now);
            c->dose_count[ch] = 0;
            c->dosed_once[ch] = false;
            c->status[ch]     = CH_OK;
            continue;
        }

        /* hysteresis hold: wetter than the request line but not yet at target -
         * don't start a new dose, don't disturb the dose counter */
        if (lvl > cc->water_at_or_below) {
            c->status[ch] = CH_OK;
            continue;
        }

        /* in [MOIST_DRY .. water_at_or_below]: dry enough to want water */
        if ((int32_t)(now - c->soak_until_ms[ch]) < 0) {
            /* still inside the soak lockout (now < soak_until_ms, wrap-safe) */
            c->status[ch] = CH_SOAKING;
            continue;
        }

        /* soak expired and still dry: judge whether the last dose actually helped */
        if (c->dosed_once[ch]) {
            int improvement = (int)c->raw_at_dose[ch] - (int)c->mstate[ch].last_raw;
            if (improvement >= (int)c->sys->min_improvement_raw) {
                c->dose_count[ch] = 0;            /* genuine progress */
            } else {
                c->dose_count[ch]++;              /* a dose that didn't wet the soil */
                if (c->dose_count[ch] >= c->sys->max_doses) {
                    c->faulted[ch] = true;
                    c->status[ch]  = CH_FAULT;
                    emit(c, ch, IRRIG_EV_NO_IMPROVEMENT_FAULT, now);
                    continue;
                }
            }
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

        c->status[ch]           = CH_OK;
        c->level[ch]            = mstate[ch].committed;
        c->wants[ch]            = false;
        c->faulted[ch]          = false;
        c->soak_until_ms[ch]    = now_ms;
        c->raw_at_dose[ch]      = mstate[ch].last_raw;
        c->dose_count[ch]       = 0;
        c->dosed_once[ch]       = false;
        c->prev_level[ch]       = mstate[ch].committed;
        c->prev_health_warn[ch] = false;
        c->warn_count[ch]       = 0;
        c->last_water_ms[ch]    = now_ms;
        c->forced[ch]           = false;
        c->forced_ms[ch]        = 0;
    }

    c->mode           = SYS_SAMPLING;
    c->active_ch      = -1;
    c->phase_start_ms = now_ms;
    c->next_sample_ms = now_ms;             /* sample on the first tick */
    c->last_served    = IRRIG_CHANNELS - 1; /* so rotation starts at ch 0 */
    c->active_dose_ms = 0;
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
            /* Resolve the dose length: an operator forced dose (ADR-0016) uses its
             * requested ms (0 = the channel default), clamped to pump_max_ms so the
             * ceiling holds WITHOUT tripping the overrun fault; autonomous uses the
             * channel's dose_ms. Consume the one-shot forced request here. */
            uint32_t dose = c->chan_cfg[ch].dose_ms;
            if (c->forced[ch]) {
                dose = c->forced_ms[ch] ? c->forced_ms[ch] : c->chan_cfg[ch].dose_ms;
                if (dose > c->sys->pump_max_ms) dose = c->sys->pump_max_ms;
                c->forced[ch]    = false;
                c->forced_ms[ch] = 0;
            }
            c->active_dose_ms  = dose;

            /* grant the single pump token; remember the pre-dose raw so the next
             * sweep can judge whether this dose actually wetted the soil */
            c->active_ch       = ch;
            c->last_served     = ch;
            c->raw_at_dose[ch] = c->mstate[ch].last_raw;
            c->dosed_once[ch]  = true;
            c->io.set_pump(ch, true, c->io.user);
            c->mode            = SYS_WATERING;
            c->phase_start_ms  = now;
            emit(c, ch, IRRIG_EV_PUMP_ON, now);
        } else {
            /* nothing needs water -> relax to idle cadence */
            c->next_sample_ms = now + c->sys->sample_period_ms;
        }
        return;
    }

    case SYS_WATERING: {
        int ch = c->active_ch;
        uint32_t run = now - c->phase_start_ms;
        bool dose_done = run >= c->active_dose_ms;
        bool overrun   = run >= c->sys->pump_max_ms;

        if (dose_done || overrun) {
            c->io.set_pump(ch, false, c->io.user);
            c->active_ch = -1;
            emit(c, ch, IRRIG_EV_PUMP_OFF, now);
            c->last_water_ms[ch] = now;          /* last dose-off (D1/E3 telemetry) */

            c->soak_until_ms[ch] = now + c->chan_cfg[ch].soak_ms;
            c->status[ch]        = CH_SOAKING;

            if (overrun && !dose_done) {
                c->faulted[ch] = true;
                c->status[ch]  = CH_FAULT;
                emit(c, ch, IRRIG_EV_PUMP_OVERRUN_FAULT, now);
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
    c->faulted[ch]    = false;
    c->dose_count[ch] = 0;
    c->dosed_once[ch] = false;
    c->warn_count[ch] = 0;
    c->status[ch]     = CH_OK;
    emit(c, ch, IRRIG_EV_FAULT_CLEARED, c->phase_start_ms);
}

/* Operator forced dose (ADR-0016): queue a one-shot dose on `ch`. Granted on the next
 * SYS_SAMPLING tick (choose_channel gives it priority); the dose length + ceiling clamp
 * are resolved there. Refused for a bad channel or a hard-faulted one. */
irrig_dose_result_t irrig_request_dose(irrig_ctrl_t *c, int ch, uint32_t ms)
{
    if (ch < 0 || ch >= IRRIG_CHANNELS) return IRRIG_DOSE_BAD_CHANNEL;
    if (c->faulted[ch])                 return IRRIG_DOSE_FAULTED;   /* clear it first */
    c->forced[ch]    = true;
    c->forced_ms[ch] = ms;   /* 0 = the channel's configured dose_ms; clamped at grant */
    return IRRIG_DOSE_QUEUED;
}

irrig_mode_t        irrig_mode(const irrig_ctrl_t *c)           { return c->mode; }
int                 irrig_active_pump(const irrig_ctrl_t *c)    { return c->active_ch; }
irrig_chan_status_t irrig_status(const irrig_ctrl_t *c, int ch) { return c->status[ch]; }
moisture_level_t    irrig_level(const irrig_ctrl_t *c, int ch)  { return c->level[ch]; }

/* A1: true if the probe's last read tripped the spread/health flag, OR the
 * sustained-fault latch has fired. Surface this on the serial banner / HMI so a
 * floating probe announces itself instead of silently reading "dry". */
bool irrig_health_warn(const irrig_ctrl_t *c, int ch)
{
    if (ch < 0 || ch >= IRRIG_CHANNELS) return false;
    if (c->mstate[ch].health_warn) return true;
    return c->sys->max_health_warn &&
           c->warn_count[ch] >= c->sys->max_health_warn;
}

uint8_t irrig_warn_count(const irrig_ctrl_t *c, int ch)
{
    return (ch < 0 || ch >= IRRIG_CHANNELS) ? 0 : c->warn_count[ch];
}

uint32_t irrig_last_water_ms(const irrig_ctrl_t *c, int ch)
{
    return (ch < 0 || ch >= IRRIG_CHANNELS) ? 0 : c->last_water_ms[ch];
}
