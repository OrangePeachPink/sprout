/*
 * pump_pulse.c - see pump_pulse.h.
 */
#include "pump_pulse.h"

void pump_pulse_init(pump_pulse_t *p, int channels, uint32_t default_ms,
                     uint32_t max_ms)
{
    p->channels = channels;
    p->default_ms = default_ms;
    p->max_ms = max_ms;
    p->active = false;
    p->ch = -1;
    p->off_at_ms = 0;
    p->armed_ms = 0;
}

pump_pulse_result_t pump_pulse_arm(pump_pulse_t *p, int ch, uint32_t req_ms,
                                   uint32_t now_ms)
{
    if (p->active) return PUMP_PULSE_ERR_BUSY; /* one pulse at a time */
    if (ch < 0 || ch >= p->channels) return PUMP_PULSE_ERR_CHANNEL;

    uint32_t dur = (req_ms == 0) ? p->default_ms : req_ms;
    if (dur > p->max_ms) dur = p->max_ms; /* HARD ceiling clamp */
    if (dur == 0) return PUMP_PULSE_ERR_DURATION;

    p->active = true;
    p->ch = ch;
    p->armed_ms = dur;
    p->off_at_ms = now_ms + dur;
    return PUMP_PULSE_ARMED;
}

bool pump_pulse_service(pump_pulse_t *p, uint32_t now_ms)
{
    if (!p->active) return false;
    /* Rollover-safe expiry: signed difference handles the uint32 millis() wrap.
     */
    if ((int32_t)(now_ms - p->off_at_ms) >= 0) {
        p->active = false;
        p->ch = -1;
        return true; /* just expired: caller turns the relay OFF */
    }
    return false;
}

bool pump_pulse_stop(pump_pulse_t *p)
{
    bool was = p->active;
    p->active = false;
    p->ch = -1;
    return was;
}

bool pump_pulse_active(const pump_pulse_t *p)
{
    return p->active;
}
int pump_pulse_channel(const pump_pulse_t *p)
{
    return p->active ? p->ch : -1;
}
uint32_t pump_pulse_armed_ms(const pump_pulse_t *p)
{
    return p->armed_ms;
}
