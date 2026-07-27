#ifndef SPROUT_OTA_PULL_BINDING_H
#define SPROUT_OTA_PULL_BINDING_H

/*
 * ota_pull_binding — #302 S3 / #1284 AC4: the HARDWARE half of the pull OTA.
 *
 * ota_pull_run() (lib/ota_pull, AC3) is pure logic with two injected callbacks;
 * this TU supplies the real ones for the ESP32: an HTTPS `fetch_feed` and an
 * `apply` that streams the chosen image to the inactive OTA slot, verifies its
 * signature with the S2 gate, and switches the boot slot ONLY on a valid
 * signature. Isolated here (not main.cpp) because it drags in TLS + esp_ota,
 * and because it compiles to NOTHING unless a feed was provisioned at build
 * time (OTA_PULL_ARMED) — a public build stays dark, TLS and all.
 *
 * AC4 is desk-buildable (this compiles + composes the proven verify fence). The
 * live pull + the mis-signed / wrong-board REFUSAL are AC5 — hardware, bench.
 */

#ifdef __cplusplus
extern "C" {
#endif

/* Register the `!otapull` serial command. No-op when the pull path is dark. */
void ota_pull_binding_register(void);

/* Print the armed/dark status line (ADR-0028: absence is stated, never silent). */
void ota_pull_binding_announce(void);

#ifdef __cplusplus
}
#endif

#endif /* SPROUT_OTA_PULL_BINDING_H */
