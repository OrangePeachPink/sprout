# ADR-0027 — Device / Channel / Probe / Plant / Site identity model

**Status:** Accepted — *drafted by Firmware at the bench (2026-07-04) from the three-family fleet
bring-up (#584); concluded + ratified by Trellis per the maintainer's shepherd/conclude directive
(2026-07-04). Sub-decision **1b is RESOLVED = Option B** (see §1b); the only remaining open is calibration
portability — a flagged bench test (§6), not a blocker. Was Proposed 2026-07-04 → Accepted same day.*
Establishes a stable-UUID identity model; reframes the already-merged #602 coalescing as an interim
legacy bridge rather than the permanent strategy.

## Context

Bringing up three ESP32 chip families at once (#584) surfaced that the friendly `device_id` is doing
**three jobs at once** — stable identity, human label, and (through the channel columns) plant
attribution. Every identity pain we hit is that conflation leaking out:

- renaming a board orphans its history (shipped as display-time coalescing, #602, now merged);
- two same-family boards collide on the shared default name (#601, open) — coalescing cannot
  disambiguate two boards that logged under the *same* default, because the wire never
  distinguished them;
- naming needs continuity and must not require a tethered CLI (#600, open).

Physical realities the model has to hold:

- **Boards are fixed**, but **probes are mobile.** The maintainer labels each physical capacitive
  probe with a sticker (`s1`…`s12`, three 4-packs) and thinks in those stickers. A probe moves
  between boards, can be pulled and repaired, and carries a QA history (contamination, connector
  damage, recovery) that must travel *with the probe*, not with whatever board it is on today.
- **Plants get re-probed and move.** A plant can move within a house — a south-facing full-sun
  kitchen window to a smaller east-facing bedroom window is a large light delta — or across cities.
  Location drives real science: solar geometry (#365 / #366), weather correlation, and the
  skylight-confound env sensors (ADR-0023).
- **A passive capacitive probe has no ID chip.** The board cannot know which physical probe is
  plugged into a pin — it only reads an ADC. So probe / plant / site bindings are *necessarily*
  human-asserted and host-side; they cannot ride the wire.

Two facts make this the right moment to cut once, deeply:

- The wire is **already a tagged log** (`record_type` = `plants.soil` / `plants.env`) with a fixed
  `CANONICAL_COLUMNS` set and a free-form `k=v` payload — so new observation types and new payload
  keys are additive, but the canonical column set is a **byte-identical shared contract**
  (ADR-0021 / ADR-0023), also depended on by the companion air-quality project's shared core.
- **Pre-release posture:** one maintainer, zero users, nothing published, and every useful dataset
  already committed in its own PR. Migration cost is effectively zero. There is no cheaper time to
  make a structural change to the data contract.

Cross-project note: the companion air-quality project conforms to `docs/TELEMETRY_SCHEMA.md` and
joins on `timestamp_utc` (plus a shared location). It is not built yet — sensors just reached bench
stock — but the contract must stay join-compatible for it.

## Decision

### 1a. Identity is a stable UUID — minted, never derived

Every device gets a UUID that is a random nonce minted once at first boot from the SoC's hardware
RNG and persisted to NVS. It survives renames and resets only on a factory flash. It is **minted,
never derived** — no MAC, eFuse, or serial is read — which is required by **ADR-0020 (no hardware
IDs)**, Accepted doctrine; a MAC-seeded UUID would violate it structurally. The UUID identifies the
*logical device*, not the silicon, so it also survives a board swap conceptually.

### 1b. A SHORT stable id rides the wire; the full record lives in the registry

To respect two hard constraints — the `CANONICAL_COLUMNS` set must stay **byte-identical** (the
companion shared-core binding, ADR-0021 / ADR-0023) and the serial path is **19200 baud**, so bytes
per row are not free — the wire does **not** carry a full 128-bit UUID in a new canonical column.
Instead a **short stable minted id** rides the wire and the registry maps it to the full record.
Where exactly it rides is a **sub-decision for Trellis / Data**, between:

- **(A) short id in the `k=v` payload** (a 6-hex-char key, a few bytes) — keeps `CANONICAL_COLUMNS`
  byte-identical, additive; or
- **(B) repurpose the existing `device_id` canonical column** to carry the short stable id and move
  the friendly *name* to the payload / registry — no new column, wire size ~unchanged, and the
  stable id lands exactly where the companion project already joins.

Firmware's lean is (B) or (A) over a new canonical column; the final call is Trellis / Data's against
the shared contract. Full UUID and all rich fields live registry-side regardless.

**Resolved (Trellis, 2026-07-04): Option B.** `device_id` — already a canonical column — becomes the short
stable minted id; the friendly *name* moves to the registry (which already carries a `name` field, #592) and
MAY additionally ride the payload as `name=` for raw-log legibility (byte budget permitting — Firmware's
call on the 19200 path). **Rationale:** B fixes the conflation *at its root* — `device_id` becomes a true
stable identifier (its proper job) instead of a mutable label masquerading as an id in the "id" column,
which is the exact conflation this ADR exists to end. It **converges the in-flight work**: the dashboard
fence already keys on `device_id` (#587), so it stays correct and only its *display* swaps to `regdev.name`
(already the planned binding), and #602 coalescing retires as designed (§8/§9) rather than remaining a
permanent crutch. It **strengthens the §11.2 dedupe key** `(device_id, …)` by making its lead term genuinely
stable. And a 6-hex id is *shorter* than today's friendly string — byte-favorable at 19200 baud.

This is **not** the additive-only change §11's v2 is: repurposing `device_id`'s meaning requires a **`schema_version`
bump** (pre-bump logs carry `device_id`=name; post-bump carry `device_id`=stable-id; a reader distinguishes them
by version) plus the tiny 2nd-epoch migration of the three legacy bench identities (§9). That cost is deliberate
and — per the pre-release posture (zero users, everything committed) — effectively free now; it never gets
cheaper. *(Option A — stable id in the payload, `device_id` left as the name — was considered and rejected: it is
additive/safer, but it leaves the conflation in the canonical column and forces the fence to re-point onto a
payload key anyway — trading a clean normalization for a permanent redundancy. The maintainer may override to A
at ratification if additive-safety is preferred for install-day sequencing.)*

### 2. Five host-side entities, each `stable_uuid` + mutable label

Device (board), Channel (`device_uuid` + port/GPIO), Probe (sticker + QA + calibration), Plant, and
Site (coordinates / timezone / exposure). Labels are non-unique and freely re-nameable; the UUIDs
never move. "Windowsill" as a label on three devices is fine — they stay distinct by UUID, and the
view decides whether to render them grouped or split.

### 3. Bindings are time-versioned assignments — one reusable mechanism

probe↔channel, channel↔plant, and plant/device↔site are each an assignment row with a `from`/`to`
window. A reading `(device_uuid, channel, timestamp)` **joins** to whatever probe / plant / site was
in effect at that instant. Every move, rename, or reassignment is just opening and closing
assignment rows — nothing is orphaned, and no coalescing is needed for new data.

### 4. Capture-time minimum; meaning is a retroactive join

Onboarding requires only `device_uuid + channel + value`. All entity bindings are **optional,
host-side, and back-fill history**: because each reading carries `(device_uuid, channel, timestamp)`,
bindings asserted next month retro-attribute every past reading correctly. This is the rule that
keeps onboarding one-click while allowing arbitrarily rich enrichment later — meaning is a join you
can add to forever, never a gate in front of live data.

### 5. `sensor_id` splits into Channel (port) and Probe (sticker)

Today's `sensor_id = s1..s4` is silently the board *port*, and only looks like the maintainer's
stickers because probe-`s1` currently sits in port-`s1`. The instant a probe moves, they diverge.
Going forward: **Channel** = `(device_uuid, port/GPIO)`, backstage; **Probe** = the sticker (`s3`,
`s12`), the user-facing identity carrying QA and calibration. The maintainer thinks in probes and
plants; the pin is a lookup.

### 6. Calibration = probe-intrinsic composed with a per-board ADC transfer — portability is OPEN

Raw ADC depends on **both** the probe and the board's ADC (reference, gain, parasitics). Model
calibration as composable — probe endpoints plus a per-board ADC offset / dynamic-range mapping — so
that **either** "a probe's calibration is portable across boards given the board's ADC transfer"
**or** "calibration must be re-derived per `(probe, device)`" can be expressed. Which one holds
within the app's required statistical bounds is **untested**; it is flagged as a bench test (one
probe across N boards, compare endpoints), not hard-committed here.

### 7. Observation types stay additive by `record_type`

`plants.soil` (now), `plants.env` (now), `plants.dose` (Wave 2 actuation, #94 / ADR-0016), and
external context (weather / solar keyed on site + time) all extend the tagged log without another
canonical-column cut.

### 8. The mapping table inherits #602's guards as permanent invariants

The #602 work shipped three rules that graduate from a display-time workaround into permanent
invariants of the identity registry / mapping table: **a live identity is never swallowed** by another's alias,
**provenance rows are never rewritten** (raw wire truth is preserved), and **any merge is visible,
not silent**. These are load-bearing for the UUID model, not disposable.

### 9. Migration — the 2nd epoch

Add the short stable id; one-time map the legacy bench identities (`plants_esp32_f4e9d4`,
`Sprout ESP32`) onto the classic's UUID; keep the 1st-epoch originals archived in the records store.
The merged #602 coalescing serves as the **interim legacy bridge** until the migration lands, after
which runtime coalescing may retire.

## Wave scoping

- **Wave 1 (required):** mint + emit the stable device id (firmware — this is #601's structural
  fix, below); a **UUID-keyed** host registry answering **which board / which probe / which plant**
  via plain labels (probes `s1–s12`, plants `p01–p11`). The registry is **UUID-keyed from the first
  entry** — labels are display only — so install day never creates name-keyed rows that later need
  migration. **No naming UI, no Site, no moves, no calibration portability.**
- **Designed-for, deferred:** Site + intra-house / cross-city moves, the time-versioned reassignment
  and deployment-panel UX, calibration portability, and per-species / substrate bands. The data
  model leaves the seat for all of them; the UI and firmware do not owe them in Wave 1.

**Sequencing (land before install day):** the identity substrate should land *before* install day
populates the eleven plants. Registering eleven plants name-keyed and migrating later is avoidable
work — and **plant UUIDs are what let the Wave-2 predictor's per-plant history survive repotting and
renames**, so the payoff of this decision is already banked the moment the plants are registered
UUID-keyed.

## Consequences

- Renames, reuse, and moves become label edits, not identity events; two same-family boards are
  distinct out of the box; a probe's QA history follows the probe; enrichment is optional and
  retroactive; onboarding stays one-click; the cross-project join strengthens via site; and it is
  **one schema cut, not many** — new observation types and entities layer on without a re-cut.
- Costs: one wire / schema change plus a one-time legacy migration now, and a host-side registry +
  assignment table to build progressively.
- Cross-project: the short-id add is additive (the companion project ignores it, or gains a cleaner
  join key under option B) and site strengthens the shared `timestamp_utc` join; coordinate the
  contract bump when that project starts.
- Open: where the id rides the wire (1b, Trellis / Data), and calibration portability (empirical,
  later wave).

## Rejected alternatives

- **Name-as-identity plus rename-flagging as the permanent strategy** (treating the shipped #602 as
  the end state): patches the conflation rather than fixing it; cannot disambiguate two same-family
  boards that shared a default identity; misattributes history on name reuse.
- **MAC / eFuse-derived identity:** violates ADR-0020 (no hardware IDs), and ties identity to silicon
  so it does not survive a board swap — identity should track the logical device, not the chip.
- **Full 128-bit UUID in a new canonical column:** breaks the byte-identical `CANONICAL_COLUMNS`
  contract and spends bytes per row on a 19200-baud path (see 1b).

## Open (routed)

- **Trellis:** DONE — model concluded/ratified; **1b resolved = Option B** (§1b); the wire
  `schema_version` bump is registered in `TELEMETRY_SCHEMA.md` §6/§11 (device_id becomes the stable minted
  id, name → registry). No remaining Trellis blocker; calibration portability is a bench test.
- **Firmware — #601 (open) IS this model's first slice:** mint + emit the stable id at first boot.
  Do **not** build a parallel "distinct default name" band-aid in the Wave-1 patch if this ADR lands
  this week — the mint solves the collision structurally.
- **#600 (open) survives unchanged:** a name is simply a re-nameable label over a stable UUID —
  exactly what that issue asks. (The earlier "auto-chain previous_ids" worry is moot under UUIDs.)
- **Data — new issues (no existing issue covers these):** schema v2 (the short id), the UUID-keyed
  host registry + **time-versioned assignment table** (carrying #602's three invariants), and the
  **2nd-epoch legacy migration**.
- **Firmware / bench — new:** the **calibration-portability test** (one probe across N boards).
- **Unaffected:** #598 (env-over-WiFi) and #599 (WDT) proceed independently in the Wave-1 patch.
- **Already shipped:** #602 (coalescing) and #529 (toolchain) are merged/closed; this ADR references
  their work, it does not reopen them.

— Firmware 🔧 (bench draft for Trellis ratification)
