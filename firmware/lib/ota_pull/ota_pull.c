/*
 * ota_pull.c - see ota_pull.h.
 */
#include "ota_pull.h"

#include <string.h>

/* A field is usable when it is non-empty AND terminated inside its buffer.
 * strnlen rather than strlen: these arrive from a parsed feed, and a field that
 * fills its buffer with no terminator must be a REJECT, not a read past the
 * end. */
static bool field_ok(const char *s, size_t cap)
{
    if (s == NULL) return false;
    size_t n = strnlen(s, cap);
    return n > 0u && n < cap;
}

bool ota_pull_artifact_valid(const ota_pull_artifact_t *a)
{
    if (a == NULL) return false;
    if (!field_ok(a->board_class, OTA_PULL_BOARD_MAX)) return false;
    if (!field_ok(a->version, OTA_PULL_VERSION_MAX)) return false;
    if (!field_ok(a->image_url, OTA_PULL_URL_MAX)) return false;
    /* An image with no signature is not offerable. ota_gate would reject it
     * (OTA_REJECT_NO_SIG) - but only AFTER a multi-megabyte download over a
     * household connection. Refusing here costs nothing and fails in the place
     * that can explain why. */
    if (!field_ok(a->sig_url, OTA_PULL_URL_MAX)) return false;
    return true;
}

ota_pull_decision_t ota_pull_decide(const ota_pull_artifact_t *artifacts,
                                    size_t count, const char *self_board,
                                    const char *self_version,
                                    const ota_pull_artifact_t **chosen)
{
    if (chosen) *chosen = NULL;

    /* Not knowing what we ARE is a refusal, not a default. Guessing a board
     * class is how the wrong image gets flashed. */
    if (!field_ok(self_board, OTA_PULL_BOARD_MAX) ||
        !field_ok(self_version, OTA_PULL_VERSION_MAX))
        return OTA_PULL_SELF_UNKNOWN;

    if (artifacts == NULL || count == 0u) return OTA_PULL_FEED_INVALID;

    /* Every entry must be well-formed, not just ours. A feed carrying a
     * malformed entry is a feed we do not understand, and acting on the half we
     * happen to parse is how a partial-trust bug starts. */
    for (size_t i = 0; i < count; i++)
        if (!ota_pull_artifact_valid(&artifacts[i]))
            return OTA_PULL_FEED_INVALID;

    const ota_pull_artifact_t *mine = NULL;
    for (size_t i = 0; i < count; i++) {
        /* EXACT match. No prefix, no case-folding, no "starts with esp32".
         * "esp32-c5" and "esp32-classic" share a prefix and are different
         * hardware; a fuzzy match here is a bricked board. */
        if (strncmp(artifacts[i].board_class, self_board, OTA_PULL_BOARD_MAX) ==
            0) {
            /* A feed offering the same board twice is ambiguous, and picking
             * either one is a guess. Refuse the whole feed. */
            if (mine != NULL) return OTA_PULL_FEED_INVALID;
            mine = &artifacts[i];
        }
    }
    if (mine == NULL) return OTA_PULL_NO_ARTIFACT_FOR_BOARD;

    /* DIFFERENT, not NEWER - see the header. Comparing for equality (rather
     * than ordering) is what keeps ADR-0026 D4's remediation working: curating
     * a bad release away and re-serving an older fixed one must actually reach
     * devices. A `>` here would silently reinstate the anti-rollback the ADR
     * declined, and would do it in a way that looks like ordinary good sense.
     *
     * It also means no version PARSER is needed. Nothing here has to agree with
     * semver, so a version string the feed invents ("0.8.1-rc2", a date, a
     * hash) can never be mis-ordered by us - it is either the string we are
     * running or it isn't. One less thing to get subtly wrong. */
    if (strncmp(mine->version, self_version, OTA_PULL_VERSION_MAX) == 0)
        return OTA_PULL_UP_TO_DATE;

    if (chosen) *chosen = mine;
    return OTA_PULL_UPDATE;
}

const char *ota_pull_decision_label(ota_pull_decision_t d)
{
    switch (d) {
    case OTA_PULL_UPDATE:
        return "update";
    case OTA_PULL_UP_TO_DATE:
        return "up-to-date";
    case OTA_PULL_FEED_INVALID:
        return "feed-invalid";
    case OTA_PULL_NO_ARTIFACT_FOR_BOARD:
        return "no-artifact-for-board";
    case OTA_PULL_SELF_UNKNOWN:
        return "self-unknown";
    }
    return "unknown";
}

/* ---- S3b: the feed parser ------------------------------------------------ */

/* Copy a value into a fixed field. Returns false if it would not FIT - a
 * truncated URL fetches the wrong thing, and a truncated board class could
 * collide with a different board's name. Never silently shortens. */
static bool set_field(char *dst, size_t cap, const char *src, size_t n)
{
    if (n == 0u || n >= cap) return false;
    memcpy(dst, src, n);
    dst[n] = '\0';
    return true;
}

/* One "key=value" token. `end` is one past the token's last byte. */
static bool apply_token(ota_pull_artifact_t *a, const char *tok,
                        const char *end)
{
    const char *eq = tok;
    while (eq < end && *eq != '=')
        eq++;
    if (eq == end || eq == tok) return false; /* no '=', or an empty key */

    size_t klen = (size_t)(eq - tok);
    const char *val = eq + 1;
    size_t vlen = (size_t)(end - val);

    /* UNKNOWN KEYS ARE IGNORED (see the header): the feed must be able to gain a
     * field without stranding deployed boards. A key we do not know is not an
     * error - it is a newer generator talking to an older device, which is the
     * case additive evolution exists to make survivable. */
    if (klen == 5u && strncmp(tok, "board", 5) == 0)
        return set_field(a->board_class, OTA_PULL_BOARD_MAX, val, vlen);
    if (klen == 7u && strncmp(tok, "version", 7) == 0)
        return set_field(a->version, OTA_PULL_VERSION_MAX, val, vlen);
    if (klen == 5u && strncmp(tok, "image", 5) == 0)
        return set_field(a->image_url, OTA_PULL_URL_MAX, val, vlen);
    if (klen == 3u && strncmp(tok, "sig", 3) == 0)
        return set_field(a->sig_url, OTA_PULL_URL_MAX, val, vlen);
    return true;
}

ota_pull_parse_t ota_pull_parse_feed(const char *text, size_t len,
                                     ota_pull_artifact_t *out, size_t cap,
                                     size_t *n)
{
    if (n) *n = 0;
    if (text == NULL || out == NULL || cap == 0u || n == NULL)
        return OTA_PULL_PARSE_MALFORMED;

    size_t count = 0;
    bool banner_seen = false;
    size_t i = 0;

    while (i < len) {
        size_t ls = i;
        while (i < len && text[i] != '\n')
            i++;
        size_t le = i; /* one past the line's last byte */
        if (i < len) i++; /* step over the newline */
        if (le > ls && text[le - 1] == '\r') le--; /* tolerate CRLF */

        /* trim */
        while (ls < le && (text[ls] == ' ' || text[ls] == '\t'))
            ls++;
        while (le > ls && (text[le - 1] == ' ' || text[le - 1] == '\t'))
            le--;
        if (ls == le) continue; /* blank */

        size_t llen = le - ls;
        if (!banner_seen) {
            /* The FIRST non-blank line must be the banner. It is the format's own
             * schema boundary: a v2 feed is refused whole rather than read as a
             * v1 feed that happens to parse. */
            size_t blen = strlen(OTA_PULL_FEED_BANNER);
            if (llen != blen ||
                strncmp(&text[ls], OTA_PULL_FEED_BANNER, blen) != 0)
                return OTA_PULL_PARSE_NO_BANNER;
            banner_seen = true;
            continue;
        }
        if (text[ls] == '#') continue; /* comment */

        if (count >= cap) return OTA_PULL_PARSE_TOO_MANY;

        ota_pull_artifact_t a;
        memset(&a, 0, sizeof(a));
        size_t p = ls;
        while (p < le) {
            while (p < le && (text[p] == ' ' || text[p] == '\t'))
                p++;
            if (p >= le) break;
            size_t ts = p;
            while (p < le && text[p] != ' ' && text[p] != '\t')
                p++;
            if (!apply_token(&a, &text[ts], &text[p]))
                return OTA_PULL_PARSE_MALFORMED;
        }

        /* MISSING KEYS ARE FATAL - the mirror of ignoring unknown ones. A device
         * must never fill in a default for something the feed failed to say. */
        if (!ota_pull_artifact_valid(&a)) return OTA_PULL_PARSE_MALFORMED;
        out[count++] = a;
    }

    if (!banner_seen) return OTA_PULL_PARSE_NO_BANNER;
    *n = count;
    return OTA_PULL_PARSE_OK;
}

const char *ota_pull_parse_label(ota_pull_parse_t p)
{
    switch (p) {
    case OTA_PULL_PARSE_OK:
        return "ok";
    case OTA_PULL_PARSE_NO_BANNER:
        return "no-banner";
    case OTA_PULL_PARSE_MALFORMED:
        return "malformed";
    case OTA_PULL_PARSE_TOO_MANY:
        return "too-many";
    }
    return "unknown";
}

/* ---- S3: the pull TRANSPORT orchestrator (#1284) -------------------------- */

ota_pull_run_t ota_pull_run(const ota_pull_transport_t *t,
                            const char *self_board, const char *self_version,
                            const uint8_t *pubkey, char *buf, size_t bufcap,
                            ota_pull_artifact_t *scratch, size_t scap)
{
    /* A misconfigured caller is a fail-closed case, not a crash. Missing feed
     * scratch is a "cannot even look" condition -> feed-unavailable, the same
     * as a dead network, because that is exactly the operational meaning. */
    if (!t || !t->fetch_feed || !t->apply || !buf || bufcap == 0 || !scratch ||
        scap == 0)
        return OTA_PULL_RUN_FEED_UNAVAILABLE;
    if (!field_ok(self_board, OTA_PULL_BOARD_MAX) ||
        !field_ok(self_version, OTA_PULL_VERSION_MAX))
        return OTA_PULL_RUN_SELF_UNKNOWN;

    /* 1. FETCH. A transport failure is "unknown", NEVER "empty feed" - the two
     * must not collapse, or a network blip reads as a curation (#1227). An
     * over-long return is treated as failure too: we will not parse past buf. */
    int got = t->fetch_feed(t->ctx, buf, bufcap);
    if (got < 0 || (size_t)got > bufcap) return OTA_PULL_RUN_FEED_UNAVAILABLE;

    /* 2. PARSE. All-or-nothing (S3b): a garbled feed is refused whole, so a
     * mangled line can never masquerade as a shorter feed. */
    size_t n = 0;
    if (ota_pull_parse_feed(buf, (size_t)got, scratch, scap, &n) !=
        OTA_PULL_PARSE_OK)
        return OTA_PULL_RUN_FEED_INVALID;

    /* 3. DECIDE. Exact board match, DIFFERENT-not-newer (S3a) so a curated
     * downgrade (ADR-0026 D4 remediation) still applies. */
    const ota_pull_artifact_t *chosen = NULL;
    switch (ota_pull_decide(scratch, n, self_board, self_version, &chosen)) {
    case OTA_PULL_UP_TO_DATE:
        return OTA_PULL_RUN_UP_TO_DATE;
    case OTA_PULL_NO_ARTIFACT_FOR_BOARD:
        return OTA_PULL_RUN_NO_ARTIFACT;
    case OTA_PULL_SELF_UNKNOWN:
        return OTA_PULL_RUN_SELF_UNKNOWN;
    case OTA_PULL_FEED_INVALID:
        return OTA_PULL_RUN_FEED_INVALID;
    case OTA_PULL_UPDATE:
        break; /* the only verdict that continues to apply */
    }
    /* decide returned UPDATE but no artifact - refuse rather than hand `apply`
     * a NULL. Defends the one precondition the callback is allowed to assume. */
    if (!chosen) return OTA_PULL_RUN_FEED_INVALID;

    /* 4. APPLY - the hardware half (stream -> S2 verify -> boot-slot switch).
     * The gate's verdict is decisive: ONLY OTA_ACCEPT stages a new image; every
     * other verdict leaves the running image in place. */
    return (t->apply(t->ctx, chosen, pubkey) == OTA_ACCEPT)
               ? OTA_PULL_RUN_UPDATED
               : OTA_PULL_RUN_REJECTED;
}

const char *ota_pull_run_label(ota_pull_run_t r)
{
    switch (r) {
    case OTA_PULL_RUN_UPDATED:
        return "updated";
    case OTA_PULL_RUN_UP_TO_DATE:
        return "up-to-date";
    case OTA_PULL_RUN_NO_ARTIFACT:
        return "no-artifact";
    case OTA_PULL_RUN_FEED_UNAVAILABLE:
        return "feed-unavailable";
    case OTA_PULL_RUN_FEED_INVALID:
        return "feed-invalid";
    case OTA_PULL_RUN_SELF_UNKNOWN:
        return "self-unknown";
    case OTA_PULL_RUN_REJECTED:
        return "rejected";
    }
    return "unknown";
}
