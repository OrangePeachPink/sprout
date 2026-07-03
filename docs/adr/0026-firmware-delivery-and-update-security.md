# ADR-0026 — Firmware delivery & update security (web-flasher + OTA)

**Status:** Proposed — *drafted by Trellis (2026-07-03) from the reserved skeleton (#302 comment), developed
against DX's #271 scoping spike so it cites real constraints, not hypotheticals. Both surfaces are Wave 2. The
fence is designed here **before** the W2 build so it is not retrofitted; signing-key custody and anti-rollback
sequencing are the Firmware-owned open items.*
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

## Decision

### 1. OTA is pull-only — this preserves ADR-0020's no-inbound invariant

The device **pulls** updates from a trusted source (a maintainer-controlled release location, over HTTPS) on its
own schedule or on an operator-initiated *local* trigger. It **never runs an inbound firmware-accepting
endpoint.** A push model (an open update port, remote management) is rejected — it reopens exactly what ADR-0020
§3 closed. Pull keeps the invariant literally true: the device reaches out, nothing listens.

### 2. Only signed firmware runs — this preserves ADR-0016's actuation authority

Images are **signed**, and the device **verifies the signature before applying** (ESP-IDF Secure Boot v2 / signed
app image). An update that fails verification is refused, not applied. Rationale: the firmware is the actuation
authority (ADR-0016); "only maintainer-signed code runs" is the network-era extension of that rule. **Open
(Firmware):** signing-key custody — where the private key lives, how the public key is fused/stored, how it
survives a factory reset — is Firmware's mechanics call. This ADR mandates *that* signing happens, not the key
ceremony.

### 3. A/B partitions + confirmed-boot rollback — no brick on a bad update

OTA uses the standard ESP-IDF dual-partition path (`esp_ota` + `app_rollback`): write the inactive slot, boot it,
**confirm health, else roll back to the last-good image.** #302's own AC ("fail-safe to last-good, no bricking")
is met by the platform mechanism, not a hand-rolled one.

### 4. Anti-rollback (downgrade protection) — required for OTA

A monotonic version counter prevents re-flashing a **signed-but-known-vulnerable** older image (ESP-IDF
anti-rollback). **Open (Firmware / maintainer):** whether this lands in the first OTA slice or a fast-follow — it
is cheap with Secure Boot v2 but burns a one-way counter. Flagging the *sequencing*, not deferring the
requirement.

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
- **No brick, no silent downgrade:** A/B rollback + anti-rollback make a failed or hostile update fail safe.
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
