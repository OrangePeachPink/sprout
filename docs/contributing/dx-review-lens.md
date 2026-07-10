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

*— DX 🌱*
