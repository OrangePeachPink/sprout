# ADR-0000 — Record architecture (and process) decisions

**Status:** Accepted
**Date:** 2026-06-24
**Owner:** Maintainer
**Lane:** meta

---

## Context

Sprout began as a small single-board prototype, and its first architecture decision was captured in a
single combined record. The project has since grown into a multi-part system — firmware, a host-side
logging pipeline, an analytics dashboard with forecasting, and a design system — worked on across
several focused lanes (architecture/firmware, data/analytics, design, and issue-tracking/release),
coordinated by a maintainer.

A project at this size benefits from a consistent, browsable trail of *why* it is built the way it is,
so a new contributor can come up to speed by reading decisions in order rather than reverse-engineering
them from the code. This ADR establishes that trail.

## Decision

Use a **numbered Architecture Decision Record (ADR) series** under `docs/adr/`.

1. **Location & filename:** `docs/adr/NNNN-kebab-title.md`, zero-padded to four digits.
2. **Numbering:**
   - `0000` (this file) is the **meta-record**: the decision to use ADRs, the conventions, and the
     register. (This follows the common `adr-tools` / Nygard convention.)
   - `0001` and up are **real decisions, numbered chronologically across all kinds** — architecture,
     process, and tooling decisions share one sequence; they are not sub-numbered per category.
   - The **first real decision is `0001`**.
3. **One decision per file.** Keep each ADR focused; don't bundle unrelated decisions.
4. **Status lifecycle & editing policy:** `Proposed → Accepted` (or `Rejected` / `Deprecated`).
   **Pre-1.0 (current): ADRs are living documents — edit them in place** to keep them clean, current,
   and consistent; the **git history is the decision trail** (every change is a dated commit + diff +
   message — that *is* the "what changed and why"). Do **not** create in-document amendment chains or
   `Superseded by` stubs for ordinary pre-1.0 iteration. When you materially change an *accepted*
   decision: (a) write a clear commit message capturing the why, and (b) tell the lanes building
   against it. **At 1.0 / first public release the policy flips to append-only** — from then a
   substantive decision is *superseded by a new ADR* (linked back), so external readers get the
   lineage in the document, not only in git; a one-time "clean read" precedes the flip. Genuinely
   meaningful archived snapshots (e.g. the v0 record) are kept — this stops *new* churn, it does not
   erase real history.
5. **Each ADR names an Owner and a Lane.** A cross-lane ADR may assign a **per-row owner** so each lane
   confirms only its own rows.
6. **Format:** Context → Decision → Consequences → Revisit triggers.

### Treatment of the original prototype record

The project's first combined architecture/scope record (`docs/ADR.md`) was written for a smaller
prototype scope. Rather than port it forward verbatim, it is **archived and superseded**:

- It is preserved unchanged as the **v0 record** at `docs/adr/archive/sprout-v0-architecture.md` — a
  faithful snapshot of the prototype's design and reasoning, retained as history.
- A fresh, **right-sized `0001-architecture-and-control-loop.md`** is written for the current scope,
  *informed by* the v0 record but reflecting where the system actually is now.
- The archived v0 is marked **Superseded by ADR-0001**.

This keeps `0001` an accurate, current decision a new contributor can trust, while preserving the
prototype's history honestly. (Execution belongs to the architecture/firmware lane.)

## The register

| # | Title | Status | Owner / Lane |
|---|---|---|---|
| [0000](0000-record-architecture-decisions.md) | Record architecture (and process) decisions | Accepted | Maintainer / meta |
| [0001](0001-architecture-and-control-loop.md) | Architecture & control loop | **Accepted** — informed by, and supersedes, the archived v0 record | Firmware lane / architecture |
| [0002](0002-process-tiers.md) | Process tiers (the project's engineering process choices) | **Accepted** | Maintainer / cross-lane |
| [0003](0003-work-pipeline.md) | Work pipeline: ideas, specs, backlog, issues & releases | **Accepted** | Workflow lane |
| [0004](0004-design-system.md) | Design system & token-consumption contract | **Accepted** | Design lane |
| [0005](0005-application-surface-and-frontend.md) | Application surface & frontend | **Accepted** | Data lane |
| [0006](0006-data-architecture.md) | Data architecture (telemetry schema, calibration, quality, analysis tier) | **Accepted** | Data lane |
| [0007](0007-brand-guidelines.md) | Brand guidelines & voice | **Accepted** | Design lane |
| [0008](0008-design-system-v3-personality-layer.md) | Design system v3: the personality layer | **Accepted** | Design lane |
| [0009](0009-versioning-and-release-policy.md) | Versioning & release policy | **Accepted** | Workflow lane |
| [0010](0010-design-library-front-door.md) | The Design Library is the single front door for design assets | **Accepted** | Design lane |
| [0011](0011-experiment-capture-control-plane.md) | Experiment capture control plane (browser→host) | **Proposed** — direction agreed (Firmware #57); detail at sub-issue cut | Data + Firmware lanes |
| [0012](0012-experiment-data-architecture.md) | Experiment data architecture (extends ADR-0006) | **Proposed** — schema agreed (Firmware #57); detail at sub-issue cut | Data lane |
| [0013](0013-environmental-data-architecture.md) | Environmental data architecture (extends ADR-0006) | **Proposed** — Data-led; on-device section co-authored with Firmware at sub-issue cut | Data lane |
| [0014](0014-operator-control-plane.md) | Operator control plane (Monitor + Experiment under one plane; extends ADR-0011) | **Accepted** — maintainer-ratified 2026-07-03; shipped via the Operator-Experience epic #125; ratification note: the fleet poller (#582) rides the Monitor lifecycle (one Start governs both collection paths) | Data lane |
| [0015](0015-no-personal-information-policy.md) | No personal information policy (no PII / hardware identifiers collected, generated, committed, or published) | **Accepted** — drafted by Trellis, maintainer-ratified 2026-06-26 | Maintainer + Workflow / meta |
| [0016](0016-actuation-wiring-seam.md) | Actuation wiring seam: the supervisor is the single sample & actuation authority (extends ADR-0001) | **Accepted** — drafted by Trellis; Firmware + Data rows confirmed (#94 / #232), maintainer-ratified 2026-06-27 | Firmware / architecture (Data co-owns telemetry-derivation + health rows) |
| [0017](0017-experiment-notebook-and-notes-durability.md) | Experiment notebook data model + notes durability (extends ADR-0012 §5, ADR-0006) | **Accepted** — Data-led; ratified by Workflow on maintainer delegation 2026-06-27 | Data lane (Lab Notebook; model matches Design's notebook spec) |
| [0018](0018-dual-mode-transport-and-durability.md) | Dual-mode transport & durability: source-adapter seam + device-owned time, one schema across transports (untethered; extends ADR-0006) | **Accepted** — maintainer-ratified 2026-07-01, alongside schema v2 §11 (#492) (#268) | Data lane / architecture (cross-lane: Firmware) |
| [0019](0019-capability-and-sensor-matrix.md) | Capability & sensor matrix: per-board capability descriptor (contributor extension point) + per-channel sensor_type model (untethered) | **Accepted** — Firmware-confirmed + maintainer-ratified 2026-06-28 (#269) | Firmware lane / architecture (cross-lane: Design) |
| [0020](0020-network-identity-and-credentials.md) | Network identity & secrets: NVS-local credentials, synthetic hostname (no hardware IDs), no inbound exposure (untethered; extends ADR-0015) | **Accepted** — Firmware-confirmed + maintainer-ratified 2026-06-28 (#270) | Firmware lane / architecture |
| [0021](0021-parse-v1-telemetry-contract-boundary.md) | parse_v1 is the single telemetry contract boundary (extends ADR-0006) | **Accepted** — maintainer-ratified 2026-07-03; battle-tested before ratification (#294/#295 fixed; context/pressure/untethered all extended the one boundary); the schema-v2 revisit trigger already fired + is satisfied | Trellis (author) + Data lane |
| [0022](0022-calibration-confidence-layer.md) | Calibration-confidence layer: local-truth vs pot-truth gating — confidence stages + microzone-disagreement veto + contact-quality + plant-pathway profiles; the promotion gate for plant-deployed -> autonomous-enabled (extends ADR-0016) | **Accepted** — model ratified by maintainer 2026-06-30 (#400/#402); 5-prerequisite arm-gate incl. #18 + #410 (#411); thresholds tracked as non-blocking inputs (#412/#414/#416) | Trellis (author) + Firmware (enforcement) |
| [0023](0023-contextual-env-columns.md) | Two context families: interior ambient (proximity-class fill: plant_local → room → none; weather fenced out of interior temp/RH, pressure excepted) vs exterior conditions (weather+solar drive light/season analytics, never projected); die-temp excluded from context | **Accepted** — v2 reworked from the maintainer's design review + ratified same day (2026-07-02); Data confirms post-ratification | Data lane (v2 drafted by Workflow from maintainer direction) |
| [0024](0024-multiplatform-pinning.md) | Toolchain pinning: one *exact* pin for the whole active matrix on pioarduino (revised 2026-07-01, maintainer direction — supersedes the original per-target-isolation posture); exact-pin discipline survives, isolation is now a staging state for unproven platforms only (extends ADR-0019 / #283) | **Accepted** — revised + ratified by maintainer direction 2026-07-01 (#283) | Trellis (author) + DX/Firmware (execution) |
| [0025](0025-config-provenance.md) | Config provenance & no-auto-adjust: every reading-shaping setting exposed in the header + tagged on the data; inline volatile knobs (gain/itime) + a `config_id` snapshot for the stable surface; settings dialed-in-and-held, never silently auto-adjusted (extends ADR-0006) | **Proposed** — drafted by Trellis from #416; inline slice built (#452); config_id mechanism awaits Data + maintainer ratification | Trellis (author) + Data (config_id/header) |
| [0026](0026-firmware-delivery-and-update-security.md) | Firmware delivery & update security: OTA is **pull-only** (preserves ADR-0020 no-inbound) + **signed-images-only** (preserves ADR-0016 actuation authority) + A/B rollback + anti-rollback + NVS/identity preserved; web-flasher rides the existing provenance block + a bench-verified-only manifest gate; captive-AP stays config-only (extends ADR-0020 / ADR-0016) | **Proposed** — drafted by Trellis 2026-07-03 from the #302 skeleton + DX's #271 spike; both surfaces W2; signing-key custody + anti-rollback scope are Firmware-owned opens | Trellis (author) + Firmware (OTA/secure-boot) + DX (flasher page) |
| [0027](0027-identity-model.md) | Identity model: minted stable UUIDs for device / channel / probe / plant / site + a naming-independent mapping table (extends ADR-0018/0019/0020; reframes #602 coalescing as the legacy bridge) | **Proposed** — drafted by Firmware at the bench 2026-07-04 (#584 findings); Trellis owns/advances; open sub-decisions: 1b short-id wire placement (Trellis+Data vs the shared contract) + calibration portability (bench test) | Trellis (owner) + Firmware (author) + Data (registry substrate) |
| [0028](0028-optional-peripherals-doctrine.md) | Optional-peripherals doctrine: the minimum Sprout (1 MCU + 1 soil sensor) is *complete*; every peripheral optional; **absence is a first-class path** (sensorless-primary or honest-empty), never degraded/nag; the served dashboard is the authoritative status surface, on-device displays a redundant glance (extends ADR-0019) | **Proposed** — drafted by Trellis 2026-07-04 from the maintainer's ratified principle (#20/#19); gates the W2 display build (#20) | Trellis (author) + Firmware (descriptor) + Design (absence affordance) |
| — | *(archived)* [Sprout v0 combined architecture record](archive/sprout-v0-architecture.md) | Superseded by ADR-0001 | history |

*New ADRs append a row here when proposed. Any lane may author an ADR for an ADR-sized decision in its
own area — see [ADR-0003 §10](0003-work-pipeline.md) "When a decision merits an ADR."*

## Consequences

- Contributors can read the project's decisions in order, with rationale, in one place.
- Decision history is preserved honestly: the prototype record is archived, not overwritten.
- Each lane owns its own ADR rows; no lane silently rewrites another's decision.

## Revisit triggers

- The series grows large enough to want an automated index / tooling → adopt `adr-tools`.
- Any ADR would contain a secret, credential, or private personal datum → it doesn't; keep it that way
  (standing repo-hygiene practice).
