/* ARCHIVED REFERENCE - NOT ACTIVE, NOT COMPILED, NOT THE BASELINE.
 * Late-night uncommitted prototype "design B" (2026-06-23). Source of the A1
 * health-veto latch + accessor that were grafted into the canonical module at
 * firmware/lib/irrigation/irrigation.{c,h}. See README.md in this folder.
 * --------------------------------------------------------------------------- */
/*
 * irrigation.c  - see irrigation.h for the design and invariants.
 *
 * All time comparisons use the (now - since) >= dur form so they are safe
 * across the ~49.7-day millis() wrap.
 */
#include "irrigation.h"

/* -------------------------------------------------------------------------- */
/* eligibility + arbitration                                                  */
/* -------------------------------------------------------------------------- */

/* A channel requests water only when its committed level is a genuine soil-dry
 * DISPLAY level. The lower bound (>= MOIST_DRY) deliberately excludes the
 * air-dry diagnostics (idx 0..1): if a probe reads air-dry it is almost
 * certainly out of the soil, and we must never pump onto the floor. */
static bool wants_water(const irrigation_t *irr, uint8_t c)
{
    const irr_channel_t *ch = &irr->ch[c];
    if (ch->faulted)  return false;
    if (ch->soaking)  return false;
    /* Never act on an untrustworthy reading. A floating/intermittent probe
       (water in the connector, a loose lead) can report a perfectly plausible
       level - "dry" - with a huge sample spread. Acting on it would pump into a
       pot we cannot actually see. Veto the current bad read, and also veto once
       the fault has persisted past the latch threshold. */
    if (ch->m.health_warn) return false;
    if (irr->cfg->max_health_warn &&
        ch->warn_count >= irr->cfg->max_health_warn) return false;
    return (ch->level >= MOIST_DRY) &&
           (ch->level <= irr->cfg->water_at_or_below);
}

/* Round-robin scan so no channel starves when several are dry at once. */
static int choose_channel(irrigation_t *irr)
{
    uint8_t n = irr->cfg->num_channels;
    for (uint8_t i = 0; i < n; i++) {
        uint8_t c = (uint8_t)((irr->rr_cursor + i) % n);
        if (wants_water(irr, c)) {
            irr->rr_cursor = (uint8_t)((c + 1) % n);
            return (int)c;
        }
    }
    return -1;
}

/* -------------------------------------------------------------------------- */
/* sampling (only ever called from IRR_IDLE - no pump running)                */
/* -------------------------------------------------------------------------- */

static void sample_sweep(irrigation_t *irr, uint32_t now)
{
    const irrigation_cfg_t *cfg = irr->cfg;
    for (uint8_t c = 0; c < cfg->num_channels; c++) {
        irr_channel_t *ch = &irr->ch[c];

        uint16_t raw = irr->sample(c, irr->user);
        ch->level = moisture_update(&ch->m, cfg->mcfg[c], raw);

        /* expire the soak lockout */
        if (ch->soaking && (now - ch->soak_since_ms) >= cfg->soak_lockout_ms)
            ch->soaking = false;

        if (ch->m.health_warn) {
            /* untrustworthy sample: count it toward a latched fault, and never
               let a garbage reading clear an existing fault or dose counter. */
            if (ch->warn_count < 0xFF) ch->warn_count++;
        } else {
            ch->warn_count = 0;                  /* healthy again -> self-heal   */
            /* reached target (or wetter)? watering worked - clear counters/fault */
            if (ch->level >= cfg->target_level) {
                ch->dose_count = 0;
                ch->faulted    = false;
            }
        }
    }
    irr->last_sample_ms = now;
}

/* -------------------------------------------------------------------------- */
/* state machine                                                              */
/* -------------------------------------------------------------------------- */

void irrigation_tick(irrigation_t *irr, uint32_t now)
{
    const irrigation_cfg_t *cfg = irr->cfg;

    switch (irr->phase) {

    case IRR_SETTLE:
        /* pumps are off here; just wait out the quiet window */
        if ((now - irr->phase_since_ms) >= cfg->pump_settle_ms) {
            irr->phase = IRR_IDLE;
            irr->last_sample_ms = now - cfg->sample_period_ms; /* sample asap */
        }
        break;

    case IRR_IDLE:
        /* defensive: nothing should be pumping in IDLE */
        if (irr->active_pump != -1) {
            irr->pump((uint8_t)irr->active_pump, false, irr->user);
            irr->active_pump = -1;
        }
        if ((now - irr->last_sample_ms) >= cfg->sample_period_ms) {
            sample_sweep(irr, now);              /* SAFE: no pump running     */
            int pick = choose_channel(irr);
            if (pick >= 0) {
                irr->pump((uint8_t)pick, true, irr->user);
                irr->active_pump   = (int8_t)pick;
                irr->phase         = IRR_WATERING;
                irr->phase_since_ms = now;
            }
        }
        break;

    case IRR_WATERING:
        if ((now - irr->phase_since_ms) >= cfg->pump_dose_ms) {
            uint8_t c = (uint8_t)irr->active_pump;
            irr->pump(c, false, irr->user);

            irr->ch[c].soaking       = true;
            irr->ch[c].soak_since_ms = now;
            irr->ch[c].dose_count++;
            if (irr->ch[c].dose_count >= cfg->max_doses)
                irr->ch[c].faulted = true;       /* stop pestering this channel */

            irr->active_pump    = -1;
            irr->phase          = IRR_SETTLE;     /* quiet window before resume  */
            irr->phase_since_ms = now;
        }
        break;
    }
}

/* -------------------------------------------------------------------------- */
/* init + introspection                                                       */
/* -------------------------------------------------------------------------- */

void irrigation_init(irrigation_t *irr, const irrigation_cfg_t *cfg,
                     irr_sample_fn sample, irr_pump_fn pump, void *user,
                     uint32_t now)
{
    irr->cfg    = cfg;
    irr->sample = sample;
    irr->pump   = pump;
    irr->user   = user;
    irr->active_pump = -1;
    irr->rr_cursor   = 0;

    /* pumps OFF before anything else */
    for (uint8_t c = 0; c < cfg->num_channels; c++)
        pump(c, false, user);

    /* seed classifiers (pumps are off, so sampling is safe) */
    for (uint8_t c = 0; c < cfg->num_channels; c++) {
        irr_channel_t *ch = &irr->ch[c];
        uint16_t raw = sample(c, user);
        moisture_init(&ch->m, cfg->mcfg[c], raw);
        ch->level         = ch->m.committed;
        ch->soaking       = false;
        ch->soak_since_ms = 0;
        ch->dose_count    = 0;
        ch->warn_count    = 0;
        ch->faulted       = false;
    }

    irr->phase          = IRR_SETTLE;
    irr->phase_since_ms = now;
}

int irrigation_active_pump(const irrigation_t *irr)
{
    return (int)irr->active_pump;
}

moisture_level_t irrigation_level(const irrigation_t *irr, uint8_t ch)
{
    return irr->ch[ch].level;
}

bool irrigation_is_soaking(const irrigation_t *irr, uint8_t ch, uint32_t now)
{
    const irr_channel_t *c = &irr->ch[ch];
    if (!c->soaking) return false;
    return (now - c->soak_since_ms) < irr->cfg->soak_lockout_ms;
}

bool irrigation_is_faulted(const irrigation_t *irr, uint8_t ch)
{
    return irr->ch[ch].faulted;
}

bool irrigation_health_warn(const irrigation_t *irr, uint8_t ch)
{
    const irr_channel_t *c = &irr->ch[ch];
    if (c->m.health_warn) return true;
    return irr->cfg->max_health_warn &&
           c->warn_count >= irr->cfg->max_health_warn;
}
