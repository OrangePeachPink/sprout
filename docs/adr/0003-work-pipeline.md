# ADR-0003 — Work pipeline: from idea to release

**Status:** Accepted (2026-06-24)
**Date:** 2026-06-24
**Owner:** Workflow lane
**Lane:** work intake, specs/PRDs, backlog, issues, the team workflow, releases & insights
**Elaborates:** [ADR-0002](0002-process-tiers.md) area #6 (Spec & requirements), #7 (Backlog & issue
tracking), #14 (Process telemetry).

---

## Context

One lane owns the entire path a unit of work travels — from a half-formed idea to a released,
documented change — and the process the whole team uses to move it. That includes where ideas land,
how requirements get written and stored, how work is tracked, how an item reaches "done," and how
releases and their notes are produced.

The record used to be a flat markdown backlog edited by several people. A mutable, multi-writer record
belongs in a service with native IDs and concurrency — a database, not a version-control file — so it
moves to GitHub's native tools. This ADR is the single source for that pipeline. It is
deliberately **right-sized as one ADR**; a sub-area spins out only if it grows heavy (a revisit
trigger), rather than fragmenting the pipeline on day one.

## 1. The pipeline at a glance

```text
  idea / goal        requirement         theme            unit of work     the change
  ───────────        ───────────         ─────            ────────────     ──────────
  Discussion   ──▶   PRD (docs/prd/) ──▶ Epic (issue ──▶  Issue       ──▶  PR (Refs #N) ──▶ Release
  (the inbox)        (when it's big)     + sub-issues)    (one slice)      (the gate)        (auto notes)
```

Not every item starts at the left. A typo fix is born as an Issue; a vague "should we add grow-lights?"
is born as a Discussion. The pipeline is *where each altitude of work has a home* — not a mandatory
gauntlet.

## 2. Where work lives at each altitude

| Altitude | What it is | Home |
|---|---|---|
| **Idea / goal** | a not-yet-actionable proposal, roadmap theme, or question | **GitHub Discussions** (an idea inbox; converts to an issue when ready) |
| **Spec / PRD** | a written requirement for a feature or body of work | a versioned markdown file in **`docs/prd/`**, reviewed via PR |
| **Epic** | a theme spanning many issues | a **parent issue with native sub-issues** (progress bar) |
| **Issue** | one independently shippable, reviewable slice | a GitHub **Issue** |
| **Change** | the implementation | a **PR** referencing the issue |

> **Authoring an epic:** its **state lives exclusively in the native sub-issue list** (the progress bar).
> The body carries doctrine, scope notes, and sequencing — **never work-item task-list checkboxes** (`- [ ]`
> / `- [x]`). Two trackers drift silently (#739); the epic-hygiene lint
> ([`tools/dx/lint_epic_subissues.py`](../../tools/dx/lint_epic_subissues.py)) flags it at event time (#810).

## 3. Ideas & questions — GitHub Discussions (the inbox)

**What it is:** a forum-style space (its own repo tab) for open-ended conversation that isn't a
trackable task. The distinction from Issues is sharp and worth internalizing:

- **Issue** = *work to be done* — actionable, assignable, has a "done," gets closed.
- **Discussion** = *a conversation* — a question, an idea, a proposal, an announcement. Threaded,
  up-votable, can be marked "answered"; it has no done/closed-as-shipped lifecycle.
- **The test:** *"Can I assign it and define 'done' in a sentence?"* → Issue. *"Is it a question or a
  maybe?"* → Discussion.

**Categories** (each category has a format) to enable for this repo:

- **Announcements** *(announcement format — maintainers post, anyone comments)* — releases, direction.
- **Ideas** *(open-ended)* — **the inbox**: not-yet-actionable proposals and goals.
- **Q&A** *(question/answer format with an accepted answer)* — usage and contributor questions.
- **Show & tell** *(open-ended, optional)* — people sharing their own builds/setups.

**Converting to action:** when an Idea becomes concrete, use GitHub's **"Create issue from discussion"**
to open an issue (it keeps a link back). If it's big, write a PRD first (§4). The discussion stays as
the rationale trail.

**Enabling it:** repo **Settings → General → Features → check "Discussions"** (a maintainer toggle; not
scriptable). We'll do this together during setup, then seed the categories above.

## 4. Specs & PRDs — `docs/prd/` (how, when, where)

**When to write a PRD** (a Product Requirements Doc — "what we're building and why," before the how):

- the work is bigger than a few issues, or
- it has several acceptance criteria, spans multiple areas, or needs design input, or
- the team needs shared understanding *before* building (to avoid building the wrong thing).
A single shippable slice does **not** need a PRD — it's just an issue.

**Where & format:** `docs/prd/NNN-short-title.md`, versioned, reviewed via PR like code. A
`docs/prd/TEMPLATE.md` (created at setup) provides the shape: *Problem → Goals / Non-goals →
Requirements → Acceptance criteria → Open questions → Out of scope*. A PRD carries a status
(`Draft → Accepted → Implemented`) and links to the epic/issues it spawns.

**Why markdown-in-repo (not the tracker):** a PRD is a *document* — reviewed, occasionally edited,
diff-able — which is what version control is good at. (That's different from the *backlog ledger*,
which is mutable and multi-writer and therefore belongs in Issues, §5.)

## 5. Backlog & issues

**Primitives:** Issues (the ledger; IDs are `#N`) · Labels · Milestones (= builds) · Project v2 (the
board + fields) · Releases (auto notes) · Insights (velocity/cycle-time).

**Labels — colon-namespaced (~16).** `type:` mirrors the project's Conventional-Commits vocabulary so
issue → commit → release-note stays one thread:

- `type:` (one): `type:feat` · `type:fix` · `type:docs` · `type:refactor` · `type:chore`
- `area:` (one+): `area:control` · `area:logging` · `area:sensing` · `area:actuators` · `area:analytics`
- `layer:` (one+): `layer:firmware` (flash-gated) · `layer:host` (build anytime)
- community: `good first issue` · `help wanted` · meta: `blocked` · `needs-verification`

**Project fields** (Priority & Size are fields, not labels — they sort and feed Insights):

- **Status:** `Backlog → In Progress → Needs Verification → Ready to Merge → Done`, + `Won't Do`
  *(Evolved from the lean start: `Ready to Merge` added with the two-stage gate (#369); `In Review`
  removed as ambiguous — it had no owner or trigger, and the two review phases that matter each have
  one: **Needs Verification** = Workflow, **Ready to Merge** = maintainer.)*
- **Priority:** `P0`–`P3` · **Size:** `XS`–`XL` (feeds velocity) · **Milestone** (built-in)

**Templates:** YAML Issue Forms under `.github/ISSUE_TEMPLATE/` (`feature`, `bug`, `task` + chooser);
a `.github/PULL_REQUEST_TEMPLATE.md` carrying the linking convention.

## 6. Right-sized issues

An issue is **one independently shippable, reviewable unit** — about one focused PR, a few days for one
person. **No lower-bound ceremony** (a typo sweep is a fine one-line issue). The concern is
**over-large** issues — **split when any "epic smell" appears:**

- the title needs an **"and"** · sized **L or XL** · spans multiple `area:`/`layer:` · several
  independent acceptance criteria · "done" needs more than a sentence · it'd be more than one PR.

## 7. Decomposition (idea → slices)

Break a PRD/epic into **vertical slices** — each issue a thin *end-to-end* piece of value (read → store
→ show one channel), not a horizontal layer (all parsing, then all storage). Group many slices under an
**epic parent issue** with sub-issues. **Reach for formal decomposition when:** you've written a
PRD/plan and need tickets; you're writing one issue with many independent criteria; an item is L/XL or
clearly multi-part. (A `/to-prd` → `/to-issues` assistant flow can automate context → PRD →
vertical-slice issues.)

## 8. The team workflow & the verification gate

How any item travels, and the rule everyone follows:

1. **Pick up:** card `Backlog → In Progress`; open a short branch `type/short-desc`.
2. **Build:** Conventional-Commit messages; PR links the issue with a **non-closing** reference —
   `Refs #N` / `Part of #N`, **never `Closes #N`** (a closing keyword auto-closes on merge and would
   bypass the gate).
3. **Hand off, don't self-close:** the implementer **posts evidence as an issue comment**, moves the
   card to **`Needs Verification`**, adds the `needs-verification` label — and stops. It does **not**
   close its own work.
4. **Verify:** a **reviewer** (a person, or a separate reviewing role) confirms the result meets the
   issue's **technical, functional, and quality** intent, then closes it (`Closes #N` is the reviewer's
   to use). Otherwise the card goes back with notes.

**Stacked-PR discipline (post-mortem #216):** two rules that must not be skipped when PRs build on each
other:

- **Land base-first.** Merge the bottom PR to `main` first, then rebase the next onto `main`, then
  merge that, and so on. Never merge a child into its parent branch and close the parent unmerged — the
  child's changes go nowhere and any issues closed on the child are falsely marked Done.
- **Verify on `main` before closing an issue.** An issue is not Done until its code is confirmed on the
  default branch (`git log origin/main` or `git show origin/main:<file>`). "Merged into some branch" is
  not enough. The reviewer owns this check at close time.

This is the process the whole team adopts; it will be surfaced to outside contributors via a
`CONTRIBUTING.md` (a setup deliverable).

**Attribution (2026-06-27):** all lanes post from the one `OrangePeachPink` account, so each **signs its
work** — a `— <Lane>` sign-off on PRs, comments, ADRs, docs, and copy, plus a `Lane: <Lane>` commit
trailer so attribution survives in `git log`/`git blame`. The operative convention lives in
[`docs/team/OPERATIONS.md`](../team/OPERATIONS.md) § Lane attribution (internal lanes only) — relocated there
from `AGENTS.md` by the #1125 doc split.

## 9. Milestones, releases, insights

- **Milestones = builds**, SemVer (`v0.4.0`). Closing a milestone + cutting a **Release** generates
  notes from its merged work; a `.github/release.yml` categorizes them by `type:` label.
- **Insights** gives velocity (via Size) and status-flow charts. Deeper cycle-time is deferred (below).

## 10. When a decision merits an ADR

Not every choice needs an ADR — and "ADR everything" is its own over-engineering. An ADR is the **top
rung** of the change ladder (commit → issue + PR → ADR), reserved for decisions a future contributor
will need the *why* for. **Any lane may author an ADR** for an ADR-sized decision in its own area,
under the same numbered series + [register](0000-record-architecture-decisions.md).

**The decision-vehicle ladder** (lightest → heaviest — pick the lightest that fits):

- **Just the change** — reversible, low-stakes, obvious. The git diff is the record.
- **Issue (+ its comments)** — a scoped change, bug, or task; the thread is the record.
- **Discussion** — open-ended exploration ("should we…?"), *before* there is a decision (the ideas inbox).
- **PRD** (`docs/prd/`) — a feature's *what + why* (requirements + acceptance), before the *how*.
- **ADR** (`docs/adr/`) — an architecturally-significant, durable, cross-cutting *decision of record*.

**Write an ADR when any of these is true:**

- **Hard or expensive to reverse** — architecture, data substrate, a public schema/API, repo
  structure, a framework choice.
- **Binds more than one lane** — a shared contract, interface, or cross-cutting policy.
- **Chooses among real alternatives** where the rejected options matter ("why not X?").
- **Establishes a convention everyone must follow** — naming, branching policy, the label taxonomy,
  the verification gate.
- **Sets a foundational default/boundary** — born-correct things, cheap now and painful to retrofit
  (line endings, env tool, data store, directory layout).
- You'd otherwise **re-explain the same "why" repeatedly** to new contributors.

**Good ADR material (patterns):**

- "GitHub Issues is the work ledger; IDs are `#N`." *(cross-lane convention)*
- "Closed-loop on soil moisture only; environmental sensors are logging-only." *(architecture; alternatives rejected)*
- "Raw CSV is immutable; the DuckDB tier is rebuildable." *(substrate; hard to reverse)*
- "Host functionality presents as one application surface." *(cross-lane boundary)*

**NOT an ADR (antipatterns) — use the lighter rung instead:**

- A bug fix or a single feature → an **issue + PR**.
- A reversible, low-stakes tweak (rename a var, nudge a threshold) → just the change.
- A routine choice with no real alternative → no record needed.
- Restating a decision already in another ADR → **link it**, don't duplicate.
- A how-to, runbook, or frequently-edited reference → **docs**, not an ADR (an ADR is a *decision*,
  not a living reference — though pre-1.0 the ADR text itself is editable in place; see
  [ADR-0000 §4](0000-record-architecture-decisions.md)).

Rule of thumb: *if you'll edit it often, it's a doc; if you'll defend it later, it's an ADR.*

## Consequences

- Every altitude of work has a home — a loose idea isn't forced into the tracker, and a shippable slice
  isn't lost in a doc.
- The mutable ledger leaves version control for a concurrent, natively-ID'd service.
- Implementers get an evidence trail with a hard, reviewer-confirmed close gate.
- One lane owns the pipeline end-to-end, so the process stays coherent across the team.

## Revisit triggers

- A sub-area grows heavy (e.g. a formal RFC process) → spin it into its own ADR.
- The Project board starts taxing the planning you enjoy → consider a dedicated tracker (new ADR).
- Manual review proves reliable → earn auto-merge (merge-when-green) + branch protection.
- Velocity needs true cycle-time → add `Started` / `Verified` / `Released` date fields.
- Epics become frequent → add an `epic` label + a Project "type" view.
- Approaching first public release → add a `CONTRIBUTORS` / `AUTHORS` file naming the maintainers.

## Setup dependencies

- Enable **Discussions** (Settings toggle) and seed categories (§3).
- Create `docs/prd/TEMPLATE.md` and a `CONTRIBUTING.md` (§4, §8).
- Grant the `gh` token the **`project`** scope for the board (`gh auth refresh -s project`); issues,
  labels, milestones, and templates need only the existing `repo` scope.
