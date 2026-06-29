# Experiment findings

Durable **findings reports** from Experiment-mode captures live here — one per experiment, as a **pair**:

- `*.md` — the human-readable write-up (what was tested, conditions, outcome, what it means).
- `*.json` / `*.yaml` — the machine-readable sidecar (structured outcomes: per-state mean raw, spread,
  settling time, proposed band anchors) that feeds the A2 calibration reconciliation
  ([ADR-0006](../adr/0006-data-architecture.md) §5–6).

This folder holds **findings**, not raw data. The raw experiment **captures** live in the separate
experiment data folder defined in [ADR-0012](../adr/0012-experiment-data-architecture.md) — deliberately
apart, so findings stay reviewable and captures stay isolated from the monitoring baseline.

Convention finalized in [ADR-0012](../adr/0012-experiment-data-architecture.md) and
[PRD-0001](../prd/0001-experiment-capture-mode.md). Placeholder until Epic 1 lands.

## Bench procedures

- [Sage bench preflight checklist](../bench-procedures/bench-preflight-checklist.md) -
  restart/flash/serial/cadence checks before collecting evidence.
- [Multi-plant dry/wet baseline run sheet](../bench-procedures/multi-plant-dry-wet-run-sheet.md) -
  plant IDs, probe placement, dry baseline, watering, and post-water captures.
- [Environment evidence procedure](../bench-procedures/environment-evidence-procedure.md) -
  sunlight, heat, water temperature, exposure notes, photos, and Data handoff tags.
