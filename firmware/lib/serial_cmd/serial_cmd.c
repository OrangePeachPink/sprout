/*
 * serial_cmd.c - see serial_cmd.h.
 */
#include "serial_cmd.h"
#include <string.h>

static uint8_t hexval(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
    if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
    return 0xFF;
}

cadence_parse_t cadence_cmd_parse(const char *line, uint32_t floor_ms,
                                  uint32_t ceil_ms, uint32_t *ms_out)
{
    if (line == NULL) return CADENCE_NOT_A_COMMAND;

    /* Re-sync past any leading UART noise: the command starts at "!cad,". */
    const char *cmd = strstr(line, "!cad,");
    if (cmd == NULL) return CADENCE_NOT_A_COMMAND;

    const char *body = cmd + 1;                 /* checksum covers "cad,<ms>"  */
    const char *star = strchr(cmd, '*');
    if (star == NULL || star <= body) return CADENCE_ERR_PARSE;

    /* Validate the "*HH" checksum suffix (both hex digits must be present). */
    if (star[1] == '\0' || star[2] == '\0') return CADENCE_ERR_PARSE;
    uint8_t hi = hexval(star[1]);
    uint8_t lo = hexval(star[2]);
    if (hi == 0xFF || lo == 0xFF) return CADENCE_ERR_PARSE;
    uint8_t want = (uint8_t)((hi << 4) | lo);
    uint8_t got = 0;
    for (const char *p = body; p < star; p++) got ^= (uint8_t)*p;
    if (got != want) return CADENCE_ERR_CHECKSUM;

    /* Parse the integer ms between "!cad," and "*". */
    const char *num = cmd + 5;                  /* skip "!cad,"                 */
    if (num >= star) return CADENCE_ERR_PARSE;
    uint32_t ms = 0;
    int digits = 0;
    for (const char *p = num; p < star; p++) {
        if (*p < '0' || *p > '9') return CADENCE_ERR_PARSE;
        ms = ms * 10u + (uint32_t)(*p - '0');
        if (++digits > 9) return CADENCE_ERR_PARSE;   /* overflow guard        */
    }
    if (digits == 0) return CADENCE_ERR_PARSE;

    if (ms_out) *ms_out = ms;                   /* report value even out of range */
    if (ms < floor_ms || ms > ceil_ms) return CADENCE_ERR_RANGE;
    return CADENCE_OK;
}

const char *cadence_err_name(cadence_parse_t status)
{
    switch (status) {
        case CADENCE_ERR_CHECKSUM: return "checksum";
        case CADENCE_ERR_RANGE:    return "range";
        case CADENCE_ERR_PARSE:    return "parse";
        default:                   return "";
    }
}
