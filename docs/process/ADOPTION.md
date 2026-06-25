# Sprout — lane onboarding & adoption

*How each working lane plugs into the GitHub workflow. Pairs with
[CONTRIBUTING.md](../../CONTRIBUTING.md) (the canonical loop) and
[ADR-0003](../adr/0003-work-pipeline.md) (the decision of record).*

## Welcome

Sprout is on GitHub now — and the no-fly on repo writes is **lifted**.

Thank you for holding the line while the scaffolding went in. You cleared the runway, paused your own
work, and waited patiently for the process to land. That patience is exactly what let us build it *right*
instead of *fast* — labels, board, the verification gate, and a clean idea-to-merge path that every lane
shares. It's appreciated, genuinely. **Sprout welcomes you.** The watering's honest, the board's clean,
and there's one path now. Let's grow it.

## What changed, in one breath

`BACKLOG.md` is retired. **Issues** are the ledger · the
**[board](https://github.com/users/OrangePeachPink/projects/2)** is the working view ·
**[Discussions](https://github.com/OrangePeachPink/plants/discussions)** are the idea inbox. Every backlog
item (A1–E10) is now an issue. The full loop — branch → PR with `Refs #N` → the review-before-close
**verification gate** — is in [CONTRIBUTING.md](../../CONTRIBUTING.md). Read it once; it's short.

## The one rule that defines us

You **post evidence and propose**; a reviewer **confirms and closes**. Never close your own issue — it's
enforced (merged PRs don't auto-close). This is the trust contract that lets four lanes move at once.

## Thread by thread — how to implement

### 🔧 Firmware lane

- **Filter the board:** `area:control` · `area:sensing` · `area:actuators` · `layer:firmware`
- **You own:** [ADR-0001 (architecture & control loop)](../adr/0001-architecture-and-control-loop.md), the
  native C test harness, and `firmware/`.
- **Start here:** **#2** and **#3** are **P0 + `blocks:pumps`** — the safety gates before any pump can
  run. Both carry an independent-review comment spelling out exactly what's still missing; read those
  first. **#38** (the `value`/% relabel) is also yours (`layer:firmware`, `blocks:data-integrity`).
- **Your open board items:** #2, #3, #4, #8, #9, #18, #19, #20, #38. `#18` (pump/actuator logging) is
  `blocks:pumps` — P2 now, promote to P1/P0 when pump bring-up starts.

### 📊 Data lane

- **Filter the board:** `area:logging` · `area:analytics` · `layer:host`
- **You own:** [ADR-0005 (application surface)](../adr/0005-application-surface-and-frontend.md),
  [ADR-0006 (data architecture)](../adr/0006-data-architecture.md), the served app, and analytics.
- **Start here:** **#28** (schema-v1 parser) and **#29** (4-channel dashboard) are your **P1** spine.
  **#9** and **#12** carry `blocks:data-integrity` (durability); **#38** touches the `value` column on the
  schema side.
- **Carry-over:** the HotBoxAQ schema alignment that closed out of #14 (plants-side complete) is a
  **HotBox-side todo** — pick it up when HotBox development starts.

### 🎨 Design lane

- **Access:** the repo stays **read-only** for Design — deliverables land via the commit-proxy thread, not
  a direct push. Ideas → Discussions · specs → PRDs · brand decisions → ADRs.
- **You own:** [ADR-0004 (design system)](../adr/0004-design-system.md),
  [ADR-0007 (brand & voice)](../adr/0007-brand-guidelines.md),
  [ADR-0008 (personality layer)](../adr/0008-design-system-v3-personality-layer.md), and `docs/design/`.
- **On your plate:** the batch-2 voice pass (issue forms + PR / CONTRIBUTING templates — non-blocking
  polish), and a voice pass over this welcome whenever you like.
- **A welcome gift to shape:** an **animated "a day in the life of Sprout"** for the repo home — something
  elegant that draws people in the moment they land. We're seeding it as an Ideas Discussion; the vision is
  yours to own.

## Shared first moves (every lane)

1. **Read** [CONTRIBUTING.md](../../CONTRIBUTING.md) once (~5 min).
2. **Open** the [board](https://github.com/users/OrangePeachPink/projects/2), filter to your area / layer,
   find your column.
3. **For your next piece of work:** move the card `Backlog → In Progress`, branch `type/short-desc`, open a
   PR with **`Refs #N`** (never `Closes #N`), then move the card to **Needs Verification**, post your
   evidence, and **stop** — a reviewer takes it from there.
4. **New idea?** → Discussions. **Significant or hard-to-reverse decision?** → an ADR (any lane may author
   one in its own area; criteria in [ADR-0003 §10](../adr/0003-work-pipeline.md)).

---

*Questions about the process itself go to the Workflow lane (via the project maintainer). Welcome aboard.*
