# ADR-0021 — parse_v1 is the single telemetry contract boundary

**Status:** Proposed
**Date:** 2026-06-27
**Owner:** Trellis (ADR author) + Data lane (implementation)
**Lane:** data/analytics
**Extends:** [ADR-0006](0006-data-architecture.md) §2 (telemetry schema / contract)
**Refs:** #293 (gap issue), #294 (C2 null-value violation), #295 (C3 stale cal bounds)

---

## Context

ADR-0006 §2 establishes `docs/TELEMETRY_SCHEMA.md` as the canonical wire format and requires
column-by-name mapping so readers survive column additions and reordering. The implementation of
that contract lives in `tools/analytics/parse_v1.py`: it reads schema-v1 CSV (and `.csv.gz`),
parses the `#` provenance headers, explodes the `payload` field, derives `band`, exposes
`raw_value` as the trustworthy signal, and carries `value`/`unit` through unchanged (not analysed
-- ADR-0006 §4).

Seven production modules consume `parse_v1` directly:

| Module | Import |
|---|---|
| `analysis_store.py` | `parse_files` |
| `dashboard.py` | `parse_files`, `LogData`, `LogRecord`, `build_context` |
| `forecast.py` | `parse_files`, `LogData`, `DEFAULT_CAL_BOUNDS` |
| `lab_detail.py` | `parse_files` |
| `lab_studies.py` | `parse_files` |
| `legacy_log.py` | `CANONICAL_COLUMNS` (column-name sync) |
| `serve.py` | `parse_files` |

This is the contract in practice. But it is **convention, not enforcement**. Nothing structurally
stops a future PR from opening `logs/*.csv` directly in `dashboard.py` or a new `forecast_v2.py`,
fracturing schema knowledge across multiple files. As the project adds transport variants (ADR-0018)
and a second `record_type=env` stream, the "single contract point" invariant is harder to hold
without a decision that names it.

Two active violations also need naming:

- **C2** -- `tools/analytics/make_sample_log.py` (lines 149-150) and
  `tools/capture/experiment_capture.py` (line 152) emit `value=<pct float>` and `unit="pct"` instead
  of `NULL/""` per the schema-v1 contract. Any downstream fixture built from these embeds the legacy
  interpretation as if it were a measurement. (Tracked: #294.)
- **C3** -- `parse_v1.DEFAULT_CAL_BOUNDS` is hard-coded to `(2760, 2140, 1830, 1520, 1260, 1030)` --
  the un-reconciled spec boundaries, not the as-flashed values. `forecast.py` imports this constant
  directly. Cal boundaries must derive from the `# cal bounds` provenance header in the log, not be
  a module constant. (Tracked: #295.)

## Decision

### 1. parse_v1 is the contract boundary

`tools/analytics/parse_v1.py` is the **single authorised entry point** for all telemetry reads
inside Sprout. No other module in `tools/` reads raw telemetry CSV (`logs/*.csv`, `logs/*.csv.gz`,
or any equivalent) directly. Schema knowledge -- column layout, provenance header parsing, band
classification, cal bounds -- lives in `parse_v1`, not scattered across callers.

**Rule:** if a module needs a telemetry record or a field derived from one, it calls `parse_files()`
(or a versioned successor) and works from the returned `LogData` / `LogRecord` objects. It does
not open CSV, split lines, or parse `#` headers itself.

### 2. `DEFAULT_CAL_BOUNDS` is a temporary scaffold, not a caller export

`DEFAULT_CAL_BOUNDS` is an interim fallback for log segments that pre-date the `# cal bounds`
provenance header. It **must not be imported as calibration truth** by callers. Once #295 lands
and `parse_v1` derives cal bounds from the log header, `DEFAULT_CAL_BOUNDS` becomes an internal
fallback only; callers that need the effective bounds for a dataset read them from `LogData` (a
field to be added by #295), not from the module constant.

### 3. Violations are tracked defects, not acceptable convention

C2 and C3 are tracked defects with their own issues. Any PR that touches `make_sample_log.py`,
`experiment_capture.py`, or telemetry fixtures must not add new `value=<pct>` / `unit="pct"`
emissions.

- C2 fix: #294 -- emit `value=NULL`, `unit=""` per schema-v1.
- C3 fix: #295 -- derive cal bounds from the `# cal bounds` log header; retire `DEFAULT_CAL_BOUNDS`
  as a caller import.

### 4. Optional import-lint

A cheap enforcement gate: a `pytest` check (in the not-yet-existing
`tools/analytics/test_parse_v1.py`) that asserts no sibling module in `tools/` opens a `*.csv`
file outside `parse_v1`. This follows after #294 and #295 are clean and falls inside #291s scope
(telemetry round-trip golden tests). Recommended but not required to ratify this ADR.

## Consequences

- Schema knowledge lives in one place; a column rename or schema bump happens in one file.
- `forecast.py` stops importing `DEFAULT_CAL_BOUNDS` once #295 lands; cal bounds come from the
  data, not a module constant.
- C2 and C3 are named; contributors know not to add more `value=pct` emissions or constant-imports.
- New streams (`record_type=env`, ADR-0018 transport variants) extend `parse_v1` as a new function
  or versioned successor, not a parallel parser in another module.

## Revisit triggers

- `schema_version=2` ships -- this ADR extends to cover `parse_v2` or versioned dispatch inside
  `parse_v1`; the boundary rule stands.
- The DuckDB/parquet derived tier (ADR-0006 §3) stands up -- parquet reads are derived, not raw-CSV
  reads; the raw-to-derived boundary remains `parse_v1` to DuckDB.
- The import-lint check (#291 scope) passes CI -- note enforcement active here.

-- Trellis