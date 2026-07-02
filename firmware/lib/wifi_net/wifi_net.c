#include "wifi_net.h"
#include <string.h>

void wifi_net_init(wifi_net_ctx_t *ctx)
{
    memset(ctx, 0, sizeof(*ctx));
    ctx->state = WIFI_NET_IDLE;
}

bool wifi_net_tick(wifi_net_ctx_t *ctx, bool has_creds, bool arduino_connected,
                   unsigned long now, const wifi_net_cfg_t *cfg)
{
    if (!has_creds) {
        /* Fresh/cleared board: the config AP is the only way forward (#275).
         * ADR-0020 §4: the portal exists while not yet configured. */
        ctx->state = WIFI_NET_PORTAL;
        ctx->retry_count = 0;
        ctx->portal_origin = false;
        return false;
    }

    if (arduino_connected) {
        bool was_connected = (ctx->state == WIFI_NET_CONNECTED);
        ctx->state = WIFI_NET_CONNECTED;
        ctx->portal_origin = false;
        if (!was_connected) ctx->retry_count = 0;
        return false;
    }

    switch (ctx->state) {
    case WIFI_NET_IDLE:
        ctx->state = WIFI_NET_CONNECTING;
        ctx->attempt_started_ms = now;
        ctx->portal_origin = false;
        return true;

    case WIFI_NET_CONNECTING:
        if (now - ctx->attempt_started_ms >= cfg->connect_timeout_ms) {
            ctx->retry_count++;
            if (ctx->portal_origin ||
                ctx->retry_count >= cfg->portal_after_failures) {
                /* Repeated failure -> (stay in / fall to) the config AP, but
                 * keep background STA retries on the LONG portal backoff so a
                 * transient outage self-heals (#275). */
                ctx->state = WIFI_NET_PORTAL;
                ctx->next_retry_ms = now + cfg->portal_retry_backoff_ms;
            } else {
                ctx->state = WIFI_NET_FAILED;
                ctx->next_retry_ms = now + cfg->retry_backoff_ms;
            }
        }
        return false;

    case WIFI_NET_CONNECTED:
        /* dropped since the last tick - reconnect immediately, no backoff for
         * a fresh drop (backoff only applies after a failed attempt). */
        ctx->state = WIFI_NET_CONNECTING;
        ctx->attempt_started_ms = now;
        ctx->portal_origin = false;
        return true;

    case WIFI_NET_FAILED:
        if (now >= ctx->next_retry_ms) {
            ctx->state = WIFI_NET_CONNECTING;
            ctx->attempt_started_ms = now;
            ctx->portal_origin = false;
            return true;
        }
        return false;

    case WIFI_NET_PORTAL:
        /* AP is up (caller raised it on the entry edge). With creds stored,
         * keep trying STA in the background on the portal backoff; the AP
         * tears down only via the CONNECTED edge. */
        if (now >= ctx->next_retry_ms) {
            ctx->state = WIFI_NET_CONNECTING;
            ctx->attempt_started_ms = now;
            ctx->portal_origin = true; /* a timeout returns to PORTAL */
            return true;
        }
        return false;
    }
    return false; /* unreachable; keeps -Wswitch quiet without a default case */
}

const char *wifi_net_state_name(wifi_net_state_t s)
{
    switch (s) {
    case WIFI_NET_IDLE:
        return "idle";
    case WIFI_NET_CONNECTING:
        return "connecting";
    case WIFI_NET_CONNECTED:
        return "connected";
    case WIFI_NET_FAILED:
        return "failed";
    case WIFI_NET_PORTAL:
        return "portal";
    }
    return "unknown";
}
