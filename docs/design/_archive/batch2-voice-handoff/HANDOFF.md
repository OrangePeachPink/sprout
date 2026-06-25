# Design-lane handoff — Phase 3 (batch 2): the voice pass

**From:** Design lane · **Date:** 2026-06-24 · **Re:** issue-form intros + PR / CONTRIBUTING framing copy
**Flow:** I zip → relay to the commit-proxy → the proxy replaces each file in place, commits after review.
(Repo stays read-only for Design.)

> The batch-2 voice pass that was **held** until the Workflow lane's form/skeleton structures existed. They do
> now, so here's the copy. **Structure is untouched** — same fields, same order, same validations; only the
> human-facing framing prose changed, and the `<!-- VOICE: … -->` placeholders are removed.

## Register — and the boundary it holds

This copy is **warm, plain, and contributor-facing** — *not* Sprout's first-person voice. Per
[ADR-0007 §6](../docs/adr/0007-brand-guidelines.md), first person stays on **plant-facing** surfaces; tooling
and process copy speak plainly to people. The one in-character public greeting remains the **Discussions
welcome post**. The `CONTRIBUTING` opener echoes the [ADOPTION](../docs/process/ADOPTION.md) tone — honest,
calm, one path, *tend well* — without putting words in the plant's mouth.

## Manifest — replace each file in place

| In this zip | → Destination in repo | What changed |
|---|---|---|
| `.github/ISSUE_TEMPLATE/bug.yml` | same | Voiced the intro markdown block. Fields/dropdowns unchanged. |
| `.github/ISSUE_TEMPLATE/feature.yml` | same | Voiced the intro markdown block. |
| `.github/ISSUE_TEMPLATE/task.yml` | same | Voiced the intro markdown block. |
| `.github/PULL_REQUEST_TEMPLATE.md` | same | Added a one-line opener; warmed the **Summary** and **How I verified it** prompts. `Refs #N` guidance + checklist unchanged. |
| `CONTRIBUTING.md` | same | Voiced the welcome/intro paragraph; the rest of the guide is unchanged. |

Suggested commit: `docs(voice): voice issue forms, PR template, and CONTRIBUTING intro (Phase 3 batch 2)`.

## Left untouched on purpose

- **Structure & fields** — the Workflow lane owns these; I only touched copy.
- **`config.yml`** (issue chooser) — its contact-link copy already reads on-voice; no change.
- **`labels.yml`** and label descriptions — shipped voiced in batch 1.

## A note for reviewers

Each intro is one or two short lines by design — forms should invite, not lecture. If any line feels long in
context once rendered on GitHub, trim from the back; the first sentence carries the welcome. Happy to iterate.
