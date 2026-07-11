# Never-stitch consumer audit — 2026-07-10

**Author:** Trellis · **Issue:** #929 · **Scope:** v0.7.2 hardening
**Verdict:** PASS — every current history consumer honors never-stitch. **No code fix needed today.** The only
risk is in the not-yet-built v0.8.0 consumers (the rollup tier and the predictor), and it is already fenced by
ADR-0031 §2 and ADR-0025 — recorded below as a build requirement.

This is a point-in-time record (per the ADR-0021 parse-boundary + ADR-0006 three-layer contracts). Re-run it when
a new consumer starts reading multi-version history.

---

## What "never-stitch" means (three facets)

The wire has advanced `schema_version` 1 → 2 → 3 → 4, each a strict superset. "Never-stitch" is the rule that a
consumer must not **fabricate a value across a boundary**. Three concrete facets:

1. **Field-level.** A higher-version field (`config_id`, `rssi`, `uptime`, `heap`, the `SENSOR_FAULT` token) reads
   `None`/absent on a lower-version row — never back-filled or carried forward from a neighboring row.
2. **Stream isolation.** The `schema_version=2` experiment-capture stream is written to an isolated tree and is
   never auto-discovered into the baseline monitor stream (PRD-0001 R6/R7).
3. **`config_id` boundary.** A gain/itime change (a new `config_id`, ADR-0025) changes what a raw *means*; an
   aggregate must not blend rows across that boundary.

## Consumers audited

| Consumer | Reads multi-version history? | Guarantee | Evidence |
|---|---|---|---|
| `parse_v1` (the parse boundary) | yes — the origin of the guarantee | Field-level: v4-only fields resolve to `None` on a v3/v2/v1 row, never stitched | `parse_v1.py` "read None on a v3/v2/v1 row (never stitched): only a >=4 board emits them"; `test_parse_v4` asserts a pre-v4 row has `config_id is None` |
| `experiment_capture` (v2 writer) | writes, isolated | Stream isolation: writes `experiments/<id>/`, **never** `logs/` | `experiment_capture.py` §isolated writer + PRD-0001 R6/R7 gate test (`gather_inputs` can't auto-discover `experiments/`) |
| `parse_v1._default_logs` (auto-discovery) | picks the input set | Globs `logs/*.csv[.gz]` only — structurally cannot reach `experiments/` | `parse_v1.py:_default_logs` |
| `dashboard.py` aggregations (settled-window stats `_settled_readings`, `band_movement`, `_sessions`, trajectory) | yes — over a time window | Aggregate `raw_value` + band only (present in every version, v1+); **no v4-only field is consumed**; charts draw gaps, never interpolate across a hole | grep: zero `config_id`/`rssi`/`uptime`/`heap` reads in consumers; the only `interpolate` mentions are "never interpolate across a hole" |
| `legacy_log.py` (legacy → v1 converter) | writes v1 | Emits `schema_version=1` rows shaped by `CANONICAL_COLUMNS`; a converter, does not merge across versions | `legacy_log.py` header `schema_version=1 CONVERTED FROM LEGACY` |
| **rollup tier** (ADR-0031, v0.8.0) — *not built* | will, across all history | **Mandated:** per `(device_id, channel)` only, over `raw_value`, and **never blend across a `config_id` change** | ADR-0031 §2 (envelope contract) |
| **predictor** (#25, v0.8.0) — *not built* | will, across all history | Must condition **after** per-channel calibration (ADR-0019/#170) and honor the `config_id` boundary | ADR-0031 §6 consumer caveats + ADR-0025 |

## Findings

1. **No current consumer stitches.** Field-level honesty is enforced at the parse boundary; the experiment stream
   is structurally isolated; no consumer back-fills, forward-fills, or interpolates a telemetry value across rows.
2. **The v4-only fields are parsed but unconsumed.** `config_id` / `rssi` / `uptime` / `heap` are exposed by
   `parse_v1` but read by no aggregation yet — so there is no field-level stitch *surface* to get wrong today. The
   `SENSOR_FAULT` token rides `quality_flag` (an existing column, all versions), so its consumer
   (`dashboard.py` sensor-fault gate) is version-safe by construction.
3. **`config_id` is not yet checked by any aggregation** — acceptable today (no live `config_id` change has
   occurred, and raw is comparable within one board + one config), but it is the load-bearing requirement for the
   first consumer that aggregates across history.

## Routed (the forward requirement, not a v0.7.2 fix)

- **Data — rollup tier build (v0.8.0, #828/ADR-0031):** the materializer must key on `(device_id, channel)`,
  aggregate `raw_value` (not the legacy `value` %), and **not blend across a `config_id` change**. This audit is
  the standing reference; ping Trellis on the materializer PR for the never-blend conformance check.
- **Data — predictor (v0.8.0, #25):** condition after per-channel calibration, honor the `config_id` boundary.

**Nothing to fix in v0.7.2.** The guarantee holds; this audit records it per consumer and hands the forward
requirement to the ADR-0031/0025-fenced builds.

— Trellis 🪴
