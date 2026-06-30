# 🌱 Sprout — Living Glossary

Shared terminology so lanes — and eventually users — speak one language. Internal/developer terms need
**precision** so lanes don't use the same word for different things; user-facing terms should be **warm,
clear, and consistent**.

**Tracking issue:** #364 · **How to contribute:** add a term to the right section as you coin it while
shipping — one or two sentences, alphabetical within a section. Mark user-facing terms with 👤. Every lane
owns its own section.

---

## Process, gate & board (Workflow)

- **Certification** (*Ready to Merge certification*) — Workflow's GO comment on an item: which lanes
  approved the design, what Workflow verified, and the merge order (`before #X` / `after #Y` / `any order`
  / `may need rebase`). It's the audit-trail anchor that moves a card to Ready to Merge.
- **Evidence map** (*requirement-by-requirement map*) — the proof an implementer posts on an issue before
  Needs Verification: each acceptance criterion → how it's met → a concrete artifact (PR # + commit SHA,
  the file/function `path:line`, the passing test, CI status, any bench check). "Done ✓" is not evidence.
- **Gate (verification gate)** — the two-stage review every change passes: **Needs Verification**
  (Workflow's inbox) → Workflow certifies → **Ready to Merge** → maintainer merges. A PR is never merged
  until Workflow certifies it.
- **Gate labels** — `blocks:pumps` / `blocks:public-release` / `blocks:data-integrity`: milestone gates,
  independent of Priority.
- **Lane** — a coordinated line of work run by one agent: Firmware, Data, Design, DX, Sage (bench), Trellis
  (architecture), Ingest (Design's commit-proxy), Workflow (issues/board/process). Lanes post from one
  shared account, so each **signs** its work (`— <Lane>`).
- **`for:<lane>` label** — a *first-approximate routing hint* — a best-guess owner so an item doesn't sit
  without one. A hint, not an assignment.
- **Needs Verification** — board status: *built + evidence posted, awaiting Workflow's review.* It is
  **Workflow's review inbox**, not the maintainer's.
- **Partial / spin-out** — when a PR meets an issue's *core* requirement but a clean follow-on falls out,
  Workflow opens a **new linked issue** for the tail (with the context of what fell out) and closes the
  original — so a tail is never swept into the merge dustbin and lost.
- **Per-lane worktree** — each lane works in its **own** git worktree, never the shared repo root (which
  stays neutral on `main`). Sharing one checkout caused the 2026-06-28 multi-agent collision.
- **Ready to Merge** — board status: *Workflow-certified — the maintainer's merge queue.* The maintainer
  merges only from this column.
- **Squash-trap** (*Attempt #2/#3 trap*) — after a base PR squash-merges, the next stacked PR shows a
  false "conflict" because the squash gave the base a new SHA. The fix is `git rebase --onto origin/main
  <old-base>`, **not** "Update branch" (which re-introduces the merged commit).
- **Stacked PR** — a PR based on another open PR's branch, used to avoid inter-slice conflicts on shared
  files during a build. With squash-merge, each must be rebased after its base merges (see *squash-trap*).
- **Work hierarchy** — an **epic** (`epic` label) groups slices toward a goal; a **PRD** (`docs/prd/`)
  specs a larger feature; an **ADR** (`docs/adr/`) records a significant or hard-to-reverse decision.

## Capability stages (Sage / Bench)

How far a feature or sensor configuration has progressed through *physical* validation:

- **code-staged** — implemented, not yet wired to hardware.
- **bench-wired** — hardware connected, not yet exercised.
- **dry-verified** — exercised without liquid; basic electrical behavior confirmed.
- **wet-verified** — exercised with water/substrate; sensor response confirmed.
- **plant-deployed** — running in a real pot with a plant; real data flowing.
- **autonomous-enabled** — making watering decisions without manual intervention.

*Current: pumps/relay are code-staged; sensors are bench-wired.*

## Data & honesty (Data)

- **Honest-data law** — raw ADC counts + the calibrated **band** are truth; any 0–100 figure is a
  *labelled index*, never real volumetric moisture. Mood, status color, and watering derive from the band,
  never the index.
- **The `data` branch** — the **data-records store** (csv / gz / database archives), checked out at
  `.data-worktree`. It is *not* a code workspace; it is intentionally far behind `main`; treat it
  read-only.
- *(Data: add band names, the parse_v1 contract, schema versions, run_label / sensor_position, the source
  registry, etc.)*

## Bench & sensing (Sage)

- *(Sage: add envelope, per-channel wet/dry bounds, microsite, sensor "personality," the capture-id slug
  conventions, etc.)*

## Firmware

- *(Firmware: add the FSM terms, the supervisor, irrig_tick, forced-dose, the arm-gate, the serial
  commands, etc.)*

## Architecture & ADRs (Trellis)

- **Calibration confidence stage** — how trustworthy a per-channel band is for *action*:
  `provisional` (uncalibrated / shared bounds) → `calibrated` (per-channel bounds locked from controlled
  characterization) → `corroborated` (cross-channel + tray/contact agree). Autonomous watering gates on at
  least `calibrated`. (#170, the calibration-confidence ADR.)
- **Contract boundary** — the single authorized entry point for a data contract, so the rule lives in one
  place: e.g. `parse_v1` is the only telemetry reader (ADR-0021); the supervisor is the only sampler/actuator
  (ADR-0016, *single authority*).
- **Format-gate scope** — clang-format runs on **changed files** (whole-file reformat — the v1 residual that
  collapses manual alignment in any file you touch) vs **changed lines** (`git-clang-format` — formats only
  the diff, preserving untouched alignment). The repo ships changed-files; changed-lines is the tracked
  upgrade. (ADR-0002 #10, #120/#343.)
- **io seam** (*injected-callback seam*) — the framework-agnostic driver pattern: hardware lives behind
  injected callbacks (`irrig_io_t`, `env_i2c_t`) so the **full** module — protocol + math, not just the math
  — is native-testable with a mock bus. The reason firmware logic compiles and tests on the host (ADR-0001).
- **Local truth vs pot truth** — a per-channel band is *locally* true (the probe reads its microsite
  correctly) but is **not** whole-pot truth: pot geometry, contact quality, hydrophobic flow, and tray state
  dominate interpretation (#383). Per-channel calibration removes *sensor* personality; it does not remove
  *microsite* effects.
- **Promotion gate** — the prerequisite set required to advance a *capability stage*. E.g.
  `plant-deployed → autonomous-enabled` requires the dry-safety chain (`#93/#191/#2/#215`) **+** per-channel
  calibration (#170, locked) **+** the confidence layer — not any one alone.
- **Single authority** — ADR-0016: exactly one owner for a safety-critical resource — the supervisor is the
  sole sample **and** actuation authority. No second sampler, no second relay driver; the arm-gate and forced
  doses both route through it.

## Design & brand (Design)

- *(Design: add the brand/voice/token terms, the "character beside the instrument, not on top of it" rule,
  etc.)*

## User-facing 👤 (DX / Design)

- *(DX / Design: warm, clear definitions a non-coder owner reads — what the bands mean, "what Sprout is
  telling you," and so on.)*

---

*Seeded by Workflow with the process / board / gate vocabulary. Every lane owns its section — add terms as
you ship. Refs #364.*
