# ADR-0037 — The production epoch, data admissibility, and the archive boundary

**Status:** Accepted — the epoch value and all four admissibility rules were maintainer-ratified in session
2026-07-20; this ADR records them so they are never re-derived from memory. V1 (doctrine).
**Date:** 2026-07-20
**Owner:** Trellis (this ADR). Execution: **Data** (#1330 — the `start_ts` stamp and the sweep).
**Lane:** architecture
**Relates:** #1330 (execution) · #1331 (the interval join this epoch feeds) · #1315 (the migration incident) ·
[ADR-0006](0006-data-architecture.md) (raw-evidence preservation) ·
[ADR-0027](0027-identity-model.md) (identity, assignment intervals) ·
[ADR-0031](0031-read-path-rollup-tiers.md) (the derived tier) · `docs/TIER_STORE_CONTRACT.md` §3

---

## Context

The corpus contains three kinds of data that were never formally distinguished: **production observations**,
**bench and commissioning captures**, and **noise from boards with nothing wired to them**. Because no boundary
existed, all three were reachable by dashboards, models, and charts. The visible symptom was a moisture-history
chart titled *"8 plants"* rendering sixteen-plus series, with bench boards drawn as first-class lines beside the
Anthurium.

The deeper problem is that pre-production captures **cannot be attributed**, and not because the mapping was
lost. Every commissioning capture from 2026-07-01 carries this header:

```text
# run=4probe-coloc-origplant
# sensors: ch0=GPIO36/s3@origplant ch1=GPIO39/s4@origplant …
```

All nine captures assert four probes co-located in one plant — across the very evening the maintainer was
physically walking probes from pot to pot doing per-plant checks. The firmware's `@plant` annotation never
updated. That is **worse than a missing mapping**: absent data produces uncertainty, whereas this produces a
clean, plausible, entirely false history. A join across it would confidently attribute eleven plants' readings
to one.

This is also the original real-world instance of the failure [ADR-0036](0036-sensor-identity-layers.md) exists
to end — an immutable-flashed firmware constant encoding a mutable probe↔channel binding, outliving the
arrangement it described.

## Decision

### 1. The production epoch

> **`2026-07-06T00:00:06Z` (2026-07-05 19:00:06 CDT)** — the first row of the continuous production feed.

Derived, not remembered. All eight channels appear in that first sample; `logs/` contains nothing earlier; and
`docs/experiments/2026-07-04_prewire_drydown_prediction.md` independently corroborates the mapping the day
before, with six plants on their correct boards and values flowing smoothly into the first production rows.
The probes were in their final homes by 07-04, so **the pre-settle trim on production boards is zero.**

**The epoch is stored as data, not configuration** — real `start_ts` values on the eight assignments. It is the
field the temporal interval join reads (`TIER_STORE_CONTRACT.md` §3), it makes the boundary self-documenting,
and it closes the all-null `start_ts` gap in the same pass. A config constant would be a second place for the
truth to live.

### 2. Four admissibility rules

| # | Rule | Why |
|---|---|---|
| 1 | **Unwired board → deleted outright**, not archived | An unconnected ADC pin emits noise. Noise is not evidence; retaining it only creates future work deciding whether it is noise. |
| 2 | **Pre-epoch production-board data → out of production**, lives only in the lab record | Its mapping is *wrong*, not missing. Bench-learning evidence, not observation. |
| 3 | **Nothing pre-epoch enters dashboards, models, or charts** | The boundary must hold at every consumer, or it isn't a boundary. |
| 4 | **Wired-but-unused streams stay admissible** | SHT and spectral keep collecting. The line is *wired + post-epoch + production-intended* — **never *currently consumed***. Being unused is not being inadmissible. |

Rule 4 is the one that keeps this from becoming a purge doctrine. Admissibility is about provenance, not utility.

### 3. The archive boundary, and the sweep order

Bench and commissioning records live in `experiments/`, `docs/experiments/`, `docs/evidence/`, and the `data`
branch archive — **already segregated from `logs/`.** This ADR ratifies that boundary rather than creating it.

The sweep executes in one order, and the order is load-bearing:

> **resolve citations → archive → delete**

Several documents under `docs/experiments/` cite `logs/` paths. Removing a cited file before resolving the
citation orphans the very lab record rule 2 names as the legitimate home. The 2026-06-26 common-cup anchor
experiment is already **self-contained** — its JSON carries its own states, comparisons, provenance, and
authority block — so [ADR-0035](0035-band-model-and-instrument-exceptions.md)'s ratified values do not depend on
raw logs surviving.

The delete step is the only irreversible act. It runs in the migration tool's shape — **plan → rendered dry-run
diff → maintainer approval → execute** — never on a lane's judgment.

### 4. The archive is safe by disuse, not by construction

Nothing currently reads the archived captures, which is the only reason their `@origplant` headers are
harmless. **If anything ever ingests the archive, that header is a live trap** — it will map eleven plants'
data onto one, silently and plausibly, and the result will look correct.

Therefore: **any future archive ingestion must treat pre-epoch headers as untrusted and resolve identity through
the registry projection, or not run at all.** Recorded here because the hazard is invisible at the point where
someone would create it.

## Consequences

- The moisture-history legend goes from sixteen-plus series to eight.
- The temporal interval join has real `start_ts` values to join against instead of nulls.
- Bench learning is preserved as bench evidence and is never mistaken for observation.
- The distinction is written down once, so it is not re-litigated from memory in six months — which was the
  maintainer's stated reason for wanting an ADR at all.

## Rejected alternatives

- **Mark pre-epoch rows `excluded` and keep them in production** (Trellis's first position). Rejected: the
  `excluded` axis (#1152) expresses *analysis admissibility for attributable data*. These rows have no
  recoverable attribution at all, so exclusion preserves a mapping that never existed.
- **Move the epoch past the 26-hour logging gap (07-08 → 07-09).** Rejected: the regime is identical on both
  sides — same plants, placement, and mappings — and only the logger failed. Moving a boundary to avoid a gap
  is evidence-editing, and it would discard the three densest days in the corpus (~127,000 rows).
- **Delete the bench archive outright.** Rejected: it is genuine evidence of bench work, and ADR-0035's anchors
  trace to it. Archived, never joined.
- **Store the epoch as a configuration constant.** Rejected in §1 — a second home for the truth.

## Open (routed)

- **`n3jhsp` — RULED BARE (maintainer, 2026-07-20): delete under rule 1.** Nothing but the classic ESP32 and
  the official C5 was ever wired, so its 5 captures (07-07, 07-12) are unwired-pin noise, not evidence. The
  tombstone manifest still records what was removed — the ruling decides the disposition, not whether the
  deletion is auditable.
- **`for:data`** (#1330) — stamp the eight `start_ts` values; run the sweep in the §3 order behind the dry-run
  gate.

## Revisit triggers

- A second production epoch (a re-deployment, a fleet rebuild) — this ADR describes one boundary, not a
  mechanism for many.
- Any proposal to ingest the archive into a production surface (§4).

— Trellis 🏛️
