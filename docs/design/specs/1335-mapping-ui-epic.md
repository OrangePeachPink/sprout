# The mapping-UI epic — spec draft for maintainer review

**Issue:** #1335 (v0.8.1) · **Status:** DRAFT — for review before building
**Absorbs:** #1027 (honesty classes) · #1188 (editor depth tail) · #963 (the cal wizard surface)
**Lane:** Design-QA 🔍 — surface work only; this epic adds no identity-system concepts.

---

## 0. The one sentence

> When the operator types "Gertrude" over "Big Green Plant", **the app must not guess what
> they meant** — because the two possible meanings produce permanently different histories,
> and only one of them is recoverable by editing a string back.

Everything below follows from that.

---

## 1. What the backend already gives us (verified, not assumed)

Read against `registry_model.py` on `main`:

| Primitive | What it does | Which flow it serves |
| --- | --- | --- |
| plant label edit | a string on `Plant` — **no event** | **Rename** |
| `assign(plant_id, sensor_id, device_id, channel)` | opens a mapping, **closing any open assignment on that channel at the same instant** | **Reassignment**, new-plant, install-time capture |
| `close_channel(device_id, channel)` | closes without opening (unmap / disable) | probe retired, board removed |
| `move_plant(plant_id, location)` | close-then-open on location, **synthesising the prior interval** for grandfathered plants | the plant moved shelves |
| `next_plant_id()` / `next_sensor_id()` | minted ids | new-plant, adopt |
| `set_lifecycle` / `purge` | retire / remove | board removal |

**The seam is already atomic and already correct.** `assign()` closes the old binding with the
*same* timestamp it opens the new one, so there is no gap and no overlap — the join can
attribute every reading to exactly one plant. What is missing is **only the surface that
chooses which primitive to call.**

One correction to the issue text, worth stating because it changes the spec's shape:
`move_plant()` is the **location** primitive (a plant moved shelves). The Gertrude case is
**`assign()`** — the *channel* rebinding to a different plant. Both are close-then-open, but
they are different events on different entities, and the UI must not conflate them.

---

## 2. The disambiguation — the heart of this epic

Editing the name field is **ambiguous by nature**. Three intents share one gesture:

| Intent | What is true | Event | History |
| --- | --- | --- | --- |
| **Rename** | same plant, better label | none | continuous — every past reading still this plant's |
| **Reassignment** | the probe now reads a *different* plant | `assign()` on the channel | split — old readings stay with the old plant, new ones bind to the new |
| **New plant** | a plant that never existed here before | `next_plant_id()` + `assign()` | fresh entity, its own dimensions |

**Ruling I'm proposing:** the name field alone **never** triggers reassignment. Typing a new
name and saving is *always* a rename. Reassignment is a **separate, deliberate act** with its
own affordance — because rename is the overwhelmingly common case, and making the common case
carry a modal every time trains the operator to dismiss it.

The reassignment door sits next to the field, not inside it:

> **Gertrude** ✎
> *…is this a different plant on this probe?* → **[ Move this probe to another plant ]**

Only that button opens the flow in §3. Rationale: an accidental rename costs one edit to undo;
an accidental reassignment permanently splits a history and cannot be undone by retyping.
**Asymmetric cost ⇒ asymmetric friction.**

*(Alternative if she prefers symmetry: make the save button itself a two-way choice — "Just
renaming" / "Different plant". I recommend against it — it taxes the common path — but it is a
clean option and hers to take.)*

---

## 3. Flow A — Reassignment ("the probe moved to Gertrude")

Deliberately entered. Four steps, no surprises:

1. **What is on this probe now?**
   Pick an existing plant, or **＋ a plant I haven't added yet**. (The latter falls into Flow B
   and returns here.)
2. **What happened to the old one?** — the branch the backend needs and only the human knows:
   - *It's still growing, just not probed* → the old plant stays, becomes **sensorless**
     (ADR-0028's first-class absence: alive, not probed — an invitation, never an error).
   - *It's gone* → the old plant is **retired** via `set_lifecycle`, history preserved.
   The default is **"still growing"**, because destroying an entity should never be the path
   of least resistance.
3. **When?** — defaults to *now*, with "earlier" available. Backdating matters: if the probe was
   swapped Tuesday and recorded Friday, three days of readings otherwise attribute to the wrong
   plant. `assign(now=…)` already accepts an explicit timestamp.
4. **Confirm — stating the consequence in plain words, not jargon:**
   > Readings before *Tue 3pm* stay with **Big Green Plant**.
   > Readings after bind to **Gertrude**.
   > Nothing is deleted; both histories keep their own past.

**After:** a boundary marker renders in history views (dashed vertical + "probe reassigned"),
the same visual class as the ADR-0023 context boundaries — **never a data gap**.

---

## 4. Flow B — New plant

Reachable from the grid's empty state, an unassigned channel, and inside Flow A. Minimum
required: **a name.** Everything else — type, pot, location, photo — is absent-safe (ADR-0028:
a bare `plant_id` is always valid). A new plant with no probe is legitimate and renders as a
sensorless card, not an error.

---

## 5. Flow C — Adopt-a-board · **HELD FOR HER IDEATION**

Per the routing, I am **not** designing this flow. What I can usefully contribute is the frame
and the questions, so her ideation starts from the constraints rather than discovering them.

**What adoption must produce:** a device record, its channels, and a plant assignment per
populated channel — after which every later change is a recorded event rather than a memory.

**What already exists to build on:** device registry records, `next_sensor_id()`, `assign()`,
and the fleet poller's own view of which boards are reporting.

**The questions I'd want her ideation to answer:**

1. **Discovery or declaration?** Does a new board *announce itself* (it appears in the poller,
   Sprout offers "a new board is reporting — adopt it?"), or does she declare it first and then
   flash? The first is friendlier; the second is the only one that works before the board has
   ever connected.
2. **When are probes mapped — at adoption, or later?** Adopting a 4-channel board with no plants
   yet is legitimate. Does adoption *require* mapping, *offer* it, or *defer* it entirely?
3. **What does a channel with no plant look like** on Home and Workbench? (My default:
   present-or-silent on Home, explicit on Workbench — but this is a product-voice call.)
4. **Does adoption carry calibration?** #963's wizard is the natural next step after adopting —
   but chaining them makes a long first-run. Chain, offer, or separate?
5. **Trust posture:** should adopting require confirming the board's identity (its minted
   `device_id`, ADR-0027), or is appearing-in-the-poller sufficient?

---

## 6. Flow D — Install-time capture

The cheapest and highest-value flow: at the moment a probe goes into soil, record which plant
it is. Requirement: reachable **from the phone at the windowsill**, not only the desk — this is
a hands-dirty moment. It is the same `assign()` call as Flow A step 1, minus the branch (nothing
is being displaced).

---

## 7. The projection requirement (from the issue)

One authoritative current-registry projection consumed by dashboard, fleet polling, Home, and
tier alike. Design-QA's constraint on it: **surfaces read the projection, never the event log
directly.** A surface that re-derives "who is on this channel now" by scanning events is a
second identity truth able to disagree with the first — the same class of defect as deriving a
band from raw (#1148). One projection, every surface.

---

## 8. Test contract

The issue's end-to-end bar, made concrete:

- apply → save → reload → **new attribution asserted** *and* **old history preserved**
- a rename leaves the assignment chain **byte-identical** (no event emitted)
- a reassignment produces exactly **one** closed + **one** open assignment on that channel,
  sharing a timestamp — no gap, no overlap
- a backdated reassignment attributes the in-between readings to the **old** plant
- the grandfathered first move synthesises its prior interval (already covered for locations;
  the assignment equivalent needs the same check)

---

## 9. What I need from her

1. **§2's ruling** — name-edit-is-always-rename, with reassignment behind its own door? (my
   recommendation), or the symmetric two-way save?
2. **§5** — the adopt flow's ideation, against those five questions.
3. **§3 step 2's default** — "still growing" as the default disposition for the displaced
   plant. Confirm, or prefer an explicit no-default choice?

Nothing here builds until §2 and §5 come back. #1203's confirm/reject surface rides alongside
this epic and is not blocked by it.

— Design-QA 🔍
