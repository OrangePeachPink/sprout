#include "commands.h"
#include "serial_cmd.h"
#include "irrigation.h"
#include <Arduino.h>
#include <Preferences.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef GIT_REV
#define GIT_REV "nogit"  /* overridden by scripts/git_rev.py at build */
#endif

/* Module-level copy of the context (shallow: pointer targets live in main.cpp). */
static commands_ctx_t s_ctx;

/* Convenience casts so handler bodies read cleanly. */
static inline Preferences *prefs()
{
    return (Preferences *)s_ctx.prefs_handle;
}
static inline irrig_ctrl_t *irrig()
{
    return s_ctx.irrig;
}

/* ---- private helpers ---------------------------------------------------- */

/*
 * Derive the friendly default device name from the chip model only (#188).
 * "ESP32-D0WD-V3" -> "Sprout ESP32". The model is a board type shared by
 * millions of chips — no MAC, eFuse, or serial is read.
 */
static void derive_default_id(char *out, size_t outlen)
{
    const char *model = ESP.getChipModel();
    char family[16];
    size_t i = 0;
    for (; model[i] && model[i] != '-' && i < sizeof(family) - 1; i++)
        family[i] = model[i];
    family[i] = '\0';
    if (family[0] == '\0')
        snprintf(out, outlen, "Sprout MCU");
    else
        snprintf(out, outlen, "Sprout %s", family);
}

/* ---- command handlers (#92 registry) ------------------------------------ */

/* !cad,<ms>[,temp] - retune the supervisor's idle sweep cadence (#63 / #227: the
 * FSM owns sample_period_ms now).
 *   !cad,<ms>       persists to NVS — the operator's deliberate default (survives reboot).
 *   !cad,<ms>,temp  SESSION-ONLY: set live, NO NVS write; reverts to the saved/compiled
 *                   default on reset. Experiments use this so a fast capture rate can
 *                   never leak into the next monitor run (#322). */
static void handle_cad(const char *args, char *reply, size_t replen)
{
    char msbuf[12];
    const char *comma = strchr(args, ',');
    size_t mslen = comma ? (size_t)(comma - args) : strlen(args);
    uint32_t ms;
    if (mslen == 0 || mslen >= sizeof(msbuf)) {
        snprintf(reply, replen,
                 "# nak err=parse (use: !cad,<ms>[,temp]) floor=%lu",
                 s_ctx.cadence_floor_ms);
        return;
    }
    memcpy(msbuf, args, mslen);
    msbuf[mslen] = '\0';
    if (!serial_cmd_parse_u32(msbuf, &ms)) {
        snprintf(reply, replen,
                 "# nak err=parse (use: !cad,<ms>[,temp]) floor=%lu",
                 s_ctx.cadence_floor_ms);
        return;
    }
    bool temp = (comma && strcmp(comma + 1, "temp") == 0);
    if (comma && !temp) { /* a second arg that isn't exactly "temp" */
        snprintf(reply, replen, "# nak err=scope (use: !cad,<ms>[,temp])");
        return;
    }
    if (ms < s_ctx.cadence_floor_ms || ms > s_ctx.cadence_ceil_ms) {
        snprintf(reply, replen, "# nak cad=%lu err=range floor=%lu",
                 (unsigned long)ms, s_ctx.cadence_floor_ms);
        return;
    }
    unsigned long prev = (unsigned long)*s_ctx.sample_period_ms;
    *s_ctx.sample_period_ms = ms;
    *s_ctx.cadence_temp = temp;
    if (temp) {
        /* session-only: never touch NVS, so it can't leak into the next boot (#322) */
        snprintf(reply, replen,
                 "# ack cad=%lu prev=%lu src=temp (reverts on reset)",
                 (unsigned long)ms, prev);
    } else {
        *s_ctx.cadence_from_nvs = true;
        prefs()->putULong("cadence_ms", ms);
        snprintf(reply, replen, "# ack cad=%lu prev=%lu src=nvs floor=%lu",
                 (unsigned long)ms, prev, s_ctx.cadence_floor_ms);
    }
}

/* !ping - liveness check. */
static void handle_ping(const char *args, char *reply, size_t replen)
{
    (void)args;
    snprintf(reply, replen, "# ack pong");
}

/* !ver - identity / provenance (fw + device_id + git rev). */
static void handle_ver(const char *args, char *reply, size_t replen)
{
    (void)args;
    snprintf(reply, replen, "# ack ver fw=%s device_id=%s git=%s",
             s_ctx.fw_version, s_ctx.device_id, GIT_REV);
}

/* !cfg,reset - clear persisted config and apply compile-time defaults (#90). */
static void handle_cfg(const char *args, char *reply, size_t replen)
{
    if (strcmp(args, "reset") == 0) {
        prefs()->clear();
        *s_ctx.sample_period_ms = (uint32_t)s_ctx.cadence_default_ms;
        *s_ctx.cadence_from_nvs = false;
        *s_ctx.cadence_temp = false;
        derive_default_id(s_ctx.device_id, s_ctx.device_id_len);
        *s_ctx.device_id_custom = false;
        snprintf(reply, replen, "# ack cfg reset cad=%lu device_id=%s",
                 s_ctx.cadence_default_ms, s_ctx.device_id);
    } else {
        snprintf(reply, replen, "# nak err=cfg (use: !cfg,reset)");
    }
}

/*
 * !name,<string> - set a custom device name (#188), persisted to NVS (#90).
 * An empty arg clears back to the chip-model default.
 * Sanitized for CSV: commas + control chars -> '_'.
 */
static void handle_name(const char *args, char *reply, size_t replen)
{
    if (args[0] == '\0') {
        prefs()->remove("device_name");
        derive_default_id(s_ctx.device_id, s_ctx.device_id_len);
        *s_ctx.device_id_custom = false;
        snprintf(reply, replen, "# ack name device_id=%s (default)",
                 s_ctx.device_id);
        return;
    }
    char clean[32]; /* matches device_id_len in practice */
    size_t j = 0;
    for (size_t i = 0; args[i] && j < sizeof(clean) - 1; i++) {
        char c = args[i];
        clean[j++] = (c == ',' || c < 0x20 || c == 0x7f) ? '_' : c;
    }
    clean[j] = '\0';
    strncpy(s_ctx.device_id, clean, s_ctx.device_id_len - 1);
    s_ctx.device_id[s_ctx.device_id_len - 1] = '\0';
    prefs()->putString("device_name", s_ctx.device_id);
    *s_ctx.device_id_custom = true;
    snprintf(reply, replen, "# ack name device_id=%s (custom)",
             s_ctx.device_id);
}

/*
 * !water,<ch>[,<ms>] - operator manual pulse (#215), expressed as a FORCED DOSE
 * into the supervisor (single actuation authority, ADR-0016) — not a second relay
 * driver. Granted on the next sweep (prompt: a pending forced dose makes the FSM
 * sweep right away); ms is clamped to pump_max_ms; a hard-faulted channel is
 * refused (clear it first).
 */
static void handle_water(const char *args, char *reply, size_t replen)
{
    char chbuf[12];
    uint32_t ms = 0;
    const char *comma = strchr(args, ',');
    size_t chlen = comma ? (size_t)(comma - args) : strlen(args);
    if (chlen == 0 || chlen >= sizeof(chbuf)) {
        snprintf(reply, replen, "# nak err=parse (use: !water,<ch>[,<ms>])");
        return;
    }
    memcpy(chbuf, args, chlen);
    chbuf[chlen] = '\0';
    uint32_t ch;
    if (!serial_cmd_parse_u32(chbuf, &ch) ||
        (comma && comma[1] != '\0' && !serial_cmd_parse_u32(comma + 1, &ms))) {
        snprintf(reply, replen, "# nak err=parse (use: !water,<ch>[,<ms>])");
        return;
    }
    switch (irrig_request_dose(irrig(), (int)ch, ms)) {
    case IRRIG_DOSE_QUEUED:
        snprintf(reply, replen,
                 "# ack water ch=%lu ms=%lu max=%lu (forced dose queued)",
                 (unsigned long)ch, (unsigned long)ms,
                 (unsigned long)s_ctx.pump_max_ms);
        break;
    case IRRIG_DOSE_BAD_CHANNEL:
        snprintf(reply, replen, "# nak err=channel ch=%lu n=%d",
                 (unsigned long)ch, s_ctx.num_channels);
        break;
    case IRRIG_DOSE_FAULTED:
        snprintf(reply, replen, "# nak err=faulted ch=%lu (clear it first)",
                 (unsigned long)ch);
        break;
    }
}

/*
 * !label,<run_label> - update the active run label at runtime (#321). The label
 * lives only in the provenance header, so reprint it on success: the operator
 * (and Data, which joins on run_label) sees the change immediately.
 */
static void handle_label(const char *args, char *reply, size_t replen)
{
    if (run_meta_set_label(s_ctx.run_meta, args, reply, replen) &&
        s_ctx.reprint_header)
        s_ctx.reprint_header();
}

/*
 * !pos,<ch>,<name> - update one channel's sensor_position at runtime (#321).
 * It's a per-row field, so the next soil row for that channel carries it; no
 * header reprint needed (the ack confirms, and the periodic header catches up).
 */
static void handle_pos(const char *args, char *reply, size_t replen)
{
    run_meta_set_position(s_ctx.run_meta, args, reply, replen);
}

/* !stop - operator e-stop: abort any active dose, cancel pending ones, and drive
 * every relay OFF now (#215, single-authority via ADR-0016). */
static void handle_stop(const char *args, char *reply, size_t replen)
{
    (void)args;
    int ch = irrig_active_pump(irrig());
    bool was = irrig_abort(irrig(), millis());
    s_ctx.all_relays_off(); /* hardware backstop on top of the FSM abort */
    if (was)
        snprintf(reply, replen, "# ack stop ch=%d (aborted)", ch);
    else
        snprintf(reply, replen, "# ack stop idle");
}

/* !auto,on|off - arm / disarm AUTONOMOUS dosing (#227, ADR-0016 arm gate).
 * Session-scoped: the device boots DISARMED every time (fail-safe; not persisted),
 * so a reboot never silently resumes autonomous watering. The bench arms it only
 * after the dry-safety chain (#93/#191/#2/#215) has passed on real hardware.
 * Manual !water (a forced dose) works in either state. */
static void handle_auto(const char *args, char *reply, size_t replen)
{
    if (strcmp(args, "on") == 0) {
        irrig_set_autonomous(irrig(), true);
        snprintf(reply, replen, "# ack auto on (autonomous dosing ARMED)");
    } else if (strcmp(args, "off") == 0) {
        irrig_set_autonomous(irrig(), false);
        snprintf(reply, replen, "# ack auto off (autonomous dosing disarmed)");
    } else {
        snprintf(reply, replen, "# nak err=auto (use: !auto,on|off) state=%s",
                 irrig_autonomous(irrig()) ? "on" : "off");
    }
}

/*
 * !wifi,<ssid>[,<pass>] - set WiFi credentials (#21 connect-scaffold), persisted
 * to NVS; main.cpp's loop() picks up the dirty flag and attempts to (re)connect.
 * Empty args clears credentials (WiFi goes back to idle - no fabricated
 * "disconnected" state, the device just stops trying). No password means an open
 * network. Sanitized for CSV the same way !name is: the SSID can't contain a
 * comma (that's the args separator); the password is taken verbatim after the
 * first comma, so it MAY contain commas.
 */
static void handle_wifi(const char *args, char *reply, size_t replen)
{
    if (args[0] == '\0') {
        prefs()->remove("wifi_ssid");
        prefs()->remove("wifi_pass");
        s_ctx.wifi_ssid[0] = '\0';
        s_ctx.wifi_pass[0] = '\0';
        *s_ctx.wifi_creds_dirty = true;
        snprintf(reply, replen, "# ack wifi cleared");
        return;
    }
    const char *comma = strchr(args, ',');
    size_t ssid_len = comma ? (size_t)(comma - args) : strlen(args);
    if (ssid_len == 0 || ssid_len >= s_ctx.wifi_ssid_len) {
        snprintf(reply, replen, "# nak err=parse (use: !wifi,<ssid>[,<pass>])");
        return;
    }
    strncpy(s_ctx.wifi_ssid, args, ssid_len);
    s_ctx.wifi_ssid[ssid_len] = '\0';
    const char *pass = comma ? comma + 1 : "";
    strncpy(s_ctx.wifi_pass, pass, s_ctx.wifi_pass_len - 1);
    s_ctx.wifi_pass[s_ctx.wifi_pass_len - 1] = '\0';
    prefs()->putString("wifi_ssid", s_ctx.wifi_ssid);
    prefs()->putString("wifi_pass", s_ctx.wifi_pass);
    *s_ctx.wifi_creds_dirty = true;
    /* ADR-0020 §1: credentials are never logged - and the serial stream IS a
     * log (the host logger records every line to CSV). Ack without echoing
     * the SSID; confirm only that something was stored. */
    snprintf(reply, replen, "# ack wifi stored (ssid set, pass %s)",
             pass[0] ? "set" : "open/none");
}

#ifdef WDT_WEDGE_TEST
/*
 * !wedge - WATCHDOG WEDGE-TEST BUILD ONLY (#191 / #93).
 * Strands relay ch0 ON, then spins forever without feeding the task watchdog:
 * the chip must reset within ~WDT_TIMEOUT_MS, and the reboot's allRelaysOff()
 * must leave ch0 de-energized. Never returns; only in esp32dev_wdttest env.
 */
static void handle_wedge(const char *args, char *reply, size_t replen)
{
    (void)args;
    (void)reply;
    (void)replen;
    s_ctx.pump_set(0, true);
    Serial.printf("# ack wedge ch0=ON - hanging the loop; watchdog must reset "
                  "in <=%lums\n",
                  (unsigned long)s_ctx.wdt_timeout_ms);
    Serial.flush();
    for (;;) { /* no esp_task_wdt_reset() -> watchdog fires -> reset */
    }
}
#endif /* WDT_WEDGE_TEST */

/* ---- public API --------------------------------------------------------- */

void commands_init(commands_ctx_t *ctx)
{
    s_ctx =
        *ctx; /* shallow copy; pointer targets live in main.cpp for the session */

    /* Load persisted runtime config (#90): cadence + device identity. */
    Preferences *p = prefs();
    p->begin("plants", false); /* rw namespace; kept open for the session */

    uint32_t saved = p->getULong("cadence_ms", 0);
    if (saved >= s_ctx.cadence_floor_ms && saved <= s_ctx.cadence_ceil_ms) {
        *s_ctx.sample_period_ms = saved;
        *s_ctx.cadence_from_nvs = true;
    }

    char name[32];
    size_t n = p->getString("device_name", name, sizeof(name));
    if (n > 0 && name[0] != '\0') {
        strncpy(s_ctx.device_id, name, s_ctx.device_id_len - 1);
        s_ctx.device_id[s_ctx.device_id_len - 1] = '\0';
        *s_ctx.device_id_custom = true;
    } else {
        derive_default_id(s_ctx.device_id, s_ctx.device_id_len);
    }

    /* WiFi credentials (#21): load whatever !wifi persisted last session. Empty
     * (never set) leaves the connect-scaffold in WIFI_NET_IDLE - no attempt made. */
    size_t sn = p->getString("wifi_ssid", s_ctx.wifi_ssid, s_ctx.wifi_ssid_len);
    if (sn == 0) s_ctx.wifi_ssid[0] = '\0';
    size_t pn = p->getString("wifi_pass", s_ctx.wifi_pass, s_ctx.wifi_pass_len);
    if (pn == 0) s_ctx.wifi_pass[0] = '\0';

    /* Register all inbound serial-command handlers (#92). */
    serial_cmd_register("cad", handle_cad);
    serial_cmd_register("ping", handle_ping);
    serial_cmd_register("ver", handle_ver);
    serial_cmd_register("cfg", handle_cfg);
    serial_cmd_register("name", handle_name);
    serial_cmd_register("water", handle_water);
    serial_cmd_register("stop", handle_stop);
    serial_cmd_register("auto", handle_auto);
    serial_cmd_register("label", handle_label);
    serial_cmd_register("pos", handle_pos);
    serial_cmd_register("wifi", handle_wifi);
#ifdef WDT_WEDGE_TEST
    serial_cmd_register("wedge", handle_wedge);
#endif
}

void commands_poll(void)
{
    static char buf[48];
    static uint8_t len = 0;
    while (Serial.available() > 0) {
        int ci = Serial.read();
        if (ci < 0) break;
        char c = (char)ci;
        if (c == '\n' || c == '\r') {
            if (len == 0) continue;
            buf[len] = '\0';
            char reply[96];
            if (serial_cmd_dispatch(buf, reply, sizeof(reply)) !=
                SERIAL_CMD_IGNORED)
                Serial.println(reply);
            len = 0;
        } else if (len < sizeof(buf) - 1) {
            buf[len++] = c;
        } else {
            len = 0; /* oversized line: drop it */
        }
    }
}
