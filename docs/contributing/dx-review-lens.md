# The DX review lens

*Owned by DX.* The questions a DX reviewer asks **before** technical merits, to protect the person the
[DX North Star](arduino-onramp-north-star.md) describes. It's the DX-owned counterpart to the
[design doctrine](../design/foundations/design-doctrine.md); the lens grows one entry at a time, each one
earned by a concrete case that no other gate caught.

---

## 1. Out of the box (the golden-path fence)

**Any recommendation that touches hardware or setup must answer first: *can the North-Star user do this out
of the box?*** — and it answers *before* its technical merits are weighed. The golden path (the one every
user is expected to walk) may never require **soldering, board modification, or any tool or skill beyond
"plug in the kit."** Power-user options are welcome, but documented as optional, never load-bearing.

A recommendation can be superior on our bench and still disqualifying: the iron, the solder, the practice
boards, and the attrition they imply silently break the "get an ESP32 + a kit + this software, and it
works" promise — and no other gate catches it.

**Precedent — [#566](https://github.com/OrangePeachPink/sprout/issues/566).** A required, user-facing
soldering mod (an EN-pin cap) survived every review with only its *technical* merits examined; it was
rejected on product grounds, because a required solder joint is not "plug in the kit." Option A (the solder
mod) rejected; option B (host-side) ruled. That is the concrete story this lens exists to stop recurring.

This is the operational half of the **out-of-box fence** in the
[design doctrine §3](../design/foundations/design-doctrine.md) — it fences required **skills, tools, and
physical modifications** (ADR-0028 fences required *parts*).

---

## 2. One bug is a class (prove the class is empty)

**A single-instance defect report is never a one-off — it's the first sighting of a class, and the fix
isn't done until the class is swept.** When a bug is filed, the DX reviewer asks *what's the general shape
of this, and where else does it live?* — then sweeps the tree for siblings and either fixes them or files
them, so the closing evidence reads "the class is empty," not just "this instance is fixed."
(#895 house standard.)

**Precedent — [#908](https://github.com/OrangePeachPink/sprout/issues/908).** One reported broken
contributor link (`/blob/HEAD/`) was the visible tip of a link-integrity class; the DX audit swept every
tracked doc, which surfaced the internal sweep (#911) and the broken-image page (#912) that the single
report never mentioned. The maintainer shouldn't have to ask "did you check the rest?" — the sweep is the
default, and the answer ships with the fix.

The automated form of this rule for the link class is the **link-check gate**
([#913](https://github.com/OrangePeachPink/sprout/issues/913), `tools/dx/link_check.py`): once a class can
be mechanically swept, the gate keeps it empty so no one re-sweeps by hand.

*— DX 🌱*
