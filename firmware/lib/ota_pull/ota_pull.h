#ifndef SPROUT_OTA_PULL_H
#define SPROUT_OTA_PULL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * ota_pull — #302 S3a: the pull DECISION core (ADR-0026 D1/D4).
 *
 * The device reaches out; nothing listens (ADR-0020 §3 stays literally true).
 * This module owns the part of that which can be silently wrong: given what the
 * feed offers and what this board is, SHOULD an update be applied, and WHICH
 * artifact is it.
 *
 * Deliberately NOT here: the network fetch, TLS, and the feed's on-the-wire
 * format. Those are S3b - the transport binding and a feed contract that wants
 * ratifying before it is minted (see the PR). Splitting them keeps the decision
 * host-testable, which is where the failure modes below actually live.
 *
 * The applying half is ota_gate (S2): this module decides WHETHER, ota_gate
 * enforces that only a verified image reaches the boot slot. Neither trusts the
 * other's judgement - a device that decided to update still cannot switch slots
 * on an unsigned image.
 *
 * ---------------------------------------------------------------------------
 * TWO FAILURE MODES THIS EXISTS TO PREVENT
 *
 * 1. FLASHING THE WRONG BOARD'S IMAGE. The feed carries one artifact per board
 *    class. An esp32c5 image on a classic is a brick that USB has to recover.
 *    So the match is exact and absence is refusal - never "take the first one",
 *    never "close enough".
 *
 * 2. SILENTLY RE-IMPLEMENTING ANTI-ROLLBACK. This is the subtle one, and it is
 *    the reason this module exists rather than an `if (newer) update;` in
 *    main.cpp.
 *
 *    ADR-0026 D4 DECLINED anti-rollback for this device class, and named the
 *    remediation for a bad release: PULL IT FROM THE FEED and serve the fixed
 *    one. That remediation only works if devices actually apply what the feed
 *    offers. The natural-looking check - "update only if the offered version is
 *    NEWER" - quietly breaks it: curate a bad v0.9.1 away and re-serve v0.9.0,
 *    and every device refuses the fix, because the fix is older than what it is
 *    running. The safety mechanism the ADR chose would be disabled by a
 *    one-line convention nobody would flag in review.
 *
 *    So the rule is DIFFERENT, not NEWER. A downgrade is a legitimate,
 *    maintainer-initiated action here (the ADR's words: a monotonic counter
 *    "blocks every legitimate downgrade, not just bad ones"). Signing is what
 *    stops hostile images; the feed is what decides which signed image is
 *    current.
 * ---------------------------------------------------------------------------
 */

/* Bounds. Sized for the shipped shape, not aspiration: a version string like
 * "0.8.1" plus headroom, a board class like "esp32-classic", a URL that fits a
 * GitHub release asset path. Over-long fields are a REJECT, never a truncation -
 * a silently shortened URL would fetch the wrong thing. */
#define OTA_PULL_VERSION_MAX 24
#define OTA_PULL_BOARD_MAX 24
#define OTA_PULL_URL_MAX 256

/* One artifact the feed offers: the image for a specific board class. */
typedef struct {
    char
        board_class[OTA_PULL_BOARD_MAX]; /* must match BOARD_CAP.name exactly */
    char version[OTA_PULL_VERSION_MAX]; /* the release version, e.g. "0.8.1" */
    char image_url[OTA_PULL_URL_MAX]; /* the signed .bin                   */
    char sig_url[OTA_PULL_URL_MAX]; /* its detached .sig (ADR-0026 D2)   */
} ota_pull_artifact_t;

typedef enum {
    /* apply this artifact - it is for this board and differs from what runs */
    OTA_PULL_UPDATE = 0,
    /* the feed offers this board the version it is already running */
    OTA_PULL_UP_TO_DATE,
    /* the feed is structurally unusable (empty, over-long field, missing url) */
    OTA_PULL_FEED_INVALID,
    /* the feed is fine but offers nothing for THIS board class */
    OTA_PULL_NO_ARTIFACT_FOR_BOARD,
    /* the caller did not supply a usable current version / board identity */
    OTA_PULL_SELF_UNKNOWN
} ota_pull_decision_t;

/*
 * Validate one artifact in isolation: non-empty required fields, no over-long
 * field, and both URLs present (an image without a signature is not offerable -
 * ota_gate would reject it anyway, and finding that out after a multi-megabyte
 * download is worse than finding it out here).
 */
bool ota_pull_artifact_valid(const ota_pull_artifact_t *a);

/*
 * Pick this board's artifact from the feed and decide.
 *
 * `artifacts` may hold entries for several board classes; exactly the one whose
 * board_class equals `self_board` is considered. On OTA_PULL_UPDATE, `*chosen`
 * points at that entry (borrowed from the caller's array, never copied).
 *
 * `chosen` may be NULL if the caller only wants the verdict.
 */
ota_pull_decision_t ota_pull_decide(const ota_pull_artifact_t *artifacts,
                                    size_t count, const char *self_board,
                                    const char *self_version,
                                    const ota_pull_artifact_t **chosen);

/* Stable short token for logs / the update banner. Never NULL, never a secret
 * (ADR-0026 D5: an update log names the VERSION, never a credential). */
const char *ota_pull_decision_label(ota_pull_decision_t d);

#ifdef __cplusplus
}
#endif

#endif /* SPROUT_OTA_PULL_H */
