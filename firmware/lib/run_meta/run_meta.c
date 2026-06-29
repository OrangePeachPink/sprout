/*
 * run_meta.c - see run_meta.h.
 */
#include "run_meta.h"
#include "serial_cmd.h" /* serial_cmd_parse_u32 - the project's channel parser */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/*
 * Copy src into dst[dstlen], mapping CSV-hostile bytes (',' + control chars) to
 * '_' so a label/position can never break a row or the device CSV columns.
 * Always NUL-terminates.
 */
static void copy_clean(char *dst, size_t dstlen, const char *src) {
    size_t j = 0;
    if (dstlen == 0) return;
    for (size_t i = 0; src && src[i] && j < dstlen - 1; i++) {
        char c = src[i];
        dst[j++] = (c == ',' || c < 0x20 || c == 0x7f) ? '_' : c;
    }
    dst[j] = '\0';
}

void run_meta_init(run_meta_t *m, const char *default_label,
                   const char *default_position, int num_channels) {
    if (num_channels < 0) num_channels = 0;
    if (num_channels > RUN_META_MAX_CH) num_channels = RUN_META_MAX_CH;
    m->num_channels = num_channels;
    copy_clean(m->run_label, sizeof(m->run_label), default_label);
    for (int ch = 0; ch < RUN_META_MAX_CH; ch++)
        copy_clean(m->sensor_position[ch], RUN_META_POS_MAX, default_position);
}

const char *run_meta_label(const run_meta_t *m) { return m->run_label; }

const char *run_meta_position(const run_meta_t *m, int ch) {
    if (ch < 0 || ch >= m->num_channels) return "";
    return m->sensor_position[ch];
}

int run_meta_set_label(run_meta_t *m, const char *arg, char *reply,
                       size_t replen) {
    if (arg == NULL || arg[0] == '\0') {
        snprintf(reply, replen, "# nak err=label (use: !label,<run_label>)");
        return 0;
    }
    copy_clean(m->run_label, sizeof(m->run_label), arg);
    snprintf(reply, replen, "# ack label run=%s", m->run_label);
    return 1;
}

int run_meta_set_position(run_meta_t *m, const char *arg, char *reply,
                          size_t replen) {
    const char *comma = arg ? strchr(arg, ',') : NULL;
    if (comma == NULL || comma == arg || comma[1] == '\0') {
        snprintf(reply, replen, "# nak err=parse (use: !pos,<ch>,<name>)");
        return 0;
    }
    char   chbuf[12];
    size_t chlen = (size_t)(comma - arg);
    if (chlen >= sizeof(chbuf)) {
        snprintf(reply, replen, "# nak err=parse (use: !pos,<ch>,<name>)");
        return 0;
    }
    memcpy(chbuf, arg, chlen);
    chbuf[chlen] = '\0';
    uint32_t ch;
    if (!serial_cmd_parse_u32(chbuf, &ch)) {
        snprintf(reply, replen, "# nak err=parse (use: !pos,<ch>,<name>)");
        return 0;
    }
    if ((int)ch >= m->num_channels) {
        snprintf(reply, replen, "# nak err=channel ch=%lu n=%d",
                 (unsigned long)ch, m->num_channels);
        return 0;
    }
    copy_clean(m->sensor_position[ch], RUN_META_POS_MAX, comma + 1);
    snprintf(reply, replen, "# ack pos ch=%lu pos=%s", (unsigned long)ch,
             m->sensor_position[ch]);
    return 1;
}
