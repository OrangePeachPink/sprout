Thanks for tending Sprout. Fill in what helps and trim what doesn't — these notes carry your change through the
verification gate.

> ✍️ **Your PR title becomes a release-notes line** (auto-generated from titles, grouped by `type:` label —
> ADR-0009 §6). Write it as the sentence you'd want a stranger to read in the notes, and make sure the PR
> carries a `type:` label (`type:chore` is excluded from notes).

## Summary

What does this change do, and why? A sentence or two is plenty.

## Linked issue

Refs #<!-- issue number -->

<!-- Use `Refs #N` / `Part of #N`, NOT `Closes #N` — the reviewer closes the issue after verifying it
     (see CONTRIBUTING.md → "The verification gate"). -->

## How I verified it

What you ran or saw that shows it works — the evidence the reviewer checks at the gate.

## Checklist

- [ ] Commits follow Conventional Commits (`type(scope): subject`)
- [ ] Ran the relevant checks (ruff / clang / markdownlint — see the README)
- [ ] Updated docs if behavior or setup changed
- [ ] The linked issue is in **Needs Verification** with evidence posted
