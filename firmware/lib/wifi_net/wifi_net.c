#include "wifi_net.h"
#include <string.h>

void wifi_net_init(wifi_net_ctx_t *ctx)
{
    memset(ctx, 0, sizeof(*ctx));
    ctx->state = WIFI_NET_IDLE;
}

bool wifi_net_tick(wifi_net_ctx_t *ctx, bool has_creds, bool arduino_connected,
                   unsigned long now, uint32_t connect_timeout_ms,
                   uint32_t retry_backoff_ms)
{
    if (!has_creds) {
        ctx->state = WIFI_NET_IDLE;
        ctx->retry_count = 0;
        return false;
    }

    if (arduino_connected) {
        bool was_connected = (ctx->state == WIFI_NET_CONNECTED);
        ctx->state = WIFI_NET_CONNECTED;
        if (!was_connected) ctx->retry_count = 0;
        return false;
    }

    switch (ctx->state) {
    case WIFI_NET_IDLE:
        ctx->state = WIFI_NET_CONNECTING;
        ctx->attempt_started_ms = now;
        return true;

    case WIFI_NET_CONNECTING:
        if (now - ctx->attempt_started_ms >= connect_timeout_ms) {
            ctx->state = WIFI_NET_FAILED;
            ctx->retry_count++;
            ctx->next_retry_ms = now + retry_backoff_ms;
        }
        return false;

    case WIFI_NET_CONNECTED:
        /* dropped since the last tick - reconnect immediately, no backoff for a
         * fresh drop (backoff only applies after a CONNECTING attempt fails). */
        ctx->state = WIFI_NET_CONNECTING;
        ctx->attempt_started_ms = now;
        return true;

    case WIFI_NET_FAILED:
        if (now >= ctx->next_retry_ms) {
            ctx->state = WIFI_NET_CONNECTING;
            ctx->attempt_started_ms = now;
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
    }
    return "unknown";
}
