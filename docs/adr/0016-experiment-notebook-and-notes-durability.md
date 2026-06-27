# ADR-0016 — Experiment notebook data model and notes durability

**Status:** Proposed — *awaiting ratification (Veronica + Design); the notes home and the
gitignore re-anchor are the human-decision points*
**Date:** 2026-06-26
**Owner:** Data lane
**Lane:** data/analytics (Lab Notebook — the read/review side of experiments)
**Extends:** [ADR-0012](0012-experiment-data-architecture.md) §5 (findings reports),
[ADR-0006](0006-data-architecture.md) (calibration handshake)
**Relates:** [PRD-0004](../prd/0004-experiment-lab-notebook.md) R3 / R5 / R6 / R7

---

## Context

[PRD-0004](../prd/0004-experiment-lab-notebook.md) introduces the **Lab Notebook** — the
read/review surface over experiments. Its precious deliverable is the **living log** (R3): a
per-experiment, editable record of **Hypothesis / Method / Findings / Conclusion** — *"we thought
X, tried Y1/Y2/Y3, concluded Z."* The numbers come from the capture; the conclusions are the
operator's, and they are the part worth keeping.

R3 says the notes are *"saved beside the experiment; versioned."* R5 says they need a *"durable,
backed-up home."* These pull in opposite directions, because of one hard fact established in
[ADR-0012](0012-experiment-data-architecture.md) §1: the raw captures live in
**`experiments/<experiment_id>/`, which is gitignored / local-only**, isolated by construction so
they can never be stitched into the monitor baseline. Notes saved *literally* beside the capture
(inside `experiments/<id>/`) would inherit that gitignore and be **stranded** — exactly the loss
R5 forbids.

This ADR resolves that tension and fixes the notebook's notes data model. It does **not** restate
ADR-0012; the never-stitch isolation, the manifest, and the storage ladder carry over unchanged.

## Decision

### 1. The notes ARE the findings — they live in the tracked `docs/experiments/` pair

[ADR-0012](0012-experiment-data-architecture.md) §5 already defines a **durable, git-tracked**
home for experiment outcomes: a paired **human `.md` + machine `.json`** in **`docs/experiments/`**,
*distinct from the raw captures*. The living-log notes are precisely that findings record. So the
notebook does **not** invent a new store — it **writes the notes as the findings pair**:

- `docs/experiments/<experiment_id>.md` — the human-readable write-up.
- `docs/experiments/<experiment_id>.json` — the machine sidecar (the notes object + the structured
  anchors that feed the A2 reconciliation).

This is the durable home R5 demands: **git-tracked → committed → pushed → backed up** on the
remote. It is the same path the common-cup characterization procedure already points operators to.

### 2. "Beside the experiment" is a *link*, not physical co-location (R3 vs R5, resolved)

The notes are bound to their capture by **`experiment_id`**, not by sitting in the same folder.
The raw capture stays isolated in gitignored `experiments/<id>/` (ADR-0012 §1, never-stitch); the
notes live tracked in `docs/experiments/`. "Beside the experiment" is satisfied **logically** — the
`/lab` detail view renders the capture's trajectory and its notes together, keyed by id — while the
two storage paths stay correctly separate (immutable evidence vs. human interpretation, R5).

### 3. Notes data model (matches Design's notebook spec)

The machine sidecar carries a `notes` object whose shape follows
[`docs/design/foundations/Sprout Lab Notebook.dc.html`](../design/foundations/Sprout%20Lab%20Notebook.dc.html):

```json
{
  "experiment_id": "2026-06-26_common-cup_pin-spread",
  "notes": {
    "hypothesis": "",
    "method": "",
    "findings": "",
    "conclusion": "",
    "saved_at": "2026-06-26T17:40:00Z",
    "version": 3
  },
  "anchors": { "...": "per-state mean raw / spread / proposed band anchors (ADR-0012 §5)" }
}
```

- Field names are snake_case in the file; the UI maps `saved_at`/`version` to the spec's
  `savedAt`/`version` display (`saved {{savedAt}} · v{{version}}`).
- The four prose fields are free text. `findings` may be **seeded** from the analysis tier (the
  workbench's per-probe stats), but the operator owns every word — the notebook never overwrites a
  field the operator edited.

### 4. Versioning is git history; `version` is the in-file counter (R3)

"Versioned" is satisfied **for free** because the home is a tracked file: **every commit of
`docs/experiments/<id>.json` is a durable version**, viewable as a diff and recoverable. The in-file
`version` integer increments on each in-app save and `saved_at` stamps it, so the UI can show
"v3 · saved …" between commits. We do **not** build a bespoke version store — git is the version
store, the `version`/`saved_at` fields are the live-session breadcrumb.

### 5. Who writes, and the honest durability boundary

The `/lab` notes editor (in `serve.py`, the localhost operator tool) **writes the tracked pair to
the working tree**. Durability is realized on **commit + push** — a normal git action, not a hidden
one. This keeps faith with the project's no-hidden-server / no-surprise-state posture: the app never
auto-commits or pushes behind the operator's back.

The honest boundary: notes written but **not yet committed** are local-only. That is acceptable and
truthful for a single-operator local tool, and it is surfaced in the UI (an "uncommitted" hint is a
Design follow-up). Two **optional future enhancements** can shrink the gap without violating the
posture — both deferred, neither required by this ADR:

- a "Save & commit notes" action in the notes editor; and/or
- the launcher committing pending notes on quit (ties to the #151 one-action-quit lifecycle).

### 6. Not in `reports/` — that tier is derived and rebuildable (R6)

The DuckDB analysis store (`reports/plants.duckdb`, ADR-0006 ladder / #155) is **derived,
gitignored, and rebuildable from raw**. It is emphatically **not** the notes home: notes are
source-of-truth *human interpretation* and must survive a `reports/` wipe. The store may **index**
notes for cross-experiment query, but it reads them from `docs/experiments/`, never owns them.

### 7. Tracking `docs/experiments/` cleanly — the gitignore re-anchor (Workflow handshake)

For §1 to work without friction, `docs/experiments/` must be a **tracked** path. Today the
unanchored `experiments/` pattern in `.gitignore` (intended only for the **repo-root** raw captures)
**over-matches** `docs/experiments/`, so its findings README is force-tracked and new findings/notes
need `git add -f`. **Recommendation:** re-anchor the ignore to **`/experiments/`** so it matches only
the root captures, leaving `docs/experiments/` trackable normally. This is a **shared-state change**
owned by the pipeline — proposed here, to be executed in coordination with **Workflow**, not grabbed
by the Data lane unilaterally.

## Consequences

- The living log — the precious part — is **durable by construction**: a git-tracked file, backed up
  on the remote, version-historied by commits. R5 is met without a new datastore.
- The R3/R5 tension dissolves: notes are *linked* to the capture by id while staying in a separate,
  durable lifecycle from the isolated raw evidence (R5's evidence-vs-interpretation split holds).
- The notebook reuses ADR-0012 §5's findings pair instead of forking a parallel store — one durable
  home for "what this experiment concluded," whether typed in `/lab` or written by hand.
- A clear, honest durability boundary (committed = backed up) keeps the no-hidden-action posture and
  names the two optional enhancements that would tighten it later.
- The gitignore re-anchor is surfaced as a coordinated Workflow task, not a silent Data edit.

## Revisit triggers

- Notes outgrow four prose fields (structured sub-findings, attachments, images) → revisit the
  sidecar schema and whether a richer store is warranted.
- Multi-operator editing or concurrent `/lab` sessions appear → the "git is the version store"
  assumption needs locking / merge handling.
- The "uncommitted notes are local-only" gap proves painful in practice → promote one of §5's
  optional enhancements (save-and-commit, or launcher-commits-on-quit) from deferred to required.
- Studies (#159) need a roll-up conclusion across many experiments → decide whether the study record
  is another `docs/experiments/` sidecar or its own tracked index (carry this ADR's tracked-path
  principle forward).
