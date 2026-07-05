# AGENTS.md — Sprout

Operating rules for any agent (or human) working in this repository.
**Read this first** — it points you to everything else.

> ## ⏱️ If you only have 30 seconds
>
> - **Sprout** is an honest, automatic plant-watering system: ESP32 firmware → host
>   logger → analytics dashboard, with a brand character that speaks for the plant.
> - **Work lives in GitHub Issues** on the [project board][board] — not in files.
>   `BACKLOG.md` is retired.
> - **The gate (two stages):** do the work on a branch, open a PR with **`Refs #N`** (never
>   `Closes`), post a **requirement-by-requirement evidence map**, move the card to **Needs Verification**,
>   and **stop** — that's **Workflow's** inbox. Workflow certifies → **Ready to Merge** → **Veronica merges
>   only from that column.** **Never merge or close your own issue.**
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

Sprout is built by coordinated agent lanes — all on Claude Code with full repo + GitHub read/write
(Firmware runs as a Claude Code sub-agent inside VS Code). Stay in yours; route cross-lane needs through
the maintainer.

| Lane | Scope | Owns |
|---|---|---|
| **Trellis** | Senior technical architect — cross-cutting architecture, ADR authorship + review, gap analysis, "does this decision merit an ADR?" | the ADR register's health; architecture reviews |
| **Data** | Host logger, analytics, ML / predictive analysis, and the served dashboard + front-end | ADR-0005, ADR-0006 |
| **DX** | Developer, user & consumer experience; **documentation maintainer** (docs stay consistent + current — a real consumer-facing concern); community & awareness, the go-public **marketing/visibility strategy**, social engagement, and onboarding the maintainer's contributor identity + graph | the contributor front door, onboarding, `docs/contributing/` |
| **DesignQA** | **All design work** — design system, brand, voice, *and* design-QA of the running app | ADR-0004, ADR-0007, ADR-0008 |
| **Firmware** | ESP32 control, sensing, actuators (`firmware/`) **+ the physical bench** — flash, probe serial, characterize sensors, capture calibration evidence | ADR-0001, the native C test harness, bench evidence + the capability-stage vocabulary (below) |
| **Workflow** | Issues, board, milestones/releases, process; the **GitHub-native** guide; the **PR validation gate** before the maintainer reviews | .github/CONTRIBUTING.md, this file, the release train |
| **Veronica** | *Human* maintainer — vision, ideation, product direction, merges, hardware approvals | the repo; the final call |

**Escalation, not a lane:** *Claude Design (Web)* is a creative-brainstorming / prototyping resource
DesignQA or the maintainer can pull in when a design need wants divergent exploration — its output lands
through DesignQA.

**Retired lanes:** *Sage* (bench work folded into **Firmware**) and *Ingest* (design intake folded into
**DesignQA**). Don't route new work to either — it will not get done.

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

## Lane self-audit

You don't merge here (the maintainer does), so "watch CI until it's green" doesn't apply. But when you
review your own recent work — **especially before a status brief** — do **CI archeology** on your PRs:

- `gh run list --branch <your-branch> --json conclusion,headSha,createdAt` — did any run go red? — then
  `gh run view <id> --log-failed` for *why*.
- **Classify each red:** **own-code** (your defect → tighten your process) · **shared-infra** (a gate-wide
  break that caught you → note it, don't re-fix) · **cross-lane** (another lane's change broke yours → raise
  it as a comms need).
- Fold the finding into the brief's `Gate:` / `Flag:` lines. A green PR with reds in its history has a story
  worth telling.

## Lane self-sync — check before you start, check before you stop

Lanes run **concurrently**; the board and your PRs change *while you're heads-down*. **Don't wait for the
maintainer to assemble a status round and relay it — the maintainer is not your messenger, and the issue is
the message bus.** Self-sync at **three moments: when you start, just before you stop, and when you post a
status brief / share-out (requested or proactive).**

Each sync, sweep your slice: **PRs you own** (moved? merged?), **issues newly `for:<your-lane>`**,
**questions / RFCs aimed at you**, and **what just merged that unblocks your gated work** — but **skip
`needs:hardware`** (the maintainer's hardware/bench queue; filter `for:<your-lane> -label:needs:hardware`).
**A status/priority change alone triggers no GitHub notification** — only a comment/label/assignee does. Don't
rely on notifications to catch new work; **re-pull the live board each sync.**

**Which item? No ambiguity:** your queue = `for:<your-lane> -label:needs:hardware -label:needs:maintainer`
**sorted by Priority**; your next task = the **top-priority *sliced* item** (P0/P1 → P2 → P3). Every P1/P2 is
triaged to be owned, sliced, actionable — start it without asking. **Epics are parents, not tasks** — work
their sliced children, never the epic card. Escalate (`for:workflow`) only a top item that truly isn't
actionable; that should be rare. Then **act**:

- Your PR merged → reconcile it and **chase what it unblocks**. A dependency landed → **pick up the unblocked
  work this session.** A new `for:<lane>` issue or an RFC for you → triage / answer / act.
- **You have a question for another lane → post it on the issue and route it `for:<lane>` right then.** Don't
  hold it for the maintainer to carry.
- **Default to action over questions.** If it's unblocked and in your lane, do it. Escalate to the maintainer
  only for genuinely maintainer-only calls (merges, hardware approvals, product direction).

Full protocol + the sweep checklist: [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## Lane routing

When an issue comes up mid-lane and can't route through Workflow first, tag it `for:<lane>` to flag a
**first-approximate recipient** — a best-guess owner so it doesn't sit without one. The family:
`for:firmware` (incl. bench) · `for:data` · `for:design` (→ DesignQA) · `for:dx` · `for:trellis` ·
`for:workflow` · `for:maintainer`.

- It's a routing **hint**, not an assignment or a commitment — Workflow still triages, slices, and gates.
- Use `for:workflow` when you're unsure, or when an item explicitly needs the pipeline (e.g. "please slice
  this"); `for:trellis` flags an architecture / gap review.

## Bench work (Firmware lane)

Bench-and-lab work — hardware bring-up, sensor characterization, calibration evidence, bench-safety
procedures, and experiment-method documentation — is owned by **Firmware**. The maintainer is the hands
(wiring, power, plants); Firmware flashes, probes serial, reads the microcontrollers, and writes the
evidence. **Sign-off:** `— Firmware` · **Label:** `for:firmware`, plus `needs:hardware` for anything that
needs a physical session (the maintainer's bench queue).

**Capability-stage vocabulary:** describes how far a feature or sensor configuration has progressed through
physical validation. Use it consistently in issues, evidence docs, and ADRs so any lane can read bench
state at a glance:

| Stage | Meaning |
|---|---|
| `code-staged` | Implementation exists but has not yet been wired to hardware |
| `bench-wired` | Hardware connections made; not yet exercised |
| `dry-verified` | Exercised without liquid present; basic electrical behavior confirmed |
| `wet-verified` | Exercised with water/substrate; sensor response confirmed |
| `plant-deployed` | Running in an actual pot with a plant; real-world data flowing |
| `autonomous-enabled` | System making watering decisions without manual intervention |

Current state: the 8-sensor windowsill fleet is **plant-deployed** (live over WiFi since v0.7.0);
pumps/relay remain **code-staged**.

Firmware coordinates bench procedures with **Data** on schema extensions for new sensor readings and
raises wiring/power changes to the maintainer. Route bench-adjacent work `for:firmware` + `needs:hardware`.

## Workflow & GitHub

- **Issues are the ledger.** Every unit of work is an issue (open via the forms). IDs are `#N`.
- **The [board][board]** is the working view. Native fields: **Status** (Backlog → In Progress →
  Needs Verification → **Ready to Merge** → Done / Won't Do) · **Priority** (P0–P3, execution order) ·
  **Size** (XS–XL) · **Milestone** (target version — see below) · **Verification** (Pending / Approved /
  Conditional / Changes requested) · native **Sub-issues progress**. *(The old custom "Wave" field is
  retired — milestones are the roadmap spine.)*
- **Discussions** = the idea inbox · **PRDs** (`docs/prd/`) = specs for larger features ·
  **ADRs** (`docs/adr/`) = significant or hard-to-reverse decisions (any lane may author one in its area).
- **The verification gate (the rule that matters most), two stages:** the implementer builds to the issue's
  **acceptance criteria** (tests + **local == CI green**), posts a **requirement-by-requirement evidence
  map**, and moves the card to **Needs Verification** — **Workflow's review inbox.** Workflow then
  *independently validates* — against the source docs, the AC-by-AC evidence, commit history, issue/PR
  comments, and **local + remote CI green** — that the work is **fully implemented, substantially meets the
  *entirety* of the requirement's goals, and is quality** (no bugs / build / dependency issues). On pass it
  posts a **Ready to Merge certification** (who approved the design + what was verified + merge-order) and
  moves it to **Ready to Merge** — **the maintainer merges only from there, relying on that whole chain plus
  Workflow's review.** Partials spin a new linked issue for the tail before the original closes. PRs use
  **`Refs #N`** / `Part of #N`, **never `Closes #N`**; merged PRs do not auto-close issues. Full lifecycle +
  per-stage expectations: [CONTRIBUTING.md](.github/CONTRIBUTING.md).
- **`main` is protected:** PR required, squash-merge, no direct pushes, no force-push/deletion.
- **Gate labels** `blocks:pumps` / `blocks:public-release` / `blocks:data-integrity` mark
  milestone gates, independent of Priority.
- **Milestones = versions = the roadmap/release spine** ([ADR-0009](docs/adr/0009-versioning-and-release-policy.md)).
  A milestone is a shippable SemVer version (`v0.7.1`, `v0.8.0`, …) and the home for its planned work —
  **no milestone = backlog.** The roadmap runs `v0.7.0` (Monitor, shipped) → `v0.9.0` (pumps) → `v0.9.9`
  (pre-release playbook) → **`v1.0.0`** (the deliberate public release, never reached by counting).
- **Releases carry the notes.** Cutting a **GitHub Release** at a version tag **auto-generates** notes from
  the PRs merged since the last tag, categorized by `.github/release.yml` (`type:` labels), then curated.
  A release isn't done until its notes **and** a [`CHANGELOG.md`](CHANGELOG.md) entry exist (ADR-0009 §6).
  So a PR's title + `type:` label *are* release-notes copy — write them accordingly.

## GitHub-native by default — don't reinvent the wheel

Prefer the standard GitHub primitive over a custom one, **every time.** Before building a new process,
field, tool, or template, check whether GitHub already provides it:

- work items → **Issues** · ideas/specs → **Discussions** + **PRDs** · decisions → **ADRs**
- a body of work → an **epic** with **native sub-issues** (progress bar), not a prose checklist
- a shippable version → a **Milestone** · a shipped version → a **Release** with **auto-generated notes**
- planning views, **labels**, issue/PR **templates**, protected branches, CODEOWNERS → the native features

Custom mechanisms (a bespoke field, a hand-rolled tracker, a from-scratch template) need a real
justification and usually an ADR. **Reinventing standard process is how a small project drifts into pain
and exhausts its maintainer.** If you notice drift — a custom thing doing a native thing's job — **push
back and propose the native path.** This is a direct investment in the DX North Star: contributors already
know GitHub, so every bit of bespoke machinery we *don't* build is friction a future contributor never meets.

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
