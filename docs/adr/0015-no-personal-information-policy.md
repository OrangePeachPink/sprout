# ADR-0015: No personal information in the repository

**Status:** Accepted (drafted by Trellis; maintainer-ratified 2026-06-26)
**Date:** 2026-06-26
**Deciders:** Maintainer + Workflow lane

## Context

Sprout is heading toward a public, portfolio-grade release. An architecture review plus a repository scan
surfaced personal-information (PI / PII) leakage that must not reach a public artifact:

- a raw device **MAC** in the committed sample log (`docs/sample_log.csv`), with `device_id` derived from it (`#166`);
- the maintainer's **personal name** in 6 tracked files (`BACKLOG.md` + 5 archived design HANDOFFs) (`#168`, `#169`).

No emails, home paths, or committed secrets were found — but the project has no *durable, enforced* policy
to keep it that way as new logs, samples, fixtures, and docs are generated.

## Decision

**No personal information is collected into, generated into, written to, committed to, or published from
this repository.** Specifically:

- **Identities** — no real personal names, emails, phone numbers, or addresses in tracked files. Use the
  GitHub handle or "the maintainer".
- **Location** — the operator's real coordinates / address are PI. They live **only** in gitignored config
  (`config/location.local.json`), never in tracked files, code comments, or git history. Committed templates use
  **placeholder city-center** values; tools **hash coordinates out of any cached filename** so even filenames
  leak nothing (PRD-0002 R6 / ADR-0013 §3).
- **Device identity** — public artifacts (sample logs, fixtures, docs, screenshots) carry only **synthetic
  or pseudonymous** device IDs: never a real MAC, and never a `device_id` derived from a real MAC. Internal
  / gitignored logs may carry real identifiers; the host **scrubs them on any public export**.
- **Screenshots** — committed screenshots (evidence, docs, PRs) are **cropped to the app / content area
  only**: no browser chrome (bookmarks bar, toolbar, tabs, URL bar), no OS chrome (taskbar, system tray,
  notifications), no other windows. Browser/OS chrome leaks names, handles, visited sites, file paths, and
  operator identity *even when the app content itself is clean*. Crop before commit; a reviewer rejects any
  screenshot showing chrome.
- **Generation** — tools that write files (loggers, exporters, the calibration workbench, sample generators)
  must not emit real PI; public-facing output is synthetic / pseudonymized **by construction**, not by
  after-the-fact cleanup.
- **Enforcement** — a publish-scrub checklist (`#173`) plus, where feasible, a **pre-commit / CI
  check** that greps for the known PI classes (personal name, raw-MAC pattern, emails, home paths, operator
  coordinates / location)
  and fails on a hit. The pre-1.0 checklist includes a one-time **git-history scrub** (a working-tree
  scrub is not a history scrub).

## Consequences

- Public artifacts become safe to share; the integrity / provenance posture extends cleanly to privacy.
- Small ongoing cost: sample / fixture generation must use synthetic data, and the scrub check runs in CI / pre-commit.
- Existing leaks are remediated by `#166` (sample), `#168` (BACKLOG), `#169` (names), `#172`
  (archive purge), plus the history scrub in `#173`.

## Related

`#166`, `#168`, `#169`, `#172`, `#173`, `#59`. Aligns with the workspace dev guidance on privacy
(no personal name / email / identifiers in public repo content).

*Register in `docs/adr/0000-record-architecture-decisions.md` on acceptance.*
