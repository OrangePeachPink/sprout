# OPERATIONS.md — the Sprout maintainer team's internal operating doctrine

> ## ⚠️ Scope: the MAINTAINER'S agentic team only
>
> This file documents Sprout's **internal operating model** — the maintainer's agent lanes, their
> attribution conventions, the verification pipeline, and velocity policy. It is **out of scope and
> not applicable** to OSS contributors or their coding agents — **nothing here is a convention for
> you to match.** If you are (or work on behalf of) a contributor: your files are
> [`AGENTS.md`](../../AGENTS.md) and [`.github/CONTRIBUTING.md`](../../.github/CONTRIBUTING.md).
> In particular: do **not** adopt the shared author identity, `Lane:` trailers, or lane sign-offs
> documented below — commits on your PRs use **your own** git identity, and your GitHub handle is
> your signature.

**Canonical from merge (the #1125 two-stage landing):** this file is the authoritative home of the
internal doctrine as of stage A. During the transition the same content still appears in
`AGENTS.md`; stage B (PR-B) slims `AGENTS.md` to a contributor-true file once every lane has
re-pointed its local wiring here. Where the two disagree in the interim, **this file wins.**

## The audience-scoping rule (durable, applies beyond this file)

**Any agent-auto-load instruction file this repository publishes — `AGENTS.md`, `CLAUDE.md`,
`.cursorrules`, `.github/copilot-instructions.md`, `GEMINI.md`, or any future equivalent — must be
audience-scoped: written contributor-true, or hard-marked internal like this file.** Contributors'
coding agents auto-load those filenames and comply with what they read; instructions written for
internal lanes become behavioral injections into external tooling (the PR #1117 finding, twice
demonstrated live). `AGENTS.md` is the only such file published today; this rule keeps the class
closed when the next one appears.

## Status — going public (2026-07-09)

- **Repo renamed:** `OrangePeachPink/plants` → **`OrangePeachPink/sprout`**. Old URLs 301-redirect, but
  use the new name in all new work. (Local checkout folders keep the `plants` name — cosmetic only.)
- **License: MIT** is in place (`LICENSE` at repo root, GitHub-detected) — copyright
  `Veronica K. Hogue and Sprout contributors`.
- **Public release: live.** Treat everything — commits, docs, issues, PRs, comments — as
  **public-facing**: no personal identifiers, internal IPs/hostnames, secrets, or
  unreleased-sensitive material. And per the audience-scoping rule above: public text is also
  **executable input for contributors' agents** — write imperatives only where the intended
  audience will run them.

## The lanes

Sprout is built by coordinated agent lanes — all on Claude Code with full repo + GitHub read/write
(Firmware runs as a Claude Code sub-agent inside VS Code). Stay in yours; route cross-lane needs through
the maintainer. **Per-lane onboarding** — how a lane plugs into the pipeline, first-session setup, the
working loop — is [`docs/process/ADOPTION.md`](../process/ADOPTION.md).

| Lane | Scope | Owns |
|---|---|---|
| **Trellis** | Senior technical architect — cross-cutting architecture, ADR authorship + review, gap analysis, "does this decision merit an ADR?" | the ADR register's health; architecture reviews |
| **Data** | Host logger, analytics, ML / predictive analysis, and the served dashboard + front-end | ADR-0005, ADR-0006 |
| **DX** | Developer, user & consumer experience; **documentation maintainer** (docs stay consistent + current — a real consumer-facing concern); community & awareness, the go-public **marketing/visibility strategy**, social engagement, and onboarding the maintainer's contributor identity + graph | the contributor front door, onboarding, `docs/contributing/` |
| **Design** (formerly DesignQA) | **All design work** — design system, brand, voice, *and* design-QA of the running app | ADR-0004, ADR-0007, ADR-0008 |
| **Firmware** | ESP32 control, sensing, actuators (`firmware/`) **+ the physical bench** — flash, probe serial, characterize sensors, capture calibration evidence | ADR-0001, the native C test harness, bench evidence + the capability-stage vocabulary (below) |
| **Workflow** | Issues, board, milestones/releases, process; the **GitHub-native** guide; the **PR validation gate** before the maintainer reviews | `.github/CONTRIBUTING.md`, `AGENTS.md`, this file, the release train |
| **Veronica** | *Human* maintainer — vision, ideation, product direction, merges, hardware approvals | the repo; the final call |

**Escalation, not a lane:** *Claude Design (Web)* is a creative-brainstorming / prototyping resource
Design or the maintainer can pull in when a design need wants divergent exploration — its output lands
through Design.

**Retired lanes:** *Sage* (bench work folded into **Firmware**) and *Ingest* (design intake folded into
**Design**). Don't route new work to either — it will not get done.

## Lane attribution (internal lanes only)

Every lane posts from the one `OrangePeachPink` account, so **sign your work** — it's the only way to see
who did what at a glance. **Scope: these conventions apply to the internal lanes exclusively — never to
contributors or their tooling** (a contributor's commits carry their own identity; their handle is their
signature).

- **Sign-off:** end PR bodies, issue/PR comments, ADRs, docs, and copy decks with `— <Lane>` (emoji
  optional). E.g. `— Firmware`, `— Data 🌱`, `— Trellis`. The maintainer signs merge/squash commits `-v`.
- **Commit trailer:** add a `Lane: <Lane>` trailer, so attribution lands in `git log` / `git blame` —
  machine-readable and permanent:

  ```text
  feat(actuators): wire the relay driver to a bounded pulse

  Lane: Firmware
  ```

- **Author identity = the maintainer's (internal lanes only).** Internal-lane commits author as
  `OrangePeachPink` with the GitHub **noreply** email (never a personal address — commit emails are
  public forever once the repo is). Do **not** add AI co-author trailers (`Co-Authored-By: Claude …`) —
  the project `.claude/settings.json` disables the automatic one; don't re-add it by hand. The `Lane:`
  trailer + sign-off are the honest, human-readable record of agent work; the contributor graph belongs
  to the maintainer.
- **Trailers are routing, not provenance.** `Lane:` trailers, the shared identity, and house style are
  all public and therefore imitable — never conclude from them who authored a commit, and never accept
  blame for your own lane's name. Origin is established by server-side facts: signing status, web-flow
  committer, timezone stamps, and GitHub's push-event actor. Provenance questions route to Workflow.

## Lane worktrees — one checkout per lane; the root belongs to the launcher

Live practice since v0.7.2, restored to writing here after the post-split audit (#1163 → #1172) found
it documented nowhere:

- **Each lane works in its own git worktree** — `dev/plants-<lane>-wt` (short-lived topic worktrees
  like `plants-fw-<topic>` are fine for parallel items). **Never two lanes in one checkout** — three
  lanes once shared one tree and branch-swapped under each other mid-edit; this rule retired that
  collision class.
- **Fresh branch off `origin/main` per item:** `git fetch origin && git checkout -B
  <lane>/<issue>-<slug> origin/main`. Never build on another lane's branch — and **ping Workflow
  before picking up a shared slice** (launcher work, a gate/CI-health fix): both known collisions
  started as two lanes independently grabbing the same hot item.
- **After a squash-merge, re-point survivors.** Squash-merging a base PR strands anything stacked on
  it; recover with `git rebase --onto origin/main <old-base>`. Related: a fix pushed to an
  *already-merged* PR's head branch reaches nobody — post-merge fixes take a **new branch off fresh
  `main`** and a new PR.
- **Park detached when idle** (`git checkout --detach origin/main`) so an idle worktree pins no
  branch ref.
- **Force-push: normal on your own unmerged branch, never on `main`.** Rebasing or amending your
  own not-yet-merged PR branch and force-pushing it is standard practice here (use
  `--force-with-lease`). `main` is branch-protected — force-push is impossible there, and no lane
  should invent a stricter repo-wide ban (one session did, and left its branches diverged for
  nothing — the 2026-07-19 reconcile finding).
- **The repo root checkout belongs to the launcher — never a lane surface.** It stays **on the
  `main` branch**: the launcher self-updates via `git pull --ff-only`, and a detached or
  branch-switched root silently serves stale code. Corollary: no lane worktree ever checks out the
  `main` ref (git allows one worktree per branch — the root holds it).

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

## Owner & consulted (revised 2026-07-21, ADR-0003 §5 — the label→field migration)

**Accountability is the `Owner` board field — exactly one lane per issue** (the maintainer is a
lane). Workflow sets it at triage; a lane that thinks an owner is wrong proposes a re-own, never
silently takes work. Lanes find their queue in their one-word board view (`firmware`, `data`,
`design`, `dx`, `trellis`, `workflow`; the maintainer's is `vmine`).

**`for:<lane>` now means CONSULTED — zero or more per issue: you owe the owner an input.** A
consulted ask carries an **explicit response window or an explicit non-blocking marker** — never
an expiring default. Check your consult bookmark (`issues?q=is:open+label:for:<lane>`) each
sweep so no owed input rots. Family: `for:firmware` · `for:data` · `for:design` · `for:dx` ·
`for:trellis` · `for:workflow`. (`for:maintainer` is **retired** — work that is hers carries
`owner = maintainer`; a decision/click due *now* is the `needs:maintainer` label, nothing else.)

- A label is never evidence of who authored a commit (Lane attribution above governs).
- Use `for:workflow` when unsure where something goes, or when an item needs the pipeline
  ("please slice this"); `for:trellis` flags an architecture / gap review — advisory, not a gate.
- **Review is never labeled** — it's a fixed pipeline stage (Workflow certifies everything; the
  maintainer merges V1), not per-issue routing.

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
  **Size** (XS–XL) · **Milestone** (target version — see below) · native **Sub-issues progress**.
  *(The former **Verification** field is retired — the Status column is the one verification
  signal, #729.)* *(The old custom "Wave" field is
  retired — milestones are the roadmap spine.)* **Priority & Size meanings are the standard** — set them
  on the board, never in comments; definitions in
  [CONTRIBUTING](../../.github/CONTRIBUTING.md#priority--size--the-standard).
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
  **`Refs #N`** / `Part of #N`, **never `Closes #N`**; merged PRs do not auto-close issues. The full
  per-stage detail + the tombstone-banner conventions are in **§ The verification pipeline**, below.
- **`main` is protected:** PR required, squash-merge, no direct pushes, no force-push/deletion.
- **Gate labels** `blocks:pumps` / `blocks:public-release` / `blocks:data-integrity` mark
  milestone gates, independent of Priority.
- **Milestones = versions = the roadmap/release spine** ([ADR-0009](../adr/0009-versioning-and-release-policy.md)).
  A milestone is a shippable SemVer version (`v0.7.1`, `v0.8.0`, …) and the home for its planned work —
  **no milestone = backlog.** The roadmap runs `v0.7.0` (Monitor, shipped) → `v0.9.0` (pumps) → `v0.9.9`
  (pre-release playbook) → **`v1.0.0`** (the deliberate public release, never reached by counting).
- **Releases carry the notes.** Cutting a **GitHub Release** at a version tag **auto-generates** notes from
  the PRs merged since the last tag, categorized by `.github/release.yml` (`type:` labels), then curated.
  A release isn't done until its notes **and** a [`CHANGELOG.md`](../../CHANGELOG.md) entry exist (ADR-0009 §6).
  So a PR's title + `type:` label *are* release-notes copy — write them accordingly.

## The verification pipeline

The per-stage detail behind the two-stage gate above — the flow the maintainer and the lanes run to.
(Contributors don't need this; CONTRIBUTING keeps the plain path and points here.)

**Backlog → In Progress → Needs Verification → Ready to Merge → Done** · *Won't Do*

**Backlog — triaged ideas.** An item here has a clear, done-definable goal and carries **acceptance
criteria**: a short, testable list of what "done" means. Shape the requirement *here* (comments, an ADR,
outside opinions) — far cheaper than reworking it after it's built.

**In Progress — the lane builds.** Before moving on, the implementer: confirms / sharpens the acceptance
criteria on the issue; implements the work; tests it (the relevant `pytest` / native harness); runs lint +
format + commit hooks and confirms **local == CI green**; opens a PR with **`Refs #N`** (never `Closes`).

**→ Needs Verification — post evidence, then stop (Workflow's inbox).** Gated on a
**requirement-by-requirement evidence map**: for each acceptance criterion, show *how* it's met with a
concrete artifact — PR # + commit SHA, file/function (`path:line`), the test that covers it *and that it
passes*, CI status, plus any manual / bench check. Not "defaults fixed ✓" — instead `AC #1 (serial default)
→ dashboard_template.html:265 + test_control.py::test_serial_default passing, PR #338 @d4315ef`. The
implementer does **not** self-merge or move further. **Needs Verification is Workflow's review inbox, not
the maintainer's.**

**Workflow review (at Needs Verification).** Workflow **independently validates** — beyond the lane's
self-report — against: the source docs (PRD / ADR / issue) and the requirement's goals; the AC-by-AC evidence
map; commit history and issue / PR comments; **CI green — local hooks *and* remote CI — and mergeable** (no
conflicts, no stacked-PR traps) — plus its own judgment that the work is **fully implemented** (not a slice
that happened to move the card), **substantially meets the *entirety* of the requirement's goals**, and is
**quality** (correct, no regressions, in-lane, honest-data-compliant where it applies). On pass, Workflow
posts a **Ready to Merge certification** (what was verified + which lanes approved the design + any
**merge-order** notes) and moves the card. A weak map, a missed goal, or a dependency snag **bounces back**
with specifics.

**→ Ready to Merge — merged.** The card carries the full evidence chain **plus Workflow's independent
certification**. Who merges depends on velocity mode (§ below): **V1 → the maintainer merges** from here,
relying on the whole chain plus Workflow's review; **V2 → Workflow merges/closes** under the V2 fence. PRs
squash-merge.

**Done — and Won't Do.** On merge the issue closes (auto-Done moves the card; because PRs use `Refs`, the
close is explicit). **Won't Do** is the terminal for "decided against": close as **"not planned"** (not
"completed") with a one-line reason. **Partials:** if a merged PR met an issue's *core* requirement but a
clean, separable follow-on fell out, spin a **new issue** for the remainder (linked both ways) and close the
original — a tail never gets swept into the merge dustbin. A PR that misses the issue's *main point* is not
closed — it's flagged back.

### Closing a duplicate, superseded, or rejected issue — tombstone banners (#635)

The close-reason ("not planned") and board column say *what* but never *why*, and an explanatory comment sits
at the **bottom** of the thread — so a developer onboarded later lands at the top of the body with zero
context. When you close as a duplicate / superseded / declined, **prepend** the matching banner to the
original body (never replace it — the original text is history), and optionally prefix the title
`[DUPE → #NNN]`:

```markdown
> [!IMPORTANT]
> **DUPLICATE — closed, not on the roadmap.** Superseded by **#NNN** (reason — e.g. *first-filed wins, parallel-cut collision*). Anything of value here was folded into #NNN. Nothing in this thread is planned work. *(Banner per the duplicate-context convention, #635.)*
```

Use **SUPERSEDED** when the work was overtaken by shipped functionality rather than a single newer issue.
**Look before you label:** banner only genuinely dead threads — verify the issue wasn't *reopened and merged*
as the real implementation before tombstoning it.

Use **DECIDED AGAINST** when the issue was *considered and declined* — the **highest-value** variant: a
rejection's lost context is expensive (a contributor burns a day re-proposing a ruled-out idea; a good idea
with a **revisit trigger** stays buried because nobody can see the trigger). Two rules keep it honest:
**cite, never reconstruct** (quote or link the recorded decision *verbatim*; if no rationale is findable,
flag it for a fresh maintainer ruling rather than inventing one), and **closed work only** (parked-but-alive
keeps its `parked` label; delivered work gets nothing). Preserve any **revisit trigger** — the narrow
condition that would reopen it:

```markdown
> [!IMPORTANT]
> **DECIDED AGAINST — closed, not on the roadmap.** \<one-line rationale, quoting the recorded decision + who decided>. **Revisit trigger:** \<the narrow condition that would reopen it, or "none recorded">. Nothing here is planned work. *(Banner per the decided-against convention, #635.)*
```

## Velocity modes — V1 / V2 (standing policy as of v0.7.3)

**The v0.7.2 pilot graduated on its results — 45 accelerated merges, zero reverts, zero red mains, two
real defects caught at the gate pre-merge — and the maintainer's retro directive: expand it.** Target:
**~80% of merges ride V2**, so maintainer review time concentrates where only the maintainer adds value:
grill rulings, first renders of new user surfaces, ADRs, and hardware.

- **V2 — accelerated (the default for internal-lane work).** The lane builds and posts AC-by-AC
  evidence exactly as always — nothing changes for the implementer — but **Workflow verifies AND
  merges/closes**, without the maintainer in the loop.
- **V1 — maintainer-merged.** The two-stage gate with the maintainer's click: Workflow certifies to
  **Ready to Merge** (label `needs:maintainer`), **the maintainer merges.**
- **Velocity lives on the `Velocity` board field** (set at planning; the retired `velocity:*`
  labels are gone — one basket). **Escalation = the lane flips the field**: if a build reveals a
  V1-triggering property (public surface, doctrine, enforcement, hardware, PII), flip V2 → V1 —
  same surface, no second vocabulary, no ask. The gate reads the field at certification.
- **Record-sync refinement (maintainer-ruled 2026-07-20):** a PR that merely records an
  **already-ratified** decision — a ratified ADR status-line flip, scribing a landed ruling into
  its document, register-row sync — is **V2**: the decision already carried the maintainer's
  click; the record catching up doesn't need a second look. Anything that *changes* a ruling, its
  scope, or its public surface stays V1. **Pre-approved scope generally:** an amendment within
  the scope and intent of something already ruled is V2; doubt = V1.
- ***Proposed with this PR (the maintainer's merge ratifies):*** **AC-conformance corrections are
  V2** — an AC correction that only brings an AC into conformance with an already-ratified rule
  (e.g. decoupling retirement from build because the confirmation cycle forbids same-release
  retirement) is gate-executable; only corrections that change *intent* route to the maintainer
  (§8b). Born from the #1144 approval that needed no judgment.

**Standing V1 classes (always V1, regardless of tags):**

- **Firmware delivery-channel** — anything flash-affecting: released bins, manifests, signing, OTA,
  `WEB_FLASH_VERIFIED`. (Firmware *host-side / native-tested library code* with no delivery-channel
  effect is V2-eligible.)
- **ADR / doctrine** — including this section.
- **New public-voice surfaces** — the *first render* of a new user-facing surface, new voice copy
  outside a grill-locked contract, README/release-notes voice. **Iterations within a grill-locked
  contract and the design library are V2** — this is what the grill buys: rulings become contracts,
  contracts make design work verifiable at the gate.
- **Repo/process configuration and NEW enforcement** — CI workflows, guards, branch protection.
  (Allowlist/suppression *clears* with fix-landed evidence are V2 — the #1013 precedent.)
- **External contributions** — a community PR never rides V2; outside contributors always get
  maintainer review.
  **Record it as a formal GitHub review** (*Files changed → Review changes → **Approve***), not a
  comment that says "looks good" followed by a merge. Costs nothing, and it is the difference
  between a contributor being approved and merely being merged: the approval is a first-class event
  on their PR, it shows in the timeline as a review rather than a remark, and it leaves the record
  saying who signed off rather than only who clicked merge. A changes-requested review is the same
  instrument pointed the other way — clearer than a comment thread, and it tells them the ball is in
  their court without anyone having to say so. Internal lane PRs keep using certification comments;
  this applies where someone outside the team is waiting to find out whether their work was accepted.
- **Hardware/bench actions and the maintainer's local config** — her hands, her files.
- **PII/identifier-adjacent work** — evidence packets carrying captured output, images, or logs;
  identifier-guard/denylist changes; and any issue/PR **text** naming machines, networks, or people.
  The v0.7.2 lesson: issue titles and bodies carried real identifiers, and the leak-tracking issue WAS
  the leak (#865). The maintainer's eyes on anything an identifier could ride.

**The V2 fence (unchanged, all of it, always):**

- **Builder ≠ certifier survives inside V2.** Workflow never merges its own builds — those route to an
  independent lane verifier, or to the maintainer if no lane fits.
- **Every V2 merge lands one line in the release's accel-merge digest issue** (PR, item, evidence link).
  The maintainer skims it anytime and holds an **instant no-questions revert lever** — comment
  `revert #N` and Workflow reverts, no debate. The lever itself is drill-tested each release (#1040).
- **Docs-only changes** (no captured output, no images, no identifiers) ride V2; **bench-evidence
  packets are V1 under the PII class above** — the gate still pre-verifies them per the landing
  convention, but the maintainer clicks the merge.

(Future rungs V3/V4 — more autonomous building, self-certification — remain named and deliberately not now.)

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

## Backlog / triage

- `BACKLOG.md` is **retired** — historical only, **do not add to it.** All work is in Issues.
- Idea not ready to build → **Discussions.** Ready, assignable, "done" definable in a sentence
  → an **Issue** (use the forms).
- **Labels (post-migration, 2026-07-21):** `type:*` (work kind) · `for:<lane>` (consulted — see
  Owner & consulted) · `blocked` (wait-marker; see below) · `blocks:*` (gates) ·
  `needs:maintainer` (a maintainer click/decision due **now** — nothing else) · `needs:hardware`
  (bench-gated) · `good first issue` · `help wanted`. **Retired** (kept on closed issues —
  history is never relabeled): `area:*`, `layer:*`, `for:maintainer`, `velocity:*` (the `epic`
  label follows once #1446's structural lint discovery lands).
- **The five planning fields live on the board** — Owner · Velocity · Size · Priority · Status —
  written by lanes themselves, one line each: `just board N` reads all five; `just
  owner|velocity|size|priority|status N <value>` writes one (each write re-queries and prints).
  **The readiness gate (ADR-0003 §5):** an issue needs owner + velocity + size + priority +
  complete AC *before work starts* — the `readiness` view shows the debt; nothing in-milestone
  is picked up while it appears there.
- **`blocked` — a wait-marker riding on the true stage, never a column** (maintainer-ruled
  2026-07-21): an item can be blocked in Backlog or In Progress. **No naked blocks** — applying
  `blocked` requires a comment naming *whom/what it waits on and the unblocking event*. Workflow
  sweeps `label:blocked is:open` every cycle and strips the label when the named event fires —
  jams clear by the gate noticing. Never idle silently on a block: label it, name it, keep moving.
- **Epics: status = furthest-along child** (maintainer-ruled 2026-07-21): an epic's Status
  mirrors its most-advanced sub-issue; the gate sweeps epic statuses at each digest merge, and
  an epic whose children read 100%-closed gets flagged to its owner as close-or-name-scope.
- **The verification signal is the Status column and nothing else** (#729, maintainer-ruled):
  `Needs Verification` = evidence posted (each AC individually marked met, with evidence),
  awaiting review · `Ready to Merge` = certified GO. The reviewer's disposition lives in the
  certification comment; changes-requested = the card returns to In Progress with the reason.
  The old `Verification` field and `needs-verification` label are retired — one signal, no drift.
- **A `Won't Do` close names its owner in the closing comment** — an item vanishing from a
  lane's board is not a notification; the ruling comment is ("ruled Won't Do; owner was
  `<lane>`, no action owed"). Push at event time, not absence-noticing.

[board]: https://github.com/users/OrangePeachPink/projects/2

## Architecture review cadence (maintainer-ruled 2026-07-24)

Guard against the strategy quietly falling behind the implementation — or behind what the
roadmap demands. On a **~monthly baseline the maintainer commissions an external
technical-architecture review**, working with an external agent to grade Sprout against
**public-release standards, not internal-prototype health**. It is a **maintainer trigger, not a
scheduled job** — read it as *"prompt the maintainer to request an external architecture
review,"* cadence-guided. The interval **flexes with velocity, volume, and rate of change**:
pull it forward when a chapter warrants (an epic close, a big architecture wave, a fast-moving
week), stretch it when the codebase is quiet. The precedent is the review that drove this week's
hardening pass.

**Delivery pattern — board-and-build, don't narrate (ruled from what worked, 2026-07-24):** a
commissioned review's findings go **straight onto the board as issues, then get built and
shipped — with no running narrative on the Discussions board.** The v0.8.1 hardening pass proved
it: the external review's entire flagged capability set was boarded and delivered in ~2 days of
coding, shipping with the release, zero discussion-board back-and-forth. Boarding-and-building
beat discussing. This does **not** change *§ GitHub-native by default* (general, not-yet-buildable
ideas still belong in **Discussions**) — the distinction is that a *commissioned review's
findings are work*, so they route to **Issues** directly, like any other work.

**The theme-conformance gate (maintainer-ratified 2026-07-24, the #1534 fold):** a **themed
release closes with a theme-level delta review** — expectation → promise → delivery — before its
retro is considered complete. Increments passing their ACs does not establish that the *theme*
shipped: v0.8.0 "Predict" closed with its self-declared headline (`predictor.py`) reaching no
surface and its trust instrument dark, and the retro never asked. The review runs blind-first
where practical (independent expectation baselines before the record is read; the fold pattern
of #1534), composes with the monthly external review above, and its delta lands as issues per
the board-and-build rule. The question it must answer on the record: *did the release name
become true on the operator's surface?*

## Deliberately-not-at-our-scale ledger (ratified 2026-07-20)

Things we have considered and **decline at our current scale** — each with the written trigger that reopens it.
These are decisions, not oversights; the maintainer defends them. Do not file issues for these; revisit only when
a trigger fires.

| Declined | Reopen when |
| --- | --- |
| Build attestations / SLSA provenance (signing + immutable releases + exact-tag builds already give the property that matters) | a supply-chain incident, or we distribute through a channel where users can't read the source |
| Dashboard authn / authz / CSRF / threat-model redesign (it's a localhost operator tool; non-loopback rejection covers it) | we intentionally support remote access — an ADR-0014 revisit, not a defect fix |
| Governance / maintainers / decision-rights document (the lane model + this file already record decision rights) | a second maintainer gets merge rights; a contributor disputes a decision; regular contributors exceed ~10 |
| One-approval branch-protection rule | a second trusted maintainer exists |
| Per-device OTA onboarding credentials (signed pull-updates already route this) | we ship push-OTA to devices we don't own |
| Parquet WAL / staging / atomic publication | — already scoped in #1241; it's that issue's own design work |
