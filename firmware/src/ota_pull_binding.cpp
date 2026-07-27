/*
 * ota_pull_binding.cpp — see ota_pull_binding.h.
 *
 * The ESP32 half of signed pull OTA (#1284 AC4). Dark by construction: the whole
 * TLS + esp_ota body is inside `#if OTA_PULL_ARMED`, so a build with no
 * OTA_FEED_URL provisioned carries none of it.
 */
#include "ota_pull_binding.h"

#include <Arduino.h> /* before config.h — config.h uses HIGH/LOW (relay levels) */

#include "config.h"

#if OTA_PULL_ARMED

#include "board_capability.h"
#include "ota_gate.h"
#include "ota_pull.h"
#include "ota_release_key.h"
#include "serial_cmd.h"

#include <WiFi.h>
#include <esp_crt_bundle.h>
#include <esp_http_client.h>
#include <esp_ota_ops.h>
#include <esp_partition.h>
#include <esp_task_wdt.h>
#include <string.h>

/* How many board classes the feed may list (classic + c5 today, headroom kept).
 * Static, not on the loop-task stack: one artifact is ~560 bytes. */
#define OTA_PULL_FEED_BOARDS 6
#define OTA_PULL_FEED_TEXT_MAX 2048 /* the feed is a handful of short lines */
#define OTA_PULL_STREAM_CHUNK 1024

/* ---- TLS GET (small bodies: the feed, the 64-byte .sig) -------------------
 * ESP-IDF esp_http_client + the Mozilla root bundle (esp_crt_bundle). The
 * signature — not the transport — is what authorises code (ADR-0026 D2), so the
 * trust model here only has to stop a casual MITM from wasting a download; it is
 * NOT the thing that keeps unsigned code from booting. Returns bytes read into
 * `buf` (0..cap), or -1 on any transport failure (fail-closed for the caller). */
static int ota_https_get(const char *url, uint8_t *buf, size_t cap)
{
    esp_http_client_config_t cfg = {};
    cfg.url = url;
    cfg.crt_bundle_attach = esp_crt_bundle_attach;
    cfg.timeout_ms = 15000;
    esp_http_client_handle_t h = esp_http_client_init(&cfg);
    if (!h) return -1;

    int result = -1;
    if (esp_http_client_open(h, 0) == ESP_OK) {
        /* fetch_headers returns the Content-Length (>=0) or -1 for a chunked
         * body. The feed and the .sig are small STATIC files served with a
         * length; a body that would overflow `buf`, or one whose length we can't
         * know up front, is a REJECT — never a silent truncation (the same rule
         * the feed parser applies to an over-long field). */
        int clen = esp_http_client_fetch_headers(h);
        if (esp_http_client_get_status_code(h) == 200 && clen >= 0 &&
            (size_t)clen <= cap) {
            size_t total = 0;
            bool io_ok = true;
            while (total < (size_t)clen) {
                int r = esp_http_client_read(h, (char *)buf + total,
                                             (int)((size_t)clen - total));
                if (r < 0) {
                    io_ok = false;
                    break;
                } /* read error -> closed */
                if (r == 0) break; /* early EOF */
                total += (size_t)r;
            }
            if (io_ok && total == (size_t)clen) result = (int)total;
        }
    }
    esp_http_client_close(h);
    esp_http_client_cleanup(h);
    return result;
}

/* fetch_feed callback: the feed text into the caller's buffer. */
static int ota_fetch_feed(void *ctx, char *buf, size_t cap)
{
    (void)ctx;
    if (WiFi.status() != WL_CONNECTED)
        return -1; /* unknown, not "empty feed" */
    return ota_https_get(OTA_FEED_URL, (uint8_t *)buf, cap);
}

/* The boot-slot switch — invoked by ota_gate_apply ONLY on OTA_ACCEPT, so a
 * verified image is the sole thing that can ever change what boots next. */
static bool ota_commit(void *ctx)
{
    const esp_partition_t *part = (const esp_partition_t *)ctx;
    return esp_ota_set_boot_partition(part) == ESP_OK;
}

/* Stream `image_url` into the INACTIVE slot, then verify the flashed bytes
 * against `sig` before touching the boot pointer. The wrong image lands in the
 * inactive slot and is never booted; even a verify we somehow got wrong is
 * caught by D3 confirmed-boot rollback (esp_ota_mark_app_valid, main.cpp). */
static ota_verdict_t ota_stream_verify_commit(const char *image_url,
                                              const uint8_t *sig,
                                              const uint8_t *pubkey)
{
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    if (!part) return OTA_REJECT_COMMIT_FAILED; /* no A/B slot to write */

    esp_http_client_config_t cfg = {};
    cfg.url = image_url;
    cfg.crt_bundle_attach = esp_crt_bundle_attach;
    cfg.timeout_ms = 30000;
    esp_http_client_handle_t h = esp_http_client_init(&cfg);
    if (!h) return OTA_REJECT_NO_IMAGE;

    ota_verdict_t verdict = OTA_REJECT_NO_IMAGE;
    esp_ota_handle_t ota = 0;
    bool ota_open = false;
    size_t total = 0;

    if (esp_http_client_open(h, 0) == ESP_OK) {
        esp_http_client_fetch_headers(h);
        if (esp_http_client_get_status_code(h) == 200 &&
            esp_ota_begin(part, OTA_SIZE_UNKNOWN, &ota) == ESP_OK) {
            ota_open = true;
            static uint8_t chunk[OTA_PULL_STREAM_CHUNK];
            bool io_ok = true;
            for (;;) {
                int r = esp_http_client_read(h, (char *)chunk, sizeof(chunk));
                if (r < 0) {
                    io_ok = false;
                    break;
                }
                if (r == 0) break; /* EOF */
                if (esp_ota_write(ota, chunk, (size_t)r) != ESP_OK) {
                    io_ok = false;
                    break;
                }
                total += (size_t)r;
                esp_task_wdt_reset(); /* a multi-MB write outlives the 8 s WDT */
            }
            /* esp_ota_end validates the image header; a partial/garbage transfer
             * fails here and never reaches the verify. */
            if (io_ok && total > 0 && esp_ota_end(ota) == ESP_OK) {
                ota_open = false;
                /* Map the freshly-written slot as one contiguous region and hand
                 * it to the S2 gate. ota_gate_apply verifies the ed25519 sig over
                 * the domain-separated image and calls ota_commit ONLY on a valid
                 * signature — so the boot slot moves iff the bytes are genuinely
                 * ours. Every other path leaves the running image in place. */
                const void *mapped = NULL;
                esp_partition_mmap_handle_t mh = 0;
                if (esp_partition_mmap(part, 0, total, ESP_PARTITION_MMAP_DATA,
                                       &mapped, &mh) == ESP_OK) {
                    verdict =
                        ota_gate_apply((const uint8_t *)mapped, total, sig, 64,
                                       pubkey, ota_commit, (void *)part);
                    esp_partition_munmap(mh);
                } else {
                    verdict = OTA_REJECT_NO_IMAGE;
                }
            } else {
                verdict = OTA_REJECT_NO_IMAGE;
            }
        }
    }
    if (ota_open)
        esp_ota_abort(ota); /* transfer failed before end -> discard */
    esp_http_client_close(h);
    esp_http_client_cleanup(h);
    return verdict;
}

/* apply callback: fetch the detached .sig, then stream+verify+commit the image.
 * The sig is fetched FIRST and length-checked so a bad/short signature costs a
 * 64-byte GET, not a multi-megabyte download that ota_gate would reject anyway. */
static ota_verdict_t ota_apply(void *ctx, const ota_pull_artifact_t *chosen,
                               const uint8_t *pubkey)
{
    (void)ctx;
    uint8_t sig[64];
    if (ota_https_get(chosen->sig_url, sig, sizeof(sig)) != (int)sizeof(sig))
        return OTA_REJECT_NO_SIG; /* absent / wrong-length sig -> fail closed */
    return ota_stream_verify_commit(chosen->image_url, sig, pubkey);
}

/* `!otapull` — one pull cycle, on demand. Blocks the loop for the transfer (WDT
 * fed in the stream loop); safe because autonomous dosing ships disarmed and
 * this is a deliberate bench command. On UPDATED the caller reboots to the new
 * slot; every other verdict is a no-op that names why. */
static void ota_pull_cmd(const char *args, char *reply, size_t replen)
{
    (void)args;
    static char feed[OTA_PULL_FEED_TEXT_MAX];
    static ota_pull_artifact_t scratch[OTA_PULL_FEED_BOARDS];
    ota_pull_transport_t transport = {ota_fetch_feed, ota_apply, NULL};

    ota_pull_run_t r =
        ota_pull_run(&transport, BOARD_CAP.name, PLANTS_FW_VERSION,
                     SPROUT_OTA_RELEASE_PUBKEY, feed, sizeof(feed), scratch,
                     OTA_PULL_FEED_BOARDS);

    snprintf(reply, replen, "# otapull %s", ota_pull_run_label(r));
    if (r == OTA_PULL_RUN_UPDATED) {
        Serial.println("# otapull: verified image staged - rebooting to it");
        Serial.flush();
        esp_restart();
    }
}

#endif /* OTA_PULL_ARMED */

void ota_pull_binding_register(void)
{
#if OTA_PULL_ARMED
    serial_cmd_register("otapull", ota_pull_cmd);
#endif
}

void ota_pull_binding_announce(void)
{
#if OTA_PULL_ARMED
    Serial.println("# OTA: signed-pull ARMED (feed provisioned) - !otapull "
                   "checks the release feed, verifies, and switches slots");
#else
    /* Absence stated, never silent (ADR-0028): a web-flashed board has no feed. */
    Serial.println("# OTA: signed-pull OFF - no feed provisioned at build time "
                   "(#1284). USB flashing unaffected.");
#endif
}
