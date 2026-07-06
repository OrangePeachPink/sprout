# 🌱 Sprout — Vocabulary

**This file is the source of truth for what Sprout's words mean.** Use these exact terms in UI copy, code
identifiers (where reasonable), issue / PR / ADR prose, commit messages, and any docs or copy you generate.
The goal is the same alignment we have on brand and voice — but for *concepts*: one word, one meaning, across
every lane. If two lanes use the same word for different things, or different words for the same thing, fix it
*here* first.

> **How a term reads:** **Term** — a one-line definition, then its *enforcement rule*. Watch for:
> **NEVER** *x* (a banned synonym), **replaces** *x* (a retired term this supersedes), **not** *x* (a
> near-miss it's often confused with). Tags: **(👤 user-facing)** an owner reads it — keep it warm and plain ·
> **(code-only)** an identifier / internal concept, never UI copy · **(role)** a who/what that acts.
>
> **Ownership:** each lane owns the *accuracy* of its domain section; **DX owns the standard + structure**
> (this charter, the format, the Retired list) — #364. Add a term to your section, alphabetical, when you coin
> it. Seeded sections marked *“<lane> ratifies”* are DX-drafted from existing ADRs/docs and await the owning
> lane's confirmation.

---

## Workflow & actions (Workflow)

- **Certification** (*Ready to Merge certification*) — Workflow's GO comment: which lanes approved the design,
  what Workflow independently verified, and merge-order notes. The audit anchor that moves a card to Ready to
  Merge. **not** a rubber-stamp of the lane's own report — Workflow validates independently.
- **Evidence map** (*requirement-by-requirement map*) — the proof posted on an issue before Needs
  Verification: each acceptance criterion → how it's met → a concrete artifact (PR # + commit SHA, `path:line`,
  the passing test, CI status, any bench check). **NEVER** "done ✓" — that is not evidence.
- **Lifecycle** — the five board stages: **Backlog → In Progress → Needs Verification → Ready to Merge →
  Done** (· *Won't Do*). **replaces** the old "In Review" stage (retired).
- **Verification gate** — the two-stage review every change passes: the lane posts evidence and moves to
  **Needs Verification** (Workflow's inbox) → Workflow certifies → **Ready to Merge** → the maintainer merges.
  **NEVER** self-merge or self-close your own issue.
- **Needs Verification** — board status: *built + evidence posted, awaiting Workflow's review.* It is
  **Workflow's** inbox, **not** the maintainer's.
- **Ready to Merge** — board status: *Workflow-certified — the maintainer's merge queue.* The maintainer
  merges **only** from this column.
- **Won't Do** — terminal status for "decided against": close the issue **"not planned"** (one-line reason).
  **not** Done — Done means *shipped*.
- **Refs #N / Part of #N** — the non-closing issue link every PR uses. **NEVER `Closes #N`** — merged PRs do
  not auto-close issues here (the human gate does).
- **Partial / spin-out** — when a merged PR met an issue's *core* but a clean follow-on fell out, Workflow
  opens a **new linked issue** for the tail and closes the original, so a tail is never lost in the merge.
- **Gate labels** — `blocks:pumps` / `blocks:public-release` / `blocks:data-integrity`: milestone gates,
  independent of Priority.
- **Self-sync** — the protocol of checking your own slice of the board (PRs, `for:<lane>` issues, unblocks) at
  session start, before stop, and at every status brief — and **acting**, not waiting for a relay. **The
  maintainer is not a messenger; the issue is the message bus.**
- **Squash-trap** (*Attempt #2/#3 trap*) — after a base PR squash-merges, a stacked PR shows a false
  "conflict." Fix: `git rebase --onto origin/main <old-base>` — **NEVER** "Update branch" (it re-introduces the
  merged commit).
- **Work hierarchy** — **epic** (`epic` label) groups slices · **PRD** (`docs/prd/`) specs a larger feature ·
  **ADR** (`docs/adr/`) records a significant/hard-to-reverse decision. Ideas-not-yet-ready go to
  **Discussions**, never `BACKLOG.md` (retired).

## Roles & agents

- **Maintainer** — the one human who **merges, approves hardware actions, and sets product direction**
  (Veronica). The only actor who merges. **not** a relay between lanes.
- **Lane** — a coordinated line of work run by one agent: **Firmware · Data · Design · DX · Sage** (bench) ·
  **Trellis** (architecture) · **Ingest** (Design's commit-proxy) · **Workflow** (issues/board/process). All
  post from the one `OrangePeachPink` account, so each **signs** its work `— <Lane>`.
- **`for:<lane>` label** — a *first-approximate routing hint*, a best-guess owner so an item doesn't sit
  ownerless. A hint, **not** an assignment or commitment — Workflow still triages and gates.
- **Agent** — a generic AI lane-driver. **NEVER** a human. The maintainer is the human; agents are the lanes.

## Data & honesty (Data)

- **Honest-data law** *(non-negotiable)* — raw ADC counts + the calibrated **band** are truth; any 0–100
  figure is a **labelled relative index**, **NEVER** real volumetric moisture or a bare "percentage." Mood,
  status color, and watering derive from the **band**, never the index.
- **Band** — one of the **7** calibrated firmware moisture classes (`air-dry → DRY → needs water → OK →
  well watered → overwatered → submerged`); the calibrated truth shown beside raw ADC. **not** the index.
- **Band-label lag** *(👤 user-facing)* — on a **fast transient** (a bench dunk, install poke) the `level`
  **band** trails the raw ADC by **~1 cadence tick** — raw already dropped to 888 while the label still read
  `dry`; raw back to 2985 while still `submerged` (#660). This is **intended anti-flap hysteresis**, not a bug:
  the classifier holds the committed band across a `deadband`-wide gap (±deadband/2 on each boundary) plus a
  ms confirmation window, so a band **change must be confirmed**, not chased sample-to-sample — trading
  transient-responsiveness for stability in slow soil (band flapping would be noise, not signal). At the 30 s
  cadence the confirm window rounds to ~1 sample, so the lag is ~1 tick (`READ_INTERVAL_MS`, `lib/moisture_classifier`).
  **Raw ADC stays the authoritative fast signal** (ADR-0006: raw is truth; the band is a smoothed index) — read
  raw, not the band, when watching a live transient. (#678)
- **Raw-only contract** — firmware writes empty `value`/`unit` (`,,`) for `plants.soil` (DEC-#38): soil is
  uncalibrated, so an engineering value would be false precision. **Soil-specific** — a factory-calibrated env
  sensor (SHT45) *does* carry real `value`/`unit`.
- **`parse_v1` contract** — the single telemetry-parsing boundary (ADR-0021): analytics read logs **only**
  through `parse_v1`, **NEVER** by ad-hoc CSV parsing. One parser owns schema truth.
- **`record_type`** *(code-only)* — the row discriminator: `plants.soil` (capacitive soil), `plants.env`
  (onboard ambient — SHT45 temp/RH, AS7263 NIR), `plants.pump` (actuation event, reserved).
- **Tidy / long row** — one row per *(sensor, channel)* reading (soil `s1…s4`; NIR `nir_610…nir_860`), never a
  packed multi-value row — so every channel is a uniform, joinable series.
- **`cadence_src`** *(code-only)* (`nvs` | `temp` | `default`) — banner field (#322): whether the live cadence
  is the persisted default, a **session-only** `!cad,<ms>,temp` override (reverts on reset), or the fallback.
- **`sensor_position`** *(code-only)* — where a probe physically sits (`origplant`, `breadboard_near_esp32`):
  placement provenance. A probe swap **invalidates** per-channel calibration.
- **derived/model vs authoritative** — source **trust classes**: computed/modelled data (solar geometry,
  Open-Meteo weather) is `derived/model`, **NEVER** presented as authoritative measurement.
- **Source registry** — a per-source provenance entry (origin, jurisdiction, cadence, **trust class**, schema
  version, discovery date), so every dataset declares where it came from and how far to trust it.
- **Night band / skylight window** — solar-geometry constructs (PRD-0002): a *night band* is a sun-down
  span shaded on the trajectory; the *skylight window* is the operator-calibrated time the rig actually
  sees direct sky.
- **Bench-arc / arc table** — the per-plant `start → wettest → pull` summary of a bench day, **recomputed
  from raw samples** (`bench_arc.py`, #380) and rendered on the band ladder (`bench_arc_view.py`, #423).
  One read per plant across valid probes — not sensor-by-sensor.
- **Wettest: sustained vs instant** — in the bench-arc, `wettest` (**sustained**) is the wettest *cross-probe
  median* over the peak window — a whole-pot level; `wettest_instant` is the single deepest probe sample —
  one zone. The view shows sustained solid + instant as a faint ghost, so a preferential-flow pot (one probe
  dove, the rest stayed dry) never reads a false "well watered."
- **Probe-spread whisker** — `max − min` across included-probe medians at pull; surfaces microzone
  disagreement honestly (ADR-0022's *surface, don't average* posture), rather than hiding it in one number.
- **`probe_included_by_sage` / included probe** — the per-row valid-probe flag (Sage owns validity, Data
  consumes it); excluded probes (stuck / air-reference / no-contact) never enter a plant's read.
- **`derivation_status`** — Sage's honest-completeness typology for a bench plant's arc (`sample_window` ·
  `…_no_valid_peak` · `measure_only_no_water` · `single_probe` · `…_missing_pull` · `mixed_summary_and_samples`):
  it says what a plant's arc can and can't claim, so a gap stays a gap.
- **`context_source`** — the provenance tag naming which feed filled a row's `*_context_*` columns (SHT45 /
  ESP32 die / weather / Zigbee); **one source per row, never blended** (ADR-0023), with the trust class
  travelling alongside.
- **The `data` branch** *(code-only)* — the data-records store (csv/gz/db archives) at `.data-worktree`. Not a
  code workspace; intentionally far behind `main`; treat read-only.

## Firmware & control (Firmware) — *DX-drafted from ADR-0001/0016; Firmware ratifies*

- **Supervisor** — the single firmware authority that owns **both** sampling **and** actuation (ADR-0016).
  **NEVER** add a second sampler or relay driver — the arm-gate and forced doses route through it.
- **`irrig_tick`** *(code-only)* — the supervisor's per-cycle step that evaluates band + safety and decides
  whether to drive a pump. **not** a timer ISR — it's called from the main control loop.
- **Arm-gate** — the safety interlock that keeps actuation **disarmed** until the dry-safety chain passes;
  watering is impossible while disarmed. **NEVER** describe pumps as "ready" while the arm-gate is closed.
- **Forced dose** — an operator-commanded bounded pump pulse (`!water`, capped, e.g. ≤5000 ms), distinct from
  autonomous watering. **not** autonomous-enabled — it's manual and bounded.
- **Serial commands** — `!water` / `!stop` (manual bounded actuation) · `!cad,<ms>[,temp]` (cadence;
  `,temp` = session-only, reverts on reset). The host-facing control surface.
- **Boot banner** — the provenance line the firmware prints at boot (`fw`, `git`, build time, `cadence_ms`,
  health, safety state). The single source of post-flash *what's-actually-running* truth.
- **Watchdog (WDT)** — the task watchdog the main loop must feed within its window or the board resets — the
  hang-safety backstop.

## Bench & sensing (Sage) — *DX-drafted from the bench-procedures + #383; Sage ratifies*

- **Sensor personality** — the per-probe offset/gain difference that makes two probes read differently in the
  *same* soil. Per-channel calibration removes it; it is **not** microsite (see below).
- **Microsite** — the specific spot in the pot a probe reads (depth, contact, root density). A band can be
  *locally* true yet not whole-pot truth. **not** sensor personality — calibration does not remove microsite.
- **Wet / dry anchors** — the per-channel raw readings at saturated soil (**wet**) and bone-dry air (**dry**)
  that bound the relative index. **NEVER** share one anchor pair across channels (that's the v1 residual #170
  fixes).
- **Calibration envelope** — the practical wet-to-dry raw span observed for an installed probe set; the usable
  ADC headroom per-channel calibration works within.
- **Wet-reference** *(👤 when explained)* — a reading taken with probes in water, used as the saturated anchor
  and to isolate board/thermal artifacts from real drying.
- **Capability stage** — how far through *physical* validation a feature/config has progressed:
  `code-staged` (built, not wired) → `bench-wired` (wired, not exercised) → `dry-verified` (exercised, no
  liquid) → `wet-verified` (exercised in water) → `plant-deployed` (real pot, real data) →
  `autonomous-enabled` (watering without a human). *Current: pumps/relay are **code-staged**; sensors are
  **bench-wired**.* Use these exact words for bench state — **NEVER** vague "ready / not ready."

## Architecture & contracts (Trellis)

- **Single authority** — ADR-0016: exactly one owner for a safety-critical resource (the supervisor is the
  sole sampler **and** actuator). **NEVER** a second authority for the same resource.
- **Contract boundary** — the single authorized entry point for a data contract, so the rule lives in one
  place (e.g. `parse_v1` is the only telemetry reader; the supervisor the only actuator).
- **io seam** (*injected-callback seam*) — hardware behind injected callbacks (`irrig_io_t`, `env_i2c_t`) so
  the **full** module — protocol + math — is native-testable with a mock bus (ADR-0001).
- **Calibration confidence stage** — how trustworthy a band is *for action*: `provisional` (uncalibrated /
  shared bounds) → `calibrated` (per-channel bounds locked) → `corroborated` (cross-channel + tray agree).
  Autonomous watering gates at `corroborated` — `calibrated` is **necessary, not sufficient** (ADR-0022 / #170).
- **Promotion gate** — the prerequisite set to advance a capability stage. E.g. `plant-deployed →
  autonomous-enabled` requires **all five**: the dry-safety chain (#93/#191/#2/#215) **+** locked per-channel
  calibration (#170) **+** the confidence layer **+** schema-conformant pump telemetry (#18) **+** the
  under-watering fail-safe (#410) — **not** any one alone (ADR-0022).
- **Local truth vs pot truth** — a per-channel band is locally true (the probe reads its microsite correctly)
  but **not** whole-pot truth (geometry, contact, tray state dominate). Calibration removes sensor
  personality, not microsite (#383).
- **Format-gate scope** — the C/C++ format gate runs on **changed lines** (`git-clang-format` — formats only
  the diff, preserving untouched manual alignment), **replaces** the v1 **changed-files** whole-file reformat
  (#352, pending merge of PR #405). ADR-0002 #10.

## Design, brand & voice (Design) — *DX-drafted from BRAND.md / ADR-0007-0008; Design ratifies*

- **Sprout** — the character, **not** a readout. Speaks first-person, calm and honest. **NEVER** write Sprout
  as a dashboard talking *about* a plant — it *is* the plant's voice.
- **Character beside the instrument** — the layout law: the character (mood, voice) sits *beside* the data,
  **never on top of it**. Data stays legible; personality never obscures a number.
- **Design tokens** — the canonical CSS variables (`docs/design/`). **Consume** them; **NEVER** redefine or
  hard-code a token's value in a component.
- **Mood** — the character's emotional state mapped 1:1 from the band: `soaked · refreshed · thriving ·
  content · thirsty · parched · faint`. Derived from the **band**, never the index.
- **Data looks like data** — numbers are mono, right-aligned, tabular; **gaps are surfaced, not smoothed.**

## Hardware (physical) — *DX-drafted from README/wiring; Firmware + Sage ratify*

- **ESP32** — the microcontroller (classic dual-core, `esp32dev`). The board Sprout's firmware runs on. **not**
  an Arduino Uno (no Wi-Fi, different ADC).
- **Capacitive soil sensor** — the moisture probe (no exposed metal → no corrosion). Four on ADC1 (`s1…s4`).
  **not** resistive (those corrode; community-extension only).
- **Pump / relay** — the DC actuation path (**code-staged**, never powered on the bench yet). DC only —
  **NEVER** mains.
- **SHT45** — the factory-calibrated ambient temp/RH sensor (real `value`/`unit`; `plants.env`).
- **AS7263** — the 6-band NIR spectral sensor (`nir_610…nir_860`; `plants.env`, context, not plant-truth).
- **OLED** — the 1.3" SH1106 I²C status display.

## Onboarding & developer experience (DX)

- **Co-equal routes** — the **two** first-class firmware-dev environments: **VS Code + PlatformIO** (local)
  and **GitHub Codespaces** (browser). Neither is "the" way. **replaces** "Codespaces-first." The **Arduino
  IDE is dropped project-wide** (#261).
- **Three-command firmware loop** — `just build` / `just test-native` / `just flash`. Build + test are
  **hardware-free** (so is CI); only **flash** needs the ESP32 on USB.
- **Developer front door** — the contributor-onboarding copy surface
  ([`developer-front-door.copy.md`](contributing/developer-front-door.copy.md)). DX owns the words, Design the
  render (#136).
- **Contributors Welcome** — the living "where outside help is wanted + how to start" list
  ([`CONTRIBUTORS_WELCOME.md`](CONTRIBUTORS_WELCOME.md)) (#266).
- **`just preview`** — serve a design `.dc.html` over `http://` so its `fetch()`-based components load
  (`file://` blocks them) (#190).
- **Bench preflight** — DX's process-facing pre-bench standard
  ([`docs/process/BENCH_PREFLIGHT.md`](process/BENCH_PREFLIGHT.md)); Sage's
  [bench checklist](bench-procedures/bench-preflight-checklist.md) is its at-the-bench companion (#332).

## User-facing 👤 (DX / Design) — *DX-drafted; Design ratifies the wording*

- **Band names 👤** — the seven plain-language moisture labels an owner reads:
  **Saturated · Wet · Moist · Ideal · Drying · Dry · Parched** (Parched & Saturated are diagnostic edges).
  Use these in owner-facing copy; the firmware class names (`air-dry`…`submerged`) stay code-side.
- **Relative index 👤** — the 0–100 number: a **labelled position between this probe's wet and dry anchors**,
  for *trends on one probe over time*. **NEVER** call it moisture %, VWC, or compare it across probes.
- **Reading 👤** — what Sprout takes from the soil. Warm, plain. **not** "capture" or "sample" in owner copy
  (those are bench/code words).
- **On-ramp bands 👤** — the beginner Arduino on-ramp's own **three** plain-language moisture states (#435):
  **High and dry · All good · Just watered**. **Not** the same vocabulary as Full's seven **Band names**
  above — deliberately simpler, so don't conflate the two systems or reuse Full's seven names in on-ramp copy.
  Full's seven bands are what the three graduate into, not a synonym for them. See
  [`arduino-onramp-north-star.md`](contributing/arduino-onramp-north-star.md).
- **Calibrate by hand 👤** — the on-ramp's own act of measuring your probe's dry and wet readings and typing
  them into the sketch's tunable-constants block (#435). The **teaching**, not a gap to be automated away — Full
  calibrates automatically; the on-ramp's whole point is to *feel* what calibration means first.

---

## ⛔ Retired — do not use

These are superseded or banned. Replace on sight:

| Don't write | Use instead |
| --- | --- |
| `BACKLOG.md`, "the backlog file" | **Issues** (the board); Discussions for not-yet-ready ideas |
| "In Review" (board stage) | the five-stage **Lifecycle** (no In Review) |
| `Closes #N` | **`Refs #N`** / **`Part of #N`** |
| "Arduino IDE" (as a dev path) | **VS Code + PlatformIO** or **Codespaces** (#261) |
| "Codespaces-first" | **co-equal routes** (#261) |
| moisture **%**, "percentage", VWC (as truth) | the **band** + raw ADC; the 0–100 is a *labelled relative index* |
| "changed-files" clang-format / "the mirror hook" | **changed-lines** `git-clang-format` (#352) |
| "ready / not ready" (for bench state) | a **capability stage** (`code-staged` … `autonomous-enabled`) |
| pumps are "ready" (while disarmed) | pumps are **code-staged**, **arm-gate** closed |

---

*The standard, structure, and Retired list are DX-owned (#364); each lane owns its domain section's accuracy.
Seeded sections await their lane's ratification — see the routing on #364.*
