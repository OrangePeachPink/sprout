# 2026-07-01 P01-P11 48-Hour Follow-Up Bench Rescue

Sage recovery bundle for the 48-hour follow-up bench pass after the 2026-06-29
greenhouse characterization session.

This directory exists for one immediate reason: if the active thread dies, a new
Sage/Data/Workflow thread can recover today's bench evidence without mining the
chat transcript.

## Fast Recovery

Start here:

- `RECOVERY_INDEX.md` - human-readable handoff, plant-by-plant notes, thread/log
  breadcrumbs, and known caveats.
- `experiment_captures/` - copied raw Experiment Capture folders for P01-P11.
- `monitor_logs/` - copied monitor logs that contain baseline, post-run, or fault
  evidence not represented by Experiment Capture metadata.
- `docs/experiments/20260701_*.json` - notebook sidecars, including the recovered
  P11 sidecar created after the run.

## What This Bundle Is

- Local durable rescue packet, not yet reviewed or merged.
- Raw telemetry preservation plus Sage notes.
- A staging point for the eventual issue and PR.

## What This Bundle Is Not

- Not Data's final aggregation table.
- Not a cleaned dashboard dataset.
- Not a claim that all probes were valid. In particular, P11 s3/GPIO36 is fault
  evidence, not clean plant moisture evidence.

## PII Posture

The bundle intentionally contains relative repo paths, local timestamps, device
telemetry, probe labels, raw ADC counts, environmental sidecar readings, and
bench notes. It should contain no home coordinates, personal identifiers, or
private account metadata. Verify again before PR.

Refs: #379, #170, #191. Supports Data follow-up on #380 and any s3/GPIO36 fault
triage issue Workflow opens.

-- Sage
