# AGENTS.md — Sprout

Operating rules for any agent (or human) working in this repository.
**Read this first** — it points you to everything else.

> ## ⏱️ If you only have 30 seconds
>
> - **Sprout** is an honest, automatic plant-watering system: ESP32 firmware → host
>   logger → analytics dashboard, with a brand character that speaks for the plant.
> - **Work lives in GitHub Issues** on the [project board][board] — not in files.
>   `BACKLOG.md` is retired.
> - **The gate:** do the work on a branch, open a PR with **`Refs #N`** (never
>   `Closes`), post evidence, move the card to **Needs Verification**, and **stop**.
>   A reviewer merges and closes. **Never close your own issue.**
> - **Honest data is law:** raw counts + the calibrated **band** are truth; any
>   percentage is a *labelled index*, never real moisture. Mood, status, and watering
>   follow the band, never the index.
> - **`main` is protected** — PRs only, squash-merge, no direct pushes.

## Reading order

1. **This file** — operating rules.
2. **[CONTRIBUTING.md](.github/CONTRIBUTING.md)** — the canonical work loop + the verification gate.
3. **[docs/process/ADOPTION.md](docs/process/ADOPTION.md)** — per-lane onboarding (which
   board filter, which issues, which ADRs you own). *Current specifics live here, not above.*
4. **[docs/adr/](docs/adr/)** — decisions of record. Start at
   [ADR-0000](docs/adr/0000-record-architecture-decisions.md) (the register) and
   [ADR-0001](docs/adr/0001-architecture-and-control-loop.md) (architecture).
5. **Your domain docs** — firmware: `firmware/` + ADR-0001 · data: ADR-0005/0006 +
   [docs/TELEMETRY_SCHEMA.md](docs/TELEMETRY_SCHEMA.md) · design: `docs/design/` + ADR-0004/0007/0008.

## The lanes

Sprout is built by coordinated lanes. Stay in yours; route cross-lane needs through the maintainer.

| Lane | Scope | Owns |
|---|---|---|
| **Firmware** | ESP32 control, sensing, actuators (`firmware/`) | ADR-0001, the native C test harness |
| **Data** | host logger, analytics, the served dashboard | ADR-0005, ADR-0006 |
| **Design** | design system, brand, voice (repo read-only; lands via commit-proxy) | ADR-0004, ADR-0007, ADR-0008 |
| **Workflow** | issues, board, releases, process | .github/CONTRIBUTING.md, this file |

## Lane attribution

Every lane posts from the one `OrangePeachPink` account, so **sign your work** — it's the only way to see
who did what at a glance.

- **Sign-off:** end PR bodies, issue/PR comments, ADRs, docs, and copy decks with `— <Lane>` (emoji
  optional). E.g. `— Firmware`, `— Data 🌱`, `— Trellis`. The maintainer signs merge/squash commits `-v`.
- **Commit trailer:** add a `Lane: <Lane>` trailer alongside the `Co-Authored-By:` line, so attribution
  lands in `git log` / `git blame` — machine-readable and permanent:

  ```text
  feat(actuators): wire the relay driver to a bounded pulse

  Lane: Firmware
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

## Workflow & GitHub

- **Issues are the ledger.** Every unit of work is an issue (open via the forms). IDs are `#N`.
- **The [board][board]** is the working view. Fields: **Status** (Backlog → In Progress →
  In Review → Needs Verification → Done / Won't Do) · **Priority** (P0–P3, execution order) ·
  **Size** (XS–XL) · **Verification** (Pending / Approved / Conditional / Changes requested).
- **Discussions** = the idea inbox · **PRDs** (`docs/prd/`) = specs for larger features ·
  **ADRs** (`docs/adr/`) = significant or hard-to-reverse decisions (any lane may author one in its area).
- **The verification gate (the rule that matters most):** the implementer posts evidence
  and moves the card to **Needs Verification**; a **reviewer** confirms and closes. PRs use
  **`Refs #N`** / `Part of #N`, **never `Closes #N`**. Merged PRs do not auto-close issues.
- **`main` is protected:** PR required, squash-merge, no direct pushes, no force-push/deletion.
- **Gate labels** `blocks:pumps` / `blocks:public-release` / `blocks:data-integrity` mark
  milestone gates, independent of Priority.

## Branches & commits

- Branch from `main`: `type/short-desc` (e.g. `feat/tank-level`, `fix/banner-spacing`).
- **Conventional Commits:** `type(scope): imperative subject`, where
  `type ∈ {feat, fix, docs, refactor, chore}` (+ `test, ci, style`). State the *result* when
  that's the point. Keep commits **atomic** — one reviewable concern each.
- PRs are **squash-merged**; the branch auto-deletes.

## Code style

| Area | Tooling | Rule |
|---|---|---|
| **Python** (logger, analytics, build hooks) | [ruff](ruff.toml) lint + format | line length 88; `ruff check .` · `ruff format .` |
| **C / C++** (firmware) | clang-format + clang-tidy | 4-space, K&R braces, 80 cols; **format new/changed files only** — never bulk-reformat (it collapses the firmware's manual column alignment) |
| **Markdown** | markdownlint | `npx markdownlint-cli2 "**/*.md"` |
| **Endings / encoding** | git + EditorConfig | LF · UTF-8 · final newline |

Tests: `pytest` on the Python core; a native C harness for firmware logic (compiles on host,
no board). Coverage is **visible, not gated**.

## Backlog / triage

- `BACKLOG.md` is **retired** — historical only, **do not add to it.** All work is in Issues.
- Idea not ready to build → **Discussions.** Ready, assignable, "done" definable in a sentence
  → an **Issue** (use the forms).
- Labels: `type:*` (work kind) · `area:*` (control/logging/sensing/actuators/analytics/design) ·
  `layer:*` (firmware/host) · `blocks:*` (gates) · `good first issue` · `help wanted` ·
  `needs-verification`. Priority / Size / Verification live on the **board**, not as labels.

## Design & brand guidance

Sprout is a **character**, not a readout — it speaks in the first person, calm and honest.

- **Honest by default (non-negotiable):** raw counts + the calibrated **band** are truth. Any
  0–100 figure is a clearly-labelled *relative index*, never real volumetric water content.
  **Mood, status color, and watering derive from the band, never the index.**
- Data looks like data: mono, right-aligned, tabular. **Gaps are surfaced, not smoothed.**
- **Consume design tokens** (`docs/design/`), don't redefine them. Honor `prefers-reduced-motion`.
  Keep the character *beside* the instrument, not on top of it.
- Brand guide: [docs/design/brand/BRAND.md](docs/design/brand/BRAND.md). Decisions of record:
  ADR-0004 (design system), ADR-0007 (brand & voice), ADR-0008 (personality layer).

## Provenance & honesty (project doctrine)

- Don't fabricate results, command output, or test results. Separate fact from inference.
  Preserve raw data; never rewrite evidence to hide a bad result.
- This repo is built **public-clean:** no private absolute paths, no personal names in tracked
  files, neutral role names. Keep it that way.

[board]: https://github.com/users/OrangePeachPink/projects/2
