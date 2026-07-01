/*
 * wifi_net.h - WiFi connect-scaffold state machine (#21 desk-buildable slice).
 *
 * Pure C, no Arduino/WiFi.h dependency: this is the connect/retry/reconnect POLICY,
 * native-testable with synthetic inputs. The Arduino-side glue (main.cpp) owns the
 * actual WiFi.begin()/WiFi.status() calls and just feeds this state machine the
 * observed connection status each loop tick, acting on the edge-triggered "call
 * begin() now" signal it returns.
 *
 * Scope: connect + automatic reconnect with backoff. Does NOT cover captive-portal
 * onboarding (#275, separate), RSSI telemetry (a later slice), or control-endpoint
 * auth (#21's fuller scope) - this is the prerequisite #276/#278 need: "is WiFi up."
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    WIFI_NET_IDLE, /* no credentials stored, or WiFi off for this board */
    WIFI_NET_CONNECTING, /* an attempt is in flight (begin() was just called)   */
    WIFI_NET_CONNECTED, /* WiFi.status() == WL_CONNECTED as of the last tick   */
    WIFI_NET_FAILED, /* an attempt timed out; waiting out the retry backoff */
} wifi_net_state_t;

typedef struct {
    wifi_net_state_t state;
    unsigned long
        attempt_started_ms; /* when the current CONNECTING attempt began */
    unsigned long
        next_retry_ms; /* FAILED -> earliest time to retry           */
    uint32_t retry_count; /* consecutive failures since the last CONNECTED   */
} wifi_net_ctx_t;

/* Zero-initializes to WIFI_NET_IDLE. Call once at boot. */
void wifi_net_init(wifi_net_ctx_t *ctx);

/*
 * Call every loop() tick. Inputs are facts the caller already knows this tick:
 *   has_creds         - a non-empty SSID is stored (NVS-backed, set via !wifi)
 *   arduino_connected - WiFi.status() == WL_CONNECTED right now
 *   now               - millis()
 *   connect_timeout_ms - how long a CONNECTING attempt gets before it's FAILED
 *   retry_backoff_ms   - how long a FAILED attempt waits before retrying
 *
 * Returns true exactly on the tick the caller should call WiFi.begin(ssid, pass) -
 * edge-triggered, so the caller never calls begin() twice for one attempt.
 */
bool wifi_net_tick(wifi_net_ctx_t *ctx, bool has_creds, bool arduino_connected,
                   unsigned long now, uint32_t connect_timeout_ms,
                   uint32_t retry_backoff_ms);

/* Human-readable state name for banners/status pages/serial replies. */
const char *wifi_net_state_name(wifi_net_state_t s);

#ifdef __cplusplus
} /* extern "C" */
#endif
