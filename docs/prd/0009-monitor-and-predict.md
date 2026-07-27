# PRD: Monitor & Predict — the contract of record the headline never had

**Status:** **Accepted — ratified per-requirement at the PRD ratification session, 2026-07-24.** Every
requirement below carries a maintainer-ruled **disposition** (`committed` / `deferred`) alongside its
build-state tag, and the three open questions are ruled (§Rulings). It remains a *first* contract, not a final
one — the caveat that opened it still holds: *"darn close to spot on… a really good first step toward defining
it as a set of product requirements."* Requirements may be revisited; that is the document working, not
failing. <!-- Draft → Accepted → Implemented -->
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

- **Not** minting implementation tickets. The wiring cluster already has its home (#1535 / v0.8.2); this is the
  contract, not the work order. *(Priority was a non-goal of the draft; it is now ruled — see §Rulings.)*
- **Not** re-specifying the modeling itself (the cycle-interval rhythm model is #1535's).
- **Not** a definitive spec. This is a first step, ratified requirement by requirement.

## The definition (the outside read's contract, adopted)

> **A prediction is `outcome + horizon + confidence + evidence`.** *"This plant will want water (outcome) in
> ~2 days (horizon), moderately sure (confidence), because it has run ~5-day cycles and is 4 days in
> (evidence)."* A band label is a classification of **now**, not a prediction — **classifiers are not a
> substitute for predictions.** Any surface that answers "when / whether" with only a current-state label has
> not met this contract.

## Requirements — the contract, and the delta register

Each requirement carries two marks. The **build-state tag** is against `main` as of 2026-07-24 — **`shipped`**
= meets the requirement on a user surface; **`partial`** = present but incomplete, or only in one place / only
in the model; **`gap`** = not on any surface. The **disposition** is the maintainer's ratification ruling —
**`committed`** = in the wave, build tickets follow; **`deferred`** = recorded, no ticket, revisited at a later
release.

### Predict — the validated spine

- **R1 — Predictions carry outcome + horizon + confidence + evidence.** `partial` · **committed** — the instrument
  forecast carries outcome + horizon and computes confidence (slope significance, `se`, `r2`), but confidence and
  evidence do not reach the surface; the shown chip is horizon-only (`next water ~Nd`).
- **R2 — A ranked predicted-urgency queue.** `gap` · **committed** — per-plant ETAs and runway bands exist, but nothing
  orders the greenhouse by *time-to-need* (who needs me first), which is not the same as current wetness.
- **R3 — Confidence / uncertainty on the shown surface.** `gap` · **committed** — the violet "predicted" channel is
  honest about *what* it is but shows no *how-sure*. **Ruled at ratification: Design owns the vocabulary** — *"have
  Design invent a range or numeric amount of a presentation array that is appropriate."* The **form is Design's
  deliverable**, filed as its own Design task: a range, a numeric scale, or a bounded set of confidence words, their
  call within the design system. This requirement deliberately does **not** pre-decide it. What R3 does fix is the
  contract the vocabulary must satisfy: the cue rides the **predicted channel** (never a mood — R8), it is legible at
  card size, and it degrades into R5's readiness states rather than inventing a confident-looking value where the model
  has none.
- **R4 — A visible track record (forecast-vs-actual).** `gap` · **committed** — `backtest.py` scores forecasts against
  the real watering record, and it is entirely hidden. The changelog's score reaches no user.
- **R5 — First-class prediction-readiness states.** `partial` · **committed** — only a single `"learning its rhythm"`
  fallback renders, and it over-promises: it also fires at the dry-end plateau where the model measured *flat*, not
  *learning*. Readiness must be truthful per state — at least {learning/collecting · ready · insufficient ·
  plateau/unreliable} — copy honest to each (#1534 D2).
- **R6 — The forecast drawn on the history chart with an unambiguous observed/predicted boundary.** `partial` ·
  **committed** — the #1136 band-journey is the one place prediction clearly reaches an ordinary user; the general
  history chart does not mark where measurement ends and projection begins.
- **R7 — The surfaced model *is* the backtested model, and the learned per-plant predictor reaches the surface.** `gap`
  · **committed** — the headline (`predictor.py`, household/learned cadence) and its backtest are unsurfaced; the Home
  chip runs the bare instrument extrapolator. This is the banner finding; #1535 / v0.8.2 is its repair. **Ruled approach
  (delegated to Trellis at ratification — *"make the best choice possible with what you know; if we have to review and
  adjust later we will do so"*): the #1535 wiring-cluster shape.** The three-tier `predictor.py` becomes the model
  behind the Home chip — **rate extrapolation mid-dry-down** (where the slope is live and the instrument is the better
  estimator), **per-plant learned interval at the dry-end plateau** (where the rate model goes silent exactly when the
  operator most wants an answer — the founding p03 case), and **honest none** when neither qualifies. The **backtest
  wires to what is shown**, not to a shelf model, and **the blend rule is stated and backtest-scored** rather than tuned
  by feel. *Chosen on the available record, explicitly review-and-adjust-permitted: if the blend scores worse than
  either tier alone, the score decides, not this paragraph.*
- **R8 — Classifiers are not surfaced as predictions.** `shipped` · **committed** (as doctrine, worth protecting) — the
  violet predicted channel is never a mood, and band is never dressed as a forecast. Keep this boundary as the spine
  fills in.
- **R13 — ONE "thirsty" definition, everywhere.** `gap` · **committed** — #1534 D1: the Home card can say *Thirsty now*
  (band ladder) while the classic view forecasts *5.6h to Thirsty* (the needs-water raw edge); one plant, two truths,
  neither surface naming its definition. **Ruled at ratification: unify — *"use a single definition, not two different
  and differently defined."*** The both-shown-and-labeled option is dead. **The authority is the ADR-0035 seven-mood
  band ladder**, decided on the merits and stated here as the fold was asked to:
  1. **It is already the ratified one-vocabulary rule.** ADR-0035 §1: *"seven in-soil mood bands — one
     vocabulary everywhere… the mood words ARE the band names… a plant's state has exactly one name across every
     surface."* R13 is that rule reaching the forecast, not a new decision.
  2. **The competing edge self-identifies as debt.** `forecast.py` calls its own target *"the A2
     (un-reconciled) needs-water boundary"* — twice, in the module docstring and in its printed footnote. It is
     a proxy awaiting this reconciliation, not a rival authority.
  3. **The ladder is measured and ratified; the proxy is inherited.** The brackets come from the fresh
     dual-envelope dry-down (#1174 / #1211, 36/36 fixture validation); the A2 names (`air | DRY | needs water |
     OK | well watered | over`) are the retired pre-#995 register the ladder replaced.
**Therefore:** the forecast retargets its ETA to the **ladder's Thirsty entry edge**, read from the #1164 cal-suite
  fixtures (authoritative for the numbers — never hard-coded here), and the A2 `needs water` proxy retires from the
  forecast path. Both surfaces then answer "thirsty" from one boundary, and the D1 contradiction cannot recur by
  construction rather than by discipline.

### Monitor — the foundation Predict inherits (never audited at the requirements level)

- **R9 — Zones / grouping.** `gap` · **deferred** — no way to organize the greenhouse into zones or groups.
- **R10 — Filters.** `gap` · **deferred** — no filtered greenhouse view (by state, attention, board class).
- **R11 — Attention states.** `partial` · **committed** — band mood + the exceptions lane carry raw attention signal;
  there is no dedicated "these N need you" attention surface composed from them.
- **R12 — Device-health vs plant-health, distinguished on surface.** `partial` · **committed** — fleet-health / SUSPECT
  rollups exist workbench-side; on Home a bad sensor collapses to no-mood, indistinguishable to the operator from a calm
  plant. "The instrument is unwell" must read differently from "the plant is thirsty."

## Candidate requirements — the aspiration gaps (ruling 5a: parked, tagged `gap`, priority deferred)

All seven are **candidate** requirements. Per-item priority — and which v0.8.2 must ship for "Predict, finished"
to be true — is the maintainer's ruling at the ratification session, held deliberately so the PRD is ruled whole.

- **G1 — Away-week greenhouse composition.** `gap` · **deferred** — *"water these 3 before you leave; the rest hold
  until you're back."* Per-plant runway exists; the greenhouse-level composition does not. (Device-side also unsupported
  — the edge buffers nothing, seeds fresh at boot; a real horizon is host-composed.)
- **G2 — A distinct early-danger surface.** `gap` · **committed** — *"this one is heading for harm,"* separate from
  ordinary thirst. Its raw material already exists: the #1497 exception labels, currently hidden.
- **G3 — The calm signal.** `gap` · **committed** — *"everyone's fine for days"* — the affirmative all-clear, not just
  the absence of alarms.
- **G4 — Seasonal drift.** `gap` · **deferred** — *"your plants are drying faster than last month."* `env_decompose` is
  the latent substrate, currently dormant.
- **G5 — Post-watering hold.** `gap` · **committed** — *"this drink should hold ~N days."* A forecast anchored to a
  detected watering event, not just the drying-direction ETA.
- **G6 — The prediction feedback loop.** `gap` · **committed** — a prediction log (append `{ts, plant, model_tier, eta,
  interval}` at emit), recalc-after-watering, and model versioning — the substrate that makes R4's track record and any
  "shown-then-revised" accountability possible. No prediction log exists today.
- **G7 — Prediction-Center summaries.** `gap` · **committed** — a consolidated place that answers the greenhouse-wide
  prediction questions at a glance, rather than one chip per card.

## Acceptance criteria (of this PRD)

- [x] Every requirement carries a `shipped` / `partial` / `gap` tag verified against `main` — the delta register
      was accurate at ratification.
- [x] The seven aspiration-gap items were parked as candidate requirements, each tagged `gap`, with no per-item
      priority pre-decided (ruling 5a) — **and are now dispositioned** by the ratification session.
- [x] ADR-0029's four `PRD-0008` predictor citations (§ intro, §context, §6 heading, §6 body) repointed to
      PRD-0009 in the drafting PR (#1538).
- [x] V1 — the draft landed on the maintainer's ratification (#1538, merged 2026-07-25).
- [x] **Every requirement carries a ruled disposition** (`committed` / `deferred`), and the three open questions
      are resolved in-document (§Rulings) — the ratification fold.

## Rulings — the ratification session (2026-07-24)

Every question this document opened with is answered. Recorded here so the reasoning survives the session.

| question | ruling |
|---|---|
| Per-requirement priority | **Predict R1–R8 + R13 all committed.** *"Yes, let's do all of these now."* |
| Monitor scope | **R11 + R12 committed** (attention states · device-vs-plant health); **R9 + R10 deferred** (zones/grouping · filters) |
| The aspiration gaps | **G2, G3, G5, G6, G7 committed**; **G1 + G4 deferred** (away-week composition · seasonal drift) |
| R13 — one definition or both labeled? | **Unify.** *"Use a single definition, not two different and differently defined."* Authority ruled on the merits in R13 above: the ADR-0035 band ladder |
| R7 — blend surfacing | **Delegated to Trellis**, *"make the best choice possible… if we have to review and adjust later we will do so."* Ruled in R7 above: the #1535 wiring-cluster shape, review-and-adjust-permitted |
| R3 — confidence vocabulary | **Design invents it**, as its own task. R3 fixes the contract, not the form |

### Still genuinely open (not decisions being dodged — inputs that don't exist yet)

- **The blend rule's tuning constants** (R7): where the rate tier hands off to the interval tier. This is a
  *measured* answer — `backtest.py` scores it against the real watering record — not a design opinion.
- **The Thirsty entry edge's exact value** (R13): read from the #1164 cal-suite fixtures at build time, per
  ADR-0035's rule that the fixtures are authoritative for the numbers and the ADR records only the snapshot.

## What follows this PRD (so nothing double-mints)

- **Already tracked — no new tickets:** R7 / R4 / G6's core is **#1535** (its ACs extend to carry the R-IDs);
  R13 + R5's copy fixes are **#1534**'s existing ACs (D1 now ruled = unify); the #1541 slices stand as boarded.
- **New build tickets, minted against the ratified IDs after this merges:** R2 · R3 (Design's vocabulary +
  surface) · R6 · R11 · R12 · G2 · G3 · G5 · G7.
- **Deferred, recorded here with no ticket:** R9 · R10 · G1 · G4 — each keeps its release-note line so a later
  cycle inherits the reasoning rather than rediscovering the gap.

## Out of scope / later

- The modeling of the cycle-interval rhythm model itself — #1535, Owner: Data.
- The v0.8.2 wiring implementation — #1535 + #1534's trust ACs.
- The theme-conformance gate (release DoD addition) — #1534 ruling 3, OPERATIONS.md.
