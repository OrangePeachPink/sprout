# ADR-0036 — Sensor-identity layers: sticker · channel · wire `sensor_id` · display

**Status:** Proposed — *the layer model and the "wire carries the channel, not the probe" rule are decidable from
[ADR-0027](0027-identity-model.md) §5 and ruled here (Trellis). The **naming scheme** for the wire channel + the
migration (§"The one maintainer ruling") await the maintainer's word per #1042 ("maintainer decides the rename").
A wire rename is a `schema_version` boundary (never-stitch, ADR-0006 / ADR-0021), so **nothing changes on the wire
until she rules.** V1 (ADR/doctrine + wire contract).*
**Date:** 2026-07-19
**Owner:** Trellis (the ADR + the layer model). Cross-lane at build: **Firmware** (`SENSOR_NAMES` emission +
parser), **Data** (parser + registry `channels{}` keys), **Design-QA** (display resolution).
**Lane:** architecture (cross-lane: Firmware · Data · Design-QA)
**Extends:** [ADR-0027](0027-identity-model.md) §5 (`sensor_id` splits into Channel + Probe) — **into the wire
contract** · [ADR-0019](0019-capability-and-sensor-matrix.md) (per-board channel/sensor matrix)
**Relates:** #1042 (this — the deferred #896 wire half) · #896 (the split ruling) · #921 (the display/glossary
half, shipped) · [ADR-0006](0006-data-architecture.md) / [ADR-0021](0021-parse-v1-telemetry-contract-boundary.md)
(the wire schema + parse boundary) · `docs/TELEMETRY_SCHEMA.md` (field 11 `sensor_id`)

---

## Context

`s#` is overloaded across four layers, and they only *coincidentally* agree today:

| Layer | What "s#" means | Space | Who knows it |
|---|---|---|---|
| **Physical probe (sticker)** | the maintainer's label on a capacitive probe | `s1..s12` (three 4-packs) | the maintainer; travels **with the probe** |
| **Firmware channel** | a board port / GPIO lane | `ch0..ch3` per board — **not fleet-unique** | the firmware (it reads an ADC on a pin) |
| **Wire `sensor_id`** | today `SENSOR_NAMES[ch]`, e.g. `{s3,s4,s1,s2}` | *looks like* a sticker, *is* the port | emitted on every telemetry row |
| **Display name** | what a human reads | plant name / sticker / friendly | the dashboard |

ADR-0027 §5 already named the split: *"Today's `sensor_id = s1..s4` is silently the board port, and only looks
like the maintainer's stickers because probe-`s1` currently sits in port-`s1`. The instant a probe moves, they
diverge."* Two concrete failures follow from leaving that in the wire contract:

1. **A probe move silently mislabels the wire until reflash.** `SENSOR_NAMES` is an *immutable-flashed* firmware
   constant that encodes a *mutable* probe↔channel binding. Move probe `s1` to another pin and the wire keeps
   calling that pin `s1` — a stale binding baked into firmware, wrong until someone reflashes.
2. **Per-board `s1..s4` collides fleet-wide.** Two boards both emit `sensor_id="s1"`; a reading is unique only as
   `(device_id, sensor_id)`. The token pretends to be a fleet-unique probe id but isn't.

The display/glossary half of #896 shipped with #921; this ADR is its deferred **wire half** — the definitive
record that ends the overload.

## Decision

### 1. Four layers, one owner each — named so they can never be conflated again

- **Probe** = the **sticker** (`s1..s12`), the *user-facing physical identity* that carries QA + calibration and
  **travels with the probe.** Lives in the **registry** (ADR-0027 §2/§3). The maintainer thinks in probes.
- **Channel** = `(device_id, port/GPIO)`, the board lane the firmware actually reads — per-board `ch0..ch3`,
  **fleet-unique only when scoped by `device_id`.** Firmware-owned.
- **Wire `sensor_id`** = the **channel** identity on the telemetry row (§2).
- **Display name** = **registry-resolved** (channel → probe/sticker → plant), so a human sees the maintainer's
  labels (§3).

### 2. The wire carries the CHANNEL, never the probe — ADR-0027 §5 made a wire rule

The firmware **cannot** know which physical probe is on a pin: a passive capacitive probe has no ID chip; the
board only reads an ADC (ADR-0027 Context). Therefore **`sensor_id` on the wire is the channel** — what the
firmware actually knows — and the **probe↔channel binding is a registry assignment** (a time-versioned row,
ADR-0027 §3) resolved at read/display time. The current `SENSOR_NAMES`-as-stickers emission is retired: it is the
exact *"silently the port, labelled like a sticker"* anti-pattern ADR-0027 §5 named. **Nothing on the wire ever
claims to know the probe.**

### 3. The display speaks the maintainer's language — via the registry, not the wire

She keeps her sticker/plant mental model where it belongs — on the **display**, resolved by the registry
(channel → the probe assigned to it → the plant). A probe move becomes a **registry event** (a new assignment
row), **not a reflash.** The wire stays channel-true and immutable; the meaning is a read-time join (ADR-0027 §4).

### 4. Any wire rename is a `schema_version` boundary — never an in-place mutation

Changing what `sensor_id` carries is a wire-contract change: **additive, versioned, never-stitch** (ADR-0006 /
ADR-0021). Old rows keep their old meaning under their old `schema_version`; the new meaning ships under a bumped
version, and `parse_v1` handles both (ADR-0021's versioned dispatch — already the pattern). No historical rows are
rewritten.

## The one maintainer ruling (📌 — the naming scheme; queued, non-blocking)

The *layer model* above is ruled. What is **hers** per #1042 ("maintainer decides the rename") is the **wire
channel's naming + the migration**, because it touches her operational model and the wire contract. Three forks —
Trellis recommends **A**:

- **Fork A — channel-explicit (recommended).** `sensor_id` = the channel, named `ch0..ch3` (fleet-unique as
  `device_id` + `sensor_id`). Sticker↔channel lives in the registry; display resolves. **Ends the overload
  permanently** — no layer reuses another's token, and a probe move is a registry event, never a reflash. Cost: a
  one-time `schema_version` bump + the display joins the registry to show stickers (it already resolves plant
  names that way).
- **Fork B — operator-declared sticker (the status quo, made honest).** Keep `sensor_id = SENSOR_NAMES[ch]` but
  *define* it as an operator-declared label, and require `SENSOR_NAMES` to be **fleet-unique stickers** (board 2
  is `{s5..s8}`, never a second `s1`). Simpler display (the wire already says the sticker); but a probe move
  still needs a reflash, and the overload persists (a sticker-looking token that is really configured-per-channel).
- **Fork C — hybrid.** Wire carries `sensor_id = ch0..ch3` (channel-true, Fork A) **plus** an optional
  operator-declared `sticker` column that travels for convenience. Both identities on the row; the display can use
  either. Cost: a wider schema and two identities to keep consistent.

**Trellis recommendation: A** — it is the literal realization of ADR-0027 §5 (*"the pin is a lookup; the
maintainer thinks in probes"*), it turns a probe-move into a registry event instead of a reflash, and it is the
only fork that *ends* the overload rather than managing it. B keeps the reflash-on-move fragility; C buys
convenience at the cost of a second identity to reconcile. **No wire changes until this is ruled.**

## Consequences

- The four layers are named and owned; `s#` can never silently mean four things again.
- Firmware emits what it knows (the channel); the registry owns what it can't (the probe); the display resolves
  the maintainer's language — each layer honest to its own knowledge.
- A probe move (Fork A) is a registry assignment, not a reflash — the ADR-0027 §3 mechanism already exists.
- The rename, when ruled, rides a `schema_version` bump through `parse_v1` (ADR-0021) — old data stays valid.

## Rejected alternatives

- **Leave `SENSOR_NAMES`-as-stickers on the wire (do nothing).** Rejected: it bakes a mutable binding into
  immutable firmware (stale-on-move) and perpetuates the overload ADR-0027 §5 flagged.
- **Emit the probe sticker on the wire as a first-class fleet-unique id.** Rejected: the firmware cannot know the
  probe (no ID chip) — it would be emitting a value it can only *assume* from a hand-config, which is exactly the
  fragility this ADR removes.
- **In-place mutation of historical `sensor_id`.** Rejected: never-stitch (ADR-0006 / ADR-0021) — a rename is a
  version boundary, not a rewrite.

## Open (routed)

- **Maintainer** — rule the naming scheme (Fork A / B / C) + the migration timing (📌 above). One line, or a
  short v0.8.0-session question; the build waits on it.
- **`for:firmware`** — on ruling: `SENSOR_NAMES` emission + parser under a bumped `schema_version`.
- **`for:data`** — the parser + registry `channels{}` keys align to the ruled scheme; never-stitch at the boundary.
- **`for:design`** — the display resolves channel → sticker/plant via the registry (the #921 display half already
  does the label side).

— Trellis 🏛️
