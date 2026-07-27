# ADR-0036 — Sensor-identity layers: sticker · channel · wire `sensor_id` · display

**Status:** Accepted — *the layer model and the "wire carries the channel, not the probe" rule are decidable from
[ADR-0027](0027-identity-model.md) §5 and ruled here (Trellis). **The naming scheme is RULED (maintainer,
2026-07-19, #1042): Fork A — `chN`.** The wire `sensor_id` carries `ch0..ch3` per board. A wire rename is a
`schema_version` boundary (never-stitch, ADR-0006 / ADR-0021), so the rename lands at **`schema_version=5`**:
v4 rows keep the old port-as-sticker token and are **never rewritten**, v5 rows carry the channel. V1
(ADR/doctrine + wire contract).*
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

### 5. A channel is a first-class board **declaration**, not an artifact of assignment

*(Added 2026-07-20, #1027 — the temporal registry dropped the static model's `devices[].channels{}`
and left channels existing only because a plant was assigned to one. That inverts §1 and had a
visible cost: the empty-channel state could not be rendered, because the channel did not exist.)*

**A channel exists because a pin has a probe on it. Not because a plant is mapped to it.**

§1 already names the channel as `(device_id, port/GPIO)`, **firmware-owned** — and the boards prove
it continuously: a board with zero plants mapped still emits `ch0..ch3` on every telemetry row. A
model in which channels are derived from assignments therefore **contradicts the wire contract**,
leaving the registry unable to represent something the fleet is actively reporting.

So a board **declares its channel set and pin map at adoption**, independently of any assignment:

- **Channel lifetime** — from adoption until the board is rewired or retired.
- **Assignment lifetime** — from a plant being mapped until the probe moves.

Modelling the longer-lived thing as a by-product of the shorter-lived one is backwards, and that
inversion is the whole defect. It also makes the maintainer's adoption rule expressible —
*"no-plants-yet is legitimate; no-pin-config is not an adoptable board"* — which is unstatable if a
channel cannot exist before a plant does.

### 6. Board class is a firmware-emitted token; the registry's board string is a display label

*(Added 2026-07-20 — ruled for #302 S3b's artifact matching. Same shape as §2, one layer up.)*

The overload §1 ended for `s#` existed again for the board itself: **five namespaces** described one
concept — PlatformIO env names, the registry's free-text `board` field, `BOARDS.md` nicknames, ESP
Web Tools' `chipFamily`, and the OTA feed's `board_class` — with none authoritative and one of them
prose (`'esp32-c5-devkitc-1 (official)'`) that nothing could match.

- **`board_class` is emitted by the firmware, derived at compile time.** The board knows what it was
  built as; nothing downstream can know it authoritatively. §2's rule, one layer up.
- **The token set is qualified and mutually non-prefixing:** `esp32-classic` · `esp32-c5` ·
  `esp32-s3`. **Not bare `esp32`** — it is simultaneously a specific chip *and* the family prefix of
  every other token, which would make the classic board's identity a substring of every other
  board's. Exact matching makes that safe; a single careless `startswith` anywhere would make it a
  brick. Seven characters buy structural impossibility instead of disciplined correctness.
- **Board class is hardware, never build variant.** `esp32dev_ota` and `esp32dev_recover` are the
  same silicon. An OTA-variant build of a classic is still a classic.
- **The registry's `board` string is a display label and must never be parsed** — exactly the
  probe-sticker relationship in §3. Humans get the prose; machines get the token.
- **Firmware owns the enumeration; every host consumes it** — one set, one place, never a second
  list and never prose mapped to a class.

`chipFamily` and the `BOARDS.md` nicknames remain useful **renderings** of the token. They stop
being candidates for a match.

## The naming ruling — RULED (maintainer, 2026-07-19, #1042): **Fork A — `chN`**

**Decided.** The wire `sensor_id` carries the **channel** as `ch0..ch3` per board, fleet-unique as
`(device_id, sensor_id)`. Sticker↔channel lives in the registry; the display resolves it; a probe move is a
registry event, never a reflash. Landed at **`schema_version=5`** (never-stitch: v4 rows keep the old
port-as-sticker token and are never rewritten).

The forks below are retained as the **rationale that produced the ruling**, not as an open question — a
living-doc record of what was weighed. Trellis recommended **A**; the maintainer confirmed it explicitly.

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
convenience at the cost of a second identity to reconcile. ~~No wire changes until this is ruled.~~ —
**ruled 2026-07-19 (Fork A); the wire change shipped under `schema_version=5` (#1042).**

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

- ~~**Maintainer** — rule the naming scheme + migration timing.~~ **CLOSED — ruled 2026-07-19 (Fork A, `chN`).**
- ~~**`for:firmware`** — on ruling: `SENSOR_NAMES` emission under a bumped `schema_version`.~~ **DONE (#1042):**
  `SENSOR_NAMES` → `{ch0..ch3}`, `PLANTS_SCHEMA_VERSION` 4 → 5.
- **`for:data`** — the parser + registry `channels{}` keys align to the ruled scheme; never-stitch at the boundary.
- **`for:design`** — the display resolves channel → sticker/plant via the registry (the #921 display half already
  does the label side).

— Trellis 🏛️
