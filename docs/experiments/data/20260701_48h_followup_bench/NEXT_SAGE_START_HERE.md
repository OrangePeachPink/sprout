# New Sage Start Here - 2026-07-01 Bench Recovery

You are resuming Sage / Bench work after the active thread began looping. Do
not start with GitHub or PR mechanics. First verify that this local rescue
packet is complete and readable.

## Thread Breadcrumbs

- Broken earlier Sage thread:
  `codex://threads/019f0ea6-a148-7a91-bba6-0d07f99b7750`
- Recovery thread that created this packet:
  `codex://threads/019f1513-4205-7e70-9769-91fad3980be3`
- Raw JSON transcript path was not identified from the runtime. If needed, ask
  Codex/UI or search local Codex thread/export storage for either thread ID.

## First Files To Read

1. `RECOVERY_INDEX.md` - human-readable source of truth for today's bench notes.
2. `manifest.json` - machine-readable list of copied evidence files.
3. `RECOVERY_FILE_LIST.tsv` - hashes and byte sizes for copied files.
4. `docs/experiments/20260701_*.json` - notebook sidecars.

## What Was Being Preserved

This packet preserves the 2026-07-01 48-hour follow-up bench pass for plants
P01-P11 after the 2026-06-29 full greenhouse characterization. It includes:

- Eight Experiment Capture runs covering P01 through P11.
- Five monitor logs with baseline, post-run, sunlight-artifact, and P11 fault
  context.
- Notebook sidecars, including a recovered P11 sidecar.
- Plant-by-plant method notes reconstructed from the live bench transcript.

## Critical Caveats

- P11 s3/GPIO36 produced impossible low values, then reached 0 in post-run
  monitor logging. Treat that channel as fault evidence, not valid plant
  moisture data.
- P07's experiment name says `no_water`, but Veronica did add about 1/2 cup
  into the central leaf/branch cores. The method note overrides the stale name.
- P04/P05 baseline was monitor logging, not Experiment Capture metadata.
- Hand watering was distributed across soil surface; it is not a one-hose pump
  spot-feed proxy.

## Suggested Next Steps

1. Validate the JSON sidecars and copied manifests parse.
2. Confirm the copied CSV files exist and match `RECOVERY_FILE_LIST.tsv`.
3. If time allows, make a flat plant-run index for Data, but do not alter raw
   evidence.
4. Only after local durability is verified, ask Workflow whether the evidence
   rides under #379 / #170 / #191 or needs a fresh issue.
5. Branch, commit, and open a PR with `Refs #N`; stop at Needs Verification.

-- Sage
