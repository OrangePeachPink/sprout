# ADR-0031 — Read-path rollup tiers: materialized aggregates over immutable raw

**Status:** Accepted — maintainer-ratified 2026-07-10 (v0.7.2 ADR batch, #915): fork 1 ruled **DuckDB/parquet** (the
ADR-0006 §3-sanctioned tier; a deliberate new runtime dependency); forks 2–4 accepted at the Trellis leans
(granularity map as a starting proposal, incremental-at-rotation + full-rebuild-available, `config_id` carried on the
bucket and never blended). *Drafted by Trellis (2026-07-07) from #828 during the v0.8.0 bench gap.* This ADR
**realizes ADR-0006 §3's already-planned Derived analysis tier** and its §115 revisit trigger — it does not re-fence
the raw, it stands up the tier ADR-0006 sanctioned.
**Date:** 2026-07-07
**Owner:** Trellis (architecture) — the tier / envelope / event contracts; Data builds the materializer (v0.8.0)
**Lane:** architecture (cross-lane: Data)
**Extends:** [ADR-0006](0006-data-architecture.md) §3 (the Derived analysis tier — DuckDB/parquet, rebuilt from
raw; this stands it up), §1 (three-layer, raw immutable), §4 (surface never smooth) ·
[ADR-0019](0019-capability-and-sensor-matrix.md) / #170 (per-channel calibration — the per-board-only rule) ·
[ADR-0025](0025-config-provenance.md) (`config_id` boundary)
**Relates:** #828 (this) · #827 (parse-once cache — the sequenced predecessor) · #12 (gzip rotation) ·
the cycle-pattern consumers #25 / #822 / #832 · [ADR-0029](0029-plant-pot-site-profile-registry.md) (the profile
dimension predictions join alongside these facts)

---

## Context

The read path re-parses the full corpus on every `data.json` request (~20 s at ~230k rows, growing ~23k rows/day);
month/year windows become untenable at millions of rows. The need (maintainer, 2026-07-06): *"higher frequency for
the last hour, less for the day, week, month, year — but keeping enough fidelity to always figure out historical
cycles and why we decided things the way we did."*

**This is not log trimming — and the fence is already ADR-0006 doctrine.** Raw CSVs are immutable and kept forever;
the storage math makes that trivial (~23k rows/day ≈ ~350 KB/day gzipped ≈ ~130 MB/year, inside the existing gzip
rotation + LFS archive). What ages is the **read path**, not the evidence. ADR-0006 §3 already names a *"Derived
analysis tier — DuckDB / parquet, rebuilt from the raw, gitignored, never backed up … for fast multi-day queries
once CSV re-parse gets slow. Planned; not yet stood up,"* and §115's revisit trigger is verbatim *"dataset outgrows
CSV re-parse → stand up the DuckDB/parquet tier."* This ADR operationalizes exactly that tier. The narrow, risky
part is one thing: the rollup contract — so most of this ADR is that contract.

## Decision (proposed)

### 1. Tier model — raw is Tier 0; rollups are derived and disposable

- **Tier 0 — raw** (canonical source, immutable, archived): serves recent/short windows at full fidelity, via
  #827's in-memory cache.
- **Tier 1 / 2 / 3 — materialized rollups** in ADR-0006 §3's derived analysis tier: each a coarser time-bucket
  (e.g. 1-min → 15-min → hourly; granularities are the design fork below). Derived, gitignored, never backed up.
- **Rebuildable by construction:** every tier regenerates from raw alone. A corrupt or suspect rollup ⇒ **delete
  and rebuild**, never patch — ADR-0006's "the DB/parquet is a derived layer, never the canonical source; if lost,
  regenerated from the raw."

### 2. The envelope contract (the load-bearing decision — Trellis-owned)

Everything else is tunable; this is load-bearing, because once consumers (#25 / #822 / #832) read tier buckets,
changing what is *in* a bucket is a re-materialization of the whole corpus. Per bucket, per `(device_id, channel)`:

- `mean`, `min`, `max`, `spread` — the envelope that lets a dry-down slope or a diurnal cycle survive at any age.
- `n` — sample count in the bucket. **Note:** a 2-sample bucket is not a 60-sample bucket, and a slope drawn
  through thin buckets should say so.
- a `quality` rollup — whether any `SENSOR_FAULT` / `SUSPECT` fell in the bucket, **carried, never averaged away**.

Rules that bind the contract:

- **Over `raw_value` (+ band), never the legacy `value` %** — ADR-0006 §4 already forbids analysing the moist-%
  index; the tier must not resurrect it.
- **Per-channel *and* per-board only — never rolled up across boards.** The classic ESP32 and the C5 have
  different ADCs / dynamic ranges, so a cross-board aggregate is meaningless (ADR-0019 / #170). Buckets key on
  `(device_id, channel)`; cross-plant comparison happens *after* per-channel calibration, upstream of this tier.
- **Do not blend rows across a `config_id` change** (ADR-0025) — a gain/itime shift changes what a raw *means*.
  (The bucket-boundary mechanism is a fork below.)

### 3. The event-preservation invariant (the fidelity clause)

Events are **never downsampled** — they survive at **exact timestamps in every tier**: band transitions, detected
waterings, `SENSOR_FAULT`s, session boundaries. They are the "*why we decided things*" record.

- **Materialized as a first-class sparse event table** in the derived tier — *not* re-derived on every read.
- The detection logic **already exists** (`band_movement.py` = first transition + each change; `bench_events.py`
  classify/event_rows for waterings; `dashboard._sessions` for session boundaries; the `SENSOR_FAULT` quality_flag).
  The tier work is **persisting** those at exact timestamps and **guaranteeing every tier surfaces them** — not new
  detection.
- Events are sparse, so full retention is nearly free; and the table stays **rebuildable from raw** like every tier.

### 4. The never-smooth labeling contract (ADR-0006 §4 on the time axis)

A rollup answer is **labeled as a rollup and rendered as an envelope** — a min–max band around the mean line, with
`n` — **never a smoothed line masquerading as raw samples**. Concretely: the data API response carries `tier`,
`bucket_seconds`, and `n` per point, and the dashboard picks its render from that. This is "surface, never smooth"
applied to the time axis: show the spread the bucket hides, do not hide it.

### 5. Range → source switch (composes with #827)

The dashboard already has the switch point — `dashboard.RANGE_HOURS`. Short windows (3h / 24h / 48h) serve raw from
the in-memory parse cache (#827); longer windows (7d → Tier 1; 30d / all → coarser) serve rollup buckets. **One
range→source switch**, and bucket sizes are **config, not hardcoded**, so re-tuning granularity never touches
consumers.

### 6. Sequencing

- **#827 (parse-once cache) ships first** — it is the immediate, independent fix that makes short windows fast
  *now*, with no tier at all. Build it first (Data).
- **This ADR is the scale layer** for month/year at millions of rows. Its design proceeds in parallel; its build
  follows #827. They compose: short windows ride the cache, long windows ride the tier.

## The forks for planning to rule (present, don't decree)

1. **Substrate.** DuckDB/parquet (ADR-0006 §3's named choice — cheap time-bucketing + envelopes in one SQL pass)
   vs a boring-first CSV-of-rollups (no new dependency, but you hand-roll the aggregation + indexing).
   **I lean DuckDB** — it is the already-sanctioned tier, and #827's in-memory cache remains the raw-window path, so
   the dependency buys the hard part. *Open tension:* it is a new runtime dependency — a deliberate call, not a
   default.
2. **Granularities + range→tier map.** A starting proposal: 1-min (Tier 1, 7 d) → 15-min (Tier 2, 30 d) → hourly
   (Tier 3, all) — **tunable**, derived from the existing range chips, bucket sizes kept in config.
3. **Rebuild cadence.** Incremental append at rotation boundaries (a closed gzip segment's buckets are final and
   appended) with a **full rebuild always available**. Corrupt/suspect tier ⇒ delete + rebuild.
4. **`config_id` boundary.** Bucket-within-a-config vs carry `config_id` on the bucket. **I lean: carry `config_id`
   on the bucket + never blend across a change** — the simplest plain option — but flagging it for the ADR to pin.

## Consequences

- Month/year windows stay fast at millions of rows; the raw stays the immutable source, the tiers are disposable.
- Consumers (#25 / #822 / #832) read a **stable envelope contract**; since changing a bucket's contents is a full
  re-materialization, the contract is pinned before they build.
- Events — the "why we decided" record — survive at exact timestamps forever, in every tier.
- The tier **never smooths**: a rollup is always labeled and rendered as an envelope with `n`.
- No new fence: the raw-immutability + derived-disposable doctrine is ADR-0006's; this only stands up the tier.

## Rejected / deferred alternatives

- **Trim or downsample the raw.** Rejected — violates ADR-0006 §1 (raw immutable); the storage math (~130 MB/year)
  makes trimming unnecessary. Only the read path ages, never the evidence.
- **Re-derive events on every read.** Rejected — the event table is the "why we decided" record; materialize it
  (still rebuildable) so it is queryable and guaranteed in every tier, not recomputed each request.
- **Average `quality_flag`s into the bucket.** Rejected — ADR-0006 §4 (surface, never smooth): carry the
  any-fault/worst signal, do not dissolve it into a mean.
- **Cross-board rollups.** Rejected — ADR-0019 / #170: different ADCs make a cross-board aggregate meaningless.

## Open (routed)

- **Data (v0.8.0 — #827 then #828):** build the materializer + the range→source switch + the sparse event table;
  pick the substrate on fork 1. Ping me on the schema PR; I gate the envelope + event contracts.
- **Trellis:** the `config_id`-boundary rule (fork 4) and the exact granularity map (fork 2) tighten at planning;
  the envelope + event-preservation invariants are the review gate.

— Trellis 🪴
