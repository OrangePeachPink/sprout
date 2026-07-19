# ADR-0022 — Calibration-confidence layer (local-reading vs pot-need gating)

**Status:** Accepted — *the gate **model** ratified by the maintainer 2026-06-30 (#400 / #402). The
**thresholds/metrics** remain design-light-before-build, tracked as non-blocking cross-lane inputs
(#412 Data · #414 Firmware · #416 config-provenance · Sage bench). The **under-action failure mode** is a
named open concern owned by the #410 epic — gate item 5.*
**Date:** 2026-06-30
**Owner:** Architecture (Trellis, author) — promotion-gate owner; control-loop enforcement co-owned with Firmware
**Lane:** architecture (cross-lane: Firmware enforcement · Sage bench · Data substrate)
**Extends:** [ADR-0016](0016-actuation-wiring-seam.md) (single authority / arm-gate)
**Relates:** #170 (per-channel split) · #348 (arm-gate chain) · #383 (bench evidence) ·
[ADR-0006](0006-data-architecture.md) (raw-first data) · #377 / #300 (telemetry header) · the capability-stage
vocabulary (`docs/GLOSSARY.md`) · #400

---

## Context

Per-channel calibration (#170) removes **sensor personality** — each probe gets its own raw→band boundaries,
so a reading is no longer skewed by that probe's individual signature. But Sage's #383 greenhouse pass shows
the deeper problem: even a perfectly-calibrated band is **the local reading** — what one probe senses in its
microzone — and **not pot need**, i.e. whether the plant actually needs water. Microzone disagreement,
contact quality, hydrophobic/preferential flow, and tray state routinely dominate the whole-pot decision.
Across P01–P11, runoff did not mean "fully watered," a plausible number did not mean "good contact," and one
dry channel did not mean the pot was dry.

ADR-0016 ships autonomous dosing **DISARMED** and gates arming on the dry-safety chain
(`#93 / #191 / #2 / #215`) — but that chain proves the *hardware* is safe (relays fail off, the watchdog
resets, the bench passed). Hardware-safe is not the same as **decision-trustworthy**: there is no gate today
on whether the *reading* justifies watering. Acting on the local reading as if it were pot need is precisely how an
autonomous loop over-waters. This ADR defines that missing decision-trust gate.

It is explicitly **not** the per-channel raw→band split (that is #170) and **not** the value-locking of bounds
(that is Sage's probe-orientation round). It is the layer that sits **between** "the band is calibrated" and
"act on the band."

## Decision

A **calibration-confidence layer** with four components, enforced inside the ADR-0016 supervisor (the single
authority — there is no second decision path).

### 1. Confidence stages (the promotion gate)

Extend the capability-stage vocabulary with an explicit, per-channel confidence state evaluated **at decision
time**:

| Stage | Meaning | Autonomy |
|---|---|---|
| `provisional` | shared / uncalibrated bounds (today) | monitor only — never auto-doses |
| `board-cal` | a **measured board-type envelope** (#952 cal-source ladder: uncalibrated → **board-cal** → channel-cal; the C5's #898 case) — trust above shared/uncalibrated, below per-channel | monitor only — never auto-doses (not yet `calibrated`) |
| `calibrated` | per-channel bounds locked from controlled characterization (#170) | necessary, **not** sufficient |
| `corroborated` | a `calibrated` band that, at this decision, is **corroborated** — no microzone-disagreement veto, good contact-quality, no contradicting pot/tray signal | the **only** stage that may drive an autonomous dose |

`calibrated` is a static per-channel property (set once #170 locks values); `corroborated` is **dynamic and
per-decision** — a channel can enter and leave it sweep-to-sweep.

### 2. Microzone-disagreement veto

When cross-channel (or cross-reading) spread exceeds a configured bound, confidence drops and the loop **does
not act** on that channel — it holds or pulses-and-observes. This is the conservative direction by
construction: disagreement → **pause**, never → act. It corroborates Firmware's #383 take ("don't chase one
dry channel while another channel or the tray already shows water arrived"). It extends the existing
*per-channel* spread/health veto with a *cross-channel* disagreement check; the exact metric and threshold are
a Sage bench input.

### 3. Contact-quality evidence

Each reading carries a **contact-quality** signal; a low-contact reading can veto or monitor but **cannot drive
watering**. P07 (hidden standing water, invalid S3 contact) and P10 (clumped soil on probe) showed
plausible-but-mechanically-questionable numbers. Contact-quality is **logged as first-class evidence** (Data's
annotation layer / telemetry header), not inferred silently, and feeds the confidence state.

### 4. Plant-pathway profiles

Per-pot water-response context constrains dose size, soak, and the "recovered" interpretation — because #383
proved a cactus micro-dose, a rootbound low-retention pot, a hydrophobic parched pot, and a tray-resoak pot
cannot share one naive trigger. Profiles are **config/data, not hardcoded**, and the **default profile is the
most conservative** (smallest pulse, longest observe). A profile never *loosens* the safety gates; it only
tightens dose behavior.

### The promotion gate (the core decision)

`plant-deployed → autonomous-enabled` requires **all** of:

1. the dry-safety chain (`#93 / #191 / #2 / #215`) — hardware safety (ADR-0016, existing);
2. per-channel calibration **locked** (#170 → `calibrated`);
3. the calibration-confidence layer **active** (this ADR): a channel may autonomously dose **only while
   `corroborated`** — no disagreement veto, good contact, profile-consistent.
4. **schema-conformant pump telemetry** (#18) — when armed, pump events must emit as schema-conformant
   `plants.pump` records, not the interim diagnostic line, so telemetry integrity and the data join hold
   exactly when watering happens. (#348 ships DISARMED precisely because this and the dry-safety chain are
   not yet met.)
5. **the under-watering fail-safe** (#410) — items 1-4 guard *over*-action (do not dose without
   confidence). They do **not** guard *under*-action: a channel that never reaches `corroborated` is never
   watered and the plant can die **silently**. The system must not ARM until an under-watering fail-safe
   exists (detect a never-opening gate + an alert-or-fail-toward-watering response). See the open concern
   below.

Until all pass on real hardware, dosing stays **DISARMED** (the ADR-0016 arm-gate). The confidence layer is an
**additional, continuous** arm condition — not a one-time check. Even after the operator arms, a channel that
drops `corroborated → vetoed` mid-operation **loses its autonomous grant for that cycle** (fail-safe). Operator
forced doses (ADR-0016) are unaffected — they are an explicit human decision, not an autonomous one.

### Open concern — the under-action failure mode (#410)

This ADR guards **one** failure — *over*-action (over-watering: a flood / runaway dose). It does **not** yet
guard the opposite, asymmetric failure — *under*-action (a plant dying of thirst because the gate never
opens):

| Failure | Character | Guarded here |
|---|---|---|
| over-water (gate opens wrongly) | noisy, usually **recoverable**, self-evident | yes |
| under-water to death (gate never opens) | **silent, irreversible**, no alarm | **no** |

The very conservatism that makes this gate fail-safe for the **pump** (disagreement -> pause, low contact ->
do not water) makes it fail-**deadly** for the **plant** in a persistently-ambiguous pot. "Fail-safe by not
acting" is the right default for hardware; it is **not** sufficient for the mission (the plant surviving).
The silent / irreversible failure deserves *more* engineering attention than the noisy / recoverable one —
yet it is the currently-unguarded one. (Owning it plainly: this blind spot is a direct consequence of how
conservative the gate above is — naming it, not hiding it.)

**First-class open concern, owned by the #410 epic** (Trellis architecture + Data forecast + Firmware
control); its resolution is **arm prerequisite #5**. Shape (detail in #410): (a) **detect** a never-opening
gate via a deployment-data forecast of the *never-confident* likelihood; (b) **respond** — alert-first, with
a **bounded fail-toward-watering** fallback only under tight over-water-safe conditions (no tray water, no
recent runoff, the good-contact channels read dry); (c) **distinguish pass-through soil** — stop-on-runoff
must tell *absorbed* from *ran-through* (hydrophobic soil channels water away without wetting the root zone;
the answer is a pulse-soak-repeat cycle, not more volume — ties to #382).

## Inputs required (design-light-before-build)

These do not block **ratification of the gate model**; they are required before **build**, and are
tracked in #400:

- **Sage (bench):** the **contact-quality metric** and the **microzone-disagreement threshold** — what "good
  contact" and "disagreement" actually measure on the bench (the probe-orientation / contact-procedure round).
  Until then, thresholds in any implementation are explicit placeholders.
- **Data:** the **event-annotation layer** + `cal_source` / date / `confidence` / `contact_quality` riding the
  telemetry header (ties #377 `plants.env` + #300). The confidence layer reads this substrate; profiles and
  contact-quality must be recorded and queryable.
- **Firmware:** **veto enforcement** in the control loop — the cross-channel disagreement check + contact-quality
  gate evaluated each sweep, extending the arm-gate inside the ADR-0016 supervisor (reusing the `do_sweep` veto
  pattern; no second decision path).

## Rejected alternatives

- **Act on per-channel calibrated bands directly (no confidence layer).** Rejected: #383 proves a calibrated
  band is the local reading; acting on it as pot need over-waters parched / hydrophobic / tray-confounded plants.
  Calibration is necessary, not sufficient.
- **A single global moisture threshold across plants.** Rejected: #383 plant-pathway diversity (cactus vs
  rootbound vs pothos) — no naive trigger generalizes.
- **Treat cross-channel disagreement as noise to average out.** Rejected: per Sage, "local disagreement is
  signal, not noise" — it describes real microzones, contact differences, and water pathways. Averaging hides
  exactly the signal that should pause the decision.
- **Block #170 on this ADR.** Rejected: #170 (the raw→band split) is independently valuable and a prerequisite;
  this layer sits above it. They proceed in parallel — #170 = structure + values, this = the act-or-not gate.

## Consequences

- Autonomous dosing gains a **decision-trust gate** above the hardware-safety gate. "Armed" no longer means
  "doses whenever a channel reads dry" — it means "doses only on a **corroborated**-dry channel."
- Confidence is **per-channel, per-decision, continuous** — a channel can lose its autonomous grant mid-cycle on
  disagreement or contact loss (fail-safe direction).
- New telemetry surfaces: confidence stage + contact-quality + disagreement flag per channel (Data header).
  Per ADR-0006, these are **surfaced, not smoothed**.
- Plant-pathway profiles become operator config per pot — a future UX surface (Design / DX), conservative by
  default.
- **This ADR can be ratified as the architecture (the gate model) now**, with thresholds/metrics named as
  placeholders; it cannot be **built** until the Sage/Data/Firmware inputs land.
- Extends ADR-0016: the arm-gate prerequisite chain grows, and the veto is enforced **inside** the
  single-authority supervisor — there is no competing decision path.

## Revisit triggers

- **The #410 under-watering fail-safe lands:** promote it from *open concern* to a **co-equal mission-safety
  gate** beside the over-action gate — symmetric guarding of both failure directions.
- **Sage's contact-procedure round lands:** replace placeholder thresholds with measured ones; revisit the
  disagreement metric.
- **Multi-probe-per-pot deployment:** revisit whether "microzone disagreement" needs spatial weighting (probe
  position within the pot), not just a flat spread bound.
- **Plant-pathway profiles grow:** revisit whether profiles need a richer per-species library vs the
  conservative-default + few-profiles approach.
- **Tray / tank sensing arrives:** the "tray shows water arrived" signal becomes a first-class veto input rather
  than inferred from runoff.

*Register in `docs/adr/0000-record-architecture-decisions.md` on acceptance.*
