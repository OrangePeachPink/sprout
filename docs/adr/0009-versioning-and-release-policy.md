# ADR-0009 — Versioning & release policy

**Status:** Accepted (2026-06-24)
**Date:** 2026-06-24
**Owner:** Workflow lane
**Lane:** releases & versioning
**Elaborates:** [ADR-0003 §9](0003-work-pipeline.md) (releases) and [ADR-0002](0002-process-tiers.md) #9 (commits).

---

## Context

Sprout is at firmware `0.7.0` with **no release tags** — it has never cut a formal release. Milestones
and Releases (ADR-0003 §9) introduce one, which forces two questions this ADR answers: **how many
version lines** the project carries, and **the discipline for bumping the number.**

Two failure modes to avoid, both seen before:

1. **Single-version blindness** — one product version silently "ships" components that didn't change,
   so the number stops telling you what is actually *in* a given part (e.g. the firmware or an ML
   feature that didn't move is still labelled with the new umbrella version).
2. **Version inflation** — reflexively bumping the MINOR digit for small changes, drifting the number
   toward `1.0` long before the project is anywhere near stable or complete.

## Decision

### 1. A single product version line (for now)

Firmware + host + docs share **one SemVer**; a release is a snapshot of the whole repo at a version.
The `layer:firmware` / `layer:host` labels and the **CHANGELOG** record which parts actually changed, so
the single number stays meaningful. *(The revisit trigger for splitting this is below — deliberately
solid, per the failure mode above.)*

### 2. SemVer bump discipline (pre-1.0)

- **PATCH (`0.0.X`)** — fixes, non-functional changes, internal refactors, docs, tooling: anything with
  **no new user-facing capability.** This is the **default** for small changes.
- **MINOR (`0.X.0`)** — a **new user-facing feature or capability.** Not reflexive — earn it with actual
  new functionality, not "we touched the code."
- **MAJOR (`1.0.0` and up)** — `1.0.0` is a **deliberate "first stable / complete-enough" declaration,
  not a number you reach by incrementing.** After `1.0`, MAJOR = a breaking change.
- **Default to PATCH. Don't spin the MINOR. Don't drift toward `1.0`** — the version reflects real
  progress, not activity.

### 3. Per-component honesty

Because one number covers all parts, the **release notes / CHANGELOG must state what changed per
component**, so "v0.8.0" is meaningful even though a component may be unchanged from the prior release.
The firmware version constant (`firmware/include/config.h`) is kept **in sync with the project version**
at each release.

### 4. Milestones are created per planned build

A milestone is created **when a build is planned**, numbered **by its content** per §2 — not
pre-allocated to inflate ahead of the work. **No milestone = backlog.**

## Consequences

- One version line is simple and standard; the CHANGELOG carries the per-component detail the single
  number can't.
- The bump discipline keeps the version **honest and slow** — small fixes don't inflate it, and `1.0`
  stays a deliberate milestone rather than an accident of counting.
- Every lane bumps the same way; releases read truthfully to an outside contributor.

## Revisit triggers (the solid revisit)

- **The single number can no longer answer "which firmware / ML / data version is actually in release
  `vX.Y.Z`"** — firmware that didn't change is still "at" the new version, a component evolves between
  releases, or ML/firmware need independent version tracking → **split into per-component version lines**
  (e.g. firmware / host / ml), recorded as a **superseding ADR**.
- A component ships on a cadence **genuinely independent** of the others → give it its own version line.
- The project is **stable and complete enough** → declare `1.0.0` deliberately (never by increment).

## Binds all lanes (relay)

Every lane follows the bump discipline; the **Firmware lane** maintains the version constant per this
policy; the **Workflow lane** cuts releases and writes the per-component CHANGELOG. Relay to the lanes so
they adopt it.

## Register row (add)

```text
| [0009](0009-versioning-and-release-policy.md) | Versioning & release policy | **Accepted** | Workflow lane |
```
