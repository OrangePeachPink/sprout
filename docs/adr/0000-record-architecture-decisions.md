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
4. **Status lifecycle:** `Proposed → Accepted → Superseded by ADR-NNNN` (or `Deprecated`). ADRs are
   **append-only history**: never edit a past decision's substance or delete it — supersede it with a
   new ADR that links back. An ADR is a dated snapshot with revisit triggers, not a permanent contract.
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
| [0001](0001-architecture-and-control-loop.md) | Architecture & control loop | **Proposed** — informed by, and supersedes, the archived v0 record | Firmware lane / architecture |
| [0002](0002-process-tiers.md) | Process tiers (the project's engineering process choices) | **Proposed** — per-row owners to confirm; maintainer to accept | Maintainer / cross-lane |
| [0003](0003-work-pipeline.md) | Work pipeline: ideas, specs, backlog, issues & releases | **Proposed** | Workflow lane |
| 0004 | Design system + token-consumption contract | **Planned** | Design lane |
| [0005](0005-application-surface-and-frontend.md) | Application surface & frontend | **Proposed** | Data lane |
| [0006](0006-data-architecture.md) | Data architecture (telemetry schema, calibration, quality, analysis tier) | **Proposed** | Data lane |
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
