# Design-lane ADR handoff — for Veronica to relay to a coding agent

**From:** Design lane · **Date:** 2026-06-24 · **Re:** ADR-0002 confirmations, new ADR-0004, register update

This package contains the Design lane's ADR deliverable. Nothing here touches the backlog or issues. Three
mechanical changes for the coding agent to apply under `docs/adr/` and commit (after review):

---

## 1. Add the new ADR file

Add **`0004-design-system.md`** (in this package) to `docs/adr/0004-design-system.md`, verbatim.

It ratifies the already-built design system and defines the token-consumption contract (the Design→Data
interface). Status: **Proposed** — maintainer flips to Accepted per the 0000 lifecycle.

## 2. Confirm two rows in `docs/adr/0002-process-tiers.md`

Per the reconciliation, flip these two row tags from 🟡 (proposed) to ✅ (confirmed in-lane) and adjust the
"Proposed choice" wording for #17 to reflect the agreed seam. Suggested edits:

**Row #17 — Frontend stack**
- Owner tag: `🟡 Design / Data` → `✅ Design (half) / Data (half)`
- Proposed-choice text → *"Seam: **Design** owns the token + component system and the token-consumption
  contract (see [ADR-0004](0004-design-system.md)); **Data** owns the served-app runtime/stack. Decided host
  stack for now: **vanilla + Sprout tokens**. The control-page framework (React+Tailwind?) is **deferred** to a
  later Data-lane decision; if it goes Tailwind, Design pins the token-consumption bridge then."*

**Row #18 — Design system**
- Owner tag: `🟡 Design` → `✅ Design`
- Proposed-choice text is correct as written ("Design tokens … as CSS custom properties + a small component
  set"); optionally append: *"— ratified in [ADR-0004](0004-design-system.md)."*

> Note: ADR-0002's overall **Status** stays as-is (the maintainer flips it to Accepted once all per-row owners
> have confirmed). This handoff only confirms the two Design-owned rows.

## 3. Add the register row in `docs/adr/0000-record-architecture-decisions.md`

In "The register" table, append after the 0003 row:

```
| [0004](0004-design-system.md) | Design system & token-consumption contract | **Proposed** | Design lane / design |
```

---

## What the Design lane confirmed (summary)

- **#18 Design system** — confirmed as-is; the built v1 (tokens + components + seven-band honesty rules) and
  additive v2 brand match the proposed choice.
- **#17 Frontend stack (Design half)** — confirmed; Design owns the token/component system + consumption
  contract, Data owns the served-app runtime, control-page framework deferred, host stack = vanilla + tokens.
- **Token-consumption contract** — defined in ADR-0004 §3 as the single source of truth for
  color/type/space/radius/elevation.
- **v1 ↔ v2 reconciliation** — owned by Design under #18; deltas reconciled deliberately, never silently
  overwritten.
- **No lane swaps proposed.**

After review + commit, the Design lane **holds** for the no-fly lift and assigned issues.
