# Contributing to Sprout

Welcome — glad you're here. Sprout is a small, honest project with one clean path from idea to merge, and this
guide walks it in about five minutes. However you've arrived — fixing a typo, wiring up a pump, or just curious —
there's a place for you. We keep it calm, plain, and kind: the watering's honest, the board's clean, and there's
one path now. **Tend well.**

Sprout is built with AI assistance, and AI-assisted contributions are as welcome as hand-written ones — use
whatever tools fit how you work, or none. The bar is the same either way.

## Where things go

| You have… | Put it in… |
|---|---|
| a question, a loose idea, a "should we…?" | [**Discussions**](https://github.com/OrangePeachPink/sprout/discussions) — the idea inbox |
| a written requirement for a larger feature | a **PRD** in [`docs/prd/`](https://github.com/OrangePeachPink/sprout/tree/main/docs/prd/) |
| a concrete, shippable piece of work | a [**GitHub Issue**](https://github.com/OrangePeachPink/sprout/issues) (use the forms) |
| a change that implements an issue | a **Pull Request** |

The test: *can I assign it and define "done" in a sentence?* → Issue. *Is it a question or a maybe?* →
Discussion.

## The board

The [**Sprout board**](https://github.com/users/OrangePeachPink/projects/2) is the working view of every
issue. These native fields drive it:

| Field | Values | Means |
|---|---|---|
| **Status** | Backlog → In Progress → Needs Verification → Ready to Merge → Done · Won't Do | where the work is in its life — **and the one and only verification signal** (#729) |
| **Priority** | P0 · P1 · P2 · P3 | execution order (P0 = do first) |
| **Size** | XS · S · M · L · XL | rough effort (feeds velocity) |
| **Milestone** | `v0.7.1`, `v0.8.0`, … | the target **version** (see [Releases & versioning](#releases--versioning)) |

**One verification signal (#729, maintainer-ruled):** the Status column carries the whole gate —
`Needs Verification` = evidence posted, awaiting review; `Ready to Merge` = certified GO. The
reviewer's disposition lives in the certification comment; changes-requested returns the card to
In Progress with the reason. The former `Verification` field and `needs-verification` label are
**retired** — one signal, nothing to drift.

Priority and Size are **board fields, not labels** — they sort and chart without
cluttering the issue's label list. **Milestone is GitHub's native release container** — it groups a
version's work and drives its progress bar and release notes. *(An earlier custom "Wave" field was
retired in favor of milestones — we use the standard primitive.)*

### Priority & Size — the standard

**Priority (P0–P3)** — execution order. It's a *field*, so it sorts and groups every view:

| | Meaning |
|---|---|
| **P0** | Drop everything — the live product is broken, unsafe, or losing data. Rare. |
| **P1** | This release — blocks the release's goal, or fixes a real user-facing pain. |
| **P2** | This release *if capacity allows* — valuable, not blocking. |
| **P3** | Nice-to-have — do if cheap, else defer to a later release. |

*No Priority set = not yet triaged* — the triage view surfaces these on purpose.

**Size (XS–XL)** — T-shirt effort. It feeds velocity and lets you size a release at a glance:

| Size | Effort | |
|---|---|---|
| **XS** | minutes — a *nit* | **just do it** (verified + approved: faster than scheduling it) |
| **S** | hours | |
| **M** | a day or two | |
| **L** | about a week | |
| **XL** | weeks | **too big — split it** (an epic smell) |

Set both on the **board** (or the issue's Projects sidebar) — **never in comments** (a comment can't
sort a view). By the end of triage, every open issue (not Done / Won't Do) should carry a Priority and
a Size.

## Opening an issue

Use the **issue forms** (New issue → Feature / Bug / Task). They capture the area, layer, and details a
maintainer needs to triage. Don't worry about labels — the form applies the `type:` label, and a
maintainer confirms `area:` / `layer:` at triage.

## Making a change

1. **Pick up** an issue (a maintainer can assign it and move its card to *In Progress* on the board).
2. **Branch** from `main`, named `type/short-desc` — e.g. `feat/tank-level`, `fix/banner-spacing`.
   (Outside collaborators: fork, then branch.)
3. **Commit** with [Conventional Commits](https://www.conventionalcommits.org/):
   `type(scope): imperative subject`, where `type` is `feat | fix | docs | refactor | chore` (plus
   `test | ci | style` for finer changes). State the *result* in the subject when that's the point.
4. **Run the checks** before pushing: **`just check`** (lint + format + tests — exactly what CI runs).
   Even better, run **`uv run pre-commit install`** once and the format/lint runs automatically on every
   commit. (First-time setup: `uv sync`, or open the repo in **Codespaces** — see the
   [README quick start](../README.md#quick-start).)
5. **Open a PR** and fill in the template. Link the issue with **`Refs #N`** or **`Part of #N`** —
   **not** `Closes #N` (see the gate below). Include how you verified the change.
6. PRs are **squash-merged** — one clean commit per change; the branch auto-deletes after merge.
7. **It gets reviewed, then merged.** Someone other than the author checks your PR against the issue's
   acceptance criteria; once it passes, it's merged. **Community contributions always get direct maintainer
   review** — no exceptions. *(How the maintainer's internal review runs — including a faster path used only
   for pre-scoped internal work — is in [AGENTS.md](../AGENTS.md); you don't need it to contribute.)*

> **`just check` needs one more tool than `just start` does.** `uv sync` + `just` alone are enough to run the
> dashboard and the *lint/format* hooks — but `just check` also runs `just test`, which **unconditionally**
> compiles and runs the native C firmware-logic suite (`test-native`), even for a docs-only change. That step
> needs **PlatformIO** (`pip install platformio`) and a **host C compiler** (`gcc` on PATH — e.g. a winget
> MinGW install on Windows) *in addition to* `uv`/`just`. If you'd rather skip installing those locally,
> **GitHub Codespaces already has both** (its base image bundles `gcc`, and `pip install platformio` is a
> quick add) — see the Firmware section below, or just push and let CI run the full gate for you.
>
> **Why CI is designed to run everything (the default posture — currently overridden; see the sprint note
> below):** `just check` is the same full gate as your machine — on purpose. Pre-commit *hooks* are
> file-type-scoped for speed (e.g. `clang-format` only touches `.c`/`.h` files) — but the *test* step above is
> not type-scoped, so don't read "hooks are scoped" as "a docs change skips firmware tests." Running
> everything is what buys predictability and prevents local≠remote drift; path-filtering would re-introduce
> exactly the class of surprise we deliberately closed.
>
> ⚠️ **Temporary sprint posture (#740, private phase only):** remote per-PR CI currently runs the *fast lane
> only* (lint + hygiene + host tests); the firmware compile, native C tests, and experimental boards run in a
> **weekly full battery** (+ on-demand dispatch) instead — an Actions-minutes decision, velocity over
> per-commit remote coverage. **`just check` locally is therefore the real full gate during the sprint** —
> run it before pushing, and post local `just test-native` + `just build` evidence on firmware-touching PRs.
> This posture is reverted per #740's launch checklist before the repo goes public.
>
> **The one exception — clang-format:** it runs on the *lines you changed*, not `--all-files`, because the
> firmware carries intentional manual column alignment a full-tree reformat would destroy (AGENTS.md
> §code-style; changed-lines via `git-clang-format`, #352). Edit a file and only your touched lines are
> checked — untouched aligned blocks are left alone. Every other check — `ruff` / `cspell` / `markdownlint` —
> stays repo-wide.
>
> **Spelling (`cspell`) is advisory, not a gate (#524).** It accepts US and UK English and reports unknown
> words without ever failing your commit or CI — write normally, and if it flags a real term, ignore it or add
> it to `cspell.json` at your convenience.
>
> **If CI goes red after a base fix:** re-running the job alone isn't enough — it replays the *stale* merge
> commit. **Update your branch** (merge or rebase `main`) so CI re-checks against the fixed base. That's the
> "Attempt #2 / #3" trap.
>
> **`git checkout`/`git switch` says `Aborting … uv.lock`?** A stray `uv` re-lock dirtied `uv.lock` (uv
> re-serializes it when your uv version differs from the lock's writer). Run **`git restore uv.lock`** and
> switch again. Routine commands go through `just` with `--frozen` so this shouldn't happen (#254) — change
> dependencies via **`just lock`**, never by editing `uv.lock` by hand.

## Firmware — build, test, flash (no Arduino IDE)

Picking up a firmware issue? You **never touch the Arduino IDE** — Sprout dropped it project-wide. The firmware
is a **PlatformIO** project (it builds the Arduino framework underneath, so you write Arduino-API firmware
without the IDE or a hand-assembled cross-compiler). **Two first-class ways in — pick whichever fits you:**

- **VS Code + PlatformIO (local).** Install the PlatformIO extension; it fetches the ESP32 toolchain for you.
  Your own editor, full local control, the board on your own USB.
- **GitHub Codespaces (browser).** *Open in Codespaces* → the devcontainer builds the toolchain for you →
  `just check` runs green. Zero local install — ideal for editing, building, and the native tests; flashing a
  board you're holding stays a local USB step.

Neither is "the" way. Once you're in, the commands are identical:

| Do | Command | Needs the board? |
|---|---|---|
| **Build** (compile) | `just build` | no |
| **Test** (native host logic) | `just test-native` | no |
| **Flash** (upload to the ESP32) | `just flash` | yes — board on USB |

Build and test need **no hardware** — so most firmware work, and all of CI, happens without a board plugged in.
You only need the ESP32 on USB for the flash step. *(Under the hood these are plain PlatformIO from the
`firmware/` folder: `pio run` · `pio test -e native` · `pio run -t upload` — the `just` recipes add
`-d firmware` so the path is always right.)*

**What you need:** an ESP32, a USB cable, and one tool — **PlatformIO** (the VS Code extension, or it's already
in the Codespace). That's the whole list. First flash on a fresh board? **[FLASHING.md](../docs/FLASHING.md)**
walks you in.

**PlatformIO reinstalling on every VS Code restart, or otherwise acting up?**
**[PlatformIO troubleshooting](../docs/PLATFORMIO_TROUBLESHOOTING.md)** tells a normal one-time
re-provision apart from a loop (the `penv.stale-*` breadcrumb test), covers the dual-Python trigger,
and gives a safe clean-reset runbook.

> **Brand-new to microcontrollers?** A gentle, deliberately-separate Arduino starter on-ramp is on the way
> ([#387](https://github.com/OrangePeachPink/sprout/issues/387)) — it hands back the tunable constants and
> shared terms, then graduates you to this VS Code / Codespaces project.

## How a change gets reviewed and merged

**In one line:** you open a PR; someone *other than the author* checks it against the issue's acceptance
criteria; once it passes, it's merged. That independent check is the whole point — nothing merges on the
author's say-so alone.

**You don't need more than that to contribute.** How that review runs *internally* — the per-stage pipeline
(Backlog → In Progress → Needs Verification → Ready to Merge → Done), Workflow's independent certification, the
velocity modes, and the tombstone-banner conventions for closing issues — lives in
**[AGENTS.md](../AGENTS.md#the-verification-pipeline)**, the operating manual for the maintainer and the AI
workstreams ("lanes") that do the day-to-day building. Open a PR with **`Refs #N`** (never `Closes`) plus a
note on how you verified it, and it'll be reviewed there.

## Releases & versioning

Sprout ships as **versioned milestones** — standard SemVer, defined in
[ADR-0009](../docs/adr/0009-versioning-and-release-policy.md):

- A **milestone** (`v0.7.1`, `v0.8.0`, …) is a shippable **version** and the home for its planned work —
  **no milestone = backlog.** The roadmap runs from `v0.7.0` (Monitor, shipped) toward **`v1.0.0`** (the
  deliberate public release). **MINOR** (`0.X.0`) earns a new user-facing capability; **PATCH** (`0.X.Y`)
  is fixes / polish / docs; `1.0.0` is chosen on purpose, never reached by counting. ADR-0009 §5 has the
  full version roadmap.
- When a milestone ships, we cut a **GitHub Release** at the version tag. Its notes are
  **auto-generated** from the PRs merged since the previous tag, grouped by each PR's **`type:` label**
  (`.github/release.yml`), then lightly curated. **Your PR title + `type:` label become the release
  notes** — so write the title as the line you'd want a stranger to read. (`type:chore` is excluded.)
- The **[CHANGELOG](../CHANGELOG.md)** is the same record, in-repo and appendable, with per-component detail.

## GitHub-native by default

We run standard GitHub the standard way — **Issues, Milestones, Releases, Discussions, sub-issues,
labels, issue/PR templates, protected `main`.** If a process here looks bespoke, it probably shouldn't be:
prefer the native primitive, and if you spot a custom thing doing a native thing's job, **say so.** The
less custom machinery you have to learn, the faster you can help — that's the whole point.

## Labels (quick reference)

- `type:*` — the kind of work (mirrors the commit `type:` vocabulary)
- `area:*` — the subsystem (control / logging / sensing / actuators / analytics)
- `layer:*` — `firmware` (needs a reflash) vs `host` (build anytime)
- `for:*` — routing hint to a lane (a best-guess owner, not a commitment — Workflow still triages):
  `for:firmware` (incl. bench) · `for:data` · `for:design` (→ DesignQA) · `for:dx` · `for:trellis` ·
  `for:workflow` · `for:maintainer`. See the lane roster in [AGENTS.md](../AGENTS.md#the-lanes).
- `blocks:*` — milestone **gates**, independent of Priority: `blocks:pumps`, `blocks:public-release`,
  `blocks:data-integrity`. Filter by these to see what stands between us and pumps / a public release /
  trustworthy data.
- `needs:hardware` — blocked on a **maintainer hardware/bench session** (wiring, pump/relay setup, hardware
  not yet on hand). The maintainer's hardware queue; **lanes skip these** when sweeping Backlog.
- `needs:maintainer` — certified and sitting in the **maintainer's merge/action queue**.
- `good first issue` / `help wanted` — welcoming places to start

Priority and Size are **board fields**, not labels; the verification state is the **Status column**
itself (#729) — see [The board](#the-board).

## Where we'd love help

**[Contributors Welcome](../docs/CONTRIBUTORS_WELCOME.md)** is our living list of things the project would
genuinely love a hand with — resistive-sensor support, board configs beyond ESP32 + Arduino, and a
host-the-stack tier. At launch these graduate into `help wanted` issues; until then, the list is the map.

## Questions?

Ask in [**Discussions → Q&A**](https://github.com/OrangePeachPink/sprout/discussions/categories/q-a).
No setup question is too small.
