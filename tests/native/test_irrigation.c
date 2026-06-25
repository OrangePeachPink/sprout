/*
 * test_irrigation.c - host-native unit tests for the irrigation supervisor FSM
 * plus the moisture-classifier band boundaries (issue #3).
 *
 * The engine is framework-agnostic C, so we compile it for the host alongside a
 * synthetic ADC+pump rig and drive it with a fake millisecond clock - no ESP32,
 * no flash. Asserts cover the A1 health veto/latch, the two hard invariants
 * (<=1 pump at a time; never sample while pumping), and the preserved
 * no-improvement and pump-overrun failsafes.
 *
 * Build + run:  tests/native/build_and_run.sh   (or: CC=<gcc> sh build_and_run.sh)
 * Exit code 0 = all pass, nonzero = failures.
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include "irrigation.h"

/* -------------------------------------------------------------------------- */
/* synthetic rig: ADC source + pump observer + event sink                     */
/* -------------------------------------------------------------------------- */

typedef struct {
    uint16_t target_raw;   /* trimmed-mean raw this channel reports          */
    bool     noisy;        /* inject a wide spread -> classifier health_warn */
    uint32_t reads;        /* free-running per-channel sample counter         */
} chan_sim_t;

typedef struct {
    chan_sim_t sim[IRRIG_CHANNELS];
    bool pump_on[IRRIG_CHANNELS];
    int  pump_on_count[IRRIG_CHANNELS];  /* OFF->ON transitions               */
    int  pumps_on_now;                   /* currently energized               */
    int  max_pumps_on;                   /* high-water mark (invariant 1)      */
    bool read_during_pump;               /* sampled while a pump ran? (inv 2)  */
    int  ev[16];                         /* event counts by irrig_event_code_t */
} rig_t;

static uint16_t sim_read(int ch, void *user)
{
    rig_t *r = (rig_t *)user;
    if (r->pumps_on_now > 0) r->read_during_pump = true;   /* invariant 2 */
    chan_sim_t *s = &r->sim[ch];
    uint32_t i = s->reads++;
    int delta;
    if (s->noisy) {
        /* near-zero-mean but very wide: the kept (trimmed) range stays well
         * above spread_warn_raw (250), so health_warn trips. */
        static const int wide[8] = { -450, 400, -380, 420, -410, 440, -360, 470 };
        delta = wide[i & 7];
    } else {
        static const int tight[5] = { -2, 1, 0, 2, -1 };
        delta = tight[i % 5];
    }
    int v = (int)s->target_raw + delta;
    if (v < 0) v = 0;
    if (v > 4095) v = 4095;
    return (uint16_t)v;
}

static void sim_pump(int ch, bool on, void *user)
{
    rig_t *r = (rig_t *)user;
    if (on && !r->pump_on[ch]) {
        r->pump_on[ch] = true; r->pumps_on_now++; r->pump_on_count[ch]++;
    } else if (!on && r->pump_on[ch]) {
        r->pump_on[ch] = false; r->pumps_on_now--;
    }
    if (r->pumps_on_now > r->max_pumps_on) r->max_pumps_on = r->pumps_on_now;
}

static void sim_event(const irrig_event_t *e, void *user)
{
    rig_t *r = (rig_t *)user;
    if (e->code >= 0 && e->code < 16) r->ev[e->code]++;
}

/* -------------------------------------------------------------------------- */
/* harness state + helpers                                                    */
/* -------------------------------------------------------------------------- */

static rig_t           RIG;
static moisture_cfg_t  MC[IRRIG_CHANNELS];
static irrig_chan_cfg_t CH[IRRIG_CHANNELS];
static moisture_state_t MS[IRRIG_CHANNELS];
static uint16_t        SCRATCH[128];
static irrig_sys_cfg_t SYS;
static irrig_ctrl_t    CTRL;
static uint32_t        NOW;

/* Configure (but do NOT init yet) - all channels default to well-watered &
 * healthy so they want no water; the test then tweaks specific RIG.sim[]. */
static void base_cfg(uint8_t max_health_warn, uint8_t max_doses,
                     uint32_t pump_max_ms, uint32_t dose_ms)
{
    memset(&RIG, 0, sizeof RIG);
    for (int i = 0; i < IRRIG_CHANNELS; i++) {
        MC[i] = (moisture_cfg_t)MOISTURE_CFG_DEFAULT;   /* spread_warn_raw=250 */
        CH[i] = (irrig_chan_cfg_t){ .dose_ms = dose_ms, .soak_ms = 3000,
                 .water_at_or_below = MOIST_NEEDS_WATER, .target_level = MOIST_OK };
        RIG.sim[i] = (chan_sim_t){ .target_raw = 1400, .noisy = false }; /* WELL_WATERED */
    }
    SYS = (irrig_sys_cfg_t){ .sample_period_ms = 1000, .adc_discard = 0,
            .post_pump_settle_ms = 500, .pump_max_ms = pump_max_ms,
            .max_doses = max_doses, .min_improvement_raw = 30,
            .max_health_warn = max_health_warn };
}

static void start(void)
{
    irrig_io_t io = { sim_read, sim_pump, sim_event, &RIG };
    NOW = 1000;
    irrig_init(&CTRL, &SYS, CH, MC, MS, SCRATCH, io, NOW);
}

static void step(uint32_t dt) { NOW += dt; irrig_tick(&CTRL, NOW); }

/* -------------------------------------------------------------------------- */
/* assert plumbing                                                            */
/* -------------------------------------------------------------------------- */

static int TESTS = 0, FAILS = 0;
#define CHECK(cond, msg) do {                                            \
    TESTS++;                                                             \
    if (!(cond)) { FAILS++; printf("    FAIL: %s  (line %d)\n", (msg), __LINE__); } \
} while (0)

/* -------------------------------------------------------------------------- */
/* tests                                                                      */
/* -------------------------------------------------------------------------- */

/* A1: a floating (high-spread) probe reading a plausible "dry" is vetoed every
 * sweep, and after max_health_warn sweeps hard-latches a fault that survives a
 * return to healthy and only clears manually. */
static void t_health_veto_and_latch(void)
{
    printf("  health veto + sustained hard latch (A1)\n");
    base_cfg(/*mhw*/3, /*mdoses*/3, /*pmax*/5000, /*dose*/2000);
    RIG.sim[0] = (chan_sim_t){ .target_raw = 2400, .noisy = true };  /* DRY + unhealthy */
    start();

    step(SYS.sample_period_ms);                                      /* sweep 1 */
    CHECK(irrig_status(&CTRL, 0) == CH_FAULT,      "unhealthy -> CH_FAULT");
    CHECK(RIG.pump_on_count[0] == 0,               "per-read veto: no pump");
    CHECK(irrig_warn_count(&CTRL, 0) == 1,         "warn_count == 1");
    CHECK(irrig_health_warn(&CTRL, 0) == true,     "health_warn accessor true");
    CHECK(RIG.ev[IRRIG_EV_SENSOR_FAULT] == 1,      "SENSOR_FAULT on rising edge");

    step(SYS.sample_period_ms);                                      /* sweep 2 */
    CHECK(RIG.ev[IRRIG_EV_HEALTH_FAULT] == 0,      "not latched at 2 < 3");

    step(SYS.sample_period_ms);                                      /* sweep 3 -> latch */
    CHECK(RIG.ev[IRRIG_EV_HEALTH_FAULT] == 1,      "HEALTH_FAULT latched at threshold");
    CHECK(irrig_warn_count(&CTRL, 0) >= 3,         "warn_count >= 3");

    RIG.sim[0].noisy = false;                                        /* probe goes healthy */
    step(SYS.sample_period_ms);
    step(SYS.sample_period_ms);
    CHECK(irrig_status(&CTRL, 0) == CH_FAULT,      "hard latch persists when healthy again");
    CHECK(RIG.pump_on_count[0] == 0,               "still no pump while latched");
    CHECK(irrig_health_warn(&CTRL, 0) == true,     "accessor still flags the latch");

    irrig_clear_fault(&CTRL, 0);
    CHECK(irrig_warn_count(&CTRL, 0) == 0,         "clear resets warn_count");
    CHECK(irrig_health_warn(&CTRL, 0) == false,    "accessor clears after manual clear");
}

/* Control: a healthy dry channel DOES get watered (proves the veto above is the
 * only thing stopping ch0), with both hard invariants intact. */
static void t_healthy_dry_waters(void)
{
    printf("  healthy dry channel waters + invariants\n");
    base_cfg(3, 3, 5000, 2000);
    RIG.sim[1] = (chan_sim_t){ .target_raw = 2400, .noisy = false }; /* DRY + healthy */
    start();

    step(SYS.sample_period_ms);                                      /* sweep -> grant */
    CHECK(RIG.pump_on_count[1] == 1,               "healthy dry ch waters");
    CHECK(irrig_active_pump(&CTRL) == 1,           "active pump is ch1");
    CHECK(RIG.max_pumps_on <= 1,                   "invariant 1: <=1 pump");
    CHECK(RIG.read_during_pump == false,           "invariant 2: no sample during pump");
}

/* Two dry channels: still only ever one pump, both get serviced (anti-starve),
 * and we never read while a pump runs across a full run of cycles. */
static void t_invariants_two_channels(void)
{
    printf("  two dry channels: single-pump + fairness + no-sample-while-pumping\n");
    base_cfg(3, 3, 5000, /*dose*/300);
    RIG.sim[1] = (chan_sim_t){ .target_raw = 2400, .noisy = false };
    RIG.sim[2] = (chan_sim_t){ .target_raw = 2400, .noisy = false };
    start();
    for (int i = 0; i < 400; i++) step(100);                         /* 40 s of ticks */
    CHECK(RIG.max_pumps_on <= 1,                   "invariant 1 holds across cycles");
    CHECK(RIG.read_during_pump == false,           "invariant 2 holds across cycles");
    CHECK(RIG.pump_on_count[1] >= 1,               "ch1 serviced");
    CHECK(RIG.pump_on_count[2] >= 1,               "ch2 serviced (no starvation)");
}

/* Preserved from design A: doses that never wet the soil latch a fault. */
static void t_no_improvement_fault(void)
{
    printf("  no-improvement fault preserved (design A)\n");
    base_cfg(/*mhw*/3, /*mdoses*/3, /*pmax*/100000, /*dose*/300);
    RIG.sim[1] = (chan_sim_t){ .target_raw = 2400, .noisy = false }; /* dry, never improves */
    start();
    for (int i = 0; i < 400; i++) step(200);                         /* 80 s of ticks */
    CHECK(RIG.ev[IRRIG_EV_NO_IMPROVEMENT_FAULT] >= 1, "no-improvement fault fired");
    CHECK(irrig_status(&CTRL, 1) == CH_FAULT,         "channel faulted");
}

/* Preserved from design A: a pump that runs past pump_max_ms latches. */
static void t_overrun_failsafe(void)
{
    printf("  pump-overrun failsafe preserved (design A)\n");
    base_cfg(/*mhw*/3, /*mdoses*/5, /*pmax*/200, /*dose*/100000); /* dose >> pump_max */
    RIG.sim[1] = (chan_sim_t){ .target_raw = 2400, .noisy = false };
    start();
    for (int i = 0; i < 40; i++) step(100);
    CHECK(RIG.ev[IRRIG_EV_PUMP_OVERRUN_FAULT] >= 1, "overrun failsafe fired");
    CHECK(irrig_status(&CTRL, 1) == CH_FAULT,       "channel faulted on overrun");
}

/* Grafted from design C: last_water_ms updates at dose-off (D1/E3 telemetry). */
static void t_last_water_ms(void)
{
    printf("  last_water_ms telemetry (graft from design C)\n");
    base_cfg(3, 5, 5000, /*dose*/300);
    RIG.sim[1] = (chan_sim_t){ .target_raw = 2400, .noisy = false };
    start();
    uint32_t at_init = irrig_last_water_ms(&CTRL, 1);
    for (int i = 0; i < 60; i++) step(200);
    CHECK(RIG.pump_on_count[1] >= 1,                    "at least one dose ran");
    CHECK(irrig_last_water_ms(&CTRL, 1) > at_init,      "last_water_ms advanced past init");
}

/* Issue #3: the reconciled boundaries map the 2026-06-21 calibration anchors
 * (docs/SENSOR_CALIBRATION.md) to the right bands - in particular a parched pot
 * now reads DRY (a watering display band), not air-dry ("out of soil"). */
static moisture_level_t band_of(uint16_t raw)
{
    moisture_cfg_t   cfg = (moisture_cfg_t)MOISTURE_CFG_DEFAULT;
    moisture_state_t st;
    moisture_init(&st, &cfg, raw);
    return st.committed;
}

static void t_band_anchors(void)
{
    printf("  reconciled band boundaries vs calibration anchors (issue #3)\n");
    /* probe in air -> air-dry diagnostic (never waters) */
    CHECK(band_of(3180) == MOIST_AIR_DRY,           "air ~3180 -> air-dry (out of soil)");
    /* THE FIX: bone-dry / parched soil now reads DRY, not air-dry. 2760 was the
     * old air-dry edge; ~2900 is a loose, air-gappy dry-soil hole. */
    CHECK(band_of(2900) == MOIST_DRY,               "parched soil ~2900 -> DRY (waters)");
    CHECK(band_of(2760) == MOIST_DRY,               "old air-dry edge 2760 -> DRY now");
    CHECK(band_of(2440) == MOIST_DRY,               "bone-dry soil ~2440 -> DRY");
    CHECK(moisture_level_is_display(band_of(2900)), "parched soil is a watering display band");
    /* field capacity -> well-watered (healthy; no too-wet alarm) */
    CHECK(band_of(1300) == MOIST_WELL_WATERED,      "field capacity ~1300 -> well-watered");
    /* saturated soil / standing water -> the 'too wet / check probe' diagnostics */
    CHECK(band_of(1060) == MOIST_OVERWATERED,       "saturated soil ~1060 -> overwatered");
    CHECK(band_of(1010) == MOIST_SUBMERGED,         "standing water ~1010 -> submerged");
}

int main(void)
{
    printf("native irrigation FSM tests\n");
    t_health_veto_and_latch();
    t_healthy_dry_waters();
    t_invariants_two_channels();
    t_no_improvement_fault();
    t_overrun_failsafe();
    t_last_water_ms();
    t_band_anchors();
    printf("\n%d checks, %d failed\n", TESTS, FAILS);
    return FAILS ? 1 : 0;
}
