# Sprout design doctrine

_Foundations · decision of record · steers every lane's day._
_Owner: Design-QA 🔍 · enforced through epic #726 · v0.7.1._

This is the north star every Sprout surface is judged against. It is short on purpose. If a screen,
card, chart, label, or control can't pass the tests below, it isn't done — regardless of how correct
the data behind it is.

It sits alongside the other decisions of record it must cohere with: the **honesty rules** (raw counts +
the calibrated band are truth; a percentage is a labelled index, never VWC — ADR-0004, ADR-0007 §5), the
**character ↔ instrument boundary** (ADR-0008), and the **canonical band vocabulary**
([`mood-band-map.json`](../components/mood-band-map.json)).

---

## 1. The four-question test

A person standing at their windowsill, maybe with a dozen plants, looks at a Sprout surface to answer
four questions **in this order**. Every element on a plant surface earns its place by helping answer one
of them; anything that answers none of them is clutter.

| # | Question | What the UI must make obvious |
|---|----------|-------------------------------|
| 1 | **Which plant?** | The physical plant, identifiable at a glance — plant-first (p01…, name, type, pot), then the sensor the user labelled, then which board and side of the ledge. Never a machine id or channel index. |
| 2 | **What band?** | The current calibrated moisture band, in the canonical band words — not a raw number alone, not a bare percentage. |
| 3 | **How urgently?** | _How badly, how soon._ Two plants in the same band are not equal — one deep in **Dry** needs water before one that just entered it. Position within the band must be legible. |
| 4 | **Should I water it?** | The decision. The surface should land the human on an action (water now / soon / fine), not leave them to compute it. |

Expanded, this is the user-centred articulation from the retro:

1. Does this plant need water?
2. How badly / how soon?
3. Does the human looking at it **know** that?
4. Can the human tell **which** physical plant — out of maybe dozens?

**How to apply it (any lane, any surface).** Before you call a plant surface done, walk the four
questions out loud against it:

- [ ] **Which plant** — could the maintainer physically walk to the right pot from what's on screen?
  (No machine ids as the human label; sensor labels mean the user's sensors, never channels — #713.)
- [ ] **What band** — is the calibrated band word present, with raw as truth and any % labelled as an index?
- [ ] **How urgently** — can you distinguish two plants in the same band by need? (Ordering, a position
  marker, weight/intensity, or an explicit water-now/soon/ok cue.)
- [ ] **Should I water it** — is the next action obvious without mental arithmetic?

If any box fails, the surface isn't shippable yet. File the gap under the epic (#726).

### Identity corollary (from #713)

Question 1 is failed most often, so it gets its own rule:

- `sN` in the UI **always** means the physical sensor the user labelled — never an MCU channel index.
- The **plant** is the primary label everywhere (p01… / name / type).
- Device ids (the ADR-0027 6-char base32 like `8gtt1h`) are stable machine keys — **never** a
  human-facing label. They live behind a details/debug affordance, if anywhere.
- Boards are named the way the maintainer named them (ESPclassic / C5Official) with their side (left / right).
- GPIO / pin numbers are one-time wiring facts — kept out of glanceable views, available behind a
  per-plant "wiring details" affordance (#714).

A good composite reads **"p02 · Pothos (XXL) · s2 · ESPclassic (left)"**, not `s2@8gtt1h GPIO 35`.

---

## 2. The two-jobs split rule

When a surface is quietly serving **two useful purposes at once** — a real-time / monitoring job **and**
a setup / calibration / configuration / reference job — do **not** rename it into one and discard the
other. Design **two discrete tools**, each on its own screen, each understandable alone.

Home each half where it belongs:

- **Live / monitoring** jobs → **Monitor**.
- **Calibration / config / verification / reference** jobs → **Diagnostics & Logs**.

The test before any rename/relabel in the sweep: _does this surface do a live job and a config job?_
If yes, split it. If no, rename freely.

**First instance — the "Calibration ladder" (#716).** Today's panel fuses two jobs: it renders the
calibrated band boundaries and their ratification state (a calibration reference) _and_ overlays each
plant's current reading (a live monitor). The split:

- Live watering-status view → **Monitor** (plant-first rows, colour = band, within-band urgency — #715).
  No "calibration" in the name.
- A real calibration ladder → its own piece under **Diagnostics & Logs**: band definitions, ratification
  / cal-verified vs. provisional state, and the hook to per-channel calibration (#170). This is where
  "ladder" and "calibration" legitimately live.

Watch for the same trap elsewhere in the sweep (the trajectory chart, the integrity / log surfaces).

---

## 3. Scope

This doctrine applies to every plant-facing surface: Monitor, the single-plant detail, Lab, the charts,
and Diagnostics & Logs, plus any surface added later. It is enforced surface-by-surface through the
north-star epic (**#726**); the sibling retro issues (#713–#725) are its first concrete applications.

_— Design-QA 🔍_
