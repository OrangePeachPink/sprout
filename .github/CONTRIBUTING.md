# Contributing to Sprout

Welcome — glad you're here. Sprout is a small, honest project with one clean path from idea to merge, and this
guide walks it in about five minutes. However you've arrived — fixing a typo, wiring up a pump, or just curious —
there's a place for you. We keep it calm, plain, and kind: the watering's honest, the board's clean, and there's
one path now. **Tend well.**

## Where things go

| You have… | Put it in… |
|---|---|
| a question, a loose idea, a "should we…?" | [**Discussions**](https://github.com/OrangePeachPink/plants/discussions) — the idea inbox |
| a written requirement for a larger feature | a **PRD** in [`docs/prd/`](docs/prd/) |
| a concrete, shippable piece of work | a [**GitHub Issue**](https://github.com/OrangePeachPink/plants/issues) (use the forms) |
| a change that implements an issue | a **Pull Request** |

The test: *can I assign it and define "done" in a sentence?* → Issue. *Is it a question or a maybe?* →
Discussion.

## The board

The [**Sprout board**](https://github.com/users/OrangePeachPink/projects/2) is the working view of every
issue. Four fields drive it:

| Field | Values | Means |
|---|---|---|
| **Status** | Backlog → In Progress → Needs Verification → Ready to Merge → Done · Won't Do | where the work is in its life |
| **Priority** | P0 · P1 · P2 · P3 | execution order (P0 = do first) |
| **Size** | XS · S · M · L · XL | rough effort (feeds velocity) |
| **Verification** | Pending · Approved · Conditional · Changes requested | the reviewer's disposition at the gate |

Priority, Size, and Verification are **board fields, not labels** — they sort and chart without
cluttering the issue's label list.

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

> **Why CI runs everything on every PR:** `just check` (what CI runs) is the same full gate as your machine —
> on purpose. Hooks are *type*-scoped for speed (a docs change never runs firmware tests locally); CI runs
> everything for predictability and to prevent local≠remote drift. Path-filtering would re-introduce exactly
> the class of surprise we deliberately closed.
>
> **The one exception — clang-format:** it runs at *changed scope*, not `--all-files`, because the firmware
> carries intentional manual column alignment a full-tree reformat would destroy (AGENTS.md §code-style, #343).
> Every other check — `ruff` / `cspell` / `markdownlint` — stays repo-wide.
>
> **If CI goes red after a base fix:** re-running the job alone isn't enough — it replays the *stale* merge
> commit. **Update your branch** (merge or rebase `main`) so CI re-checks against the fixed base. That's the
> "Attempt #2 / #3" trap.

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

> **Brand-new to microcontrollers?** A gentle, deliberately-separate Arduino starter on-ramp is on the way
> ([#387](https://github.com/OrangePeachPink/plants/issues/387)) — it hands back the tunable constants and
> shared terms, then graduates you to this VS Code / Codespaces project.

## The lifecycle & the verification gate (Workflow certifies, then the maintainer merges)

A PR is never merged until **Workflow** has *independently* certified it — not just rubber-stamped the lane's
own report. The full pipeline, with who owns each stage and what's expected:

**Backlog → In Progress → Needs Verification → Ready to Merge → Done** · *Won't Do*

### Backlog — triaged ideas

An item here has a clear, done-definable goal and carries **acceptance criteria**: a short, testable list of
what "done" means. Shape the requirement *here* (comments, an ADR, outside opinions) — it's far cheaper than
reworking it after it's built.

### In Progress — the lane builds

Before moving on, the implementer:

- **confirms / sharpens the acceptance criteria** on the issue (weigh in early if the requirement needs shaping),
- **implements** the work,
- **tests** it (the relevant `pytest` / native harness),
- runs **lint + format + commit hooks** and confirms **local == CI green**,
- opens a PR with **`Refs #N`** (never `Closes`).

### → Needs Verification — post evidence, then stop *(Workflow's inbox)*

The move is gated on a **requirement-by-requirement evidence map**: for each acceptance criterion, show *how*
it's met with a concrete artifact — PR # + commit SHA, file/function (`path:line`), the test that covers it
*and that it passes*, CI status, plus any manual / bench check. Not "defaults fixed ✓" — instead
`AC #1 (serial default) → dashboard_template.html:265 + test_control.py::test_serial_default passing, PR #338
@d4315ef`. The implementer does **not** self-merge or move further. **Needs Verification is Workflow's
review inbox, not the maintainer's.**

### Workflow review *(at Needs Verification)*

Workflow **independently validates** — beyond the lane's self-report — against:

- the **source docs** (PRD / ADR / issue) and the requirement's stated goals,
- the **AC-by-AC evidence map**,
- **commit history** and **issue / PR comments**,
- **CI green — local hooks *and* remote CI** — and **mergeable** (no conflicts, no dependency / stacked-PR traps),

plus Workflow's own judgment that the work is:

- **fully implemented** — not a minor slice that happened to move the card,
- **substantially meeting the *entirety* of the requirement's goals**, as written and intended,
- **quality** — correct, no bugs / regressions / build issues, in-lane, honest-data-compliant where it applies.

On pass, Workflow posts a **Ready to Merge certification** (what was verified + which lanes approved the
design + any **merge-order / ordering** notes) and moves the card to **Ready to Merge**. Strong evidence
certifies fast; a weak map, a missed goal, or a dependency snag **bounces back** with specifics.

### → Ready to Merge — the maintainer merges *(the maintainer's inbox)*

When a card reaches this column it carries the full evidence chain **plus Workflow's independent
certification** that the issue is fully implemented, substantively meets the *entirety* of its goals, is
quality work, is mergeable-green (local + remote), and carries any ordering notes. The maintainer relies on
**all of it** — source docs, AC evidence, commit history, issue comments, merge-readiness, GitHub-green,
valid local + remote CI runs — *and* Workflow's review — to **merge with confidence it's ready for the
codebase.** PRs squash-merge.

### Done — and Won't Do

On merge the issue closes (auto-Done moves the card; because PRs use `Refs`, the close is explicit).
**Won't Do** is the terminal for "decided against": close the issue as **"not planned"** (not "completed")
with a one-line reason — distinct from Done, which means *shipped*.

**Partials:** if a merged PR met an issue's *core* requirement but a clean, separable follow-on fell out,
Workflow spins a **new issue** for the remainder (linked both ways, with the context of what fell out) and
closes the original — so a tail never gets swept into the merge dustbin and lost. A PR that misses the
issue's *main point* is not closed — it's flagged back.

`Refs #N` / `Part of #N` (non-closing links), never `Closes #N`; the repo's auto-close setting stays **off**.

## Lane self-sync — check before you start, check before you stop

Lanes run **concurrently**, so the board and your PRs change *while you're heads-down*. Don't wait for the
maintainer to assemble a status round and relay it — **the maintainer is not your messenger, and the issue is
the message bus.** Keep the system moving by syncing yourself.

**Self-sync at three moments:**

1. **At the start** of a session — before you pick up work.
2. **Just before you stop** — catch what landed while you were heads-down.
3. **When you post a status brief / share-out** — whether someone requested it or you're posting proactively.

**The sweep — check your slice of the board:**

- **Your open PRs** — did any **move** (review, conformance, certification) or **merge** while you were away?
- **Issues newly labeled `for:<your-lane>`** — work routed to you.
- **Comments / questions / RFCs** aimed at your lane on issues and PRs.
- **What recently merged that unblocks you** — a dependency landed, or a base PR merged so your stacked PR
  can rebase.
- **Backlog** items in your area that are now actionable — but **skip anything labelled `needs:hardware`**:
  those are the maintainer's hardware/bench queue (wiring, pump/relay setup, hardware you don't have yet), not
  lane-advanceable. Filter your board view to `for:<your-lane> -label:needs:hardware`.

**Which item do you pick? No ambiguity — the board answers it:**

- **Your queue** = the board filtered to `for:<your-lane> -label:needs:hardware -label:needs:maintainer`,
  **sorted by Priority**.
- **Your next task** = the **top-priority *sliced* item** in that queue — P0/P1 before P2 before P3. Every
  P1/P2 is triaged to be **owned, sliced, and actionable**; you don't need permission to start it.
- **Epics are not tasks.** An item labelled `epic` is a *parent* — work its **sliced children**, never the epic
  card itself. If an epic has no open sliced children, *that* is the thing to flag (`for:workflow`).
- **`needs:hardware` / `needs:maintainer` are out of your queue** — the maintainer's bench and decision queues.
  The filter above already excludes them; don't pull from them.
- The **only** thing you escalate is a top item that genuinely isn't actionable (missing slice, unclear AC) —
  and that should be rare, because the backlog is kept triaged. Route it `for:workflow` and take the next item
  meanwhile.

**Then act — don't wait, don't ask when you can do:**

- **Your PR merged** → reconcile it (confirm what it satisfies) and **chase what it unblocks downstream.**
- **A dependency landed** → pick up the now-unblocked work and **advance it this session.**
- **A new `for:<your-lane>` issue, or an RFC for you** → triage, answer, or act.
- **You have a question for another lane** → **post it on the issue and route it `for:<lane>` right then.**
  Do *not* hold it for the maintainer to relay.
- **Default to action over questions.** If something is unblocked and in your lane, do it. Reserve escalation
  to the maintainer for genuinely maintainer-only calls (merges, hardware approvals, product direction).

**The anti-patterns this kills:**

- Discovering unblocked work only when the maintainer's next status round happens to surface it.
- Answering a status request with questions you could have **answered or routed** yourself.
- Making the maintainer relay a message between two lanes that the **issue thread** could carry directly.

A lane that self-syncs keeps the whole system advancing between the maintainer's check-ins — instead of
stalling until the next relay.

## Labels (quick reference)

- `type:*` — the kind of work (mirrors the commit `type:` vocabulary)
- `area:*` — the subsystem (control / logging / sensing / actuators / analytics)
- `layer:*` — `firmware` (needs a reflash) vs `host` (build anytime)
- `blocks:*` — milestone **gates**, independent of Priority: `blocks:pumps`, `blocks:public-release`,
  `blocks:data-integrity`. Filter by these to see what stands between us and pumps / a public release /
  trustworthy data.
- `needs:hardware` — blocked on a **maintainer hardware/bench session** (wiring, pump/relay setup, hardware
  not yet on hand). The maintainer's hardware queue; **lanes skip these** when sweeping Backlog.
- `needs-verification` — set when an issue enters the gate (above)
- `good first issue` / `help wanted` — welcoming places to start

Priority, Size, and Verification are **board fields**, not labels — see [The board](#the-board).

## Where we'd love help

**[Contributors Welcome](../docs/CONTRIBUTORS_WELCOME.md)** is our living list of things the project would
genuinely love a hand with — resistive-sensor support, board configs beyond ESP32 + Arduino, and a
host-the-stack tier. At launch these graduate into `help wanted` issues; until then, the list is the map.

## Questions?

Ask in [**Discussions → Q&A**](https://github.com/OrangePeachPink/plants/discussions/categories/q-a).
No setup question is too small.
