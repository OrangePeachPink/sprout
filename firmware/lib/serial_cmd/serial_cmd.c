/*
 * serial_cmd.c - see serial_cmd.h.
 */
#include "serial_cmd.h"
#include <stdio.h>
#include <string.h>

static uint8_t hexval(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
    if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
    return 0xFF;
}

/* --- the registry --------------------------------------------------------- */
typedef struct {
    const char *name;
    serial_cmd_handler_t handler;
} serial_cmd_entry_t;

static serial_cmd_entry_t s_cmds[SERIAL_CMD_MAX];
static int s_count = 0;

void serial_cmd_reset(void)
{
    s_count = 0;
}

int serial_cmd_register(const char *name, serial_cmd_handler_t handler)
{
    if (name == NULL || handler == NULL || s_count >= SERIAL_CMD_MAX) return -1;
    for (int i = 0; i < s_count; i++)
        if (strcmp(s_cmds[i].name, name) == 0) return -1; /* no duplicates */
    s_cmds[s_count].name = name;
    s_cmds[s_count].handler = handler;
    s_count++;
    return 0;
}

int serial_cmd_parse_u32(const char *s, uint32_t *out)
{
    if (s == NULL || *s == '\0') return 0;
    uint32_t v = 0;
    int digits = 0;
    for (const char *p = s; *p; p++) {
        if (*p < '0' || *p > '9') return 0;
        v = v * 10u + (uint32_t)(*p - '0');
        if (++digits > 9) return 0; /* overflow guard (fits uint32) */
    }
    if (out) *out = v;
    return 1;
}

static serial_cmd_result_t nak(char *reply, size_t replen, const char *err)
{
    if (reply && replen) snprintf(reply, replen, "# nak err=%s", err);
    return (strcmp(err, "checksum") == 0) ? SERIAL_CMD_ERR_CHECKSUM
                                          : SERIAL_CMD_ERR_UNKNOWN;
}

serial_cmd_result_t serial_cmd_dispatch(const char *line, char *reply,
                                        size_t replen)
{
    if (reply && replen) reply[0] = '\0';
    if (line == NULL) return SERIAL_CMD_IGNORED;

    /* Re-sync past any leading UART noise: a command starts at '!'. */
    const char *cmd = strchr(line, '!');
    if (cmd == NULL) return SERIAL_CMD_IGNORED;
    const char *body = cmd + 1; /* checksum covers the body after '!' */

    /* Validate the trailing "*HH" checksum over the body (both hex digits
     * present). */
    const char *star = strchr(cmd, '*');
    if (star == NULL || star <= body) return nak(reply, replen, "checksum");
    if (star[1] == '\0' || star[2] == '\0')
        return nak(reply, replen, "checksum");
    uint8_t hi = hexval(star[1]);
    uint8_t lo = hexval(star[2]);
    if (hi == 0xFF || lo == 0xFF) return nak(reply, replen, "checksum");
    uint8_t want = (uint8_t)((hi << 4) | lo);
    uint8_t got = 0;
    for (const char *p = body; p < star; p++)
        got ^= (uint8_t)*p;
    if (got != want) return nak(reply, replen, "checksum");

    /* Split the body into name + args at the first ','. */
    const char *comma = NULL;
    for (const char *p = body; p < star; p++) {
        if (*p == ',') {
            comma = p;
            break;
        }
    }
    const char *name_end = comma ? comma : star;
    size_t name_len = (size_t)(name_end - body);

    /* Copy the args (after the comma, up to '*') into a null-terminated buffer.
     */
    char argbuf[32];
    argbuf[0] = '\0';
    if (comma) {
        size_t alen = (size_t)(star - (comma + 1));
        if (alen >= sizeof(argbuf)) alen = sizeof(argbuf) - 1;
        memcpy(argbuf, comma + 1, alen);
        argbuf[alen] = '\0';
    }

    /* Look up the command by exact name and run it. */
    for (int i = 0; i < s_count; i++) {
        if (strlen(s_cmds[i].name) == name_len &&
            strncmp(s_cmds[i].name, body, name_len) == 0) {
            s_cmds[i].handler(argbuf, reply, replen);
            return SERIAL_CMD_OK;
        }
    }
    return nak(reply, replen, "unknown");
}
