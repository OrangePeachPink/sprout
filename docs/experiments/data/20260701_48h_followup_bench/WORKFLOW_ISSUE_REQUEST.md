# Issue Request - Land 2026-07-01 P01-P11 48-Hour Follow-Up Evidence

Filed issue:

```text
#533
https://github.com/OrangePeachPink/plants/issues/533
```

Suggested title:

```text
Sage: land 2026-07-01 P01-P11 48-hour follow-up bench evidence packet
```

Suggested routing:

```text
for:workflow, for:sage, type:docs, area:sensing, area:analytics
```

## Purpose

Sage recovered the 2026-07-01 P01-P11 48-hour follow-up bench session into a
local durable packet. This issue asks Workflow to route the evidence landing
work and create/track the reviewable PR that turns the local rescue packet into
repo-tracked evidence for Data, Sage, Trellis, and future calibration work.

This should support #379, #170, #191, and #380. The evidence is bench/lab data
only; it does not change firmware, host logger behavior, dashboard behavior, or
schema contracts.

## Proposed PR Scope

Include:

- `docs/experiments/20260701_*.json` notebook sidecars for the eight captured
  experiment windows.
- `docs/experiments/data/20260701_48h_followup_bench/README.md`
- `docs/experiments/data/20260701_48h_followup_bench/NEXT_SAGE_START_HERE.md`
- `docs/experiments/data/20260701_48h_followup_bench/RECOVERY_INDEX.md`
- `docs/experiments/data/20260701_48h_followup_bench/RECOVERY_FILE_LIST.tsv`
- `docs/experiments/data/20260701_48h_followup_bench/manifest.json`
- `docs/experiments/data/20260701_48h_followup_bench/WORKFLOW_ISSUE_REQUEST.md`
- `docs/experiments/data/20260701_48h_followup_bench/.gitignore`
- `docs/experiments/data/20260701_48h_followup_bench/experiment_captures/**`
- `docs/experiments/data/20260701_48h_followup_bench/monitor_logs/**`

Exclude:

- `docs/experiments/data/20260701_48h_followup_bench/LOCAL_THREAD_TRANSCRIPT_*.md`
  (local-only verbose chat transcript; ignored by the packet `.gitignore`)
- source `experiments/` runtime folders
- source `logs/` monitor folders
- `_scratch/`
- Codex local storage / raw thread JSON unless Veronica explicitly asks for it

## Acceptance Criteria

- The PR uses `Refs #<this issue>` and does not auto-close #379, #170, #191, or
  #380.
- All eight experiment sidecars parse as JSON.
- All eight copied experiment captures contain both CSV and manifest files.
- The five copied monitor logs are present and listed in `manifest.json`.
- `RECOVERY_FILE_LIST.tsv` lists tracked candidate files with hashes/sizes and
  does not include the local-only transcript.
- PII pass is clean: no home coordinates, personal identifiers, private account
  metadata, or raw local Codex storage paths in committed evidence.
- The P07 stale-name caveat is preserved: filename says `no_water`, but method
  truth says about 1/2 cup was added into central leaf/branch cores.
- The P11 s3/GPIO36 caveat is preserved: impossible low readings and later zero
  are fault evidence, not valid plant-moisture evidence.
- The packet makes the 2026-07-01 bench day recoverable by a fresh Sage thread
  using `NEXT_SAGE_START_HERE.md` and `RECOVERY_INDEX.md`.

## Evidence Already Prepared Locally

Local packet:

```text
docs/experiments/data/20260701_48h_followup_bench/
```

Recovery thread:

```text
019f1513-4205-7e70-9769-91fad3980be3
codex://threads/019f1513-4205-7e70-9769-91fad3980be3
```

Counts from the local recovery sweep:

```text
sidecars: 8
experiment CSVs: 8
experiment manifests: 8
monitor logs: 5
tracked-candidate file list rows: 28
local-only transcript: ignored by packet .gitignore
```

## Request To Workflow

Please route and board this as a Sage evidence landing item, then tell Sage
whether the PR should ride this new issue only or also explicitly cite #379, #170, #191, and #380
in the PR body. Once routed, Sage can branch from current `main`, stage only
the include-scope files above, post the evidence map, and move the card to
Needs Verification.

— Sage
