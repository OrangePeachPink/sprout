# ADR-0000 — Record architecture (and process) decisions

**Status:** Accepted
**Date:** 2026-06-24
**Owner:** Maintainer
**Lane:** meta

---

## Context

Sprout began as a small single-board prototype, and its first architecture decision was captured in a
single combined record. The project has since grown into a multi-part system — firmware, a host-side
logging pipeline, an analytics dashboard with forecasting, and a design system — worked on across
several focused lanes (architecture/firmware, data/analytics, design, and issue-tracking/release),
coordinated by a maintainer.

A project at this size benefits from a consistent, browsable trail of *why* it is built the way it is,
so a new contributor can come up to speed by reading decisions in order rather than reverse-engineering
them from the code. This ADR establishes that trail.

## Decision

Use a **numbered Architecture Decision Record (ADR) series** under `docs/adr/`.

1. **Location & filename:** `docs/adr/NNNN-kebab-title.md`, zero-padded to four digits.
2. **Numbering:**
   - `0000` (this file) is the **meta-record**: the decision to use ADRs, the conventions, and the
     register. (This follows the common `adr-tools` / Nygard convention.)
   - `0001` and up are **real decisions, numbered chronologically across all kinds** — architecture,
     process, and tooling decisions share one sequence; they are not sub-numbered per category.
   - The **first real decision is `0001`**.
3. **One decision per file.** Keep each ADR focused; don't bundle unrelated decisions.
4. **Status lifecycle & editing policy:** `Proposed → Accepted` (or `Rejected` / `Deprecated`).
   **Pre-1.0 (current): ADRs are living documents — edit them in place** to keep them clean, current,
   and consistent; the **git history is the decision trail** (every change is a dated commit + diff +
   message — that *is* the "what changed and why"). Do **not** create in-document amendment chains or
   `Superseded by` stubs for ordinary pre-1.0 iteration. When you materially change an *accepted*
   decision: (a) write a clear commit message capturing the why, and (b) tell the lanes building
   against it. **At v1.0.0 (the loud launch — NOT the 2026-07-09 soft flip) the policy flips to append-only** — from
then a
   substantive decision is *superseded by a new ADR* (linked back), so external readers get the
   lineage in the document, not only in git; a one-time "clean read" precedes the flip. Genuinely
   meaningful archived snapshots (e.g. the v0 record) are kept — this stops *new* churn, it does not
   erase real history.
5. **Each ADR names an Owner and a Lane.** A cross-lane ADR may assign a **per-row owner** so each lane
   confirms only its own rows.
6. **Format:** Context → Decision → Consequences → Revisit triggers.

### Treatment of the original prototype record

The project's first combined architecture/scope record (`docs/ADR.md`) was written for a smaller
prototype scope. Rather than port it forward verbatim, it is **archived and superseded**:

- It is preserved unchanged as the **v0 record** at `docs/adr/archive/sprout-v0-architecture.md` — a
  faithful snapshot of the prototype's design and reasoning, retained as history.
- A fresh, **right-sized `0001-architecture-and-control-loop.md`** is written for the current scope,
  *informed by* the v0 record but reflecting where the system actually is now.
- The archived v0 is marked **Superseded by ADR-0001**.

This keeps `0001` an accurate, current decision a new contributor can trust, while preserving the
prototype's history faithfully. (Execution belongs to the architecture/firmware lane.)

## The register

| # | Title | Status | Owner / Lane |
|---|---|---|---|
| [0000](0000-record-architecture-decisions.md) | Record architecture (and process) decisions | Accepted | Maintainer / meta |
| [0001](0001-architecture-and-control-loop.md) | Architecture & control loop | **Accepted** — informed by, and supersedes, the archived v0 record | Firmware lane / architecture |
| [0002](0002-process-tiers.md) | Process tiers (the project's engineering process choices) | **Accepted** | Maintainer / cross-lane |
| [0003](0003-work-pipeline.md) | Work pipeline: ideas, specs, backlog, issues & releases | **Accepted** | Workflow lane |
| [0004](0004-design-system.md) | Design system & token-consumption contract | **Accepted** | Design lane |
| [0005](0005-application-surface-and-frontend.md) | Application surface & frontend | **Accepted** | Data lane |
| [0006](0006-data-architecture.md) | Data architecture (telemetry schema, calibration, quality, analysis tier) | **Accepted** | Data lane |
| [0007](0007-brand-guidelines.md) | Brand guidelines & voice | **Accepted** | Design lane |
| [0008](0008-design-system-v3-personality-layer.md) | Design system v3: the personality layer | **Accepted** | Design lane |
| [0009](0009-versioning-and-release-policy.md) | Versioning & release policy (+ Decision 7: release-feed curation = the SBOM remediation, per ADR-0026 amended D4) | **Accepted** — amended 2026-07-19 (#1258) | Workflow lane |
| [0010](0010-design-library-front-door.md) | The Design Library is the single front door for design assets | **Accepted** | Design lane |
| [0011](0011-experiment-capture-control-plane.md) | Experiment capture control plane (browser→host) | **Proposed** — direction agreed (Firmware #57); detail at sub-issue cut | Data + Firmware lanes |
| [0012](0012-experiment-data-architecture.md) | Experiment data architecture (extends ADR-0006) | **Proposed** — schema agreed (Firmware #57); detail at sub-issue cut | Data lane |
| [0013](0013-environmental-data-architecture.md) | Environmental data architecture (extends ADR-0006) | **Proposed** — Data-led; on-device section co-authored with Firmware at sub-issue cut | Data lane |
| [0014](0014-operator-control-plane.md) | Operator control plane (Monitor + Experiment under one plane; extends ADR-0011) | **Accepted** — maintainer-ratified 2026-07-03; shipped via the Operator-Experience epic #125; ratification note: the fleet poller (#582) rides the Monitor lifecycle (one Start governs both collection paths) | Data lane |
| [0015](0015-no-personal-information-policy.md) | No personal information policy (no PII / hardware identifiers collected, generated, committed, or published) | **Accepted** — drafted by Trellis, maintainer-ratified 2026-06-26 | Maintainer + Workflow / meta |
| [0016](0016-actuation-wiring-seam.md) | Actuation wiring seam: the supervisor is the single sample & actuation authority (extends ADR-0001) | **Accepted** — drafted by Trellis; Firmware + Data rows confirmed (#94 / #232), maintainer-ratified 2026-06-27 | Firmware / architecture (Data co-owns telemetry-derivation + health rows) |
| [0017](0017-experiment-notebook-and-notes-durability.md) | Experiment notebook data model + notes durability (extends ADR-0012 §5, ADR-0006) | **Accepted** — Data-led; ratified by Workflow on maintainer delegation 2026-06-27 | Data lane (Lab Notebook; model matches Design's notebook spec) |
| [0018](0018-dual-mode-transport-and-durability.md) | Dual-mode transport & durability: source-adapter seam + device-owned time, one schema across transports (untethered; extends ADR-0006) | **Accepted** — maintainer-ratified 2026-07-01, alongside schema v2 §11 (#492) (#268) | Data lane / architecture (cross-lane: Firmware) |
| [0019](0019-capability-and-sensor-matrix.md) | Capability & sensor matrix: per-board capability descriptor (contributor extension point) + per-channel sensor_type model (untethered) | **Accepted** — Firmware-confirmed + maintainer-ratified 2026-06-28 (#269) | Firmware lane / architecture (cross-lane: Design) |
| [0020](0020-network-identity-and-credentials.md) | Network identity & secrets: NVS-local credentials, synthetic hostname (no hardware IDs), no inbound exposure (untethered; extends ADR-0015) | **Accepted** — Firmware-confirmed + maintainer-ratified 2026-06-28 (#270) | Firmware lane / architecture |
| [0021](0021-parse-v1-telemetry-contract-boundary.md) | parse_v1 is the single telemetry contract boundary (extends ADR-0006) | **Accepted** — maintainer-ratified 2026-07-03; battle-tested before ratification (#294/#295 fixed; context/pressure/untethered all extended the one boundary); the schema-v2 revisit trigger already fired + is satisfied | Trellis (author) + Data lane |
| [0022](0022-calibration-confidence-layer.md) | Calibration-confidence layer: local-reading vs pot-need gating — confidence stages + microzone-disagreement veto + contact-quality + plant-pathway profiles; the promotion gate for plant-deployed -> autonomous-enabled (extends ADR-0016) | **Accepted** — model ratified by maintainer 2026-06-30 (#400/#402); 5-prerequisite arm-gate incl. #18 + #410 (#411); thresholds tracked as non-blocking inputs (#412/#414/#416) | Trellis (author) + Firmware (enforcement) |
| [0023](0023-contextual-env-columns.md) | Two context families: interior ambient (proximity-class fill: plant_local → room → none; weather fenced out of interior temp/RH, pressure excepted) vs exterior conditions (weather+solar drive light/season analytics, never projected); die-temp excluded from context | **Accepted** — v2 reworked from the maintainer's design review + ratified same day (2026-07-02); Data confirms post-ratification | Data lane (v2 drafted by Workflow from maintainer direction) |
| [0024](0024-multiplatform-pinning.md) | Toolchain pinning: one *exact* pin for the whole active matrix on pioarduino (revised 2026-07-01, maintainer direction — supersedes the original per-target-isolation posture); exact-pin discipline survives, isolation is now a staging state for unproven platforms only (extends ADR-0019 / #283) | **Accepted** — revised + ratified by maintainer direction 2026-07-01 (#283) | Trellis (author) + DX/Firmware (execution) |
| [0025](0025-config-provenance.md) | Config provenance & no-auto-adjust: every reading-shaping setting exposed in the header + tagged on the data; inline volatile knobs (gain/itime) + a `config_id` snapshot for the stable surface; settings dialed-in-and-held, never silently auto-adjusted (extends ADR-0006) | **Accepted** — maintainer-ratified (2026-07-04 spare-word directive; register reconciled 2026-07-06 at the maintainer's cut-readiness ruling); the config_id mechanism SHIPPED in the v4 bundle (#754 firmware-computed emit + #759 header-authoritative parse, both merged + test-verified) | Trellis (author) + Data (config_id/header) |
| [0026](0026-firmware-delivery-and-update-security.md) | Firmware delivery & update security: OTA is **pull-only** (preserves ADR-0020 no-inbound) + **signed-images-only** (preserves ADR-0016 actuation authority) + A/B rollback + NVS/identity preserved; web-flasher rides the existing provenance block + a bench-verified-only manifest gate; captive-AP stays config-only (extends ADR-0020 / ADR-0016) | **Accepted** — maintainer-ratified 2026-07-10 (ADR batch) with the maker-first scaling (software-verified signatures, NO eFuse burns, USB always reflashable); **Phase-1 staged amendment ratified 2026-07-19 (#877): signed + pull both land v0.8.0, anti-rollback DECLINED for this device class (release-feed curation instead), Phase-0 password cleared first**  | Trellis (author) + Firmware (OTA/secure-boot) + DX (flasher page) |
| [0027](0027-identity-model.md) | Identity model: minted stable ids for device / channel / probe / plant / site + a naming-independent mapping table (extends ADR-0018/0019/0020; reframes #602 coalescing as the legacy bridge) | **Accepted** — maintainer-concluded 2026-07-04 (1b = B: the 6-char base32 minted id at `schema_version=3`, ratification riders appended); substrate shipped end-to-end (#622/#624/#631/#632/#633), three nonces live on silicon; calibration portability stays tracked on #621 | Trellis (owner) + Firmware (author) + Data (registry substrate) |
| [0028](0028-optional-peripherals-doctrine.md) | Optional-peripherals doctrine: the minimum Sprout (1 MCU + 1 soil sensor) is *complete*; every peripheral optional; **absence is a first-class path** (sensorless-primary, or one of the three-pattern absence vocabulary — **present-or-silent / calm-empty / first-class-absent**, internal-only names, gates certify by them), never degraded/nag; the served dashboard is the authoritative status surface, on-device displays a redundant glance (extends ADR-0019) | **Accepted** — maintainer-ratified 2026-07-04 (drafted by Trellis, #20/#19); the #1039 grill (docket 2, 2026-07-18) named the three absence patterns + retired "honest-empty" → "calm-empty" (Trellis V1 amendment); gates the W2 display build (#20) | Trellis (author) + Firmware (descriptor) + Design (absence affordance) |
| [0029](0029-plant-pot-site-profile-registry.md) | Plant / pot / site profile registry: a slowly-changing **dimension** (pot geometry, hydrology, care history) keyed by the stable `plant_id`, joined to telemetry facts in the analysis tier — *not* identity, *not* telemetry; storage mirrors the device registry (committed schema + gitignored local instance, ADR-0015); every field absent-safe (ADR-0028); the covariate set the predictor conditions on (extends ADR-0027 / ADR-0006) | **Accepted** — maintainer-ratified 2026-07-10 (ADR batch); dimensions extend-as-needed by design; Data builds loader (v0.8.0), the v0.7.2 registry editor builds on it  | Trellis (schema) + Data (loader) |
| [0030](0030-version-identity-and-display-contract.md) | Version identity, build provenance & display contract: name every versioned thing (product · fw semver · **build-instance id** = git-hash+timestamp · wire `schema_version` · `config_id` · server) with one owner-constant + one authoritative display each; the OTA receipt = a changed build-instance id on any push (same-source included); fw semver bumps **before** a coordinated reflash; masthead = product + live-fleet fw (retired excluded), Diagnostics = full table (elaborates ADR-0009) | **Accepted** — maintainer-ratified 2026-07-10 (ADR batch); packaging = standalone (concern-separation); added AC: build-instance granularity on EVERY surface incl. the served dashboard (Diagnostics shows server git hash)  | Trellis (scheme) + Firmware (build-id/OTA) + Design (display) + Workflow (bump ritual) |
| [0031](0031-read-path-rollup-tiers.md) | Read-path rollup tiers: materialized aggregates over immutable raw — raw is Tier 0 (immutable, kept forever), Tier 1/2/3 are **derived, disposable, rebuilt-from-raw** rollups picked by window; the envelope contract (`mean/min/max/spread/n` + quality rollup per `(device_id, channel)`, over `raw_value`, per-board only); **events never downsampled** (band transitions, waterings, faults, sessions survive at exact timestamps in every tier); rollups labeled + rendered as envelopes, never smoothed (realizes/extends ADR-0006 §3) | **Accepted** — maintainer-ratified 2026-07-10 (ADR batch); fork 1 = DuckDB/parquet, forks 2-4 at the Trellis leans; Data builds materializer (v0.8.0), sequenced after the v0.7.2 perf interim  | Trellis (contract) + Data (materializer) |
| [0032](0032-github-pages-design-library-serving.md) | GitHub Pages serving for the Design Library: source = "Deploy from a branch" `main` / `/docs` (no build; `.nojekyll` static); **serving boundary** — Pages serves the HTML assets only, markdown stays on github.com (never link `github.io/…/*.md`); live md links = absolute `%20`-encoded Pages URLs, historical docs (`adr/`, `_archive/`, dated handoffs) keep point-in-time links; root = relative-URL redirect landing; unpkg React at render time **accepted deliberately** (vendoring = standing follow-up); custom domain not-now; indexing accepted (extends ADR-0010) | **Accepted** — records the maintainer's executed #876 ruling (Pages enabled 2026-07-09); drafted by Workflow 2026-07-10 to close #876 AC-3; **§4 (root landing) superseded + §5 (unpkg) scoped to the library by [ADR-0034](0034-pages-root-is-the-public-front-door.md)** | DX (serving/links) + DesignQA (render surface) |
| [0033](0033-two-surface-architecture-home-and-workbench.md) | Home + Classic Sprout — a **converging** two-surface architecture: the app opens onto **Home** (a glanceable per-plant card grid in Sprout's voice — identity block + mood-colour-frame + band + first-person line + water story; scales 1→24+), and **Classic Sprout** (the old dashboard) is a **transitional migration ledger** reachable via a small link, retired piece-by-piece → **one designed product** as the end state; the plant **speaks for itself** on every surface (mood 1:1 from the calibrated band, character↔instrument boundary structural, `raw + band = the reading`, absence first-class); card **state = the seven in-soil mood bands** (Soaked→Faint, ADR-0035) with instrument conditions off-ladder; **identity by the two-register identity block, never colour** (#1109); **migration ledger = a board view** (grill-ruled); **shell-first, one shell** (#1018); realizes #875 (extends ADR-0008 + ADR-0032) | **Accepted** — amended + ratified by the #1039 grill (2026-07-18, Round 1 + band-model/absence back-half); Trellis folded the rulings; V1 maintainer-merged; #1044 closes on it; written to the #1099 canon | Trellis (structure) + Design-QA (surfaces, #875) + Data (seams) |
| [0034](0034-pages-root-is-the-public-front-door.md) | The Pages **root** is Sprout's **public** front door (the Sprout-voiced marketing hub, FD-1 #1071) — **supersedes ADR-0032 §4** (root was a redirect stub → root is a real designed page; the Design Library keeps its unchanged `docs/design/` URL as a linked destination); **reconciles ADR-0010** (library = the *design* front door, root = the *public* front door — "single front door" scoped to design assets); the hub is **zero-external-runtime** (inline SVG + CSS keyframes, no CDN scripts; Google Fonts + system fallback the sole external) — **ADR-0032 §5's unpkg exception does NOT extend to the hub** | **Accepted** — records the maintainer's locked #1069 front-door IA decision; Trellis-drafted, Design-QA co-authors §3; V1 maintainer-merged (gates FD-1's root deploy) | Trellis (IA/serving) + Design-QA (render surface) |
| [0035](0035-band-model-and-instrument-exceptions.md) | The band model & instrument-exceptions taxonomy: the ladder is **seven in-soil mood bands** (Soaked→Faint), mood words = band names, **one vocabulary** across dashboard / charter / mark; **all diagnostics off-ladder** → a first-class, **open** exceptions taxonomy (placement / physics / kinematics / comms — "four is a floor, not the design"); cross-board = **per-board-class anchor mapping** (#898), raw stays board-true, **no fleet-wide 0–100 normalization** (cross-plant uses a labelled envelope-index); bands re-partitioned onto the **in-soil envelope** per class (ratified, measured: classic [1052 … 2500], C5 [982 … 2213]); **humane-calibration doctrine** — wilt-onset is the only capture target, no plant pushed to a sensor max; the Faint-ceiling is survivor-bias-caveated (extends ADR-0022 + ADR-0006) | **Accepted** — Trellis-drafted from the #1039 grill (2026-07-18); **maintainer-ratified 2026-07-19 (#1174)** against the fresh dual-envelope dry-down (both boards measured): ceiling 2500, Data's two-board bracket sets as posted (#995), #898 annotate-don't-overwrite, 36/36 in the #1164 cal-suite (#1211); Firmware's #952 chain implements the ratified fixtures | Trellis (model) + Data (brackets/index) + Firmware (#952 chain/anchors) + Design-QA (charter vocabulary) |
| [0036](0036-sensor-identity-layers.md) | Sensor-identity layers — ends the `s#` overload across four layers: **probe/sticker** (`s1..s12`, registry, travels with the probe) · **channel** (`(device_id, port)`, firmware, `ch0..ch3` per board) · **wire `sensor_id`** (= the **channel**, never the probe — extends ADR-0027 §5 into the wire contract; firmware can't know the probe) · **display** (registry-resolved to sticker/plant); a probe move is a registry event, not a reflash; a wire rename is a `schema_version` boundary (never-stitch) | **Accepted** — Trellis-drafted 2026-07-19 (#1042, the deferred #896 wire half); the layer model is ruled, and the **naming scheme is RULED (maintainer, 2026-07-19): Fork A — `chN`**. The wire carries `ch0..ch3` at **`schema_version=5`**; v4 rows keep the old token and are never rewritten; V1 | Trellis (ADR) + Firmware (`SENSOR_NAMES`/parser) + Data (registry channels) + Design-QA (display) |
| [0037](0037-production-epoch-and-data-admissibility.md) | The production epoch, data admissibility, and the archive boundary — **epoch `2026-07-06T00:00:06Z`** (2026-07-05 19:00:06 CDT, the first continuous production row, stored as real `start_ts` values, never a config constant) · four admissibility rules (unwired → delete · pre-epoch → lab record only · nothing pre-epoch reaches dashboards/models/charts · **wired-but-unused stays admissible** — the line is provenance, not utility) · the sweep order **resolve citations → archive → delete** behind a dry-run gate · pre-epoch capture headers are a live trap (`@origplant` asserts a false mapping) so the archive is safe by disuse, never by construction | **Accepted** — maintainer-ratified in session 2026-07-20 (epoch value + all four rules); recorded so it is never re-derived from memory; execution is #1330; V1 | Trellis (ADR) + Data (stamp + sweep) |
| [0038](0038-module-boundaries-and-the-import-rule.md) | Module boundaries and the import rule — **five layers, one direction** (leaves · domain · analysis · application · delivery) with **a module may import only from a strictly lower layer**; plus the **companion rule**: identity resolution has exactly **one implementation, in any language, on any surface** — a template, SQL, or JS that maps `(device, channel) → plant` is a second implementation and a defect (the #1315 Home incident lived in a Jinja template, where no import graph reaches); identity becomes a layer-1 module with one public `resolve_plant(device, channel, at_time)`; staging is **leaves → lint → priority extractions → package-flip go/no-go at the 0.8.2 cut** — the flip is deliberately **last**, since packaging while two identity paths exist packages the confusion | **Proposed** — Trellis-drafted 2026-07-20 (#1336, the 0.8.0 plan slice); the layer table and both rules need ratification, everything downstream is scheduling; V1 | Trellis (ADR) + DX (import lint) + Data (extractions) |
| — | *(archived)* [Sprout v0 combined architecture record](archive/sprout-v0-architecture.md) | Superseded by ADR-0001 | history |

*New ADRs append a row here when proposed. Any lane may author an ADR for an ADR-sized decision in its
own area — see [ADR-0003 §10](0003-work-pipeline.md) "When a decision merits an ADR."*

## Consequences

- Contributors can read the project's decisions in order, with rationale, in one place.
- Decision history is preserved faithfully: the prototype record is archived, not overwritten.
- Each lane owns its own ADR rows; no lane silently rewrites another's decision.

## Revisit triggers

- The series grows large enough to want an automated index / tooling → adopt `adr-tools`.
- Any ADR would contain a secret, credential, or private personal datum → it doesn't; keep it that way
  (standing repo-hygiene practice).
