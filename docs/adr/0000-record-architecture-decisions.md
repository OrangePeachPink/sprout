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
   against it. **At v1.0.0 (the loud launch — NOT the 2026-07-09 soft flip) the policy flips to append-only** — from
then a
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
prototype's history faithfully. (Execution belongs to the architecture/firmware lane.)

## The register

*Grouped by domain, hub-first — the crawl to current truth is one hop. One line per ADR; the *why* lives
in each ADR. (First-cut grouping, #1462 — Workflow may re-slot a borderline row; a fold updates one line.)*

### Process & governance — how the project runs

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0000](0000-record-architecture-decisions.md) | This ADR: the register, numbering, status lifecycle, and **when a decision earns an ADR** | **Accepted** | Maintainer / meta |
| [0002](0002-process-tiers.md) | Process tiers — the project's engineering-process choices | **Accepted** | Maintainer |
| [0003](0003-work-pipeline.md) | Work pipeline — idea → spec → issue → release; the decision-vehicle ladder | **Accepted** | Workflow |
| [0015](0015-no-personal-information-policy.md) | No personal information in the repo — PII / hardware-id scrub on public export | **Accepted** | Maintainer / Workflow |

### Architecture & the control loop

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0001](0001-architecture-and-control-loop.md) | Architecture & control loop — closed-loop on soil moisture only *(hub)* | **Accepted** | Firmware |
| [0016](0016-actuation-wiring-seam.md) | Actuation wiring seam — the supervisor is the single ADC sampler | **Accepted** | Firmware / Data |
| [0038](0038-module-boundaries-and-the-import-rule.md) | Module boundaries & the import rule — five layers, imports go strictly down | **Accepted** | Trellis / DX / Data |

### Identity *(hub: 0027)*

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0027](0027-identity-model.md) | Identity model — device / channel / probe / plant / site; minted UUIDs, time-versioned bindings *(hub)* | **Accepted** | Trellis / Firmware |
| [0036](0036-sensor-identity-layers.md) | Sensor-identity layers — the wire carries the channel, never the probe *(satellite of 0027)* | **Accepted** | Trellis / Firmware / Data |
| [0019](0019-capability-and-sensor-matrix.md) | Capability & sensor matrix — per-board channel/sensor map *(satellite of 0027)* | **Accepted** | Firmware |

### Data, telemetry & the tiers *(hub: 0006)*

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0006](0006-data-architecture.md) | Data architecture — raw-immutable schema, calibration, quality *(hub)* | **Accepted** | Data |
| [0021](0021-parse-v1-telemetry-contract-boundary.md) | parse_v1 is the single telemetry-contract boundary | **Accepted** | Trellis / Data |
| [0031](0031-read-path-rollup-tiers.md) | Read-path rollup tiers — materialized aggregates over immutable raw | **Accepted** | Trellis / Data |
| [0025](0025-config-provenance.md) | Config provenance & no-auto-adjust — settings dialed-in-and-held, tagged on the data | **Accepted** | Trellis / Data |
| [0037](0037-production-epoch-and-data-admissibility.md) | Production epoch, data admissibility & the archive boundary | **Accepted** | Trellis / Data |
| [0012](0012-experiment-data-architecture.md) | Experiment data architecture — extends 0006 *(satellite of 0006)* | **Proposed** | Data |
| [0013](0013-environmental-data-architecture.md) | Environmental data architecture — external context + location privacy *(satellite of 0006)* | **Proposed** | Data |

### Experiment & lab capture

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0011](0011-experiment-capture-control-plane.md) | Experiment capture control plane — browser → host | **Proposed** | Data / Firmware |
| [0017](0017-experiment-notebook-and-notes-durability.md) | Experiment notebook data model & notes durability | **Accepted** | Data |
| [0014](0014-operator-control-plane.md) | Operator control plane — Monitor + Experiment under one plane | **Accepted** | Data |
| [0023](0023-contextual-env-columns.md) | Two context families — interior ambient vs exterior conditions | **Accepted** | Data |

### Calibration & the band model

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0022](0022-calibration-confidence-layer.md) | Calibration-confidence layer — local-reading vs pot-need gating; cal ownership | **Accepted** | Trellis / Firmware |
| [0029](0029-plant-pot-site-profile-registry.md) | Plant / pot / site profile registry — the inference dimensions | **Accepted** | Trellis / Data |
| [0035](0035-band-model-and-instrument-exceptions.md) | The band model & the instrument-exceptions taxonomy | **Accepted** | Trellis / Data |
| [0028](0028-optional-peripherals-doctrine.md) | Optional-peripherals doctrine — the minimum Sprout is one MCU + one sensor | **Accepted** | Trellis / Firmware |

### Transport & connectivity

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0018](0018-dual-mode-transport-and-durability.md) | Dual-mode transport & durability (untethered) | **Accepted** | Data |
| [0020](0020-network-identity-and-credentials.md) | Network identity & secrets (untethered) | **Accepted** | Firmware |

### Delivery, versioning & release *(hub: 0009)*

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0009](0009-versioning-and-release-policy.md) | Versioning & release policy — SemVer, auto-notes, release-feed curation *(hub)* | **Accepted** | Workflow |
| [0024](0024-multiplatform-pinning.md) | Toolchain pinning — one exact pin for the active matrix | **Accepted** | Trellis / DX |
| [0026](0026-firmware-delivery-and-update-security.md) | Firmware delivery & update security — web-flasher + signed pull OTA | **Accepted** | Trellis / Firmware |
| [0030](0030-version-identity-and-display-contract.md) | Version identity, build provenance & the display contract | **Accepted** | Trellis / Firmware |

### Design, brand & the surfaces *(hub: 0004)*

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| [0004](0004-design-system.md) | Design system & the token-consumption contract *(hub)* | **Accepted** | Design |
| [0007](0007-brand-guidelines.md) | Brand guidelines & voice | **Accepted** | Design |
| [0008](0008-design-system-v3-personality-layer.md) | Design system v3 — the personality layer | **Accepted** | Design |
| [0010](0010-design-library-front-door.md) | The Design Library is the single front door for design assets | **Accepted** | Design |
| [0032](0032-github-pages-design-library-serving.md) | GitHub Pages serving for the Design Library | **Accepted** | DX / Design |
| [0005](0005-application-surface-and-frontend.md) | Application surface & frontend — host presents as one app | **Accepted** | Data |
| [0033](0033-two-surface-architecture-home-and-workbench.md) | Home + Classic Sprout — a converging two-surface architecture | **Accepted** | Trellis / Design / Data |
| [0034](0034-pages-root-is-the-public-front-door.md) | The Pages root is Sprout's public front door | **Accepted** | Trellis / Design |

### Archived

| ADR | Decision | Status | Owner |
| --- | --- | --- | --- |
| — | *(archived)* [Sprout v0 combined architecture record](archive/sprout-v0-architecture.md) | Superseded by ADR-0001 | history |

*New ADRs append a row here when proposed. Any lane may author an ADR for an ADR-sized decision in its
own area — the test for whether it earns one is below.*

## When a decision earns an ADR

*(Consolidated here 2026-07-21, #1462 — "how ADRs work" belongs in the ADR-about-ADRs, not split across the
work-pipeline ADR. [ADR-0003 §10](0003-work-pipeline.md) keeps the decision-vehicle ladder; the ADR-specific
test lives here.)*

An ADR is the **top rung** of the change ladder (commit → issue + PR → ADR), reserved for decisions a future
contributor will need the *why* for. **Write an ADR when** any of these is true:

- **Hard or expensive to reverse** — architecture, data substrate, a public schema/API, repo structure, a
  framework choice.
- **Binds more than one lane** — a shared contract, interface, or cross-cutting policy.
- **Chooses among real alternatives** where the rejected options matter ("why not X?").
- **Establishes a convention everyone must follow** — naming, branching policy, the label taxonomy, the gate.
- **Sets a foundational default/boundary** — born-correct things, cheap now and painful to retrofit (line
  endings, env tool, data store, directory layout).
- You'd otherwise **re-explain the same "why" repeatedly** to new contributors.

**Good ADR material:** "GitHub Issues is the work ledger; IDs are `#N`" *(cross-lane convention)* · "Closed-loop
on soil moisture only; environmental sensors are logging-only" *(architecture; alternatives rejected)* · "Raw
CSV is immutable; the DuckDB tier is rebuildable" *(substrate; hard to reverse)*.

### NOT an ADR — use the lighter rung instead

- A bug fix or a single feature → an **issue + PR**.
- A reversible, low-stakes tweak (rename a var, nudge a threshold) → just the change.
- A routine choice with no real alternative → no record needed.
- Restating a decision already in another ADR → **link it**, don't duplicate.
- A how-to, runbook, or frequently-edited reference → **docs** (an ADR is a *decision*, not a living reference;
  pre-1.0 the ADR text is editable in place, §4).
- **An ADR that opens by restating another and extending it** → a **section of that ADR**, not a new one.
  *(Harvested #1462 — 0012/0013 both opened "ADR-0006 defines the data architecture…" → folded into 0006.)*
- **A stack of amendments on one ADR** → the reader should never reconstruct the current decision by applying
  ten patches. **Fold into clean current-state text + a dated changelog** (§ maintaining the set, below).
  *(Harvested #1462 — ADR-0035 carried ten.)*
- **A second doc for a concept that already has a hub ADR** → extend the hub, or file a **named satellite** the
  register groups under it — never a peer. *(Harvested #1462 — identity: 0027 is the hub; 0036/0019 satellites.)*

Rule of thumb: *if you'll edit it often, it's a doc; if you'll defend it later, it's an ADR.*

### The gate — prove you don't need a new ADR before you earn one

The antipatterns are only useful if consulted *before* minting. So a new ADR **carries its own justification**
— three lines near the top, answered honestly:

1. **Why this needs a new ADR** — which "write an ADR when" trigger it hits.
2. **Which existing ADRs you considered folding it under** — name them; the nearest-domain hub is first to check.
3. **Why it can't go under one of them** — the specific reason a section of an existing ADR won't do.

If you can't answer 3 convincingly, it's a section, an issue, or a doc — not a new ADR. **Certification checks
the block exists and is answered; a new ADR without it goes back.** The pass that trims the set is one-time; this
gate is permanent, and it is the only thing that keeps the set from re-sprawling.

*(Applied to its own author: the consolidation doctrine did **not** mint ADR-0039. Its ADR-governance half lives
here; the decision-vehicle ladder stays in ADR-0003 §10. Two existing homes, no new number — the gate
demonstrated on the first thing it governed.)*

## Maintaining the set — how the ADRs stay lean

*(Consolidated here 2026-07-21, #1462.)*

- **Fold-in-place, don't stack.** A material change rewrites the affected section to clean current-state text
  and records the change in a **dated changelog** at the ADR's foot. The reader gets one coherent decision, not
  a decision plus patches — history lives in the changelog and in git, never in the body's flow.
- **One domain, one hub.** A concept has a single **hub** ADR; extensions are **named satellites** the register
  groups under it, never peers. Identity: 0027 is the hub, 0036/0019 satellites.
- **Supersede-and-retire.** A superseded ADR is marked `Superseded by ADR-NNNN` and moved to the archived rows;
  it is never deleted (the citation must still resolve) and never left as a live-looking peer.
- **The register answers a question, it doesn't just list files.** Grouped by domain, hub-first, one line per
  ADR — the crawl to current truth is one hop.

## Consequences

- Contributors can read the project's decisions in order, with rationale, in one place.
- Decision history is preserved faithfully: the prototype record is archived, not overwritten.
- Each lane owns its own ADR rows; no lane silently rewrites another's decision.

## Revisit triggers

- The series grows large enough to want an automated index / tooling → adopt `adr-tools`.
- Any ADR would contain a secret, credential, or private personal datum → it doesn't; keep it that way
  (standing repo-hygiene practice).
