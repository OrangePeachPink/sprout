/*
 * wifi_net.h - WiFi connect-scaffold state machine (#21 desk-buildable slice,
 * extended with the captive-portal policy for #275).
 *
 * Pure C, no Arduino/WiFi.h dependency: this is the connect/retry/reconnect/
 * portal POLICY, native-testable with synthetic inputs. The Arduino-side glue
 * (main.cpp) owns the actual WiFi.begin()/softAP()/status() calls and just
 * feeds this state machine the observed connection status each loop tick,
 * acting on the edge-triggered "call begin() now" signal it returns and on
 * PORTAL-state edges (AP up on entry, AP down when CONNECTED).
 *
 * Portal policy (#275 / ADR-0020 §4): the config AP exists ONLY while not yet
 * configured (no credentials) or after repeated STA failures. While in PORTAL
 * with credentials the machine still retries STA on a LONG backoff (ESP32 runs
 * AP+STA concurrently), so a transient router outage self-heals without human
 * action; a success tears the AP down via the CONNECTED edge.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    WIFI_NET_IDLE, /* pre-init only; the first tick leaves it immediately */
    WIFI_NET_CONNECTING, /* an attempt is in flight (begin() was just called)   */
    WIFI_NET_CONNECTED, /* WiFi.status() == WL_CONNECTED as of the last tick   */
    WIFI_NET_FAILED, /* an attempt timed out; waiting out the retry backoff */
    WIFI_NET_PORTAL, /* config AP up: no creds, or too many failures (#275) */
} wifi_net_state_t;

typedef struct {
    uint32_t connect_timeout_ms; /* how long one CONNECTING attempt gets      */
    uint32_t retry_backoff_ms; /* FAILED -> wait this long before retrying  */
    uint32_t portal_after_failures; /* consecutive failures -> PORTAL         */
    uint32_t portal_retry_backoff_ms; /* PORTAL -> background STA retry pace  */
} wifi_net_cfg_t;

typedef struct {
    wifi_net_state_t state;
    unsigned long
        attempt_started_ms; /* when the current CONNECTING attempt began */
    unsigned long next_retry_ms; /* FAILED/PORTAL -> earliest retry time */
    uint32_t retry_count; /* consecutive failures since the last CONNECTED   */
    bool portal_origin; /* the in-flight attempt started from PORTAL (a
                           timeout returns there, not to FAILED)            */
} wifi_net_ctx_t;

/* Zero-initializes to WIFI_NET_IDLE. Call once at boot (and again when the
 * operator changes credentials, to force an immediate fresh attempt). */
void wifi_net_init(wifi_net_ctx_t *ctx);

/*
 * Call every loop() tick. Inputs are facts the caller already knows this tick:
 *   has_creds         - a non-empty SSID is stored (NVS-backed; !wifi/portal)
 *   arduino_connected - WiFi.status() == WL_CONNECTED right now
 *   now               - millis()
 *   cfg               - the policy constants (config.h)
 *
 * Returns true exactly on the tick the caller should call WiFi.begin(ssid,
 * pass) - edge-triggered, so the caller never calls begin() twice for one
 * attempt. The caller watches state EDGES for the AP: entering PORTAL -> AP
 * up; entering CONNECTED -> AP down.
 */
bool wifi_net_tick(wifi_net_ctx_t *ctx, bool has_creds, bool arduino_connected,
                   unsigned long now, const wifi_net_cfg_t *cfg);

/* Human-readable state name for banners/status pages/serial replies. */
const char *wifi_net_state_name(wifi_net_state_t s);

#ifdef __cplusplus
} /* extern "C" */
#endif
