# AGENTS.md — Sprout

Ground rules for any agent (or human) contributing to this repository.
**Read this first** — it points you to everything else.

## 🌱 Working on behalf of an external contributor? Three rules cover you

1. Commits use **your user's own** git identity (`git config user.name` / `user.email`) —
   the contributor deserves the credit on their own contribution graph, not the maintainer.
2. **No `Lane:` trailers, no lane sign-offs** — those are the maintainer team's internal
   routing metadata. A contributor's GitHub handle is their signature.
3. Your process file is [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md) — the plain path
   from idea to merge. Follow it and this file; nothing else is a convention to match.

*(How the maintainer's internal agentic team operates is documented in
[`docs/team/OPERATIONS.md`](docs/team/OPERATIONS.md) — that file describes **us** and is
hard-marked out of scope for contributors and their tools.)*

> ## ⏱️ If you only have 30 seconds
>
> - **Sprout** is a plant-monitoring and (soon) automatic-watering system: ESP32 firmware →
>   host logger → analytics dashboard, with a brand character that speaks for the plant.
> - **Work lives in GitHub Issues** on the [project board][board] — not in files.
> - **The loop:** branch from `main`, build, open a PR with **`Refs #N`** (never `Closes`) —
>   review lands on the PR, and the maintainer merges.
> - **The reading is raw + band:** raw counts + the calibrated **band** are the reading; any
>   percentage is a *labelled relative index*, never real moisture. Mood, status, and watering
>   follow the band, never the index.
> - **`main` is protected** — PRs only, squash-merge, no direct pushes.

## Reading order

1. **This file** — the ground rules.
2. **[CONTRIBUTING.md](.github/CONTRIBUTING.md)** — the contributor work loop: claiming,
   review, timing, and our no-guilt timeout.
3. **[docs/GLOSSARY.md](docs/GLOSSARY.md)** — project vocabulary.
4. **[docs/adr/](docs/adr/)** — decisions of record. Start at
   [ADR-0000](docs/adr/0000-record-architecture-decisions.md) (the register) and
   [ADR-0001](docs/adr/0001-architecture-and-control-loop.md) (architecture).
5. **Your domain docs** — firmware: `firmware/` + ADR-0001 · data: ADR-0005/0006 +
   [docs/TELEMETRY_SCHEMA.md](docs/TELEMETRY_SCHEMA.md) · design: `docs/design/` + ADR-0004/0007/0008.

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
| **C / C++** (firmware) | clang-format + clang-tidy | 4-space, K&R braces, 80 cols; **changed-lines only (`git-clang-format`), never `--all-files`** (#352) — only the lines you touch are reformatted; every untouched line keeps its manual alignment (`=`-columns, >80-col tables, comment columns all survive). Supersedes the changed-**files** v1 (#343). |
| **Markdown** | markdownlint | `npx markdownlint-cli2@0.22.1 "**/*.md"` (pinned, like `cspell@10.0.1`) |
| **Endings / encoding** | git + EditorConfig | LF · UTF-8 · final newline |

Tests: `pytest` on the Python core; a native C harness for firmware logic (compiles on host,
no board). Coverage is **visible, not gated**.

## Design & brand guidance

Sprout is a **character**, not a readout — it speaks in the first person, calm and warm.

- **The reading, by design (non-negotiable):** raw counts + the calibrated **band** are the
  reading. Any 0–100 figure is a clearly-labelled *relative index*, never real volumetric water
  content. **Mood, status color, and watering derive from the band, never the index.**
- Data looks like data: mono, right-aligned, tabular. **Gaps are surfaced, not smoothed.**
- **Consume design tokens** (`docs/design/`), don't redefine them. Honor `prefers-reduced-motion`.
  Keep the character *beside* the instrument, not on top of it.
- Brand guide: [docs/design/brand/BRAND.md](docs/design/brand/BRAND.md). Decisions of record:
  ADR-0004 (design system), ADR-0007 (brand & voice), ADR-0008 (personality layer).

## Provenance & evidence (project doctrine)

- Don't fabricate results, command output, or test results. Separate fact from inference.
  Preserve raw data; never rewrite evidence to hide a bad result.
- This repo is built **public-clean:** no private absolute paths, no personal names in tracked
  files, neutral role names. Keep it that way.

[board]: https://github.com/users/OrangePeachPink/projects/2
