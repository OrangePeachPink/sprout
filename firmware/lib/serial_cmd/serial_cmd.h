/*
 * serial_cmd.h
 * -----------------------------------------------------------------------------
 * Framework-agnostic registry + dispatcher for host->device serial commands
 * (ADR-0011; #63 set_cadence, generalized in #92).
 *
 * The device is otherwise write-only; this is its one inbound path. A line is:
 *
 *     !<name>[,<args>]*HH
 *
 * where `*HH` is the 2-hex XOR over the body `<name>[,<args>]` (the same
 * NMEA-style checksum the telemetry rows use), so a corrupted command can never
 * silently take effect. A small REGISTRY maps a command name -> handler, so
 * adding a command is one registration that inherits the re-sync, checksum, and
 * reply plumbing. The MCU's serial RX feeds whole lines to
 * serial_cmd_dispatch(); no Arduino deps, so it unit-tests on the host.
 * -----------------------------------------------------------------------------
 */
#ifndef SERIAL_CMD_H
#define SERIAL_CMD_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Registry capacity - v1 set is cad/ping/ver/cfg/name/water/stop (7), with
 * headroom for the actuation epic's additions (#94). */
#define SERIAL_CMD_MAX 12

typedef enum {
    SERIAL_CMD_IGNORED =
        0, /* no '!' command in the line - ignore it, no reply  */
    SERIAL_CMD_OK, /* a handler ran; its '#' reply line is in `reply`   */
    SERIAL_CMD_ERR_CHECKSUM, /* a '!' command, but the *HH checksum
                                failed/missing */
    SERIAL_CMD_ERR_UNKNOWN /* a valid-checksum command, but no handler for it */
} serial_cmd_result_t;

/* A command handler. `args` is the comma-args after "!name," ("" if none),
 * already null-terminated; it writes a single '#'-prefixed reply line into
 * `reply` (each command owns its own ack/nak format). */
typedef void (*serial_cmd_handler_t)(const char *args, char *reply,
                                     size_t replen);

/* Empty the registry (used by tests; harmless otherwise). */
void serial_cmd_reset(void);

/* Map a command `name` (without the '!') to a handler. `name` must outlive the
 * registry (pass a string literal). Returns 0 on success, -1 if full or a
 * duplicate. */
int serial_cmd_register(const char *name, serial_cmd_handler_t handler);

/* Parse one received line: re-sync to '!', validate the *HH checksum over the
 * body, split into name + args, look up the handler and call it. On
 * SERIAL_CMD_OK the handler's line is in `reply`; on _ERR_CHECKSUM /
 * _ERR_UNKNOWN dispatch writes a
 * "# nak err=..." line into `reply`; on _IGNORED `reply` is set to "". */
serial_cmd_result_t serial_cmd_dispatch(const char *line, char *reply,
                                        size_t replen);

/* Handler helper: parse a base-10 uint32 from `s` (1..9 digits, no sign/space)
 * into *out. Returns 1 on a clean parse, 0 otherwise. Shared so numeric
 * commands agree. */
int serial_cmd_parse_u32(const char *s, uint32_t *out);

#ifdef __cplusplus
}
#endif

#endif /* SERIAL_CMD_H */
