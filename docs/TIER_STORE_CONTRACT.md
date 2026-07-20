<!-- cspell:words regenerable rebuildable drydown -->

# Tier store contract — the D1 written contract (#1239)

**Status:** v1 — ratified shape (#1239, Trellis PASS on the #1238 D0 evidence, 2026-07-19)
with the two D1 folds landed: the **µs invariant** written in as doctrine and the
**provenance columns** in the schema. **Owner:** Data (this doc + the store); **Trellis**
reviews contract changes (architecture). **Implements:** [ADR-0031](adr/0031-read-path-rollup-tiers.md)
(Accepted; DuckDB/Parquet ruled #915) realizing [ADR-0006](adr/0006-data-architecture.md) §3's
Derived analysis tier. **Relates:** [ADR-0025](adr/0025-config-provenance.md) (`config_id`),
[ADR-0027](adr/0027-identity-model.md) (identity), `docs/TELEMETRY_SCHEMA.md` (the wire contract
this store preserves).

The store module is `tools/analytics/tier_store.py`. The #1238 D0 tracer (`tier_d0.py`)
is its historical evidence and is superseded by this contract.

---

## 1. The store home — derived, disposable, never the `data` branch

- Home: **`reports/tier/raw/`** under the repo root — **gitignored** (`reports/` already
  is), **regenerable**, never backed up (ADR-0031 §1 / ADR-0006 §3).
- **Delete-and-rebuild, never patch.** A corrupt or suspect store ⇒ remove the partition
  (or the whole tree) and rebuild from raw. No in-place repair, ever.
- **The `data` branch stays a records store** (standing rule): CSV/db records only —
  Parquet never lands there.

## 2. Partition layout

```text
reports/tier/raw/date=<UTC-date>/device=<device_id>/part.parquet
```

- **Hive-style `date=` / `device=` partitions.** The per-board-only rule (ADR-0031 §2)
  is visible in the path and queryable on read (DuckDB surfaces the partition keys).
- One file per (UTC day, device). A rebuild replaces whole partition files.
- Rows are selected into a partition **by the parsed `timestamp_utc`, never the
  filename** — rotation names lie across midnight.

## 3. Columns

Wire truth per channel, plus the provenance trio. Nothing else.

| column | type | origin | rule |
| --- | --- | --- | --- |
| `timestamp_utc` | TIMESTAMP (µs, UTC-naive) | wire (host-stamped) | the one clock; named `_utc` |
| `device_id` | VARCHAR | wire | the stable minted id (ADR-0027) |
| `sensor_id` | VARCHAR | wire | the board **port** (s1…) |
| `raw_value` | INTEGER | wire | immutable truth (ADR-0006) |
| `band` | VARCHAR | wire | the device-emitted level — ground truth, never re-derived |
| `quality_flag` | VARCHAR | wire | carried verbatim; **never averaged away** in rollups |
| `session_id` | VARCHAR | wire | per-boot |
| `config_id` | VARCHAR | wire (payload/header) | ADR-0025 — a **column, never blended**; a config change stays distinguishable |
| `source_file` | VARCHAR | **provenance** | the origin segment's **basename** — which raw file this row came from |
| `ingest_ts` | TIMESTAMP (µs, UTC-naive) | **provenance** | when this row was written to the store (one instant per build batch) |
| `schema_version` | INTEGER (nullable) | **provenance** | the wire schema that shaped the row (v3/v4 reads stay distinguishable) |

Rules that bind the schema:

- **No legacy `value` %** (ADR-0031 §2 / ADR-0006 §4) — the tier never resurrects the index.
- **No plant identity in the store.** Identity resolves at **read time** via the
  registry (open assignments) — the store stays board-true and the never-stitch line
  clean (ADR-0027).
- **The provenance trio is the auditable-rebuild guarantee** (#1239 fold 2): which raw
  file + when ingested + which wire schema = recoverable lineage. Chosen as **columns**
  (not a per-partition manifest): per-row lineage survives partial rebuilds and is
  filterable in the same query engine with no side-file to drift.

## 4. The µs invariant (#1239 fold 1 — doctrine, not an implementation detail)

> **All time-aggregation over the store is computed in exact integer microseconds —
> never ms-floored, never float-seconds — so any DuckDB rollup equals an independent
> pure recompute exactly.**

Why: DuckDB `TIMESTAMP` and Python `datetime` are both natively µs-precision, so
integer-µs math makes the two answer paths equal **by construction**. The D0 tracer's
first real-data run caught the alternative failing: `epoch_ms(a) − epoch_ms(b)` (floors
each absolute timestamp) diverges off-by-one from float `total_seconds()` truncation on
real sub-ms timestamps — a divergence synthetic clean-timestamp fixtures never trip.
The store's test suite carries a **sub-ms fixture** as the permanent regression net;
any tier-1+ rollup inherits this invariant.

## 5. The dwell-rule default (Data-tunable; not an architecture concern)

For duration-shaped questions (hours-per-band and kin): each reading owns the time to
the **next physical sample** on its (device, sensor), **capped at 2× the sampling
cadence** (a logging gap never inflates a band's hours); the day's last reading owns 0;
only band-bearing rows (a real band, not `NO_SIGNAL`) tally. The cap multiplier is
Data's tuning knob; changing it re-materializes derived answers, never the raw tier.

## 6. Regenerability

- The only reader of raw is **`parse_v1`** (the one parse boundary, ADR-0021); the
  store is written from parsed readings, never by re-splitting CSV text.
- Rebuild = delete the partition(s) + re-run the build over `logs/` (+ archive). The
  result is byte-stable for a fixed input set except `ingest_ts` (which truthfully
  records the new build instant).
- Fidelity gate on every build: row count, `raw_value` checksum, and distinct-sensor
  count computed **from the written Parquet** must match the parsed input.

## 7. Lifecycle

- **D2 (#1240)** backfills the full history through this contract.
- Rollup tiers (1-min → 15-min → hourly; ADR-0031's granularity map) build **on top**
  of this raw tier and inherit §3's carried-never-averaged `quality` rule and §4's µs
  invariant. Events are never downsampled (ADR-0031 §3).

## 8. Live ingest, compaction, and freshness (D3, #1241)

- **Appends.** Between compactions a partition directory may hold
  `append-*.parquet` siblings beside (or before) its canonical `part.parquet` —
  same §3 schema, written through the same one schema path (`build_partition`),
  same §6 gate per append. **Readers therefore glob `*.parquet` within a
  partition, never `part.parquet` alone.**
- **The store is its own watermark.** How much of a source segment is already
  ingested is *derived* — COUNT of stored rows grouped by the `source_file`
  lineage column. No side-car state exists to lose, drift, or contradict the
  store. Appends are **at-least-once** (a crash between an append landing and
  anything else converges next cycle); the canonical part is **exactly-once**
  (gate-checked whole rebuild). Transient duplicate rows after an ingest crash
  are possible in appends only, and heal at the next compaction.
- **Append-only source assumption.** A log segment only ever grows; the first N
  parsed rows of a segment are the N already stored. A segment that *shrank*
  (rotation, recovery, rewrite) is detected (stored > parsed) and healed by
  rebuilding every partition it feeds, whole, from source — §1
  delete-and-rebuild, never patch.
- **Compaction = the D2 path.** A partition's feeder segments are read from its
  own lineage column; the partition is rebuilt whole from source
  (fidelity-gated, §6) and only a **passing** gate deletes its appends. Default
  cadence: daily, compacting **closed** (pre-today UTC) days; the open day
  compacts on its first cycle after UTC midnight.
- **Freshness bound.** With an ingest cycle of **I**, the store lags the CSVs by
  at most I for the open day; a closed day reaches its canonical single
  `part.parquet` by the first compaction after UTC midnight. The live probe
  (`tier_ingest.py status`) reports pending rows per segment, the oldest pending
  row's age, and the append-file compaction debt.
