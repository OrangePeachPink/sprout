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
- **`record_type`** — the namespaced row discriminator: `plants.soil` (a capacitive soil reading),
  `plants.env` (onboard ambient — SHT45 temp/RH, AS7263 NIR), `plants.pump` (actuation event, reserved).
  The shared time axis + `record_type` make cross-stream joins trivial.
- **`parse_v1` contract** — the single telemetry-parsing boundary (ADR-0021): the dashboard/analytics read
  logs **only** through `parse_v1`, never by ad-hoc CSV parsing, so one parser owns schema truth.
- **Raw-only contract** — firmware writes empty `value`/`unit` (`,,`) for `plants.soil` (DEC-#38): soil is
  uncalibrated, so any engineering value would be false precision. It is **soil-specific** — a factory-
  calibrated env sensor (SHT45) *does* carry real `value`/`unit`.
- **Tidy / long row** — one row per *(sensor, channel)* reading (soil `s1…s4`; NIR `nir_610…nir_860`), not
  a packed multi-value row — so every channel is a uniform, joinable series.
- **Band** — one of the 7 calibrated firmware moisture classes (`air-dry → DRY → needs water → OK →
  well watered → overwatered → submerged`); the calibrated truth shown alongside raw ADC.
- **`cadence_src`** (`nvs` | `temp` | `default`) — banner field (#322): whether the live sample cadence is
  the persisted default, a **session-only** `!cad,<ms>,temp` override (reverts on reset — can't leak), or
  the compiled fallback.
- **`sensor_position`** — where a probe/sensor physically sits (e.g. `origplant`, `breadboard_near_esp32`)
  — placement provenance; a probe swap invalidates per-channel calibration.
- **derived/model vs authoritative** — source **trust classes**: computed/modelled data (solar geometry,
  Open-Meteo weather) is `derived/model`, **never** presented as authoritative measurement.
- **Source registry** — a per-source provenance entry (origin, jurisdiction, cadence, **trust class**,
  schema version, discovery date) so every dataset declares where it came from and how far to trust it.
- **Night band / skylight window** — solar-geometry constructs (PRD-0002): a *night band* is a sun-down
  span shaded on the trajectory; the *skylight window* is the operator-calibrated time the rig actually
  sees direct sky.

## Bench & sensing (Sage)

- *(Sage: add envelope, per-channel wet/dry bounds, microsite, sensor "personality," the capture-id slug
  conventions, etc.)*

## Firmware

- *(Firmware: add the FSM terms, the supervisor, irrig_tick, forced-dose, the arm-gate, the serial
  commands, etc.)*

## Design & brand (Design)

- *(Design: add the brand/voice/token terms, the "character beside the instrument, not on top of it" rule,
  etc.)*

## Onboarding & developer experience (DX)

- **Co-equal routes** — the two first-class ways to do firmware dev: **VS Code + PlatformIO** (local) and
  **GitHub Codespaces** (browser). Neither is "the" way; the **Arduino IDE is dropped project-wide** (#261).
- **Contributors Welcome** — the living list of where outside help is especially wanted and how to start
  ([`docs/CONTRIBUTORS_WELCOME.md`](CONTRIBUTORS_WELCOME.md)); at launch its items graduate into
  `help wanted` issues (#266).
- **Developer front door** — the contributor-onboarding copy surface
  ([`docs/contributing/developer-front-door.copy.md`](contributing/developer-front-door.copy.md)) — the "it
  just works" entry into the project; DX owns the words, Design owns the render (#136).
- **Three-command firmware loop** — `just build` / `just test-native` / `just flash`. Build and test are
  **hardware-free** (so is CI); only **flash** needs the ESP32 on USB. The `just` recipes wrap PlatformIO and
  add `-d firmware` so the path is always right (#261).
- **`just preview`** — serve a design `.dc.html` page over `http://` so its components load (the `file://`
  protocol blocks the `fetch()` they use) (#190).

## User-facing 👤 (DX / Design)

- *(DX / Design: warm, clear definitions a non-coder owner reads — what the bands mean, "what Sprout is
  telling you," and so on.)*

---

*Seeded by Workflow with the process / board / gate vocabulary. Every lane owns its section — add terms as
you ship. Refs #364.*
