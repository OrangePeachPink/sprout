/*
 * test_irrigation.c - host-native unit tests for the irrigation supervisor FSM,
 * the moisture-classifier band boundaries (#3), the set_cadence command
 * parser (#63), and the run-metadata !label / !pos handlers (#321).
 *
 * The engine is framework-agnostic C, so we compile it for the host alongside a
 * synthetic ADC+pump rig and drive it with a fake millisecond clock - no ESP32,
 * no flash. Asserts cover the A1 health veto/latch, the two hard invariants
 * (<=1 pump at a time; never sample while pumping), and the preserved
 * no-improvement and pump-overrun failsafes.
 *
 * Run:  pio test -e native -d firmware    (via: just test-native)
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <unity.h>
#include "irrigation.h"
#include "serial_cmd.h"
#include "pump_pulse.h"
#include "run_meta.h"
#include "env_i2c.h"
#include "sht45.h"
#include "as7263.h"
#include "telemetry.h"
#include "board_capability.h" /* #273 capability descriptor + gate seam */
#include "calibration.h" /* SENSOR_CAL_BOUNDARY — per-channel raw->band (#170) */
#include "wifi_net.h" /* #21 connect-scaffold state machine */
#include "device_uid.h" /* #601 stable-id base32 mint (ADR-0027 §1b) */

/* -------------------------------------------------------------------------- */
/* synthetic rig: ADC source + pump observer + event sink                     */
/* -------------------------------------------------------------------------- */

typedef struct {
    uint16_t target_raw; /* trimmed-mean raw this channel reports          */
    bool noisy; /* inject a wide spread -> classifier health_warn */
    uint32_t reads; /* free-running per-channel sample counter         */
} chan_sim_t;

typedef struct {
    chan_sim_t sim[IRRIG_CHANNELS];
    bool pump_on[IRRIG_CHANNELS];
    int pump_on_count[IRRIG_CHANNELS]; /* OFF->ON transitions               */
    int pumps_on_now; /* currently energized               */
    int max_pumps_on; /* high-water mark (invariant 1)      */
    bool read_during_pump; /* sampled while a pump ran? (inv 2)  */
    int ev[16]; /* event counts by irrig_event_code_t */
} rig_t;

static uint16_t sim_read(int ch, void *user)
{
    rig_t *r = (rig_t *)user;
    if (r->pumps_on_now > 0) r->read_during_pump = true; /* invariant 2 */
    chan_sim_t *s = &r->sim[ch];
    uint32_t i = s->reads++;
    int delta;
    if (s->noisy) {
        /* near-zero-mean but very wide: the kept (trimmed) range stays well
         * above spread_warn_raw (250), so health_warn trips. */
        static const int wide[8] = {-450, 400, -380, 420, -410, 440, -360, 470};
        delta = wide[i & 7];
    } else {
        static const int tight[5] = {-2, 1, 0, 2, -1};
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
        r->pump_on[ch] = true;
        r->pumps_on_now++;
        r->pump_on_count[ch]++;
    } else if (!on && r->pump_on[ch]) {
        r->pump_on[ch] = false;
        r->pumps_on_now--;
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

static rig_t RIG;
static moisture_cfg_t MC[IRRIG_CHANNELS];
static irrig_chan_cfg_t CH[IRRIG_CHANNELS];
static moisture_state_t MS[IRRIG_CHANNELS];
static uint16_t SCRATCH[128];
static irrig_sys_cfg_t SYS;
static irrig_ctrl_t CTRL;
static uint32_t NOW;

/* Configure (but do NOT init yet) - all channels default to well-watered &
 * healthy so they want no water; the test then tweaks specific RIG.sim[]. */
static void base_cfg(uint8_t max_health_warn, uint8_t max_doses,
                     uint32_t pump_max_ms, uint32_t dose_ms)
{
    memset(&RIG, 0, sizeof RIG);
    for (int i = 0; i < IRRIG_CHANNELS; i++) {
        MC[i] = (moisture_cfg_t)MOISTURE_CFG_DEFAULT; /* spread_warn_raw=250 */
        CH[i] = (irrig_chan_cfg_t){.dose_ms = dose_ms,
                                   .soak_ms = 3000,
                                   .water_at_or_below = MOIST_NEEDS_WATER,
                                   .target_level = MOIST_OK};
        RIG.sim[i] =
            (chan_sim_t){.target_raw = 1400, .noisy = false}; /* WELL_WATERED */
    }
    SYS = (irrig_sys_cfg_t){.sample_period_ms = 1000,
                            .adc_discard = 0,
                            .post_pump_settle_ms = 500,
                            .pump_max_ms = pump_max_ms,
                            .max_doses = max_doses,
                            .min_improvement_raw = 30,
                            .max_health_warn = max_health_warn};
}

static void start(void)
{
    irrig_io_t io = {sim_read, sim_pump, sim_event, &RIG};
    NOW = 1000;
    irrig_init(&CTRL, &SYS, CH, MC, MS, SCRATCH, io, NOW);
    /* The autonomous tests exercise self-dosing, so arm the engine here (init
     * now defaults to disarmed, #227). t_autonomous_gate inits directly to assert
     * that fail-safe default and the disarmed/forced behavior. */
    irrig_set_autonomous(&CTRL, true);
}

static void step(uint32_t dt)
{
    NOW += dt;
    irrig_tick(&CTRL, NOW);
}

/* -------------------------------------------------------------------------- */
/* Unity lifecycle hooks (required; both are no-ops here)                     */
/* -------------------------------------------------------------------------- */

void setUp(void)
{
}
void tearDown(void)
{
}

/* -------------------------------------------------------------------------- */
/* tests                                                                      */
/* -------------------------------------------------------------------------- */

/* A1: a floating (high-spread) probe reading a plausible "dry" is vetoed every
 * sweep, and after max_health_warn sweeps hard-latches a fault that survives a
 * return to healthy and only clears manually. */
void t_health_veto_and_latch(void)
{
    base_cfg(/*mhw*/ 3, /*mdoses*/ 3, /*pmax*/ 5000, /*dose*/ 2000);
    RIG.sim[0] =
        (chan_sim_t){.target_raw = 2400, .noisy = true}; /* DRY + unhealthy */
    start();

    step(SYS.sample_period_ms); /* sweep 1 */
    TEST_ASSERT_TRUE_MESSAGE(irrig_status(&CTRL, 0) == CH_FAULT,
                             "unhealthy -> CH_FAULT");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[0] == 0,
                             "per-read veto: no pump");
    TEST_ASSERT_TRUE_MESSAGE(irrig_warn_count(&CTRL, 0) == 1,
                             "warn_count == 1");
    TEST_ASSERT_TRUE_MESSAGE(irrig_health_warn(&CTRL, 0) == true,
                             "health_warn accessor true");
    TEST_ASSERT_TRUE_MESSAGE(RIG.ev[IRRIG_EV_SENSOR_FAULT] == 1,
                             "SENSOR_FAULT on rising edge");

    step(SYS.sample_period_ms); /* sweep 2 */
    TEST_ASSERT_TRUE_MESSAGE(RIG.ev[IRRIG_EV_HEALTH_FAULT] == 0,
                             "not latched at 2 < 3");

    step(SYS.sample_period_ms); /* sweep 3 -> latch */
    TEST_ASSERT_TRUE_MESSAGE(RIG.ev[IRRIG_EV_HEALTH_FAULT] == 1,
                             "HEALTH_FAULT latched at threshold");
    TEST_ASSERT_TRUE_MESSAGE(irrig_warn_count(&CTRL, 0) >= 3,
                             "warn_count >= 3");

    RIG.sim[0].noisy = false; /* probe goes healthy */
    step(SYS.sample_period_ms);
    step(SYS.sample_period_ms);
    TEST_ASSERT_TRUE_MESSAGE(irrig_status(&CTRL, 0) == CH_FAULT,
                             "hard latch persists when healthy again");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[0] == 0,
                             "still no pump while latched");
    TEST_ASSERT_TRUE_MESSAGE(irrig_health_warn(&CTRL, 0) == true,
                             "accessor still flags the latch");

    irrig_clear_fault(&CTRL, 0);
    TEST_ASSERT_TRUE_MESSAGE(irrig_warn_count(&CTRL, 0) == 0,
                             "clear resets warn_count");
    TEST_ASSERT_TRUE_MESSAGE(irrig_health_warn(&CTRL, 0) == false,
                             "accessor clears after manual clear");
}

/* Control: a healthy dry channel DOES get watered (proves the veto above is the
 * only thing stopping ch0), with both hard invariants intact. */
void t_healthy_dry_waters(void)
{
    base_cfg(3, 3, 5000, 2000);
    RIG.sim[1] =
        (chan_sim_t){.target_raw = 2400, .noisy = false}; /* DRY + healthy */
    start();

    step(SYS.sample_period_ms); /* sweep -> grant */
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[1] == 1,
                             "healthy dry ch waters");
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 1,
                             "active pump is ch1");
    TEST_ASSERT_TRUE_MESSAGE(RIG.max_pumps_on <= 1, "invariant 1: <=1 pump");
    TEST_ASSERT_TRUE_MESSAGE(RIG.read_during_pump == false,
                             "invariant 2: no sample during pump");
}

/* Two dry channels: still only ever one pump, both get serviced (anti-starve),
 * and we never read while a pump runs across a full run of cycles. */
void t_invariants_two_channels(void)
{
    base_cfg(3, 3, 5000, /*dose*/ 300);
    RIG.sim[1] = (chan_sim_t){.target_raw = 2400, .noisy = false};
    RIG.sim[2] = (chan_sim_t){.target_raw = 2400, .noisy = false};
    start();
    for (int i = 0; i < 400; i++)
        step(100); /* 40 s of ticks */
    TEST_ASSERT_TRUE_MESSAGE(RIG.max_pumps_on <= 1,
                             "invariant 1 holds across cycles");
    TEST_ASSERT_TRUE_MESSAGE(RIG.read_during_pump == false,
                             "invariant 2 holds across cycles");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[1] >= 1, "ch1 serviced");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[2] >= 1,
                             "ch2 serviced (no starvation)");
}

/* Preserved from design A: doses that never wet the soil latch a fault. */
void t_no_improvement_fault(void)
{
    base_cfg(/*mhw*/ 3, /*mdoses*/ 3, /*pmax*/ 100000, /*dose*/ 300);
    RIG.sim[1] = (chan_sim_t){.target_raw = 2400,
                              .noisy = false}; /* dry, never improves */
    start();
    for (int i = 0; i < 400; i++)
        step(200); /* 80 s of ticks */
    TEST_ASSERT_TRUE_MESSAGE(RIG.ev[IRRIG_EV_NO_IMPROVEMENT_FAULT] >= 1,
                             "no-improvement fault fired");
    TEST_ASSERT_TRUE_MESSAGE(irrig_status(&CTRL, 1) == CH_FAULT,
                             "channel faulted");
}

/* Preserved from design A: a pump that runs past pump_max_ms latches. */
void t_overrun_failsafe(void)
{
    base_cfg(/*mhw*/ 3, /*mdoses*/ 5, /*pmax*/ 200,
             /*dose*/ 100000); /* dose >> pump_max */
    RIG.sim[1] = (chan_sim_t){.target_raw = 2400, .noisy = false};
    start();
    for (int i = 0; i < 40; i++)
        step(100);
    TEST_ASSERT_TRUE_MESSAGE(RIG.ev[IRRIG_EV_PUMP_OVERRUN_FAULT] >= 1,
                             "overrun failsafe fired");
    TEST_ASSERT_TRUE_MESSAGE(irrig_status(&CTRL, 1) == CH_FAULT,
                             "channel faulted on overrun");
}

/* Grafted from design C: last_water_ms updates at dose-off (D1/E3 telemetry).
 */
void t_last_water_ms(void)
{
    base_cfg(3, 5, 5000, /*dose*/ 300);
    RIG.sim[1] = (chan_sim_t){.target_raw = 2400, .noisy = false};
    start();
    uint32_t at_init = irrig_last_water_ms(&CTRL, 1);
    for (int i = 0; i < 60; i++)
        step(200);
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[1] >= 1,
                             "at least one dose ran");
    TEST_ASSERT_TRUE_MESSAGE(irrig_last_water_ms(&CTRL, 1) > at_init,
                             "last_water_ms advanced past init");
}

/* Issue #3: the reconciled boundaries map the 2026-06-21 calibration anchors
 * (docs/SENSOR_CALIBRATION.md) to the right bands - in particular a parched pot
 * now reads DRY (a watering display band), not air-dry ("out of soil"). */
static moisture_level_t band_of(uint16_t raw)
{
    moisture_cfg_t cfg = (moisture_cfg_t)MOISTURE_CFG_DEFAULT;
    moisture_state_t st;
    moisture_init(&st, &cfg, raw);
    return st.committed;
}

void t_band_anchors(void)
{
    /* probe in air -> air-dry diagnostic (never waters) */
    TEST_ASSERT_TRUE_MESSAGE(band_of(3180) == MOIST_AIR_DRY,
                             "air ~3180 -> air-dry (out of soil)");
    /* THE FIX: bone-dry / parched soil now reads DRY, not air-dry. 2760 was the
     * old air-dry edge; ~2900 is a loose, air-gappy dry-soil hole. */
    TEST_ASSERT_TRUE_MESSAGE(band_of(2900) == MOIST_DRY,
                             "parched soil ~2900 -> DRY (waters)");
    TEST_ASSERT_TRUE_MESSAGE(band_of(2760) == MOIST_DRY,
                             "old air-dry edge 2760 -> DRY now");
    TEST_ASSERT_TRUE_MESSAGE(band_of(2440) == MOIST_DRY,
                             "bone-dry soil ~2440 -> DRY");
    TEST_ASSERT_TRUE_MESSAGE(moisture_level_is_display(band_of(2900)),
                             "parched soil is a watering display band");
    /* field capacity -> well-watered (healthy; no too-wet alarm) */
    TEST_ASSERT_TRUE_MESSAGE(band_of(1300) == MOIST_WELL_WATERED,
                             "field capacity ~1300 -> well-watered");
    /* saturated soil / standing water -> the 'too wet / check probe'
     * diagnostics */
    TEST_ASSERT_TRUE_MESSAGE(band_of(1060) == MOIST_OVERWATERED,
                             "saturated soil ~1060 -> overwatered");
    TEST_ASSERT_TRUE_MESSAGE(band_of(1010) == MOIST_SUBMERGED,
                             "standing water ~1010 -> submerged");

    /* #248 ratified ENDPOINTS (common-cup, 4-probe measured): the endpoint
     * bands must bracket the real anchors. Air-dry center 3170 (per-probe
     * 3151..3191) and saturated center 978 (per-probe 926..1020, s2 the
     * wet-biased min) - the boundaries are unchanged; these assertions are what
     * take "proposed" off the endpoints + guard them. */
    TEST_ASSERT_TRUE_MESSAGE(band_of(3170) == MOIST_AIR_DRY,
                             "#248 air-dry center 3170 -> air-dry");
    TEST_ASSERT_TRUE_MESSAGE(band_of(3151) == MOIST_AIR_DRY,
                             "#248 air-dry min (s2 3151) -> air-dry");
    TEST_ASSERT_TRUE_MESSAGE(band_of(978) == MOIST_SUBMERGED,
                             "#248 saturated center 978 -> submerged");
    TEST_ASSERT_TRUE_MESSAGE(
        band_of(926) == MOIST_SUBMERGED,
        "#248 saturated min (s2 wet-bias 926) -> submerged");
    TEST_ASSERT_TRUE_MESSAGE(band_of(1020) == MOIST_SUBMERGED,
                             "#248 saturated max (s3 1020) -> submerged");
}

/* #92: the host->device command registry + dispatcher - register/dispatch, the
 * *HH checksum, the name+args split, unknown/ignored paths, the shared
 * parse_u32, and re-sync past leading UART noise. (#63 set_cadence is now a
 * registered handler.) */
static void make_cmd(char *out, size_t n, const char *body)
{
    uint8_t x = 0;
    for (const char *p = body; *p; p++)
        x ^= (uint8_t)*p;
    snprintf(out, n, "!%s*%02X", body, x);
}

/* a numeric test handler standing in for !cad: records the args + parses a
 * uint32 */
static char g_th_args[32];
static uint32_t g_th_num;
static int g_th_num_ok;
static void th_num(const char *args, char *reply, size_t replen)
{
    snprintf(g_th_args, sizeof(g_th_args), "%s", args);
    g_th_num_ok = serial_cmd_parse_u32(args, &g_th_num);
    snprintf(reply, replen, "# ack num=%s", args);
}
static void th_ping(const char *args, char *reply, size_t replen)
{
    (void)args;
    snprintf(reply, replen, "# ack pong");
}

void t_serial_cmd_registry(void)
{
    char buf[40], reply[96];

    serial_cmd_reset();
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_register("cad", th_num) == 0,
                             "register cad");
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_register("ping", th_ping) == 0,
                             "register ping");
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_register("cad", th_num) == -1,
                             "duplicate name refused");

    TEST_ASSERT_TRUE_MESSAGE(
        serial_cmd_dispatch("plants.soil,s3,...", reply, sizeof(reply)) ==
                SERIAL_CMD_IGNORED &&
            reply[0] == '\0',
        "telemetry row (no '!') -> ignored, no reply");

    make_cmd(buf, sizeof(buf), "cad,1000");
    TEST_ASSERT_TRUE_MESSAGE(
        serial_cmd_dispatch(buf, reply, sizeof(reply)) == SERIAL_CMD_OK &&
            strcmp(g_th_args, "1000") == 0 && g_th_num_ok && g_th_num == 1000,
        "valid !cad,1000 -> OK, handler got args '1000'");

    make_cmd(buf, sizeof(buf), "ping");
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_dispatch(buf, reply, sizeof(reply)) ==
                                     SERIAL_CMD_OK &&
                                 strcmp(reply, "# ack pong") == 0,
                             "no-arg !ping -> # ack pong");

    TEST_ASSERT_TRUE_MESSAGE(
        serial_cmd_dispatch("!cad,1000*00", reply, sizeof(reply)) ==
                SERIAL_CMD_ERR_CHECKSUM &&
            strstr(reply, "checksum") != NULL,
        "wrong checksum -> nak checksum (handler never runs)");

    make_cmd(buf, sizeof(buf), "nope,1");
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_dispatch(buf, reply, sizeof(reply)) ==
                                     SERIAL_CMD_ERR_UNKNOWN &&
                                 strstr(reply, "unknown") != NULL,
                             "valid-checksum unknown command -> nak unknown");

    make_cmd(buf, sizeof(buf), "cad,1000");
    char noisy[48];
    snprintf(noisy, sizeof(noisy), "\xff\xfe%s", buf);
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_dispatch(noisy, reply, sizeof(reply)) ==
                                 SERIAL_CMD_OK,
                             "leading UART noise re-syncs to '!'");

    uint32_t v = 0;
    TEST_ASSERT_TRUE_MESSAGE(serial_cmd_parse_u32("250", &v) && v == 250,
                             "parse_u32 250 -> ok");
    TEST_ASSERT_TRUE_MESSAGE(!serial_cmd_parse_u32("12x4", &v),
                             "parse_u32 non-digit -> fail");
    TEST_ASSERT_TRUE_MESSAGE(!serial_cmd_parse_u32("", &v),
                             "parse_u32 empty -> fail");
    TEST_ASSERT_TRUE_MESSAGE(!serial_cmd_parse_u32("1234567890", &v),
                             "parse_u32 >9 digits -> fail");
}

void t_pump_pulse(void)
{
    pump_pulse_t p;
    pump_pulse_init(&p, 4, 1500,
                    5000); /* channels/default/max mirror config.h */
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_active(&p) &&
                                 pump_pulse_channel(&p) == -1,
                             "init -> idle, no channel");

    /* arm with the default duration */
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_arm(&p, 1, 0, 10000) ==
                                 PUMP_PULSE_ARMED,
                             "arm ch1 default -> ARMED");
    TEST_ASSERT_TRUE_MESSAGE(
        pump_pulse_active(&p) && pump_pulse_channel(&p) == 1, "active on ch1");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_armed_ms(&p) == 1500,
                             "omitted duration -> default 1500");

    /* second arm while busy is rejected; the first pulse is untouched */
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_arm(&p, 2, 500, 10100) ==
                                 PUMP_PULSE_ERR_BUSY,
                             "arm while busy -> ERR_BUSY");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_channel(&p) == 1,
                             "busy reject leaves ch1 pulse intact");

    /* service before/at/after expiry (10000 + 1500 = 11500) */
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_service(&p, 11000) &&
                                 pump_pulse_active(&p),
                             "service before expiry -> still on");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_service(&p, 11500),
                             "service at expiry -> OFF signal (fires once)");
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_active(&p) &&
                                 pump_pulse_channel(&p) == -1,
                             "expired -> idle");
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_service(&p, 11600),
                             "service after expiry -> no repeat signal");

    /* an over-ceiling request is clamped to max */
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_arm(&p, 0, 99999, 20000) ==
                                 PUMP_PULSE_ARMED,
                             "arm over-ceiling -> ARMED");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_armed_ms(&p) == 5000,
                             "request clamped to the hard max (5000)");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_stop(&p),
                             "stop while active -> was-active true");
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_active(&p), "stop -> idle");
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_stop(&p), "stop when idle -> false");

    /* out-of-range channels are rejected and leave it idle */
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_arm(&p, 4, 0, 30000) ==
                                 PUMP_PULSE_ERR_CHANNEL,
                             "arm ch4 (n=4) -> ERR_CHANNEL");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_arm(&p, -1, 0, 30000) ==
                                 PUMP_PULSE_ERR_CHANNEL,
                             "arm ch-1 -> ERR_CHANNEL");
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_active(&p),
                             "bad-channel arm leaves it idle");

    /* uint32 millis() rollover: off_at wraps past 0, expiry still detected */
    pump_pulse_init(&p, 4, 1500, 5000);
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_arm(&p, 3, 1000, 0xFFFFFE00u) ==
                                 PUMP_PULSE_ARMED,
                             "arm near uint32 max -> ARMED");
    TEST_ASSERT_TRUE_MESSAGE(!pump_pulse_service(&p, 0xFFFFFF00u) &&
                                 pump_pulse_active(&p),
                             "pre-expiry across wrap -> still on");
    TEST_ASSERT_TRUE_MESSAGE(pump_pulse_service(&p, 0x00000300u),
                             "post-wrap expiry -> OFF (rollover-safe)");
}

void t_forced_dose(void)
{
    /* (a) a forced dose overrides "nothing wants water" - all channels
     * well-watered. */
    base_cfg(/*mhw*/ 3, /*mdoses*/ 3, /*pmax*/ 5000, /*dose*/ 2000);
    start();
    step(SYS.sample_period_ms); /* sweep: nobody wants water */
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == -1,
                             "well-watered -> no autonomous dose");
    TEST_ASSERT_TRUE_MESSAGE(irrig_request_dose(&CTRL, 2, 0) ==
                                 IRRIG_DOSE_QUEUED,
                             "request ch2 -> queued");
    step(SYS.sample_period_ms); /* next sweep grants the forced dose */
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 2 &&
                                 irrig_mode(&CTRL) == SYS_WATERING,
                             "forced dose granted on ch2 despite well-watered");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[2] == 1, "ch2 pump ran once");
    step(2000); /* ms=0 -> chan dose_ms = 2000 */
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on[2] == false && RIG.pumps_on_now == 0,
                             "forced dose ends at dose_ms");

    /* (b) forced_ms clamps to pump_max_ms WITHOUT tripping the overrun fault.
     */
    base_cfg(3, 3, /*pmax*/ 5000, /*dose*/ 2000);
    start();
    step(SYS.sample_period_ms);
    TEST_ASSERT_TRUE_MESSAGE(irrig_request_dose(&CTRL, 0, 99999) ==
                                 IRRIG_DOSE_QUEUED,
                             "request ch0 ms=99999");
    step(SYS.sample_period_ms); /* grant */
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 0,
                             "ch0 forced dose granted");
    step(5000); /* run to the ceiling */
    TEST_ASSERT_TRUE_MESSAGE(RIG.pumps_on_now == 0,
                             "clamped dose ended at pump_max_ms");
    TEST_ASSERT_TRUE_MESSAGE(irrig_status(&CTRL, 0) != CH_FAULT,
                             "clamped dose did NOT trip an overrun fault");

    /* (c) a hard-faulted channel refuses a forced dose (clear it first). */
    base_cfg(3, 3, 5000, 2000);
    start();
    CTRL.faulted[1] = true;
    TEST_ASSERT_TRUE_MESSAGE(irrig_request_dose(&CTRL, 1, 0) ==
                                 IRRIG_DOSE_FAULTED,
                             "faulted channel -> refused");
    TEST_ASSERT_TRUE_MESSAGE(CTRL.forced[1] == false,
                             "refused request leaves no pending dose");

    /* (d) out-of-range channel rejected. */
    TEST_ASSERT_TRUE_MESSAGE(irrig_request_dose(&CTRL, IRRIG_CHANNELS, 0) ==
                                 IRRIG_DOSE_BAD_CHANNEL,
                             "ch=N -> bad channel");
    TEST_ASSERT_TRUE_MESSAGE(irrig_request_dose(&CTRL, -1, 0) ==
                                 IRRIG_DOSE_BAD_CHANNEL,
                             "ch=-1 -> bad channel");

    /* (e) one-pump invariant holds: a 2nd forced request mid-dose never opens a
       2nd pump; it's granted only after the first dose + settle release the
       token. */
    base_cfg(3, 3, 5000, /*dose*/ 2000);
    start();
    step(SYS.sample_period_ms);
    irrig_request_dose(&CTRL, 0, 0);
    step(SYS.sample_period_ms); /* ch0 dosing */
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 0, "ch0 dosing");
    irrig_request_dose(&CTRL, 1, 0); /* queue ch1 mid-dose */
    step(500); /* still within ch0's dose */
    TEST_ASSERT_TRUE_MESSAGE(RIG.pumps_on_now == 1 && RIG.max_pumps_on == 1,
                             "2nd forced request never opens a 2nd pump");
    step(2000);
    step(500);
    step(SYS.sample_period_ms); /* ch0 dose + settle + re-sample */
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[1] == 1 && RIG.max_pumps_on == 1,
                             "ch1 dosed only after ch0 released the token");

    /* (f) a forced dose takes priority over an autonomous-wanting (drier)
     * channel. */
    base_cfg(3, 3, 5000, 2000);
    RIG.sim[0] = (chan_sim_t){.target_raw = 2400,
                              .noisy = false}; /* ch0 genuinely DRY */
    start();
    irrig_request_dose(&CTRL, 3, 0); /* force ch3 (well-watered) */
    step(SYS.sample_period_ms);
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 3,
                             "forced ch3 beats autonomous-dry ch0");
}

/* -------------------------------------------------------------------------- */
/* autonomous arm gate (#227 / ADR-0016)                                      */
/* -------------------------------------------------------------------------- */

/* Disarmed (the init default): a healthy DRY channel is monitored but never
 * auto-watered, while an operator forced dose still grants. Armed: it waters. */
void t_autonomous_gate(void)
{
    irrig_io_t io = {sim_read, sim_pump, sim_event, &RIG};

    /* init directly (not start(), which arms) to assert the fail-safe default */
    base_cfg(/*mhw*/ 3, /*mdoses*/ 3, /*pmax*/ 5000, /*dose*/ 2000);
    RIG.sim[1] =
        (chan_sim_t){.target_raw = 2400, .noisy = false}; /* DRY healthy */
    NOW = 1000;
    irrig_init(&CTRL, &SYS, CH, MC, MS, SCRATCH, io, NOW);
    TEST_ASSERT_FALSE_MESSAGE(irrig_autonomous(&CTRL),
                              "autonomous disarmed by default (fail-safe)");

    step(SYS.sample_period_ms);
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == -1,
                             "disarmed: dry channel NOT auto-watered");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[1] == 0,
                             "disarmed: no autonomous dose");
    TEST_ASSERT_TRUE_MESSAGE(irrig_status(&CTRL, 1) == CH_OK,
                             "disarmed: dry channel still monitored (CH_OK)");

    /* operator forced dose still grants while disarmed (manual !water path) */
    TEST_ASSERT_TRUE_MESSAGE(irrig_request_dose(&CTRL, 1, 0) ==
                                 IRRIG_DOSE_QUEUED,
                             "forced dose queued while disarmed");
    step(SYS.sample_period_ms);
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 1,
                             "forced dose grants despite disarmed");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[1] == 1, "forced dose ran once");

    /* armed: the same dry condition now auto-waters */
    base_cfg(3, 3, 5000, 2000);
    RIG.sim[2] =
        (chan_sim_t){.target_raw = 2400, .noisy = false}; /* DRY healthy */
    NOW = 1000;
    irrig_init(&CTRL, &SYS, CH, MC, MS, SCRATCH, io, NOW);
    irrig_set_autonomous(&CTRL, true);
    TEST_ASSERT_TRUE_MESSAGE(irrig_autonomous(&CTRL), "armed");
    step(SYS.sample_period_ms);
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 2,
                             "armed: dry channel auto-waters");
    TEST_ASSERT_TRUE_MESSAGE(RIG.max_pumps_on <= 1, "invariant 1 still holds");
    TEST_ASSERT_TRUE_MESSAGE(RIG.read_during_pump == false,
                             "invariant 2 still holds");
}

/* Operator e-stop: irrig_abort forces an active dose OFF, cancels pending forced
 * doses, and is a no-op (returns false) when idle. */
void t_irrig_abort(void)
{
    base_cfg(/*mhw*/ 3, /*mdoses*/ 3, /*pmax*/ 5000, /*dose*/ 3000);
    RIG.sim[1] =
        (chan_sim_t){.target_raw = 2400, .noisy = false}; /* DRY healthy */
    start(); /* armed */

    step(SYS.sample_period_ms); /* grant ch1 dose */
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == 1, "ch1 dosing");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pumps_on_now == 1, "pump energized");

    bool was = irrig_abort(&CTRL, NOW);
    TEST_ASSERT_TRUE_MESSAGE(was, "abort while watering -> was-active true");
    TEST_ASSERT_TRUE_MESSAGE(RIG.pumps_on_now == 0, "abort forces pump OFF");
    TEST_ASSERT_TRUE_MESSAGE(irrig_active_pump(&CTRL) == -1, "no active pump");

    /* a pending forced dose is cancelled by the abort */
    irrig_request_dose(&CTRL, 2, 0);
    irrig_abort(&CTRL, NOW);
    step(SYS.sample_period_ms);
    step(SYS.sample_period_ms); /* clear the settle, run a sweep */
    TEST_ASSERT_TRUE_MESSAGE(RIG.pump_on_count[2] == 0,
                             "aborted forced dose never fired");

    /* abort while idle is a harmless no-op */
    TEST_ASSERT_FALSE_MESSAGE(irrig_abort(&CTRL, NOW),
                              "abort while idle -> false");
}

/* -------------------------------------------------------------------------- */
/* run metadata: !label / !pos runtime handlers (#321)                        */
/* -------------------------------------------------------------------------- */

void t_run_meta(void)
{
    run_meta_t m;
    char rep[96];

    /* init seeds the label and EVERY channel's position from the defaults */
    run_meta_init(&m, "4probe-coloc-origplant", "origplant", 4);
    TEST_ASSERT_EQUAL_STRING_MESSAGE("4probe-coloc-origplant",
                                     run_meta_label(&m), "init label");
    for (int ch = 0; ch < 4; ch++)
        TEST_ASSERT_EQUAL_STRING_MESSAGE("origplant", run_meta_position(&m, ch),
                                         "init seeds all channels");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("", run_meta_position(&m, 4),
                                     "position ch out of range -> \"\"");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("", run_meta_position(&m, -1),
                                     "position ch negative -> \"\"");

    /* !label updates the label (ack) */
    TEST_ASSERT_TRUE_MESSAGE(
        run_meta_set_label(&m, "4probe-drypass1", rep, sizeof(rep)),
        "set_label valid -> ok");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("4probe-drypass1", run_meta_label(&m),
                                     "label updated");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(rep, "# ack label"),
                                 "set_label ack reply");

    /* empty label is rejected and leaves the prior label intact */
    TEST_ASSERT_TRUE_MESSAGE(!run_meta_set_label(&m, "", rep, sizeof(rep)),
                             "empty label -> nak");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("4probe-drypass1", run_meta_label(&m),
                                     "nak leaves label unchanged");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(rep, "nak"), "empty label nak reply");

    /* label sanitizes CSV-hostile bytes (comma + control -> '_') */
    run_meta_set_label(&m, "a,b\tc", rep, sizeof(rep));
    TEST_ASSERT_EQUAL_STRING_MESSAGE("a_b_c", run_meta_label(&m),
                                     "label comma/control sanitized");

    /* !pos updates ONE channel; the others are untouched */
    TEST_ASSERT_TRUE_MESSAGE(
        run_meta_set_position(&m, "0,s3-origplant", rep, sizeof(rep)),
        "set_position ch0 -> ok");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("s3-origplant", run_meta_position(&m, 0),
                                     "ch0 position updated");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("origplant", run_meta_position(&m, 1),
                                     "ch1 position untouched");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(rep, "# ack pos"),
                                 "set_position ack reply");

    /* a comma inside the position name is sanitized (CSV safety) */
    run_meta_set_position(&m, "1,a,b", rep, sizeof(rep));
    TEST_ASSERT_EQUAL_STRING_MESSAGE("a_b", run_meta_position(&m, 1),
                                     "position comma sanitized");

    /* nak paths: missing comma / non-numeric ch / out-of-range / empty name */
    TEST_ASSERT_TRUE_MESSAGE(!run_meta_set_position(&m, "2", rep, sizeof(rep)),
                             "no comma -> nak");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(rep, "err=parse"),
                                 "no-comma parse nak");
    TEST_ASSERT_TRUE_MESSAGE(
        !run_meta_set_position(&m, "x,foo", rep, sizeof(rep)),
        "non-numeric channel -> nak");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(rep, "err=parse"),
                                 "non-numeric parse nak");
    TEST_ASSERT_TRUE_MESSAGE(
        !run_meta_set_position(&m, "4,foo", rep, sizeof(rep)),
        "channel 4 (n=4) -> nak");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(rep, "err=channel"),
                                 "out-of-range channel nak");
    TEST_ASSERT_TRUE_MESSAGE(!run_meta_set_position(&m, "0,", rep, sizeof(rep)),
                             "empty name -> nak");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("s3-origplant", run_meta_position(&m, 0),
                                     "empty-name nak leaves ch0 unchanged");

    /* init clamps an over-large channel count to RUN_META_MAX_CH */
    run_meta_t big;
    run_meta_init(&big, "L", "P", 99);
    TEST_ASSERT_EQUAL_STRING_MESSAGE("P", run_meta_position(&big, 3),
                                     "clamped count still seeds ch3");
    TEST_ASSERT_EQUAL_STRING_MESSAGE("", run_meta_position(&big, 4),
                                     "clamp keeps ch4 out of range");
}

/* -------------------------------------------------------------------------- */
/* bench env sensors: SHT45 + AS7263 (#373/#374)                              */
/* -------------------------------------------------------------------------- */

static void mock_delay(uint32_t ms, void *user)
{
    (void)ms;
    (void)user;
}

/* --- SHT45 mock bus: a canned 6-byte response with valid CRCs --- */
typedef struct {
    uint8_t resp[6];
    bool write_fail;
    bool read_fail;
} sht45_mock_t;

static int sht45_mock_write(uint8_t a, const uint8_t *b, size_t n, void *u)
{
    (void)a;
    (void)b;
    (void)n;
    return ((sht45_mock_t *)u)->write_fail ? -1 : 0;
}
static int sht45_mock_read(uint8_t a, uint8_t *b, size_t n, void *u)
{
    (void)a;
    sht45_mock_t *m = (sht45_mock_t *)u;
    if (m->read_fail || n != 6) return -1;
    memcpy(b, m->resp, 6);
    return 0;
}
static void sht45_set_word(uint8_t *p, uint16_t raw)
{
    p[0] = (uint8_t)(raw >> 8);
    p[1] = (uint8_t)(raw & 0xFF);
    p[2] = sht45_crc8(p, 2);
}

void t_sht45(void)
{
    /* Sensirion CRC-8 test vector: CRC(0xBE,0xEF) = 0x92 */
    uint8_t v[2] = {0xBE, 0xEF};
    TEST_ASSERT_EQUAL_HEX8_MESSAGE(0x92, sht45_crc8(v, 2),
                                   "Sensirion CRC vector");

    /* fixed-point conversion endpoints */
    TEST_ASSERT_EQUAL_INT_MESSAGE(-4500, sht45_temp_centi(0), "T(0)=-45.00C");
    TEST_ASSERT_EQUAL_INT_MESSAGE(13000, sht45_temp_centi(65535),
                                  "T(max)=130.00C");
    TEST_ASSERT_EQUAL_INT_MESSAGE(5000, sht45_rh_centi(29359), "RH~50.00%");
    TEST_ASSERT_EQUAL_INT_MESSAGE(0, sht45_rh_centi(0), "RH clamps low");
    TEST_ASSERT_EQUAL_INT_MESSAGE(10000, sht45_rh_centi(65535),
                                  "RH clamps high");

    /* full read over the mock bus */
    sht45_mock_t m;
    memset(&m, 0, sizeof m);
    sht45_set_word(&m.resp[0], 0x6666);
    sht45_set_word(&m.resp[3], 0x8000);
    env_i2c_t bus = {sht45_mock_write, sht45_mock_read, mock_delay, &m};
    sht45_reading_t r;
    TEST_ASSERT_EQUAL_INT_MESSAGE(SHT45_OK, sht45_read(&bus, &r), "read OK");
    TEST_ASSERT_EQUAL_HEX16_MESSAGE(0x6666, r.temp_raw, "temp raw");
    TEST_ASSERT_EQUAL_HEX16_MESSAGE(0x8000, r.rh_raw, "rh raw");
    TEST_ASSERT_EQUAL_INT_MESSAGE(sht45_temp_centi(0x6666), r.temp_c_centi,
                                  "temp convert");

    /* a flipped CRC byte -> CRC error */
    m.resp[2] ^= 0xFF;
    TEST_ASSERT_EQUAL_INT_MESSAGE(SHT45_ERR_CRC, sht45_read(&bus, &r),
                                  "bad CRC -> ERR_CRC");
    m.resp[2] ^= 0xFF;

    /* bus failure -> I2C error */
    m.write_fail = true;
    TEST_ASSERT_EQUAL_INT_MESSAGE(SHT45_ERR_I2C, sht45_read(&bus, &r),
                                  "bus fail -> ERR_I2C");
}

/* --- AS7263 mock bus: models the virtual-register TX/RX handshake --- */
typedef struct {
    uint8_t vreg[0x80]; /* canned virtual-register values        */
    uint8_t read_reg; /* last physical reg targeted for a read */
    int pending; /* vreg queued for READ, or -1           */
    uint8_t write_vreg; /* vreg addressed by a write (vreg|0x80) */
    bool expect_val; /* next WRITE byte is the value          */
} as7263_mock_t;

static int as7263_mock_write(uint8_t a, const uint8_t *b, size_t n, void *u)
{
    (void)a;
    as7263_mock_t *m = (as7263_mock_t *)u;
    if (n == 1) {
        m->read_reg = b[0];
        return 0;
    } /* set up a phys read */
    if (n == 2 && b[0] == AS7263_REG_WRITE) { /* phys write to WRITE */
        uint8_t val = b[1];
        if (m->expect_val) {
            m->vreg[m->write_vreg] = val;
            m->expect_val = false;
        } else if (val & 0x80) {
            m->write_vreg = val & 0x7F;
            m->expect_val = true;
        } else {
            m->pending = val;
        } /* a read request */
    }
    return 0;
}
static int as7263_mock_read(uint8_t a, uint8_t *b, size_t n, void *u)
{
    (void)a;
    as7263_mock_t *m = (as7263_mock_t *)u;
    if (n != 1) return -1;
    if (m->read_reg == AS7263_REG_STATUS)
        b[0] = (uint8_t)(m->pending >= 0 ? AS7263_RX_VALID
                                         : 0); /* TX always clear */
    else if (m->read_reg == AS7263_REG_READ) {
        b[0] = (m->pending >= 0) ? m->vreg[m->pending] : 0;
        m->pending = -1;
    } else
        b[0] = 0;
    return 0;
}

void t_as7263(void)
{
    as7263_mock_t m;
    memset(&m, 0, sizeof m);
    m.pending = -1;
    m.vreg[AS7263_HW_VERSION] = 0x3E; /* nonzero -> device present */
    env_i2c_t bus = {as7263_mock_write, as7263_mock_read, mock_delay, &m};

    TEST_ASSERT_EQUAL_INT_MESSAGE(
        AS7263_OK, as7263_init(&bus, AS7263_GAIN_64X, 50), "init OK");

    m.vreg[AS7263_CONTROL_SETUP] = AS7263_DATA_RDY; /* conversion ready */
    for (int i = 0; i < 6; i++) { /* six 16-bit channels */
        m.vreg[AS7263_R_HIGH + i * 2] = (uint8_t)(0x10 + i);
        m.vreg[AS7263_R_HIGH + i * 2 + 1] = (uint8_t)(0x20 + i);
    }
    as7263_reading_t r;
    TEST_ASSERT_EQUAL_INT_MESSAGE(AS7263_OK, as7263_read(&bus, &r), "read OK");
    TEST_ASSERT_EQUAL_HEX16_MESSAGE(0x1020, r.nm610, "ch0 = hi<<8|lo");
    TEST_ASSERT_EQUAL_HEX16_MESSAGE(0x1121, r.nm680, "ch1 assembled");
    TEST_ASSERT_EQUAL_HEX16_MESSAGE(0x1525, r.nm860, "ch5 assembled");
}

void t_env_row(void)
{
    char buf[256];

    /* SHT45 temp row: factory-calibrated -> value+unit populated; placement in
     * sensor_position; degC unit (ratified #377). */
    telemetry_env_row_t t = {"plants.env",   "3f9a1c",
                             "Sprout ESP32", "0.7.0",
                             123456ULL,      "SHT45",
                             "sht45",        "breadboard_near_esp32",
                             "ambient_temp", "26214",
                             "24.99",        "degC",
                             "OK",           "mount=breadboard_near_esp32"};
    TEST_ASSERT_TRUE_MESSAGE(telemetry_format_env_row(buf, sizeof(buf), &t) > 0,
                             "env temp row formatted");
    TEST_ASSERT_NOT_NULL_MESSAGE(
        strstr(buf, "plants.env,3f9a1c,Sprout ESP32,0.7.0,123456,SHT45,sht45,"
                    "breadboard_near_esp32,ambient_temp,26214,24.99,degC,OK,"),
        "SHT45 row columns in order (value+unit populated)");

    /* AS7263 tidy NIR row: one band, raw count, value+unit empty. */
    telemetry_env_row_t n = {
        "plants.env",
        "3f9a1c",
        "Sprout ESP32",
        "0.7.0",
        123456ULL,
        "AS7263",
        "as7263",
        "breadboard_near_esp32",
        "nir_610",
        "1234",
        "",
        "",
        "OK",
        "gain=64;itime_ms=140;aim=skylight_beam;not_canopy"};
    TEST_ASSERT_TRUE_MESSAGE(telemetry_format_env_row(buf, sizeof(buf), &n) > 0,
                             "env nir row formatted");
    TEST_ASSERT_NOT_NULL_MESSAGE(
        strstr(buf, "AS7263,as7263,breadboard_near_esp32,nir_610,1234,,,OK,"),
        "AS7263 tidy row: raw count, empty value/unit");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(buf, "aim=skylight_beam"),
                                 "aim in payload");
}

/* #278 device-owned time (ADR-0018 / schema v2 §11.1-§11.2): device_seq +
 * time_source ride the soil row's payload; device_timestamp_utc is OMITTED
 * (not printed as an empty key) when unsynced - the honest NULL, never a
 * guessed value. Pins BOTH states: today's real unsynced case, and the
 * synced case the fields are already ready for once #21 (WiFi/NTP) lands. */
void t_soil_row_time_provenance(void)
{
    moisture_cfg_t cfg = (moisture_cfg_t)MOISTURE_CFG_DEFAULT;
    moisture_state_t st;
    moisture_init(&st, &cfg,
                  1300); /* WELL_WATERED-range raw, any valid state */
    char buf[300];

    /* unsynced (today's honest reality): device_timestamp_utc key absent entirely */
    telemetry_soil_row_t unsynced = {
        "plants.soil",
        "3f9a1c",
        "Sprout ESP32",
        "0.7.0",
        123456ULL,
        "UMLIFE_v2_TLC555",
        "s3",
        "origplant",
        "soil_moisture",
        36,
        1300,
        MOIST_WELL_WATERED,
        &st,
        42,
        "device_uptime",
        "",
    };
    TEST_ASSERT_TRUE_MESSAGE(
        telemetry_format_soil_row(buf, sizeof(buf), &unsynced) > 0,
        "unsynced row formatted");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(buf, "device_seq=42"),
                                 "device_seq in payload");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(buf, "time_source=device_uptime"),
                                 "time_source=device_uptime when unsynced");
    TEST_ASSERT_NULL_MESSAGE(
        strstr(buf, "device_timestamp_utc="),
        "device_timestamp_utc key OMITTED, not empty, when NULL");

    /* synced (future-ready, once #21/NTP lands): device_timestamp_utc appears */
    telemetry_soil_row_t synced = {
        "plants.soil",
        "3f9a1c",
        "Sprout ESP32",
        "0.7.0",
        123456ULL,
        "UMLIFE_v2_TLC555",
        "s3",
        "origplant",
        "soil_moisture",
        36,
        1300,
        MOIST_WELL_WATERED,
        &st,
        43,
        "device_synced",
        "2026-07-01T14:05:30.000Z",
    };
    TEST_ASSERT_TRUE_MESSAGE(
        telemetry_format_soil_row(buf, sizeof(buf), &synced) > 0,
        "synced row formatted");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(buf, "time_source=device_synced"),
                                 "time_source=device_synced when synced");
    TEST_ASSERT_NOT_NULL_MESSAGE(
        strstr(buf, "device_timestamp_utc=2026-07-01T14:05:30.000Z"),
        "device_timestamp_utc present + exact when synced");
}

/* #21/#275 connect-scaffold + portal state machine (lib/wifi_net): pure C,
 * driven with synthetic inputs - no Arduino/WiFi.h needed. Covers: a fresh
 * board (no creds) opens the PORTAL (never a silent idle, #275/ADR-0020 §4),
 * creds trigger one edge-triggered begin(), timeout -> FAILED -> backoff ->
 * retry, repeated failure falls to PORTAL, PORTAL keeps background STA
 * retries on the LONG backoff and self-heals to CONNECTED, a drop reconnects
 * immediately, and cleared creds reopen the portal. */
void t_wifi_net_state_machine(void)
{
    const wifi_net_cfg_t cfg = {
        15000, /* connect_timeout_ms */
        30000, /* retry_backoff_ms */
        3, /* portal_after_failures */
        300000, /* portal_retry_backoff_ms (5 min) */
    };
    wifi_net_ctx_t ctx;
    wifi_net_init(&ctx);
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_IDLE, ctx.state, "starts idle");

    /* fresh board, no credentials: the config AP is the only way forward */
    TEST_ASSERT_FALSE_MESSAGE(wifi_net_tick(&ctx, false, false, 1000, &cfg),
                              "no creds -> no begin() trigger");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_PORTAL, ctx.state,
                              "no creds -> portal (fresh-board onboarding)");

    /* creds appear (portal form / !wifi -> caller re-inits): fresh attempt */
    wifi_net_init(&ctx);
    TEST_ASSERT_TRUE_MESSAGE(wifi_net_tick(&ctx, true, false, 2000, &cfg),
                             "creds appear -> begin() triggered once");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_CONNECTING, ctx.state, "-> connecting");
    /* still connecting, not yet timed out: no re-trigger, no state change */
    TEST_ASSERT_FALSE_MESSAGE(wifi_net_tick(&ctx, true, false, 5000, &cfg),
                              "mid-attempt -> no re-trigger");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_CONNECTING, ctx.state,
                              "still connecting before timeout");

    /* timeout elapses without success -> FAILED, backoff window set */
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, false, 2000 + 15000, &cfg),
        "timeout -> failed, no trigger on the failing tick itself");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_FAILED, ctx.state, "-> failed");
    TEST_ASSERT_EQUAL_MESSAGE(1, ctx.retry_count, "one failure counted");

    /* still inside the backoff window: no retry yet */
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, false, 2000 + 15000 + 1000, &cfg),
        "inside backoff -> no retry trigger");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_FAILED, ctx.state, "still failed");

    /* backoff expires -> retry triggers a fresh begin(). Times are computed
     * from the constants (failure at 17000 + 30000 backoff), not peeked from
     * the ctx - the backoff is a rollover-safe start+wait pair (#9), there is
     * no absolute deadline field to read. */
    unsigned long retry_at = 17000 + 30000;
    TEST_ASSERT_TRUE_MESSAGE(wifi_net_tick(&ctx, true, false, retry_at, &cfg),
                             "backoff expired -> retry begin() triggered");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_CONNECTING, ctx.state,
                              "retry -> connecting again");

    /* second failure, then third attempt fails -> falls to PORTAL (#275) */
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, false, retry_at + 15000, &cfg),
        "2nd timeout -> failed again");
    TEST_ASSERT_EQUAL_MESSAGE(2, ctx.retry_count, "two failures counted");
    retry_at = retry_at + 15000 + 30000; /* 2nd failure + retry backoff */
    TEST_ASSERT_TRUE_MESSAGE(wifi_net_tick(&ctx, true, false, retry_at, &cfg),
                             "3rd attempt triggers");
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, false, retry_at + 15000, &cfg),
        "3rd timeout -> threshold reached");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_PORTAL, ctx.state,
                              "repeated failure -> portal reopens (AC#3)");

    /* portal keeps a background STA retry on the LONG backoff... */
    unsigned long portal_entered = retry_at + 15000;
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, false, portal_entered + 300000 - 1000, &cfg),
        "inside portal backoff -> no retry");
    unsigned long portal_retry = portal_entered + 300000;
    TEST_ASSERT_TRUE_MESSAGE(
        wifi_net_tick(&ctx, true, false, portal_retry, &cfg),
        "portal backoff expired -> background STA retry");
    /* ...and a FAILED background retry returns to PORTAL, not FAILED */
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, false, portal_retry + 15000, &cfg),
        "portal-origin timeout -> no trigger");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_PORTAL, ctx.state,
                              "portal-origin failure -> back to portal");

    /* ...and a SUCCESSFUL background retry self-heals to CONNECTED */
    unsigned long heal_at = portal_retry + 15000 + 300000;
    TEST_ASSERT_TRUE_MESSAGE(wifi_net_tick(&ctx, true, false, heal_at, &cfg),
                             "portal retry triggers again");
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, true, true, heal_at + 500, &cfg),
        "association succeeds -> no trigger");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_CONNECTED, ctx.state,
                              "portal self-heals -> connected (AP tears down "
                              "on this edge)");
    TEST_ASSERT_EQUAL_MESSAGE(0, ctx.retry_count,
                              "retry_count resets on success");

    /* connection drops: immediate reconnect attempt, no backoff wait */
    TEST_ASSERT_TRUE_MESSAGE(
        wifi_net_tick(&ctx, true, false, heal_at + 60000, &cfg),
        "drop -> immediate reconnect trigger, no backoff");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_CONNECTING, ctx.state,
                              "drop -> connecting again immediately");

    /* credentials cleared mid-flight: portal reopens (never a silent idle) */
    TEST_ASSERT_FALSE_MESSAGE(
        wifi_net_tick(&ctx, false, false, heal_at + 61000, &cfg),
        "creds cleared -> no trigger");
    TEST_ASSERT_EQUAL_MESSAGE(WIFI_NET_PORTAL, ctx.state,
                              "creds cleared -> portal reopens");
}

/* #273 capability descriptor (ADR-0019 §1-2): the descriptor is accessible, the
 * gate seam matches the field, and an unknown/no-WiFi target falls to the Tier-0
 * floor (tethered monitor, no WiFi) — i.e. Tier-0 runs on a no-WiFi board. The
 * native/host build takes the fallback entry, so that's what this pins. */
void t_board_capability(void)
{
    TEST_ASSERT_FALSE_MESSAGE(
        board_has_wifi(), "host/fallback: no WiFi -> Tier-0 tethered monitor");
    TEST_ASSERT_EQUAL_MESSAGE((int)BOARD_CAP.has_wifi, (int)board_has_wifi(),
                              "gate seam reflects the descriptor field");
    TEST_ASSERT_EQUAL_MESSAGE(4, BOARD_CAP.num_channels, "4 soil channels");
    TEST_ASSERT_EQUAL_MESSAGE(12, BOARD_CAP.adc_bits, "12-bit ADC");
    TEST_ASSERT_NOT_NULL_MESSAGE((void *)BOARD_CAP.name,
                                 "descriptor has a name");
    TEST_ASSERT_NOT_NULL_MESSAGE((void *)BOARD_CAP.storage,
                                 "has a storage tier");

    /* #436: pins are now a descriptor field (ADR-0019 §1). The host/fallback entry
     * carries the classic pin values, so this locks the exact classic map (a
     * regression guard: config.h's SENSOR_PINS/RELAY_PINS/LED_PIN now SOURCE from
     * these, so a wrong edit here would silently reassign real hardware pins). */
    const uint8_t soil[4] = {36, 39, 34, 35};
    const uint8_t relay[4] = {25, 26, 27, 32};
    for (int i = 0; i < 4; i++) {
        TEST_ASSERT_EQUAL_MESSAGE(soil[i], BOARD_CAP.soil_pins[i],
                                  "classic soil pin unchanged");
        TEST_ASSERT_EQUAL_MESSAGE(relay[i], BOARD_CAP.relay_pins[i],
                                  "classic relay pin unchanged");
    }
    TEST_ASSERT_EQUAL_MESSAGE(2, BOARD_CAP.led_pin,
                              "classic LED pin unchanged");
    TEST_ASSERT_EQUAL_MESSAGE(21, BOARD_CAP.i2c_sda,
                              "classic I2C SDA unchanged");
    TEST_ASSERT_EQUAL_MESSAGE(22, BOARD_CAP.i2c_scl,
                              "classic I2C SCL unchanged");

    /* #436: per-board calibration. Host/fallback carries the classic endpoint
     * VALUES (the placeholder every unverified board also uses) but, like
     * has_wifi/storage, is honestly NOT a real board -> cal_verified=false. This
     * pins the value/flag as two independent facts: the numbers can match
     * classic's without the board being claimed as bench-verified. */
    const uint16_t cal[BOARD_CAL_BOUNDARY_COUNT] = {3050, 2140, 1830,
                                                    1520, 1150, 1050};
    for (int i = 0; i < BOARD_CAL_BOUNDARY_COUNT; i++) {
        TEST_ASSERT_EQUAL_MESSAGE(cal[i], BOARD_CAP.cal_boundary[i],
                                  "host cal boundary matches the placeholder");
    }
    TEST_ASSERT_FALSE_MESSAGE(BOARD_CAP.cal_verified,
                              "host is not a real board -> not bench-verified");
}

/* #274 sensor-type seam (ADR-0019 §3): a RESISTIVE channel INVERTS the raw->band
 * direction (higher raw = wetter). Pins the MECHANISM, not resistive calibration
 * values (there are none — resistive ships PROVISIONAL); the same raw lands at
 * opposite ends of the band scale for capacitive vs resistive. */
void t_sensor_type_resistive(void)
{
    moisture_cfg_t cap =
        (moisture_cfg_t)MOISTURE_CFG_DEFAULT; /* SENSOR_CAPACITIVE */
    TEST_ASSERT_EQUAL_MESSAGE(
        SENSOR_CAPACITIVE, cap.sensor_type,
        "default profile is capacitive (configs unchanged)");

    /* Resistive: same magnitudes but ASCENDING boundary[] + inverted direction. */
    moisture_cfg_t res = (moisture_cfg_t)MOISTURE_CFG_DEFAULT;
    res.sensor_type = SENSOR_RESISTIVE;
    const uint16_t asc[MOISTURE_BOUNDARY_COUNT] = {1050, 1150, 1520,
                                                   1830, 2140, 3050};
    memcpy(res.boundary, asc, sizeof(res.boundary));

    moisture_state_t sc, sr;
    /* HIGH raw (3200): capacitive -> AIR_DRY (driest); resistive -> SUBMERGED (wettest) */
    moisture_init(&sc, &cap, 3200);
    moisture_init(&sr, &res, 3200);
    TEST_ASSERT_EQUAL_MESSAGE(MOIST_AIR_DRY, sc.committed,
                              "cap: high raw -> air-dry");
    TEST_ASSERT_EQUAL_MESSAGE(MOIST_SUBMERGED, sr.committed,
                              "res: high raw -> submerged (inverted)");

    /* LOW raw (900): capacitive -> SUBMERGED; resistive -> AIR_DRY */
    moisture_init(&sc, &cap, 900);
    moisture_init(&sr, &res, 900);
    TEST_ASSERT_EQUAL_MESSAGE(MOIST_SUBMERGED, sc.committed,
                              "cap: low raw -> submerged");
    TEST_ASSERT_EQUAL_MESSAGE(MOIST_AIR_DRY, sr.committed,
                              "res: low raw -> air-dry (inverted)");
}

/* classify `raw` using channel ch's per-channel calibration (#170). */
static moisture_level_t band_on_channel(int ch, uint16_t raw)
{
    moisture_cfg_t cfg = (moisture_cfg_t)MOISTURE_CFG_DEFAULT;
    memcpy(cfg.boundary, SENSOR_CAL_BOUNDARY[ch], sizeof(cfg.boundary));
    moisture_state_t st;
    moisture_init(&st, &cfg, raw);
    return st.committed;
}

/* #170: per-channel raw->band calibration. Pins the MECHANISM (each channel
 * classifies against its OWN boundary[]), NOT the provisional values (Data's
 * #192 owns those, so this test survives a value regen). The seam: an identical
 * raw lands in different bands on two channels whose outer rails differ, while
 * the still-shared interior keeps the watering decision uniform (Step 1). */
void t_per_channel_cal(void)
{
    /* the table covers every channel and is genuinely per-channel (not a copy) */
    TEST_ASSERT_EQUAL_INT_MESSAGE(IRRIG_CHANNELS, SENSOR_CAL_CHANNELS,
                                  "cal table covers every channel");
    TEST_ASSERT_TRUE_MESSAGE(SENSOR_CAL_BOUNDARY[0][5] !=
                                 SENSOR_CAL_BOUNDARY[3][5],
                             "ch0(s3) and ch3(s2) have distinct wet rails");

    /* a raw between s2's wet rail (ch3 ~900) and s3's wet rail (ch0 ~969):
     * submerged on s3 (below its rail) but NOT on s2 (above its rail). */
    const uint16_t raw = 930;
    TEST_ASSERT_TRUE_MESSAGE(band_on_channel(0, raw) == MOIST_SUBMERGED,
                             "raw 930 < s3 wet rail -> submerged on ch0");
    TEST_ASSERT_TRUE_MESSAGE(band_on_channel(3, raw) != MOIST_SUBMERGED,
                             "raw 930 > s2 wet rail -> NOT submerged on ch3");

    /* Step-1 invariant: interior [1..4] stays SHARED, so a mid-soil raw bands
     * the SAME on every channel — the watering decision is unchanged until the
     * Step-2 per-channel field-capacity anchor lands. */
    for (int ch = 1; ch < SENSOR_CAL_CHANNELS; ch++) {
        TEST_ASSERT_EQUAL_MESSAGE(band_on_channel(0, 1300),
                                  band_on_channel(ch, 1300),
                                  "shared interior -> same mid-soil band");
    }
}

/* #404: the cal_ch header line - pins the EXACT wire format Data's #507 parser
 * (_parse_cal_channel) reads, byte-for-byte, using ch0's real calibration.h
 * values + the provenance constants. Also pins the honest-NULL date rule:
 * a NULL/empty date omits the key entirely, never emits `date=`. */
void t_cal_ch_line(void)
{
    char buf[160];

    /* full line, ch0 values straight from calibration.h */
    int n = telemetry_format_cal_ch(
        buf, sizeof(buf), "s3", SENSOR_CAL_BOUNDARY[0], MOISTURE_BOUNDARY_COUNT,
        SENSOR_CAL_SRC, SENSOR_CAL_DATE, SENSOR_CAL_CONFIDENCE,
        SENSOR_CAL_SCOPE);
    TEST_ASSERT_TRUE_MESSAGE(n > 0, "cal_ch line formatted");
    TEST_ASSERT_EQUAL_STRING_MESSAGE(
        "# cal_ch s3: bounds=3123,2140,1830,1520,1150,969 "
        "src=wipe_airdry_bench date=2026-06-28 confidence=provisional "
        "scope=channel",
        buf, "exact wire format the #507 parser reads");

    /* honest-NULL date: key omitted entirely, not printed empty */
    n = telemetry_format_cal_ch(buf, sizeof(buf), "s2", SENSOR_CAL_BOUNDARY[3],
                                MOISTURE_BOUNDARY_COUNT, "manual", NULL,
                                "provisional", "channel");
    TEST_ASSERT_TRUE_MESSAGE(n > 0, "dateless cal_ch line formatted");
    TEST_ASSERT_NULL_MESSAGE(strstr(buf, "date="),
                             "NULL date -> date= key absent");
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(buf, "src=manual confidence="),
                                 "fields stay adjacent when date omitted");

    /* truncation is reported, never a silently-clipped line */
    char tiny[24];
    TEST_ASSERT_EQUAL_MESSAGE(-1,
                              telemetry_format_cal_ch(tiny, sizeof(tiny), "s3",
                                                      SENSOR_CAL_BOUNDARY[0],
                                                      MOISTURE_BOUNDARY_COUNT,
                                                      "x", "y", "z", "w"),
                              "truncation -> -1");
}

/* -------------------------------------------------------------------------- */
/* device_uid: the stable-id base32 mint (#601 / ADR-0027 §1b)                */
/* -------------------------------------------------------------------------- */

static void t_device_uid_encode(void)
{
    char id[DEVICE_UID_LEN + 1];

    /* deterministic regression pins: all-zero -> all '0'; all-ones (each 5-bit
     * slice = 31) -> the last alphabet char 'z'. */
    device_uid_encode(0x00000000u, id);
    TEST_ASSERT_EQUAL_STRING("000000", id);
    device_uid_encode(0xFFFFFFFFu, id);
    TEST_ASSERT_EQUAL_STRING("zzzzzz", id);

    /* always exactly DEVICE_UID_LEN chars + a terminator */
    device_uid_encode(0x12345678u, id);
    TEST_ASSERT_EQUAL_UINT(DEVICE_UID_LEN, strlen(id));

    /* every char is Crockford base32 (0-9 a-z) and NEVER a lookalike i/l/o/u */
    for (unsigned k = 0; k < 200; k++) {
        device_uid_encode(k * 2654435761u,
                          id); /* Knuth mix - deterministic spread */
        for (unsigned j = 0; j < DEVICE_UID_LEN; j++) {
            char c = id[j];
            TEST_ASSERT_TRUE((c >= '0' && c <= '9') || (c >= 'a' && c <= 'z'));
            TEST_ASSERT_TRUE(c != 'i' && c != 'l' && c != 'o' && c != 'u');
        }
    }
}

/* -------------------------------------------------------------------------- */
/* runner                                                                     */
/* -------------------------------------------------------------------------- */

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(t_health_veto_and_latch);
    RUN_TEST(t_healthy_dry_waters);
    RUN_TEST(t_invariants_two_channels);
    RUN_TEST(t_no_improvement_fault);
    RUN_TEST(t_overrun_failsafe);
    RUN_TEST(t_last_water_ms);
    RUN_TEST(t_band_anchors);
    RUN_TEST(t_board_capability);
    RUN_TEST(t_sensor_type_resistive);
    RUN_TEST(t_serial_cmd_registry);
    RUN_TEST(t_pump_pulse);
    RUN_TEST(t_forced_dose);
    RUN_TEST(t_autonomous_gate);
    RUN_TEST(t_irrig_abort);
    RUN_TEST(t_run_meta);
    RUN_TEST(t_sht45);
    RUN_TEST(t_as7263);
    RUN_TEST(t_env_row);
    RUN_TEST(t_soil_row_time_provenance);
    RUN_TEST(t_per_channel_cal);
    RUN_TEST(t_cal_ch_line);
    RUN_TEST(t_wifi_net_state_machine);
    RUN_TEST(t_device_uid_encode);
    return UNITY_END();
}
