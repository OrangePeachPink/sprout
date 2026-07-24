# PRD: Monitor & Predict — the contract of record the headline never had

**Status:** Draft — **explicitly not-definitive** (maintainer caveat, 2026-07-24: *"darn close to spot on… a
really good first step toward defining it as a set of product requirements"*). Ratified per-requirement at the
PRD ratification session. <!-- Draft → Accepted → Implemented -->
**Date:** 2026-07-24
**Owner:** Trellis (drafts) · maintainer (ratifies). V1.
**Epic / issues:** #1536 (this draft — #1534 ruling 1a) · #1534 (the eight-track Predict-theme fold) · #1535
(the cycle-interval rhythm model) · seeded by the clean-room outside review + the fold's validated spine.

---

## Problem

The v0.8.0 wave was themed **"Predict & Deliver."** Its self-declared headline — a per-plant next-watering
predictor that *learns each plant's rhythm from when the operator actually watered it* — was **built, tested,
and backtested, and then never wired to any surface** (`predictor.py` is imported only by tests; the Home chip
runs the simpler instrument extrapolator `forecast.py`). Its trust instrument (`backtest.py`) validates the
model nobody sees; the model the operator *does* see has no wired track record. And none of this was catchable,
because the headline **had no contract of record**: no predictor PRD exists, and the ADR that names it points at
the wrong PRD (ADR-0029 → PRD-0008, the public front door).

No specification meant nobody was positioned to notice that the centerpiece never reached the product. This PRD
is that missing contract. It is deliberately written as **both a requirements document and a delta register** —
every requirement carries a `shipped` / `partial` / `gap` tag against current `main`, so the same document that
says *what Predict (and its Monitor foundation) should be* also says *how far today's build is from it*.

Scope note: the review that produced this covered **Predict** deeply and found the **Monitor** foundation it
rests on was never audited at the requirements level. This PRD covers both — Monitor is the surface Predict
inherits (ADR-0033); a prediction with no place to live is a prediction nobody reads.

## Goals

- Give the next-watering predictor — and the Monitor surface it lives on — a single authoritative contract, so
  "what was this supposed to guarantee?" has an answer that isn't scattered across five modules and six issues.
- Make the document double as the delta register: each requirement tagged against `main`, so priority-setting at
  ratification works from produced facts, not impressions.
- Park the seven aspiration-gap items as **candidate** requirements (ruling 5a) so nothing is lost, without
  minting orphan tickets or pre-deciding priority.

## Non-goals

- **Not** deciding per-requirement priority or the v0.8.2 "Predict, finished" scope — that is the maintainer's
  at the ratification session (she has a stated lean, held deliberately so the PRD is ruled as a whole).
- **Not** minting implementation tickets. The wiring cluster already has its home (#1535 / v0.8.2); this is the
  contract, not the work order.
- **Not** re-specifying the modeling itself (the cycle-interval rhythm model is #1535's).
- **Not** a definitive spec. This is a first step, ratified requirement by requirement.

## The definition (the outside read's contract, adopted)

> **A prediction is `outcome + horizon + confidence + evidence`.** *"This plant will want water (outcome) in
> ~2 days (horizon), moderately sure (confidence), because it has run ~5-day cycles and is 4 days in
> (evidence)."* A band label is a classification of **now**, not a prediction — **classifiers are not a
> substitute for predictions.** Any surface that answers "when / whether" with only a current-state label has
> not met this contract.

## Requirements — the contract, and the delta register

Tags are against `main` as of 2026-07-24. **`shipped`** = meets the requirement on a user surface;
**`partial`** = present but incomplete or only in one place / only in the model; **`gap`** = not on any surface.

### Predict — the validated spine

- **R1 — Predictions carry outcome + horizon + confidence + evidence.** `partial` — the instrument forecast
  carries outcome + horizon and computes confidence (slope significance, `se`, `r2`), but confidence and
  evidence do not reach the surface; the shown chip is horizon-only (`next water ~Nd`).
- **R2 — A ranked predicted-urgency queue.** `gap` — per-plant ETAs and runway bands exist, but nothing orders
  the greenhouse by *time-to-need* (who needs me first), which is not the same as current wetness.
- **R3 — Confidence / uncertainty on the shown surface.** `gap` — the violet "predicted" channel is honest about
  *what* it is but shows no *how-sure*; a `±` / low-confidence cue is absent.
- **R4 — A visible track record (forecast-vs-actual).** `gap` — `backtest.py` scores forecasts against the real
  watering record, and it is entirely hidden. The changelog's score reaches no user.
- **R5 — First-class prediction-readiness states.** `partial` — only a single `"learning its rhythm"` fallback
  renders, and it over-promises: it also fires at the dry-end plateau where the model measured *flat*, not
  *learning*. Readiness must be truthful per state — at least {learning/collecting · ready · insufficient ·
  plateau/unreliable} — copy honest to each (#1534 D2).
- **R6 — The forecast drawn on the history chart with an unambiguous observed/predicted boundary.** `partial` —
  the #1136 band-journey is the one place prediction clearly reaches an ordinary user; the general history chart
  does not mark where measurement ends and projection begins.
- **R7 — The surfaced model *is* the backtested model, and the learned per-plant predictor reaches the
  surface.** `gap` — the headline (`predictor.py`, household/learned cadence) and its backtest are unsurfaced;
  the Home chip runs the bare instrument extrapolator. This is the banner finding; #1535 / v0.8.2 is its repair.
- **R8 — Classifiers are not surfaced as predictions.** `shipped` (as doctrine, worth protecting) — the violet
  predicted channel is never a mood, and band is never dressed as a forecast. Keep this boundary as the spine
  fills in.
- **R13 — One "thirsty" definition per surface, or both shown and labeled.** `gap` — #1534 D1: the Home card can
  say *Thirsty now* (band ladder) while the classic view forecasts *5.6h to Thirsty* (needs-water raw edge);
  one plant, two truths, neither surface names its definition.

### Monitor — the foundation Predict inherits (never audited at the requirements level)

- **R9 — Zones / grouping.** `gap` — no way to organize the greenhouse into zones or groups.
- **R10 — Filters.** `gap` — no filtered greenhouse view (by state, attention, board class).
- **R11 — Attention states.** `partial` — band mood + the exceptions lane carry raw attention signal; there is
  no dedicated "these N need you" attention surface composed from them.
- **R12 — Device-health vs plant-health, distinguished on surface.** `partial` — fleet-health / SUSPECT rollups
  exist workbench-side; on Home a bad sensor collapses to no-mood, indistinguishable to the operator from a calm
  plant. "The instrument is unwell" must read differently from "the plant is thirsty."

## Candidate requirements — the aspiration gaps (ruling 5a: parked, tagged `gap`, priority deferred)

All seven are **candidate** requirements. Per-item priority — and which v0.8.2 must ship for "Predict, finished"
to be true — is the maintainer's ruling at the ratification session, held deliberately so the PRD is ruled whole.

- **G1 — Away-week greenhouse composition.** `gap` — *"water these 3 before you leave; the rest hold until
  you're back."* Per-plant runway exists; the greenhouse-level composition does not. (Device-side also
  unsupported — the edge buffers nothing, seeds fresh at boot; a real horizon is host-composed.)
- **G2 — A distinct early-danger surface.** `gap` — *"this one is heading for harm,"* separate from ordinary
  thirst. Its raw material already exists: the #1497 exception labels, currently hidden.
- **G3 — The calm signal.** `gap` — *"everyone's fine for days"* — the affirmative all-clear, not just the
  absence of alarms.
- **G4 — Seasonal drift.** `gap` — *"your plants are drying faster than last month."* `env_decompose` is the
  latent substrate, currently dormant.
- **G5 — Post-watering hold.** `gap` — *"this drink should hold ~N days."* A forecast anchored to a detected
  watering event, not just the drying-direction ETA.
- **G6 — The prediction feedback loop.** `gap` — a prediction log (append `{ts, plant, model_tier, eta,
  interval}` at emit), recalc-after-watering, and model versioning — the substrate that makes R4's track record
  and any "shown-then-revised" honesty possible. No prediction log exists today.
- **G7 — Prediction-Center summaries.** `gap` — a consolidated place that answers the greenhouse-wide prediction
  questions at a glance, rather than one chip per card.

## Acceptance criteria (of this PRD)

- [ ] Every requirement above carries a `shipped` / `partial` / `gap` tag verified against `main` — the delta
      register is accurate at ratification.
- [ ] The seven aspiration-gap items are parked as candidate requirements, each tagged `gap`, with no per-item
      priority pre-decided (ruling 5a).
- [ ] ADR-0029's four `PRD-0008` predictor citations (§ intro, §context, §6 heading, §6 body) are repointed to
      PRD-0009 in the same PR.
- [ ] V1 — this lands only on the maintainer's ratification.

## Open questions (for the ratification session — deliberately not pre-decided)

- Per-requirement priority, and specifically **which requirements v0.8.2 "Predict, finished" must ship** for the
  release name to be true. (The maintainer has a stated lean, held for the session.)
- R7's blend surfacing: when the learned predictor and the instrument extrapolator disagree, does the operator
  see one reconciled number, or both labeled? (Relates to #1535's blend rule and R13's one-definition question.)
- R3's confidence vocabulary: a numeric `±`, a coarse {low/medium/high}, or a readiness-state proxy?
- Whether Monitor's R9–R12 belong in the Predict wave's finish or open their own foundation slice.

## Out of scope / later

- The modeling of the cycle-interval rhythm model itself — #1535, Owner: Data.
- The v0.8.2 wiring implementation — #1535 + #1534's trust ACs.
- The theme-conformance gate (release DoD addition) — #1534 ruling 3, OPERATIONS.md.
