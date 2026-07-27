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

## If this PR adds or changes an ADR

Which existing ADR did you consider amending, and why didn't you?
<!-- Amend/append is the default (ADR-0003 §10); a new number needs a genuinely new decision. -->

## If this PR touches a contract or schema file

Which seams does this change cross, and are they in the seam register?
<!-- Wire tokens, registry joins, release pipeline — cross-seam claims are never fast-path
     certified (ADR-0003 §8a). Naming the seams here is what keeps the register current. -->

## How I verified it

What you ran or saw that shows it works — the evidence the reviewer checks at the gate.

## Checklist

- [ ] Commits follow Conventional Commits (`type(scope): subject`)
- [ ] Ran the relevant checks (ruff / clang / markdownlint — see the README)
- [ ] Updated docs if behavior or setup changed
- [ ] Evidence a reviewer can check is in **How I verified it** above

<!-- Board state (Needs Verification → Done) is moved by the maintainer/gate, not by you —
     it needs project access you aren't expected to have. Posting the evidence is your half. -->
