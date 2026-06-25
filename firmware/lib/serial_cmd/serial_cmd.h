/*
 * serial_cmd.h
 * -----------------------------------------------------------------------------
 * Framework-agnostic parser for host->device serial commands (ADR-0011, #63).
 *
 * The device is otherwise write-only; this is its one inbound path. v1 carries a
 * single command - set the sweep cadence at runtime:
 *
 *     !cad,<ms>*HH
 *
 * where `*HH` is the 2-hex XOR over the body `cad,<ms>` (the same NMEA-style
 * checksum the telemetry rows use), so a corrupted command can never silently
 * mis-set timing. The MCU's serial RX feeds whole lines here; no Arduino deps, so
 * it unit-tests on the host.
 * -----------------------------------------------------------------------------
 */
#ifndef SERIAL_CMD_H
#define SERIAL_CMD_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    CADENCE_NOT_A_COMMAND = 0, /* line is not a `!cad` command - ignore it     */
    CADENCE_OK,                /* valid; *ms_out holds the new cadence          */
    CADENCE_ERR_CHECKSUM,      /* `!cad` found but the `*HH` checksum failed    */
    CADENCE_ERR_PARSE,         /* `!cad` found but the body is malformed        */
    CADENCE_ERR_RANGE          /* parsed, but ms is outside [floor, ceil]       */
} cadence_parse_t;

/* Parse one received line for a `!cad,<ms>*HH` command. Re-syncs past leading
 * UART noise (looks for `!cad,`). Returns the status; writes the parsed cadence to
 * *ms_out on CADENCE_OK *and* CADENCE_ERR_RANGE (so the caller can echo the bad
 * value), and leaves it untouched otherwise. floor_ms/ceil_ms are inclusive. */
cadence_parse_t cadence_cmd_parse(const char *line, uint32_t floor_ms,
                                  uint32_t ceil_ms, uint32_t *ms_out);

/* Reason token for the `nak` line: "checksum" | "range" | "parse" | "". */
const char *cadence_err_name(cadence_parse_t status);

#ifdef __cplusplus
}
#endif

#endif /* SERIAL_CMD_H */
