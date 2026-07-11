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
7. **Who merges:** the maintainer — except that for some pre-scoped internal work items the maintainer
   delegates the merge to the verification process under audited guardrails (`velocity:v2` label; see
   AGENTS.md § Velocity modes). **Community contributions always get direct maintainer review and merge** —
   the delegation never applies to external PRs.

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

**Closing a duplicate or superseded issue — leave a top-of-body banner (#635).** The close-reason
("not planned") and board column ("Won't Do") say *what* but never *why*, and your explanatory comment sits
at the **bottom** of the thread — so a developer onboarded later lands at the top of the body with zero
context. When you close as a duplicate or superseded, **prepend** this banner to the original body (never
replace it — the original text is history), and optionally prefix the title `[DUPE → #NNN]`:

```markdown
> [!IMPORTANT]
> **DUPLICATE — closed, not on the roadmap.** Superseded by **#NNN** (reason — e.g. *first-filed wins, parallel-cut collision*). Anything of value here was folded into #NNN. Nothing in this thread is planned work. *(Banner per the duplicate-context convention, #635.)*
```

Use **SUPERSEDED** in place of **DUPLICATE** when the work was overtaken by shipped functionality rather than a
single newer issue. **Look before you label:** banner only genuinely dead threads — verify the issue wasn't
*reopened and merged* as the real implementation before tombstoning it.

Use **DECIDED AGAINST** when the issue was *considered and declined* — not a duplicate, not superseded. This is
the **highest-value** variant: a duplicate's lost context is mildly annoying, but a rejection's is expensive —
it's where a contributor burns a day re-proposing something already ruled out, or where a good idea with a
**revisit trigger** stays buried because nobody can see the trigger. Two rules keep it honest:

- **Cite, never reconstruct.** Quote or link the recorded decision (closing comment / ADR / PRD non-goal)
  *verbatim*. If no rationale is findable, flag it for a fresh maintainer ruling rather than inventing one — a
  confident-sounding banner with a reconstructed "why" launders guesswork into doctrine.
- **Closed work only.** Parked-but-alive items keep their `parked` label (no tombstone); delivered work gets
  nothing. The banner means "this ended" — diluting that meaning kills its value.

Preserve any **revisit trigger** in the banner — the narrow condition that would reopen it:

```markdown
> [!IMPORTANT]
> **DECIDED AGAINST — closed, not on the roadmap.** \<one-line rationale, quoting the recorded decision + who decided>. **Revisit trigger:** \<the narrow condition that would reopen it, or "none recorded">. Nothing here is planned work. *(Banner per the decided-against convention, #635.)*
```

`Refs #N` / `Part of #N` (non-closing links), never `Closes #N`; the repo's auto-close setting stays **off**.

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
- **Backlog *and* In Progress** items in your area that are now actionable — an item doesn't have to be sitting
  in Backlog to be untouched. Workflow (or another lane) can move a card's *status* without anyone touching
  *your* item yet — check for a PR or a comment from your own lane, not just the column it's in. But **skip
  anything labelled `needs:hardware`**: those are the maintainer's hardware/bench queue (wiring, pump/relay
  setup, hardware you don't have yet), not lane-advanceable. Filter your board view to
  `for:<your-lane> -label:needs:hardware`, across both columns.
- **A board *status* or *priority* change generates no GitHub notification** — only a comment, label, or
  assignee change does. So don't rely on your notifications/mentions alone to catch new work: **re-pull the
  live board (Project #2) each sync**, per the instructions above. If you only ever check "what's new in my
  notifications," a silent status flip is invisible to you.

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
