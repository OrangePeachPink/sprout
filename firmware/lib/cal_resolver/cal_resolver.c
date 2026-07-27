/*
 * cal_resolver.c - see cal_resolver.h.
 */
#include "cal_resolver.h"

#include <string.h>

/* Injected Layer-2 table (main.cpp -> cal_class_defaults.h). */
static const cal_class_default_t *s_defaults = NULL;
static size_t s_count = 0;

/* Layer 3: the shared factory fallback - a never-bench-measured placeholder that
 * carries the #995-ratified classic in-soil ladder (so an unknown board still
 * classifies against the CURRENT band model, not the retired rail shape). Any
 * board with no class default lands here: monitor-only, CAL_TIER_FACTORY. */
static const cal_record_t k_factory_fallback = {
    "unknown",
    SENSOR_CLASS_CAPACITIVE_V2,
    {2293, 2086, 1879, 1636, 1393, 1150},
    "factory_placeholder",
    CAL_TIER_FACTORY,
};

void cal_resolver_init(const cal_class_default_t *defaults, size_t count)
{
    s_defaults = defaults;
    s_count = defaults ? count : 0;
}

/* Layer 1 backing store (#963). Fixed buffers so the slot owns its strings.
 * CAL_INSTANCE_STR_MAX lives in the header - the blob bound depends on it. */
typedef struct {
    bool present;
    cal_record_t rec;
    char board_class[CAL_INSTANCE_STR_MAX];
    char provenance[CAL_INSTANCE_STR_MAX];
} cal_instance_slot_t;

static cal_instance_slot_t s_instance[CAL_MAX_CHANNELS];

static void copy_str(char *dst, const char *src)
{
    size_t i = 0;
    if (!src) { dst[0] = '\0'; return; }
    for (; src[i] && i < CAL_INSTANCE_STR_MAX - 1; i++) dst[i] = src[i];
    dst[i] = '\0';
}

void cal_instance_set(int channel, const cal_record_t *rec)
{
    if (channel < 0 || channel >= CAL_MAX_CHANNELS || !rec) return;
    cal_instance_slot_t *s = &s_instance[channel];
    s->rec = *rec;
    copy_str(s->board_class, rec->board_class);
    copy_str(s->provenance, rec->provenance);
    s->rec.board_class = s->board_class; /* re-point at OUR copies */
    s->rec.provenance = s->provenance;
    s->present = true;
}

void cal_instance_clear(int channel)
{
    if (channel < 0 || channel >= CAL_MAX_CHANNELS) return;
    s_instance[channel].present = false;
}

bool cal_instance_present(int channel)
{
    if (channel < 0 || channel >= CAL_MAX_CHANNELS) return false;
    return s_instance[channel].present;
}

/* ---- Layer 1 persistence codec (#963) ------------------------------------ */
/*
 * Wire layout (little-endian, self-describing):
 *
 *   'S' 'P' 'C' 'L'          magic
 *   u8   version             CAL_BLOB_VERSION
 *   u8   channels            slots that follow (<= CAL_MAX_CHANNELS)
 *   per channel:
 *     u8  present            0 -> nothing else for this slot
 *     u8  sensor_class
 *     u8  tier
 *     u16 anchors[MOISTURE_BOUNDARY_COUNT]   DESCENDING (classifier contract)
 *     u8  len + bytes        board_class (no terminator on the wire)
 *     u8  len + bytes        provenance
 *   u16  crc                 CRC-16/CCITT-FALSE over every preceding byte
 *
 * `channels` is written rather than assumed so a 4-channel build can REJECT a
 * blob from a wider board instead of reading three slots and silently dropping
 * the fourth - a dropped slot is an invisible cal loss on one channel, which is
 * exactly the "looks fine, waters wrong" failure this codec exists to prevent.
 */
static uint16_t crc16_ccitt(const uint8_t *d, size_t n)
{
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < n; i++) {
        crc ^= (uint16_t)((uint16_t)d[i] << 8);
        for (int b = 0; b < 8; b++)
            crc = (crc & 0x8000u) ? (uint16_t)((crc << 1) ^ 0x1021u)
                                  : (uint16_t)(crc << 1);
    }
    return crc;
}

/* The classifier contract: boundary[] strictly DESCENDING as the level index
 * rises (moisture_classifier.h). A blob failing this would not merely be odd -
 * it would make band edges non-monotonic, so it is a reject, not a repair. */
static bool anchors_descending(const uint16_t *a)
{
    for (size_t i = 1; i < MOISTURE_BOUNDARY_COUNT; i++)
        if (a[i] >= a[i - 1]) return false;
    return true;
}

static size_t put_str(uint8_t *buf, size_t at, const char *s)
{
    size_t n = 0;
    while (s[n] && n < CAL_INSTANCE_STR_MAX - 1)
        n++;
    buf[at++] = (uint8_t)n;
    for (size_t i = 0; i < n; i++)
        buf[at++] = (uint8_t)s[i];
    return at;
}

size_t cal_instance_serialize(uint8_t *buf, size_t cap)
{
    if (!buf || cap < CAL_BLOB_MAX) return 0; /* never a partial write */
    size_t at = 0;
    buf[at++] = 'S';
    buf[at++] = 'P';
    buf[at++] = 'C';
    buf[at++] = 'L';
    buf[at++] = (uint8_t)CAL_BLOB_VERSION;
    buf[at++] = (uint8_t)CAL_MAX_CHANNELS;

    for (int ch = 0; ch < CAL_MAX_CHANNELS; ch++) {
        const cal_instance_slot_t *s = &s_instance[ch];
        buf[at++] = s->present ? 1u : 0u;
        if (!s->present) continue;
        buf[at++] = (uint8_t)s->rec.sensor_class;
        buf[at++] = (uint8_t)s->rec.tier;
        for (size_t i = 0; i < MOISTURE_BOUNDARY_COUNT; i++) {
            buf[at++] = (uint8_t)(s->rec.anchors[i] & 0xFFu);
            buf[at++] = (uint8_t)(s->rec.anchors[i] >> 8);
        }
        at = put_str(buf, at, s->board_class);
        at = put_str(buf, at, s->provenance);
    }

    uint16_t crc = crc16_ccitt(buf, at);
    buf[at++] = (uint8_t)(crc & 0xFFu);
    buf[at++] = (uint8_t)(crc >> 8);
    return at;
}

bool cal_instance_deserialize(const uint8_t *buf, size_t len)
{
    /* Stage into a scratch copy; commit only after the LAST check passes, so a
     * blob that fails validation halfway leaves the live store untouched. */
    cal_instance_slot_t staged[CAL_MAX_CHANNELS];
    memset(staged, 0, sizeof(staged));

    if (!buf || len < 8u || len > CAL_BLOB_MAX) return false;
    if (buf[0] != 'S' || buf[1] != 'P' || buf[2] != 'C' || buf[3] != 'L')
        return false;
    if (buf[4] != (uint8_t)CAL_BLOB_VERSION) return false;

    /* CRC before interpreting ANY field - a corrupt length byte must not steer
     * the parse. */
    uint16_t want = (uint16_t)(buf[len - 2] | ((uint16_t)buf[len - 1] << 8));
    if (crc16_ccitt(buf, len - 2u) != want) return false;

    size_t channels = buf[5];
    if (channels > CAL_MAX_CHANNELS) return false; /* wider board's blob */

    size_t at = 6;
    const size_t end = len - 2u; /* the CRC is not payload */
    for (size_t ch = 0; ch < channels; ch++) {
        if (at >= end) return false;
        uint8_t present = buf[at++];
        if (present > 1u) return false;
        if (!present) continue;
        if (at + 2u + 2u * MOISTURE_BOUNDARY_COUNT > end) return false;

        cal_instance_slot_t *s = &staged[ch];
        uint8_t sc = buf[at++];
        uint8_t tr = buf[at++];
        if (sc != (uint8_t)SENSOR_CLASS_CAPACITIVE_V2) return false;
        if (tr > (uint8_t)CAL_TIER_CHANNEL) return false;
        s->rec.sensor_class = (sensor_class_t)sc;
        s->rec.tier = (cal_tier_t)tr;

        for (size_t i = 0; i < MOISTURE_BOUNDARY_COUNT; i++) {
            s->rec.anchors[i] =
                (uint16_t)(buf[at] | ((uint16_t)buf[at + 1] << 8));
            at += 2u;
        }
        if (!anchors_descending(s->rec.anchors)) return false;

        char *dsts[2] = {s->board_class, s->provenance};
        for (int k = 0; k < 2; k++) {
            if (at >= end) return false;
            size_t n = buf[at++];
            if (n >= CAL_INSTANCE_STR_MAX || at + n > end) return false;
            for (size_t i = 0; i < n; i++)
                dsts[k][i] = (char)buf[at + i];
            dsts[k][n] = '\0';
            at += n;
        }
        s->rec.board_class = s->board_class;
        s->rec.provenance = s->provenance;
        s->present = true;
    }
    /* Trailing bytes mean the blob is not what it claims - reject rather than
     * accept a prefix that happens to parse. */
    if (at != end) return false;

    /* Committed. Slots beyond `channels` (a narrower board's blob) are cleared,
     * not left stale - a restore states the whole store, not a patch. */
    for (int ch = 0; ch < CAL_MAX_CHANNELS; ch++) {
        s_instance[ch] = staged[ch];
        /* re-point the record at THIS array's buffers, not the scratch copy's */
        s_instance[ch].rec.board_class = s_instance[ch].board_class;
        s_instance[ch].rec.provenance = s_instance[ch].provenance;
    }
    return true;
}

const cal_record_t *cal_instance_lookup(const char *board_class,
                                        sensor_class_t sensor_class,
                                        int channel)
{
    if (channel < 0 || channel >= CAL_MAX_CHANNELS) return NULL;
    const cal_instance_slot_t *s = &s_instance[channel];
    if (!s->present) return NULL;
    /* An owner record is for THIS board class + sensor class - a probe moved to
     * a different board must not silently inherit the old board's calibration. */
    if (board_class && s->rec.board_class[0] &&
        strcmp(board_class, s->rec.board_class) != 0)
        return NULL;
    if (s->rec.sensor_class != sensor_class) return NULL;
    return &s->rec;
}

static const cal_record_t *class_default_lookup(const char *board_class,
                                                sensor_class_t sensor_class,
                                                int channel)
{
    if (board_class == NULL) return NULL;
    for (size_t i = 0; i < s_count; i++) {
        const cal_class_default_t *d = &s_defaults[i];
        if (d->record.sensor_class != sensor_class) continue;
        if (d->record.board_class == NULL) continue;
        if (strcmp(d->record.board_class, board_class) != 0) continue;
        if (d->channel < 0 || d->channel == channel) return &d->record;
    }
    return NULL;
}

const cal_record_t *cal_resolve(const char *board_class,
                                sensor_class_t sensor_class, int channel)
{
    const cal_record_t *r =
        cal_instance_lookup(board_class, sensor_class, channel); /* Layer 1 */
    if (r) return r;
    r = class_default_lookup(board_class, sensor_class, channel); /* Layer 2 */
    if (r) return r;
    return &k_factory_fallback; /* Layer 3 */
}

const char *cal_tier_label(cal_tier_t tier)
{
    switch (tier) {
    case CAL_TIER_CHANNEL:
        return "channel-cal";
    case CAL_TIER_BOARD:
        return "board-cal";
    case CAL_TIER_FACTORY:
    default:
        return "uncalibrated"; /* the factory floor is never bench-measured */
    }
}
