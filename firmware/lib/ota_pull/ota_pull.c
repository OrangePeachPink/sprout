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
