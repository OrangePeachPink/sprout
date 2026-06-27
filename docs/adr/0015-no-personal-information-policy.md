# ADR-0015: No personal information in the repository

**Status:** Proposed (drafted by Trellis, the architecture & gap reviewer; awaiting maintainer / Workflow acceptance)
**Date:** 2026-06-26
**Deciders:** Maintainer + Workflow lane

## Context

Sprout is heading toward a public, portfolio-grade release. An architecture review plus a repository scan
surfaced personal-information (PI / PII) leakage that must not reach a public artifact:

- a raw device **MAC** in the committed sample log (`docs/sample_log.csv`), with `device_id` derived from it (`#167`);
- the maintainer's **personal name** in 6 tracked files (`BACKLOG.md` + 5 archived design HANDOFFs) (`#168`, `#169`).

No emails, home paths, or committed secrets were found — but the project has no *durable, enforced* policy
to keep it that way as new logs, samples, fixtures, and docs are generated.

## Decision

**No personal information is collected into, generated into, written to, committed to, or published from
this repository.** Specifically:

- **Identities** — no real personal names, emails, phone numbers, or addresses in tracked files. Use the
  GitHub handle or "the maintainer".
- **Device identity** — public artifacts (sample logs, fixtures, docs, screenshots) carry only **synthetic
  or pseudonymous** device IDs: never a real MAC, and never a `device_id` derived from a real MAC. Internal
  / gitignored logs may carry real identifiers; the host **scrubs them on any public export**.
- **Generation** — tools that write files (loggers, exporters, the calibration workbench, sample generators)
  must not emit real PI; public-facing output is synthetic / pseudonymized **by construction**, not by
  after-the-fact cleanup.
- **Enforcement** — a publish-scrub checklist (`#173`) plus, where feasible, a **pre-commit / CI
  check** that greps for the known PI classes (personal name, raw-MAC pattern, emails, home paths)
  and fails on a hit. The pre-1.0 checklist includes a one-time **git-history scrub** (a working-tree
  scrub is not a history scrub).

## Consequences

- Public artifacts become safe to share; the honesty / provenance posture extends cleanly to privacy.
- Small ongoing cost: sample / fixture generation must use synthetic data, and the scrub check runs in CI / pre-commit.
- Existing leaks are remediated by `#167` (sample), `#168` (BACKLOG), `#169` (names), `#172`
  (archive purge), plus the history scrub in `#173`.

## Related

`#167`, `#168`, `#169`, `#172`, `#173`, `#59`. Aligns with the workspace dev guidance on privacy
(no personal name / email / identifiers in public repo content).

*Register in `docs/adr/0000-record-architecture-decisions.md` on acceptance.*
