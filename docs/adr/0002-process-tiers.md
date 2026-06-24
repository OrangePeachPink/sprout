# ADR-0002 — Process tiers

**Status:** Proposed (skeleton — per-row owners to confirm; maintainer to accept)
**Date:** 2026-06-24
**Owner:** Maintainer (per-row owners below)
**Lane:** cross-lane

---

> **What this is.** A single place that records *how this project is engineered* — the deliberate
> choice, per area, of how much process to apply. It is intentionally **right-sized for a small,
> mostly-solo build**: lightweight by default, heavier only where a real need justifies it. New
> contributors can read it top-to-bottom to understand how work flows here.
>
> Each row proposes a starting choice and names the **owning lane** that confirms or overrides it.
> Tags: ✅ decided in-lane · 🟡 proposed, **owner to confirm** · 📋 what the repo shows today.
>
> Some rows are **foundational** (cheap now, painful to retrofit — decide deliberately); others are
> **default-for-now** (a safe starting choice with a revisit trigger, refined as the work demands).
> "We'll decide the specifics when we get there" is a valid answer for the latter.

## Context

Sprout is a window-ledge capacitive-soil-moisture + small-pump auto-waterer: ESP32 firmware
(PlatformIO), a Python host logger and analytics, a served dashboard, and a design system. It is a
small, learning-and-portfolio build worked on across a few focused lanes. The choices below keep the
process light enough to enjoy and disciplined enough to trust — explicitly avoiding the
over-engineering that a project this size doesn't need.

The decisions are ordered as a **new-contributor reading path**: who works on it → get it running →
how work is defined and tracked → how changes are made, checked, and shipped → the domain
architecture → assurance.

## Decision — choice per area

| # | Area | Proposed choice | Owner | Today |
|---|---|---|---|---|
| **1** | Collaboration & concurrency model | Role-specialized lanes (one author per domain), coordinated by the maintainer | 🟡 Maintainer | 📋 several lanes active |
| **2** | Contributor guide & domain glossary | A lean set: `AGENTS.md` (working rules incl. native-first + a challenger/architecture-review pass) + `CONTEXT.md` (domain glossary) + the ADRs | ✅ Maintainer / Firmware | 📋 **gap** — only `README.md` today |
| **3** | Environment & dependencies | `uv`-managed Python (pinned interpreter + lockfile) + **PlatformIO/embedded toolchain pinning (`platformio.ini`)** + `.env.example`; secrets gitignored. Firmware owns the foundation; Data declares its analytics deps into it | ✅ Firmware (Data declares deps) | 📋 `ruff.toml` present; no `pyproject.toml`/`uv.lock` yet |
| **4** | Task runner & rituals | A `justfile` exposing `start` / `check` / `ship`; `start` is the runner **plumbing** that launches the host application surface (Data-owned, ADR-0005) + the firmware/device side | ✅ Firmware | 📋 none yet |
| **5** | Running the app (operator launch) | Operator self-serve: launcher + fixed port + in-UI stop; host functionality presents as **one application surface** (Data owns it — see ADR-0005) | ✅ Data | 📋 a live-serving dashboard exists |
| **6** | Spec & requirements | Specs/PRDs as `docs/prd/` markdown + an ideas inbox (Discussions); decomposed to issues — **see [ADR-0003](0003-work-pipeline.md)** | ✅ Workflow | 📋 a backlog doc is today's spec; migrating to the pipeline |
| **7** | Backlog & issue tracking | **GitHub Issues (ledger) + Projects (board); IDs = issue `#N`** — **see [ADR-0003](0003-work-pipeline.md)** | ✅ Workflow | 📋 currently a flat backlog file + letter IDs |
| **8** | Branching & merge | Short branch → PR → squash → manual review (auto-merge earned later); the flow is in [ADR-0003 §8](0003-work-pipeline.md); all lanes cut over at once when no-fly lifts | 🟡 **policy: Workflow · mechanics: Firmware · ratify: Maintainer** | 📋 commits currently land **directly on `main`** — closes at cutover |
| **9** | Commits & changelog | **Conventional Commits** (issue/PR labels = {feat, fix, docs, refactor, chore} per [ADR-0003](0003-work-pipeline.md); commits may use finer types like ci/test/style) + a generated changelog (`git-cliff`) **deferred to the first release/milestone** | ✅ Firmware | 📋 Conventional Commits **already in consistent use** — ratify; changelog not wired |
| **10** | Quality gates | `pre-commit` (fast hygiene/format/lint) + slower checks in CI — **harness owned here; each lane plugs in its own checks** | ✅ Firmware | 📋 linters configured (`ruff`, `clang-format`, `clang-tidy`, `markdownlint`, `cspell`); no `pre-commit` orchestration yet |
| **11** | Testing | `pytest` on the Python core **+ a native C harness for the firmware logic**; coverage **visible, not gated**; hardware via replay fixtures, not live-board | ✅ Firmware | 📋 `tests/` + native host FSM tests present |
| **12** | Continuous integration | GitHub Actions, hosted, path-filtered (green-or-not) — **harness owned here; lanes' checks plug in** | ✅ Firmware | 📋 no workflows yet |
| **13** | Change control & decision records | Right-sized ladder: commit → issue + PR → **ADR** for significant/hard-to-reverse decisions | 🟡 Maintainer | 📋 this ADR series is the top rung |
| **14** | Process telemetry & insights | **GitHub-native Insights / API** for velocity & cycle-time | ✅ Workflow | 📋 *product* telemetry (sensor schema) is a separate data-lane concern |
| **15** | Data store & versioning | Match the substrate to the data's shape: CSV → DuckDB/parquet analysis tier; raw archive → Git LFS; a single-writer store (SQLite) if wanted — **see [ADR-0006](0006-data-architecture.md)** | ✅ Data | 📋 `logs/*.csv` + an LFS archive worktree; DuckDB/parquet planned |
| **16** | Machine learning / inference | Native-first: classical/library methods before any trained model; earn a model with a named gap — **see [ADR-0006](0006-data-architecture.md)** | ✅ Data | 📋 classical forecast engine (drying-rate / gated ETAs / diurnal) |
| **17** | Frontend stack | **Host app = vanilla HTML/CSS/JS + Chart.js + Sprout tokens, no build** (decided); control-page framework deferred to its own decision. Split: **Design = token/component system + consumption contract · Data = served-app runtime/stack** (see ADR-0004/0005) | 🟡 Design + Data | 📋 served dashboard + `sprout-tokens.css` |
| **18** | Design system | Design tokens (color/type/space/radius) as CSS custom properties + a small component set | 🟡 Design | 📋 **already built** — v1 + v2 under `docs/design/` |
| **19** | Code intelligence | Editor/LSP + GitHub code navigation; revisit a code-graph tool later | 🟡 Maintainer | 📋 open |
| **20** | Security & compliance | Native only: secret scanning + dependency alerts (not maximal tooling); **configs here (gitleaks/Dependabot), repo-level toggles Maintainer's** | ✅ Firmware / Maintainer | 📋 credentials gitignored; secret-scan hook to confirm |

## Consequences

- The project gains a recorded, right-sized process baseline instead of an implicit one.
- Clear **gaps** are surfaced for owners: a contributor-docs set with the native-first/challenger rule
  (#2), `uv`/`pre-commit`/CI (#3/#10/#12), and a PR flow (#8).
- Deliberately **not** doing: hard coverage gates, bespoke land/backlog/changelog harnesses, heavy
  change-control ceremony, or redundant security layers — process weight is matched to this project's
  actual stakes.

## Revisit triggers

- A second author enters a lane → reconsider #1 / #8.
- A persistent multi-channel dataset outgrows CSV → make the #15 substrate decision.
- The Project board starts to feel like it's taxing planning → revisit the #7 board (e.g. a dedicated
  tracker), recorded as a new ADR.
- Manual PR review proves reliable → earn auto-merge (merge-when-green) + branch protection.

## Confirmation

Each `🟡 owner-to-confirm` row is confirmed or overridden (with a one-line reason) by its owning lane;
the maintainer then flips this ADR to **Accepted** and updates the
[0000 register](0000-record-architecture-decisions.md).

### Data lane — confirmed 2026-06-24

- **#5 Running the app** — ✅ confirmed. `serve.py` is already operator self-serve on a fixed port; the
  one-command launcher and in-UI stop are the remaining gaps.
  Detailed in [ADR-0005](0005-application-surface-and-frontend.md).
- **#15 Data store & versioning** — ✅ confirmed as-is (raw immutable → Git LFS archive → derived,
  rebuildable DuckDB/parquet). Detailed in [ADR-0006](0006-data-architecture.md).
- **#16 ML / inference** — ✅ confirmed as-is. Forecasting is classical (OLS rate, gated ETAs, diurnal);
  no trained model is warranted yet — a model is earned by a named gap.
  Detailed in [ADR-0006](0006-data-architecture.md).
- **#17 Frontend stack (Data half)** — ✅ confirmed: the served host app is vanilla + Chart.js + Sprout
  tokens, no build step (the runtime/stack, [ADR-0005](0005-application-surface-and-frontend.md)). Design
  confirms the token/component-system half (#18 / ADR-0004) separately.
- **#3 seam (ack, not owned):** Data declares its analytics dependencies (duckdb, pandas, …) into the
  Firmware-owned `uv` / `pyproject` environment when it is stood up.
