# ADR-0018 — Dual-mode transport & durability (untethered)

**Status:** Proposed — *drafted by Workflow from Discussion #243 + the Data lane's transport take;
Trellis-revised 2026-06-28 (schema-honesty + store-idempotency + raw-is-truth sharpening, per the #285 review);
awaiting maintainer ratification + Data-lane confirm. **Ratification is gated on schema v2 (#300).** (#268)*
**Date:** 2026-06-27
**Owner:** Data lane (telemetry derivation + the store) / architecture
**Lane:** data/analytics + firmware (cross-lane)
**Extends:** [ADR-0006](0006-data-architecture.md) (data architecture)
**Relates:** [PRD-0005](../prd/0005-untethered-sprout.md) R4 / R5 / R6 · epic #267 · slice #268

---

## Context

Today the host PC owns the data path: it reads the device over serial, stamps `timestamp_utc`, writes the CSV,
and serves the dashboard. Untethered (PRD-0005), there is no PC in the steady state — so *where does the data
live, how does it reach the dashboard, and who stamps the time?* all need answers that don't assume a serial
tether.

Per ADR-0001 the control loop is already offline, so this is purely an **observability** decision. Two facts
shape it:

- `TELEMETRY_SCHEMA` is **field-based, not a wire** — transport-agnostic by construction. This ADR *requires* a
  schema **v2** bump (device-owned time at the column level, row dedupe, sensor provenance) tracked in **#300**;
  canonical `TELEMETRY_SCHEMA.md`@`main` is still **v1 / host-time-authoritative** until #300 lands.
- Board storage and connectivity vary widely by tier and silicon (AVR: none; ESP32 flash: ~a day; + SD:
  months).

The risk is forking — a separate schema / dashboard / pipeline per transport. This ADR exists to prevent that.

## Decision

**The dashboard and analytics read from a *store*; the store is fed by a *source adapter*; the device owns its
own time. One schema across every transport and mode.** Concretely:

1. **Source-adapter seam (the core boundary).** `gather_inputs()` / `parse_files()` become **one adapter
   interface** behind the store. The serial-CSV reader is *one adapter*; others (a synced-file reader, a
   WiFi-push receiver, a device-served reader) implement the same interface. The dashboard never knows how the
   bytes arrived. Build the seam once; every tier and transport plugs in unchanged.
2. **The default durability model is store-and-forward, and the tethered PC is the degenerate hub.** A device
   buffers locally (flash, or SD where present) and forwards to a **store** — over serial when tethered, or over
   WiFi to a local hub / the device-served endpoint when untethered. "Tethered" is just the case where the hub
   is a directly-attached PC. One model, both modes. Store-and-forward **requires row idempotency** — a
   reconnect/replay must not duplicate rows; the dedupe key
   (`device_id`/`session_id`/`device_seq`/`record_type`/`sensor_id`, adding a `device_seq`) is defined by
   schema v2 (#300).
3. **The device owns its timestamp.** Untethered, no host stamps the time, so the device does: **NTP-on-connect**
   for WiFi tiers (UTC), with **monotonic-uptime + a synced boot-epoch** as the offline fallback, and an optional
   RTC where present. Every row carries a **`time_source` quality flag** (`ntp` / `rtc` / `uptime`) so consumers
   know how the time was set and never treat an unsynced clock as authoritative. The **column-level** model —
   whether `timestamp_utc` is nullable when `time_source=uptime`, `device_timestamp_utc` vs `ingest_timestamp_utc`,
   and the join / forecast / gap-detection rule for an unsynced row — is defined by schema v2 (#300), not asserted
   here.
4. **One schema, every transport.** Schema **v2** (once #300 lands) is the contract for all modes — a Tier-0
   untethered row and a tethered row are identical in shape. Until v2 lands this ADR stays **Proposed** and does
   *not* retroactively redefine the v1 contract on `main`. Transport and presentation differ; the data contract
   does not.
5. **Storage is capability-honest.** Onboard flash is an **hours-to-a-day buffer**; long standalone history needs
   **a microSD card or sync to a hub**. The "what you need" matrix states the real expectation per board — we
   never claim months of standalone history on bare flash.
6. **The store preserves ADR-0006's raw-is-truth.** "The store" is **append-only raw ingest + rebuildable derived
   views** — raw stays the single source of truth (ADR-0006); the store never becomes a second, mutable truth, and
   every served/derived view can be rebuilt from raw. (Guards the R3 contract boundary #293 and the C2/C3 honesty
   fixes #294/#295.)

### Rejected alternatives

- **Pick a single transport (e.g. MQTT-only) and build to it.** Rejected: forces every tier onto one wire,
  breaks no-WiFi boards, and couples the dashboard to a protocol. The adapter seam lets transport vary per tier
  without touching analytics.
- **Per-transport schemas / dashboards.** Rejected: the schema is already field-based and transport-agnostic;
  forking it is gratuitous and splits the analytics.
- **Host keeps owning time; the device emits only uptime.** Rejected: there is no host untethered. The device
  must self-timestamp, and the quality flag keeps it honest.

## Consequences

- The dashboard becomes **transport-agnostic** — one store-reading surface; new transports are adapters, not
  rewrites.
- **Tethered stays first-class** (the degenerate-hub case), so dev / experiment runs are unaffected.
- A new schema field (`time_source`) lands; consumers must handle the unsynced case — it is *not* a missing-data
  error.
- **This ADR cannot be ratified (Proposed→Accepted) until schema v2 (#300) lands** — it asserts a contract that
  #300 defines. Accepting 0018 and bumping the schema travel together.
- The interior of "which transport per tier" (push protocol, file format, sync cadence) is **left to the build
  slices** (#276 / #277 / #278) — this ADR fixes the *seam and the model*, not the wire.
- Local-vs-net read priority (PRD-0002 R9 / PRD-0005 open question) is **left open**; the adapter seam can
  express either without re-architecture.

## Revisit triggers

- **A real multi-device deployment** (several Sprouts on one LAN): revisit whether the hub becomes a first-class
  component (discovery, aggregation) rather than an adapter.
- **Cloud / remote operation is ever proposed** (currently a non-goal): the single-store model must absorb a
  remote sink — revisit.
- **Interior-band calibration lands:** no change to this seam, but the served payload's band semantics firm up.
