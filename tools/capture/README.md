# `tools/capture` — Experiment-mode capture (Epic 1)

Sprout's **Monitor mode** is the always-on baseline logger (`tools/logger`). This is
**Experiment mode**: short, operator-driven, bounded captures against an arbitrary
subject (a common cup of water, air, another plant), at a settable cadence — the
characterization work behind C1 / A2 (see [PRD-0001](../../docs/prd/0001-experiment-capture-mode.md),
[ADR-0011](../../docs/adr/0011-experiment-capture-control-plane.md),
[ADR-0012](../../docs/adr/0012-experiment-data-architecture.md)).

## What's here (issue #65, Phase 1 — device-independent core)

`experiment_capture.py` — the bounded capture process:

- **Isolated storage.** Writes to `experiments/<experiment_id>/` (a sibling of `logs/`,
  gitignored), **never `logs/`**. The monitor dashboard's `gather_inputs()` globs `logs/`
  only and cannot auto-discover experiments — the **never-stitch** guarantee.
- **`schema_version=2`.** The canonical monitor columns plus additive, *filterable*
  shared-core columns — `mode` (`experiment`), `subject`, `experiment_id`, `sample_rate_s`,
  per-probe `label`. `record_type` stays `plants.soil`; `mode` discriminates. v1 readers
  map by name and ignore the extras.
- **Fail-safe auto-stop.** The process stops itself at the set duration even if its parent
  dies — the duration timer lives in the capture loop.
- **`manifest.json`** per experiment, carrying the per-cadence **transport-error counts**
  (dropped / crc-fail / idle-noise) — the error-rate-vs-cadence signal the slow tiers exist
  to measure.

## The serial seam (Firmware #63 + #64)

The capture source is a pluggable `Reader`. `SyntheticReader` is device-free and lets the
storage / isolation / schema path be built and tested today. **`SerialReader` now implements
the full ADR-0011 host contract** — exclusive open (the OS mutex) → wait-for-boot-banner →
advisory `logs/.serial-owner.json` lock → `!cad,<ms>*HH` with `# ack`/`# nak` → close + unlock.
Its serial open is injectable, so the whole protocol is unit-tested against a fake device
(`test_serial_reader.py`). The **real device integration** still needs Firmware **#63** (the
on-device `set_cadence` command) and **#64** (reset-on-open + the monitor-side lock), and the
freed port after the baseline teardown — that's the one remaining step to close #65.

## Run it

```bash
# device-free smoke run (writes an isolated experiment + manifest)
python tools/capture/experiment_capture.py --source synthetic \
    --subject common-cup --rate-s 0.5 --duration-s 20 \
    --label s1=control --label s2=treatment

# tests (no pytest needed) — includes the never-stitch gate-proof
python tools/capture/test_experiment_capture.py
```

**The 48 h baseline is untouchable while it runs** — real (serial) captures need exclusive
ownership of the device port, so they wait until the baseline window is over and the probes
are pulled (the serial-port mutual-exclusion invariant, ADR-0011). Requires `pyserial`.
