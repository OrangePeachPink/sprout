# Sprout — project status

**The single "where are we" page.** What runs today, what's intentionally not built yet, and where to
look next. For *why* decisions were made, see the ADRs; for the live working view, see the board.

**Last updated:** 2026-07-26 · **Firmware:** 0.8.1 · **Stage:** relay-capable; autonomous watering gated

## In one line

Eight windowsill plants log soil moisture honestly (raw ADC counts plus a calibrated seven-band
classifier) across two boards on WiFi; a Python logger and a served dashboard render it.
Operator-commanded bounded pump pulses (`!water` / `!stop`) exist via the actuation supervisor;
the relay path is **bench-unverified** (#191) and autonomous watering is gated (#94).

## What runs today

- **Firmware 0.8.1** (`firmware/`, PlatformIO) — sweeps **four soil sensors per board** on ADC1,
  classifies each into seven moisture bands, and emits schema-v5 telemetry.
  Two boards are live (classic ESP32 + official ESP32-C5), so the fleet is **8 instrumented
  plants**; the count that governs the code is four, the count that governs the sill is eight.
  Operator-commanded bounded pulses via `!water <ch>` / `!stop` — wired through the actuation
  supervisor (ADR-0016); relay path **bench-unverified** (#191). Autonomous watering not yet wired.
  Commands: set sweep cadence at runtime (ADR-0011).
- **Host logger** (`tools/logger/plants_logger.py`) — stamps each row with UTC time and writes a
  rotating, self-describing CSV under `logs/` per the shared telemetry schema.
- **Dashboard** (`tools/analytics/serve.py`) — serves the live soil view; binds to localhost.
- **One-command run** — `just start` brings Sprout up and opens the dashboard; `just check` runs the
  compiler-free local gate (`just check-firmware` adds the native C tests). The dev environment is
  locked via `uv` (`uv sync`).
- **Experiment capture** — a guided capture mode with live in-mode feedback (epic complete).
- **Lab Notebook** — past experiments are cataloged at `/lab`; the notebook epic (#153) is complete.
- **Cut releases with signed artifacts** — v0.8.1 is the first release to ship them: factory bins
  built in CI, signed, checksummed (`SHA256SUMS`), and sealed at publish. See
  [`process/RELEASE_CUT.md`](process/RELEASE_CUT.md).
- **Web flasher** (`/flash`) — browser-flash a board over Web Serial, no IDE and no toolchain.
  Only **marker-verified** boards are ever offered (classic today; ADR-0026 D6), and the stable
  channel serves the *release's* signed bytes. An unpublished channel is not offered at all.
- **CI** — `lint + hygiene`, `firmware (native tests + compile)`, and the `gate` job run on every
  PR. Experimental boards (C5, S3) build non-blocking.

## What is intentionally NOT built yet

- **Autonomous pump actuation / the watering loop (#94).** `irrig_tick` is not yet wired. Manual
  operator commands (`!water`/`!stop`) exist but the relay path is bench-unverified (#191).
  Autonomous dosing stays gated in safety order — *make watering correct before it's possible*:
  per-probe calibration (#170, **done**), fail-safe actuator-off (#93, **done**), then the safety
  bench (#191) — **that one is the remaining gate**, and it needs real hardware.
- **Environmental / weather correlation (PRD-0002)** — parked behind the capture work.

## Where to look

| You want… | Go to |
| --- | --- |
| The live working view (issues by status) | [Project board #2](https://github.com/users/OrangePeachPink/projects/2) |
| Ideas / proposals inbox | [Discussions](https://github.com/OrangePeachPink/sprout/discussions) |
| Decisions of record | [`docs/adr/`](adr/) |
| How to contribute (the verification gate) | [`.github/CONTRIBUTING.md`](../.github/CONTRIBUTING.md) |
| Wiring & power plan | [`WIRING.md`](WIRING.md) *(historical baseline)* |
| Bring-up history | [`BRINGUP.md`](BRINGUP.md) *(historical)* |
| Telemetry schema | [`TELEMETRY_SCHEMA.md`](TELEMETRY_SCHEMA.md) |
| Sensor calibration anchors | [`SENSOR_CALIBRATION.md`](SENSOR_CALIBRATION.md) |

## Firmware standing (detail)

Schema v5. Each board sweeps four sensors; the co-located cross-probe agreement run that shaped this
page is **finished** — since wave-1 (2026-07-04) the probes are distributed one per plant across two
boards, eight plants in all. On the C5, probe stickers `s5`–`s8` sit on ports that emit `s3/s4/s1/s2`:
channel is not probe (ADR-0027), and the registry is what reconciles them.

`value` / `unit` are emitted NULL on purpose — raw ADC counts plus the calibrated band are
authoritative; any 0–100 figure is a labelled relative index, never volumetric water content.

---

*This page supersedes the per-ADR "Today" columns and the two `HANDOFF_2026-06-23*` notes as the
current-state pointer. Keep it short; when it drifts, fix it here first.*
