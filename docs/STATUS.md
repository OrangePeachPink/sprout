# Sprout — project status

**The single "where are we" page.** What runs today, what's intentionally not built yet, and where to
look next. For *why* decisions were made, see the ADRs; for the live working view, see the board.

**Last updated:** 2026-06-27 · **Firmware:** 0.7.0 · **Stage:** relay-capable; autonomous watering gated

## In one line

Four co-located capacitive probes log soil moisture honestly (raw ADC counts plus a calibrated
seven-band classifier); a Python logger and a served dashboard render it. Operator-commanded bounded pump pulses (`!water` / `!stop`) exist via the actuation supervisor;
the relay path is **bench-unverified** (#191) and autonomous watering is gated (#94).

## What runs today

- **Firmware 0.7.0** (`firmware/`, PlatformIO, classic ESP32) — sweeps four soil sensors on ADC1,
  classifies each into seven moisture bands, and emits schema-v1 telemetry. Operator-commanded bounded pulses via `!water <ch>` / `!stop` — wired through the actuation
  supervisor (ADR-0016); relay path **bench-unverified** (#191). Autonomous watering not yet wired.
  Commands: set sweep cadence at runtime (ADR-0011).
- **Host logger** (`tools/logger/plants_logger.py`) — stamps each row with UTC time and writes a
  rotating, self-describing CSV under `logs/` per the shared telemetry schema.
- **Dashboard** (`tools/analytics/serve.py`) — serves the live soil view; binds to localhost.
- **One-command run** — `just start` brings Sprout up and opens the dashboard; `just check` runs the
  same lint + tests as CI. The dev environment is locked via `uv` (`uv sync`).
- **Experiment capture** — a guided capture mode with live in-mode feedback (epic complete).
- **Lab Notebook** — past experiments are cataloged at `/lab` (#154, shipped); the broader notebook
  epic (#153) is in progress.
- **CI** — the `lint + tests` gate runs on every PR and is green.

## What is intentionally NOT built yet

- **Autonomous pump actuation / the watering loop (#94).** `irrig_tick` is not yet wired. Manual
  operator commands (`!water`/`!stop`) exist but the relay path is bench-unverified (#191).
  Autonomous dosing stays gated in safety order — *make watering correct before it's possible*:
  per-probe calibration (#170), then the safety bench (#191) and fail-safe actuator-off (#93).
- **Per-channel calibration (#170).** All four channels currently share one provisional classifier
  config; per-probe boundaries are pending real potted-soil data.
- **Environmental / weather correlation (PRD-0002)** — parked behind the capture work.

## Where to look

| You want… | Go to |
| --- | --- |
| The live working view (issues by status) | [Project board #2](https://github.com/users/OrangePeachPink/projects/2) |
| Ideas / proposals inbox | [Discussions](https://github.com/OrangePeachPink/plants/discussions) |
| Decisions of record | [`docs/adr/`](adr/) |
| How to contribute (the verification gate) | [`.github/CONTRIBUTING.md`](../.github/CONTRIBUTING.md) |
| Wiring & power plan | [`WIRING.md`](WIRING.md) *(historical baseline)* |
| Bring-up history | [`BRINGUP.md`](BRINGUP.md) *(historical)* |
| Telemetry schema | [`TELEMETRY_SCHEMA.md`](TELEMETRY_SCHEMA.md) |
| Sensor calibration anchors | [`SENSOR_CALIBRATION.md`](SENSOR_CALIBRATION.md) |

## Firmware standing (detail)

Rung 4 / schema v1: four sensors (`s1`–`s4`) co-located in one recovering plant for a cross-probe
agreement run. `value` / `unit` are emitted NULL on purpose — raw ADC counts plus the calibrated band
are authoritative; any 0–100 figure is a labelled relative index, never volumetric water content.

---

*This page supersedes the per-ADR "Today" columns and the two `HANDOFF_2026-06-23*` notes as the
current-state pointer. Keep it short; when it drifts, fix it here first.*
