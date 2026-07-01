# ADR-0023 — Config provenance & no-auto-adjust

**Status:** Proposed — *drafted by Trellis from the #416 RFC (all four lanes converged). The **inline** slice is
already built + Sage-ratified (`gain=16`, PR #452); this ADR generalizes the model and defines the `config_id`
snapshot mechanism for Data to implement. Awaiting Data's `config_id` shape confirmation + maintainer
ratification.*
**Date:** 2026-07-01
**Owner:** Architecture (Trellis) — the provenance model; Data owns the `config_id` / header / storage
implementation, Firmware the emit, Sage the setting *values*.
**Lane:** architecture (cross-lane: Data · Firmware · Sage)
**Extends:** [ADR-0006](0006-data-architecture.md) (honest data)
**Relates:** #416 (RFC) · #452 (inline AS7263 slice) · #295 (cal bounds in header) · #300 (schema v2
provenance) · [ADR-0019](0019-capability-and-sensor-matrix.md) (sensor profile) · #345 (env sensors)

---

## Context

Every reading is shaped by tunables that determine **how to interpret it**: the AS7263's `gain` / integration
time, the soil ADC's attenuation / sample count / trim / discard / resolution, I²C clock, sensor precision
mode, read cadences, and the classifier's calibration bounds. A reading is only trustworthy — and only
*comparable* to another reading — if you know the settings that produced it.

Sage's 2026-06-30 skylight pass made this concrete: the AS7263 **railed at `gain=64`** (`51201/65535` on
`nir_680` ×165 rows, `nir_860` ×67) — **silent saturation**, the peak lost with no after-the-fact way to know.
The tempting fix — auto-range the gain — is **rejected**: it would silently make session A's readings
non-comparable to session B's, which is the same class of dishonesty as emitting a fake moisture %. #452 already
built the ratified response for the AS7263 (`gain=16`, held fixed, surfaced in the header). This ADR generalizes
that into a **provenance model + a doctrine** so every reading-shaping knob is handled the same way.

## Decision

### 1. No-auto-adjust (doctrine)

Every reading-shaping setting is **dialed in once and held fixed**. It changes **only for a deliberate,
logged data need** — and when it does, the data carries the new setting so comparability stays explicit.
**No silent auto-adjustment, ever.** This joins ADR-0006's honest-data family ("gaps are surfaced, not
smoothed"; raw is truth): a setting that quietly moves is a truth-chain break.

### 2. Two-surface provenance (the hybrid)

Provenance rides two surfaces, split by **interpretation-locality**:

> **A knob rides inline per-row IFF it can change *between rows of the same stream* AND changes their
> interpretation at the point of measurement. Otherwise it lives in a session config snapshot keyed by
> `config_id`.**

- **Inline per-row** (few, volatile, measurement-shaping): the AS7263 `gain` / `itime`. A spectral row at
  `gain=64` is not comparable to one at `gain=16` — it must travel with the row. *(Built in #452 — kept.)*
- **`config_id` snapshot** (the broad set-once-held surface): ADC attenuation / `SAMPLES_PER_READ` /
  `SAMPLES_TRIM` / `ADC_DISCARD` / resolution / eFuse-cal, sensor pins, I²C clock + addresses, read cadences,
  SHT45 precision, and the classifier cal bounds (**#295 folds in here**). Hashed into a `config_id` in the
  boot header + one **config-snapshot record**; data rows reference the id.

### 3. `config_id` is the comparability boundary

`config_id` is a **stable hash of the active config snapshot**, emitted in the header and referenced by rows.
**Same `config_id` ⇒ rows are directly comparable. A `config_id` change ⇒ an explicit, machine-detectable
comparability boundary** — which is exactly the "what's comparable, what isn't, how to interpret across a
change" the RFC asked for. It also **enforces** no-auto-adjust: an *unexpected* `config_id` change is the
alarm. Provenance is **header-authoritative** — `parse_v1` **reads** it and never re-derives config from the
data (Data's ratified position, #452). It is precisely the `profile_version` provenance #300's schema-v2
should carry.

### 4. Setting *values* are out of scope

*Which* value to hold (Sage ratified `gain=16`) is a **bench-comparability call**, not this ADR's. The ADR
mandates only that the chosen value is **logged and held**, never which value it is.

## Rejected alternatives

- **Auto-range the gain (or any knob).** Rejected: silently destroys cross-session comparability — the observed
  #428 saturation would be "corrected" invisibly, and no reader could tell session A from session B. Same sin
  class as a fabricated percentage.
- **Per-row tags for *every* knob (RFC option a).** Rejected: ~25 knobs on every soil row is impractical, and a
  lone row still can't be checked against the intended config.
- **A pure `config_id` with nothing inline (RFC option b).** Rejected: a lone row is then **not
  self-interpreting** for the volatile knobs (`gain`/`itime`) that change *within* a stream.
- **`parse_v1` reconstructs config from the data.** Rejected (Data's position): provenance is
  header-authoritative; the reader reads it, never rebuilds it.

## Consequences

- **Every capture is self-interpreting:** volatile knobs inline, the stable surface via `config_id`.
- **`config_id` becomes the cross-session comparability contract** — joins and trend comparisons gate on it;
  an unexpected change is a flag, not a silent drift.
- **No-auto-adjust is enforceable doctrine**, not a footnote.
- **Implementation split:** Data builds the `config_id` (hash + snapshot record + row reference) on the
  telemetry-header substrate; Firmware emits it; the **inline AS7263 half is already shipped (#452)**.
- Ties **#295** (cal bounds become part of the snapshot) and **#300** (`config_id` = the schema-v2
  `profile_version` field).
- **Cannot be fully built until Data lands the `config_id` mechanics**; the inline slice (#452) ships
  independently of this ADR.

## Revisit triggers

- **A new reading-shaping knob is added** → classify it by the split rule (inline vs snapshot); default to the
  snapshot unless it changes interpretation *within* a stream.
- **A setting must change mid-session for a real need** → confirm the `config_id` rolls and the rows carry the
  new id — never a silent change.
- **Schema v2 (#300) lands** → fold `config_id` in as the canonical `profile_version`; retire any interim
  representation.

*Register in `docs/adr/0000-record-architecture-decisions.md` on acceptance.*
