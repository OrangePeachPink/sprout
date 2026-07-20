# The orientation convention

**Ratified:** 2026-07-20 (maintainer, #1263) · **Owner:** Design-QA 🔍
**Status:** ratified and applied fleet-wide

---

## The rule

> **Every orientation choice is intentional, never inherited from the scale.**

Three parts, in the order you'll need them:

### 1. Vertical axes: **wet = bottom, dry = top**

Fleet-wide, no exceptions. A dry-down **climbs**. A watering **drops**.

This holds whatever the underlying number is doing. With capacitive probes, higher raw
counts already mean drier — so plotting raw with the usual "bigger is higher" already puts
wet at the bottom. **That is a coincidence, and the convention makes it a rule.** A surface
that plots an *index* (where bigger might mean wetter) must still put wet at the bottom, by
inverting deliberately and saying so in a comment.

### 2. Horizontal surfaces: **wet = left, drier = right**

Pick the wet side once, keep it everywhere. The hero's band-journey (#1136) set it; the
band-movement lanes and the pulse histogram follow it.

Consequence worth stating: **a rightward arrow means drying.** On a horizontal ladder,
"moving right" is always "getting thirstier."

### 3. Vertical-vs-horizontal is itself a choice — and it's recorded

Not a default, not whatever the container made easy. The working rule:

- **Moisture takes the y-axis when x is time** (any history, trajectory, or sparkline).
- **Moisture takes the x-axis when the surface is timeless** (a ladder, a band strip, a
  position marker) — there is no time to spend the horizontal on, so the state uses it.

---

## Applying it

| Surface class | Orientation | Why |
| --- | --- | --- |
| History / trajectory / sparkline | vertical, dry-top | x is time |
| Distribution histogram | horizontal, wet-left | x is the envelope, timeless |
| Band ladder (hero, cal reference, watering status) | vertical, dry-top | a stack of states |
| Band-movement lane, band-journey strip | horizontal, wet-left | one row per plant, timeless |
| Trend arrow | ↑ = drier | inherits rule 1 |

## Conformance at a glance

Every surface as of the #1263 pass:

- **Conformant already:** Workbench trajectory + single-plant detail (raw ADC, dry-top) ·
  pulse histogram (wet-left) · cal-reference and watering-status ladders (dry-top) · the
  #1136 band-journey (wet-left) · all three #1148 trial surfaces (dry-top / wet-left).
- **Fixed in this pass:** the hero since-watering sparkline (was wetter-top) · the
  band-movement lanes (were drier-left) · the band-movement trend arrows (were down-for-drier).

## For the next chart

Before drawing anything with a moisture dimension, answer two questions **in a comment**:

1. Is the other axis time? → moisture is vertical, dry at top.
2. If not → moisture is horizontal, wet at the left.

If a surface needs to break this, that's a design ruling, not a local decision — raise it,
and record the exception here with its reason.

---

*Ratified from the #1263 audit. Related: ADR-0035 (the band model), the colour-roles charter
(state owns saturation), `mood-band-map.json` (the one vocabulary).*
