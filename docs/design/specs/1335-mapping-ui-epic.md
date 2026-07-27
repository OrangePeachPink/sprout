# The mapping-UI epic — spec draft for maintainer review

**Issue:** #1335 (v0.8.1) · **Status:** **RULED** — every open question answered
(rulings scribed on #1335, 2026-07-20). This is the build contract.
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

**RULED (§2):** the name field alone **never** triggers reassignment. Typing a new
name and saving is *always* a rename. Reassignment is a **separate, deliberate act** with its
own affordance — because rename is the overwhelmingly common case, and making the common case
carry a modal every time trains the operator to dismiss it.

The reassignment door sits next to the field, not inside it:

> **Gertrude** ✎
> *…is this a different plant on this probe?* → **[ Move this probe to another plant ]**

Only that button opens the flow in §3. Rationale: an accidental rename costs one edit to undo;
an accidental reassignment permanently splits a history and cannot be undone by retyping.
**Asymmetric cost ⇒ asymmetric friction.**

*(The symmetric alternative — a two-way save button — was considered and **declined**: it taxes
the common path, and a modal the operator sees on every rename is a modal they learn to dismiss.)*

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
   **RULED: the default is "still growing"** — the displaced plant becomes sensorless.
   Destroying an entity is never the path of least resistance.
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

## 5. Flow C — Adopt-a-board · **RULED**

All five questions answered. The flow below is the ruled design, not a proposal.

### 5.1 Discovery-first

A new board **announces itself**: the poller already sees boards it doesn't know, so Sprout
offers adoption rather than making her declare hardware in advance. An unknown reporter surfaces
as an adopt card — calm, not an alarm; an unadopted board is a *guest*, never a fault.

### 5.2 Adoption REQUIRES a physical-config declaration ⚠

The strongest ruling, and the one that most changes the draft. Her framing: a new board *"needs
to declare how many probes and what pins they are wired to, or else it isn't a known board
config. Could have one sensor, could have 4, could have 6. Could use our pin recs or not."*

So:

- **No-plants-yet is legitimate.** Adopting a board with nothing planted is fine.
- **No-pin-config is NOT adoptable.** Probe count and pin mapping are the minimum that makes a
  board *known*. Without them there is no channel set to assign plants to, and nothing downstream
  can be honest about what it is reading.
- The declaration offers **Sprout's recommended pinout as a default**, one tap to accept — but it
  is a default, never an assumption. A board wired differently says so here.
- **Later physical changes are edit events**, not re-adoptions — *"I took two of the sensors off
  and moved them to my esp32 in the bathroom for my ferns."* That lands on the same assignment
  primitives as §3: `close_channel()` for the removed probes, `assign()` on the new board. The
  config declaration is versioned, not overwritten.

### 5.3 An empty channel is calm, waiting, and **teaching** — `for:dx`

Absence here is first-class *and helpful*. A declared-but-unplanted channel doesn't sit silent;
it offers the next step: how to connect a sensor, which pin it maps to, and how to trust what it
reads (the FD-5 trust surface is the natural link).

**Split of labour:** **DX owns the guidance content**; **Design-QA renders it in Sprout's voice**
and owns its placement. Posting the content ask on this issue with `for:dx`.

### 5.4 Calibration is optional at adoption, permanently linked

The wizard (#963) does **not** gate adoption. Any board that has never run a calibration carries
a standing, visible **calibrate** offer — not a nag, not a warning colour, just a door that stays
open. **Requiredness is a tunable we can promote later**, so this decision doesn't have to be
re-litigated to change it.

### 5.5 Trust: the middle door

The adopt card **shows the board's minted `device_id`** (ADR-0027) and the operator confirms in
one click that it matches the physical board. No typing an id, no blind adopt. The failure mode
this prevents is adopting the wrong board when two are reporting at once.

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
- **adoption without a pin config is refused** (§5.2) — a board with no declared channel set
  never becomes adoptable, and the refusal states what is missing
- **a physical reconfiguration is an edit event, not a re-adoption** — removing two probes and
  rehoming them closes those channels and opens new ones on the other board, with both boards'
  histories intact

---

## 9. Status

**Every open question is ruled** (§2, §3 step 2, and all five of §5 — scribed on #1335,
2026-07-20). Nothing in this spec is waiting on a decision.

**Build order** (ruled slice order): the projection → its consumers → the conformance test →
the surfaces.

**One ask out to another lane:** §5.3's onboarding guidance content — `for:dx`. It does not
block the projection, the consumers, or Flows A/B/D; only the empty-channel teaching state
needs it, and that state can ship with placeholder copy I write if DX's content lands later.

— Design-QA 🔍
