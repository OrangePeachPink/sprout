# ADR-0020 — Network identity & secrets (untethered)

**Status:** Proposed — *drafted by Workflow from Discussion #243;
Trellis-revised 2026-06-28 (stated threat model + hostname collision-suffix + `!name` sanitization, per
the #285 review); awaiting maintainer ratification + Firmware-lane confirm (#270)*
**Date:** 2026-06-27
**Owner:** Firmware lane / architecture
**Lane:** firmware
**Extends:** [ADR-0015](0015-no-personal-information-policy.md) (no PII / no hardware identifiers)
**Relates:** [PRD-0005](../prd/0005-untethered-sprout.md) R2 / R9 · #188 · epic #267 · slice #270

---

## Context

Untethered, the device joins the home WiFi and serves or pushes its own data — so it now handles **secrets**
(WiFi credentials) and acquires a **network identity** (a hostname, an IP, a server). ADR-0015 already bars
hardware identifiers and PII; this ADR extends that posture to the network surface, and must keep the
captive-portal onboarding (PRD-0005 R2) safe for a **right-sized home-hobby threat model** (stated in the
decision below). A device on someone's home network is a trust surface — get it born-correct, not retrofitted.

## Decision

**Credentials stay device-local secrets; identity is synthetic (no hardware IDs); the device exposes nothing
inbound beyond the LAN.** Concretely:

1. **WiFi credentials are NVS-local secrets.** Saved to NVS, **never logged, never emitted in telemetry, never
   served**. They exist only to join the network. (Extends ADR-0015: credentials are the canonical secret.)
2. **Synthetic network identity (no hardware IDs).** The hostname / mDNS name derives from the pretty / `!name`
   identity (#188) — e.g. `sprout-greenhouse-a1b2.local` — **never the MAC or a chip serial** (ADR-0015). A reset or
   rename changes it; nothing ties it to the silicon. To avoid LAN collisions (two `sprout-greenhouse` devices)
   the hostname is **`friendly` + a generated non-hardware install suffix** (NVS-stored, *not* silicon-derived).
   The friendly / `!name` text is **sanitized** — a personal-looking name is warned against — because the mDNS
   hostname **broadcasts on the LAN**, so a raw `!name` is a PII surface (ADR-0015; cousin of #290).
3. **No inbound exposure beyond the LAN.** The on-device server binds to the local network only: **no open ports
   to the internet, no remote management, no inbound control of actuation** (the single-authority rule, ADR-0016,
   must absorb any future remote path — there is none now). Local-network and fully-local only (PRD-0005
   non-goal: no cloud).
4. **The captive portal is right-sized for the home-hobby threat model.** The setup AP exists **only while not
   yet configured, or on repeated WiFi failure**, serves only the config page, accepts credentials over the
   **local AP link** → NVS → and tears down once joined; it never reflects stored credentials back. **Stated
   threat model:** the AP is **local-link, short-lived, config-only**; NVS credentials are **plaintext-at-rest** —
   acceptable for the home-hobby model, with **encryption-at-rest flagged for the formal threat model (#59)**.
   *In scope:* no credential reflection, no inbound internet exposure, no PII in identity. *Out of scope (named,
   not solved):* a nearby attacker associated to the open setup AP during the short config window — an accepted
   residual risk for v1, revisited at #59.

### Rejected alternatives

- **MAC-based hostname / identity** (the common IoT default). Rejected outright: ADR-0015 bars hardware
  identifiers; the synthetic name is the policy.
- **A cloud relay / remote-management channel.** Rejected: out of scope (no cloud), and it would open an inbound
  actuation path that the single-authority rule (ADR-0016) forbids.
- **Persisting credentials in plaintext logs for debugging.** Rejected: credentials are secrets; debugging uses
  the connection *state*, never the secret.

## Consequences

- The onboarding and serving surfaces are **born-correct on identity / secrets**, not retrofitted — cheap now,
  expensive later.
- A device is addressable on the LAN by a **friendly, re-nameable** hostname with no hardware leak.
- **No internet exposure** — the device is invisible from outside the home network; remote operation would be a
  deliberate future ADR if ever proposed.
- The captive portal (R2 / #275) and the on-device server (R8 / #276) build against this contract.
- The threat model is **stated, not implied** — plaintext-at-rest credentials and the open setup-AP config window
  are **named residual risks** (encryption-at-rest → #59), not hidden behind "safe by construction."

## Revisit triggers

- **Remote / off-LAN access is ever proposed:** this ADR *and* ADR-0016's single-authority rule must both be
  revisited (the remote path can bypass neither).
- **A formal threat model** (publish-readiness, #59): revisit whether NVS-plaintext credentials need
  encryption-at-rest for the target threat.
- **Multi-device discovery / aggregation on a LAN:** the install-suffix already prevents hostname collisions;
  revisit whether discovery needs a richer registry than mDNS.
