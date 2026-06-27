# `_archive/` — archeology only

**Nothing in this folder is live.** What remains here traces *why* the Sprout brand and design system reached
its current state — not *how* to build anything now.

> **If it's live and current, you'll find it in the [Sprout Design Library](../Sprout%20Design%20Library.dc.html).**
> That is the single front door for every active design asset (ADR-0010). If something is in here instead, it
> has been replaced by a current, aligned version in the Library.

## What's here

- **[`roads-not-taken.md`](roads-not-taken.md)** — the distilled record of the not-selected routes: the
  alternate name candidates (Tendril / Tilth / …), the v1 and v2 visual generations, and the pre-v3 page
  originals. For each: what it was, why it was left behind, the useful anti-pattern, and where the bytes live.
- **`sprout-backlog.md`** — a stale "next session" backlog from the Day-in-the-Life era. Its naming thread is
  now folded into `roads-not-taken.md`; the rest is unactioned history. A candidate for a future pass.

## What used to be here, and where it went

On 2026-06-26 the heavy archive was pruned. The point-in-time **delivery handoffs** (`*-handoff/`,
`phase1/2/3-*`, `runtime-policy-drop/`) and the duplicated **originals/previews** (`pre-v3-originals/`,
`v1-v2-previews/`) were removed: they duplicated bytes that **Git history already preserves**, and the handoffs
carried point-in-time delivery notes (including a teammate's name) that don't belong in the standing tree.

- **The reasoning** that was worth keeping is distilled in `roads-not-taken.md`.
- **The delivered work** lives in its aligned, current form across the shelves (`tokens/`, `components/`,
  `foundations/`, `brand/`, `voice/`, `motion/`, `go-to-market/`, `merch/`) and the ADRs.
- **The original bytes** are recoverable from the canonical repo's Git history:
  `git log --all -- "<path>"` then `git show <sha>:"<path>"`.

## Why archived

These were prior generations and one-time delivery packages, not working documents. *Supersede, never delete*
(ADR-0010) is honored by distillation: the **why** is preserved above, the **bytes** in version control — so new
contributors trip over neither a stale version nor a heavy duplicate.

*tend well.*
