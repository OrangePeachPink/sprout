/*
 * run_meta.h - mutable run metadata for the plants controller (#321).
 *
 * run_label and per-channel sensor_position start as compile-time defaults
 * (config.h RUN_LABEL / SENSOR_POSITION) but must change at runtime: once the
 * bench moves probes between plants within a session, stale metadata becomes a
 * silent join hazard for Data (it joins on run_label / sensor_position / channel,
 * docs/TELEMETRY_SCHEMA.md). The !label / !pos serial commands (#92 registry)
 * mutate this state; the header reprint and each soil row read it back.
 *
 * Pure C, no Arduino — the handler-cores sanitize + format here so they are
 * native-testable (firmware/test). commands.cpp wires them to the registry;
 * persistence (NVS) is a deliberate non-goal for v1 (session-scoped is enough).
 */
#pragma once
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Sized for the bench's labels/positions with headroom; not config.h-coupled
 * (this module stays Arduino- and config-free). Keep RUN_META_MAX_CH >= the
 * firmware's NUM_SENSORS — run_meta_init clamps if a caller passes more. */
#ifndef RUN_META_LABEL_MAX
#define RUN_META_LABEL_MAX 40
#endif
#ifndef RUN_META_POS_MAX
#define RUN_META_POS_MAX 24
#endif
#ifndef RUN_META_MAX_CH
#define RUN_META_MAX_CH 4
#endif

typedef struct {
    char run_label[RUN_META_LABEL_MAX];
    char sensor_position[RUN_META_MAX_CH][RUN_META_POS_MAX];
    int  num_channels; /* active channels; positions [0, num_channels) are live */
} run_meta_t;

/*
 * Seed run_label from default_label and every channel's sensor_position from
 * default_position (the config.h compile-time values). num_channels is clamped
 * to [0, RUN_META_MAX_CH]. NULL defaults are treated as "". Both strings are
 * sanitized (see below) so a stray default can never break a CSV row.
 */
void run_meta_init(run_meta_t *m, const char *default_label,
                   const char *default_position, int num_channels);

/* Current run label (header). Never NULL. */
const char *run_meta_label(const run_meta_t *m);

/* Current sensor_position for a channel (per soil row); "" if out of range. */
const char *run_meta_position(const run_meta_t *m, int ch);

/*
 * !label,<run_label> core. Sets the active run label; formats an ack/nak into
 * reply. Empty arg is rejected (a session must carry a real label). Returns 1
 * on success (caller should reprint the header), 0 on nak.
 */
int run_meta_set_label(run_meta_t *m, const char *arg, char *reply,
                       size_t replen);

/*
 * !pos,<ch>,<name> core. Updates one channel's sensor_position; formats an
 * ack/nak into reply. Rejects a missing comma, a non-numeric / out-of-range
 * channel, and an empty name. Returns 1 on success, 0 on nak.
 */
int run_meta_set_position(run_meta_t *m, const char *arg, char *reply,
                          size_t replen);

#ifdef __cplusplus
} /* extern "C" */
#endif
