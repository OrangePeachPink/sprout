# ADR-0026 — Firmware delivery & update security (web-flasher + OTA)

**Status:** Accepted — *maintainer-ratified 2026-07-10 (v0.7.2 ADR batch), **with the maker-first scaling ruling**:
the fence is pull-only + software-verified signatures + A/B confirmed-boot rollback — and **no permanent eFuse burns,
ever, on kit boards** (no hardware Secure Boot, no fused anti-rollback counters; downgrade protection is a software
check). Boards must always remain USB-reflashable for any other project — the maker door is a feature of the threat
model, not a hole. Trellis edits this scaling + the Phase-0 acknowledgment into the body (living-document policy,
ADR-0000 §4).*

**Date:** 2026-07-03
**Owner:** Trellis (architecture) — Firmware owns OTA / secure-boot mechanics, DX owns the flasher page
**Lane:** architecture (cross-lane: Firmware · DX)
**Extends:** [ADR-0020](0020-network-identity-and-credentials.md) (network identity & no-inbound exposure) ·
[ADR-0016](0016-actuation-wiring-seam.md) (single actuation authority — whoever controls the firmware controls
the pumps)
**Relates:** #271 (web-flasher, DX spike) · #302 (OTA) · #275 (captive portal — OTA's WiFi prereq) · #457
(flasher page, merged) · #59 (go-public / hosting / encryption-at-rest) · #573 (identifier-guard) · epic #267 /
PRD-0005

---

## Context

Two Wave-2 slices change how firmware reaches a device, and both touch assumptions ADR-0020 made explicit:

- **Web-flasher (#271):** first flash from a browser (ESP Web Tools + the Web Serial API over USB), no IDE. The
  page (#457) is merged.
- **OTA (#302):** updates over WiFi after the first flash, no cable.

ADR-0020 §3 states the device "exposes nothing inbound … no remote management, **no inbound control of
actuation** — the single-authority rule (ADR-0016) must absorb any future remote path — **there is none now**."
OTA is precisely that future remote path. And because the running firmware *is* the ultimate actuation authority
(ADR-0016), an unauthenticated update path does not merely add a network surface — it hands an attacker the
pumps. This ADR designs the fence before either slice is built.

**The two surfaces are not the same risk** (grounded in DX's #271 spike):

| | Web-flasher (#271) | OTA (#302) |
|---|---|---|
| Transport | USB-local (Web Serial, user gesture, **desktop-Chromium only**) | Network (WiFi) |
| ADR-0020 tension | Low — USB is not the network-identity surface | **High — the inbound/remote path ADR-0020 anticipated** |
| Primary risk | Image **authenticity** (what got flashed?) | Authenticity **+ preserving no-inbound + actuation authority** |

DX's spike (#271) establishes three facts this ADR builds on: (1) Web Serial is **desktop-Chromium-only** — the
flasher is an onboarding-others tool, not the maintainer's path; (2) `factory_bin.py` already emits a custom
`provenance` block (sha256 / git / version) the page shows **before** Install; (3) the do-not-flash guard
(`BOARDS.md`) is today preserved **by omission** — `factory_bin` only builds the bench-verified classic image, so
there is no unverified S3/C5 image to offer.

**Phase-0 has since shipped (2026-07, #824 / #825 / #838):** a LAN-only OTA path — `just ota` runs **espota, which
*pushes* the image to the board's ArduinoOTA receiver** (mDNS-advertised, password-gated; `docs/OTA_FLASH.md`) —
plus A/B confirmed-boot rollback with a watchdog-feed, C5 recovery/OTA envs, and a board-aware `just ota`. It
realizes Decision 3 (A/B rollback), but as a bench mechanism it is **push to an inbound receiver — not yet the
pull-only, no-inbound model of Decision 1** — with a **placeholder password** and **no signature check**. So
**pull-only (Decision 1)**, the signed-only fence (Decision 2), and software anti-rollback (Decision 4) are all
hardening still to layer on before OTA is exposed beyond the trusted bench LAN. Phase-0 proved the *transport*
(image write + rollback); the pull + signing + anti-rollback fence is what makes it shippable.

## Decision

### 1. OTA is pull-only — this preserves ADR-0020's no-inbound invariant

The device **pulls** updates from a trusted source (a maintainer-controlled release location, over HTTPS) on its
own schedule or on an operator-initiated *local* trigger. It **never runs an inbound firmware-accepting
endpoint.** A push model (an open update port, remote management) is rejected — it reopens exactly what ADR-0020
§3 closed. Pull keeps the invariant literally true: the device reaches out, nothing listens.

### 2. Only signed firmware runs — this preserves ADR-0016's actuation authority

Images are **signed**, and the device **verifies the signature before applying** — a **software** signature check
(the maintainer's public key is embedded in the running firmware and verifies the update image), **not** hardware
Secure Boot v2. Per the maker-first scaling ruling (Status), **no eFuses are ever burned on kit boards**: no fused
public key, no hardware Secure-Boot enrollment. An update that fails verification is refused, not applied. This
still preserves ADR-0016: the firmware is the actuation authority, and "only maintainer-signed code runs *over the
OTA path*" is the network-era extension of that rule. **The maker door is deliberate:** a physically-present owner
can always USB-reflash any image (their board, their project) — the signature check gates the *remote* path, not
the cable. **Open (Firmware):** signing-key custody — where the private key lives, how the embedded public key is
stored and survives a factory reset — is Firmware's mechanics call; this ADR mandates *that* software signing
happens, not the key ceremony. **Concretized (2026-07-11, maintainer-approved, #989):** the scheme is
**ed25519** — small, modern, software-verifiable on the ESP32 with no eFuse; the boring default. The private
key lives only in the `SPROUT_SIGNING_KEY` GitHub Actions secret (CI is the sole signer, never a personal
machine); the public key is committed (`firmware/keys/`) so the running firmware + web-flasher verify against
a repo-shipped key. Ceremony + rotation: `docs/process/signing-key-ceremony.md`.

### 3. A/B partitions + confirmed-boot rollback — no brick on a bad update

OTA uses the standard ESP-IDF dual-partition path (`esp_ota` + `app_rollback`): write the inactive slot, boot it,
**confirm health, else roll back to the last-good image.** #302's own AC ("fail-safe to last-good, no bricking")
is met by the platform mechanism, not a hand-rolled one.

### 4. Anti-rollback (downgrade protection) — required for OTA

A monotonic version check prevents the **remote** OTA path from applying a **signed-but-known-vulnerable** older
image — a **software** counter (persisted in NVS / the app, per the maker-first ruling), **never a fused one-way
eFuse counter.** The no-burn consequence: a *physically-present* owner can still USB-flash any version (the maker
door), so this is best-effort downgrade protection on the *remote* path, not an absolute hardware lock — which
matches the home-hobby threat model (the LAN attacker is fenced; the owner is trusted). **Open (Firmware /
maintainer):** whether the software check lands in the first OTA slice or a fast-follow.

### 5. An update preserves identity + secrets, and never leaks them

An OTA or re-flash **preserves NVS** — WiFi credentials and the synthetic hostname install-suffix (ADR-0020
§1–2) survive the update; a device does not forget its network or change its `.local` name on a routine update.
The update path **never emits credentials** to serial or telemetry (the #547/#573 identifier-guard class — an
update log names the *version*, never the secret).

### 6. Web-flasher authenticity rides the existing provenance block + a verified-only manifest gate

- The flasher shows the `provenance` block (sha256 / git / version) **before Install** (already built, #457) —
  this is the authenticity surface; keep it mandatory.
- Served over an **HTTPS origin** (GitHub Pages + release assets) so the page and image cannot be MITM'd.
  *Where* it is hosted is **#59's call** (repo-visibility); this ADR requires HTTPS + provenance and defers the
  location, not duplicating #59.
- **The manifest may only include a `builds[]` entry for a bench-verified board** (DX's spike rule). Today the
  do-not-flash posture holds *by omission* (classic-only); the moment `factory_bin` becomes board-aware, a
  "verified" marker must gate manifest entries — turning the doc-only `BOARDS.md` rule (relay/pump-pin safety)
  **mechanical.** Multi-board web-flashing is a *separate future issue*, gated on that marker + S3/C5 bench
  verification (#443).

### 7. The captive-portal AP stays config-only — never a firmware endpoint

ADR-0020 §4's setup AP is local-link, short-lived, **config-only.** It never becomes a firmware-accepting surface
— no "reflash from the setup page." OTA is pull-only (Decision 1); the AP's scope is unchanged.

## Consequences

- The device gains an update path **without gaining an inbound surface** — ADR-0020 §3 stays literally true, and
  ADR-0016's "only authorized code actuates" extends to "only signed code runs."
- The web-flasher stays **low-risk by construction** (desktop-USB, user gesture, provenance-before-install,
  classic-only-by-omission) — the ADR keeps its requirements light (provenance + HTTPS + verified-marker) rather
  than over-engineering a USB path.
- **No brick, no silent downgrade:** A/B rollback + software anti-rollback make a failed or hostile update fail safe.
- **The maker door stays open by design:** no eFuse is ever burned, so a board is always USB-reflashable for any
  other project — the software signature check fences the *remote* OTA path, not the owner's cable. A feature of the
  threat model (LAN attacker fenced, physically-present owner trusted), not a hole.
- The do-not-flash safety rule becomes **enforceable** (the verified-marker gate) instead of documentation.
- **Named residual risks (not solved here):** signing-key custody + anti-rollback sequencing (Firmware);
  encryption-at-rest for NVS credentials remains #59's (ADR-0020 already flagged it); a compromised release
  origin is out of scope for the home-hobby model but bounded by signing (a MITM cannot forge a signed image).

## Rejected alternatives

- **Push-model OTA / a remote-management channel.** Rejected: reopens ADR-0020 §3's no-inbound invariant and
  ADR-0016's no-remote-actuation rule.
- **Unsigned OTA "for convenience."** Rejected: an unsigned update = arbitrary code = a full actuation bypass on
  a semi-trusted LAN (ADR-0020's stated threat model).
- **A device-served reflash page.** Rejected: it makes the config AP a firmware surface (Decision 7).
- **Hand-rolled dual-partition / rollback.** Rejected: ESP-IDF ships it; reinventing it is how a device bricks.

## Open (routed)

- **`for:firmware`** — signing-key custody + fuse strategy (Decision 2); anti-rollback slice-vs-fast-follow
  (Decision 4); the `factory_bin` "verified" marker (Decision 6 — DX's spike flagged it as Firmware's call).
- **`for:dx`** — on-page browser-support copy (desktop-Chromium-only) + the provenance-before-install UX;
  hosting rides #59.
- **Maintainer** — ratify the fence (pull-only + signed + verified-marker) before the W2 build starts, so the
  slices build against a reviewed contract instead of retrofitting one.

— Trellis 🪴
