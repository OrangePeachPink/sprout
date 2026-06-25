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
| **Status** | Backlog → In Progress → In Review → Needs Verification → Done · Won't Do | where the work is in its life |
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
4. **Run the checks** before pushing — see **Development & tooling** in the [README](README.md)
   (ruff, clang-format / clang-tidy, markdownlint).
5. **Open a PR** and fill in the template. Link the issue with **`Refs #N`** or **`Part of #N`** —
   **not** `Closes #N` (see the gate below). Include how you verified the change.
6. PRs are **squash-merged** — one clean commit per change; the branch auto-deletes after merge.

## The verification gate (why issues aren't auto-closed)

Sprout uses a **review-before-close** gate: merging a PR does **not** close its issue. Instead:

1. The implementer posts **evidence** on the issue (what was built, how it was verified), moves it to
   **Needs Verification**, and adds the `needs-verification` label — but does **not** close it.
2. A **reviewer** checks the change against the issue's **technical, functional, and quality** intent,
   records a disposition in the **Verification** field (Approved / Conditional / Changes requested), and
   *then* — as a separate, deliberate step — closes it.

That's why PRs use `Refs #N` (a non-closing link) rather than `Closes #N`, and why the repo's
"auto-close issues with merged linked PRs" setting is **off**. The human confirmation *is* the gate.

## Labels (quick reference)

- `type:*` — the kind of work (mirrors the commit `type:` vocabulary)
- `area:*` — the subsystem (control / logging / sensing / actuators / analytics)
- `layer:*` — `firmware` (needs a reflash) vs `host` (build anytime)
- `blocks:*` — milestone **gates**, independent of Priority: `blocks:pumps`, `blocks:public-release`,
  `blocks:data-integrity`. Filter by these to see what stands between us and pumps / a public release /
  trustworthy data.
- `needs-verification` — set when an issue enters the gate (above)
- `good first issue` / `help wanted` — welcoming places to start

Priority, Size, and Verification are **board fields**, not labels — see [The board](#the-board).

## Questions?

Ask in [**Discussions → Q&A**](https://github.com/OrangePeachPink/plants/discussions/categories/q-a).
No setup question is too small.
