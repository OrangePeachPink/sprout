# ADR-0022 — Calibration-confidence layer (local-truth vs pot-truth gating)

**Status:** Proposed — *drafted by Trellis from #400 (surfaced by #170 + #383). The gate **model** is ratifiable
now; the **thresholds/metrics** need the cross-lane inputs enumerated below (design-light-before-build —
ratification is not blocked on them). Awaiting Sage/Data/Firmware inputs + maintainer ratification.*
**Date:** 2026-06-30
**Owner:** Architecture (Trellis, author) — promotion-gate owner; control-loop enforcement co-owned with Firmware
**Lane:** architecture (cross-lane: Firmware enforcement · Sage bench · Data substrate)
**Extends:** [ADR-0016](0016-actuation-wiring-seam.md) (single authority / arm-gate)
**Relates:** #170 (per-channel split) · #348 (arm-gate chain) · #383 (bench evidence) ·
[ADR-0006](0006-data-architecture.md) (honest data) · #377 / #300 (telemetry header) · the capability-stage
vocabulary (`docs/GLOSSARY.md`) · #400

---

## Context

Per-channel calibration (#170) removes **sensor personality** — each probe gets its own raw→band boundaries,
so a reading is no longer skewed by that probe's individual signature. But Sage's #383 greenhouse pass shows
the deeper problem: even a perfectly-calibrated band is **local truth** — what one probe senses in its
microzone — and **not pot truth**, i.e. whether the plant actually needs water. Microzone disagreement,
contact quality, hydrophobic/preferential flow, and tray state routinely dominate the whole-pot decision.
Across P01–P11, runoff did not mean "fully watered," a plausible number did not mean "good contact," and one
dry channel did not mean the pot was dry.

ADR-0016 ships autonomous dosing **DISARMED** and gates arming on the dry-safety chain
(`#93 / #191 / #2 / #215`) — but that chain proves the *hardware* is safe (relays fail off, the watchdog
resets, the bench passed). Hardware-safe is not the same as **decision-trustworthy**: there is no gate today
on whether the *reading* justifies watering. Acting on local truth as if it were pot truth is precisely how an
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
   `plants.pump` records, not the interim diagnostic line, so telemetry honesty and the data join hold
   exactly when watering happens. (#348 ships DISARMED precisely because this and the dry-safety chain are
   not yet met.)

Until all pass on real hardware, dosing stays **DISARMED** (the ADR-0016 arm-gate). The confidence layer is an
**additional, continuous** arm condition — not a one-time check. Even after the operator arms, a channel that
drops `corroborated → vetoed` mid-operation **loses its autonomous grant for that cycle** (fail-safe). Operator
forced doses (ADR-0016) are unaffected — they are an explicit human decision, not an autonomous one.

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
  band is local truth; acting on it as pot truth over-waters parched / hydrophobic / tray-confounded plants.
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
  Per ADR-0006 honesty, these are **surfaced, not smoothed**.
- Plant-pathway profiles become operator config per pot — a future UX surface (Design / DX), conservative by
  default.
- **This ADR can be ratified as the architecture (the gate model) now**, with thresholds/metrics named as
  placeholders; it cannot be **built** until the Sage/Data/Firmware inputs land.
- Extends ADR-0016: the arm-gate prerequisite chain grows, and the veto is enforced **inside** the
  single-authority supervisor — there is no competing decision path.

## Revisit triggers

- **Sage's contact-procedure round lands:** replace placeholder thresholds with measured ones; revisit the
  disagreement metric.
- **Multi-probe-per-pot deployment:** revisit whether "microzone disagreement" needs spatial weighting (probe
  position within the pot), not just a flat spread bound.
- **Plant-pathway profiles grow:** revisit whether profiles need a richer per-species library vs the
  conservative-default + few-profiles approach.
- **Tray / tank sensing arrives:** the "tray shows water arrived" signal becomes a first-class veto input rather
  than inferred from runoff.

*Register in `docs/adr/0000-record-architecture-decisions.md` on acceptance.*
