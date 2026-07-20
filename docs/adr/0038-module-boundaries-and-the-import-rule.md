# ADR-0038 — Module boundaries and the import rule

**Status:** Accepted — the layer table (§1), the import rule (§2), and the companion one-implementation rule (§3)
were maintainer-ratified 2026-07-20 (#1336, PR #1362). Everything downstream is scheduling. V1 (doctrine).
**Date:** 2026-07-20
**Owner:** Trellis (the boundaries + the rules). Build: **Data** (host modules), **DX** (the lint).
**Lane:** architecture
**Relates:** #1336 (this — the 0.8.0 plan slice) · #1338 (seam conformance — parallel, gates nothing)
· #1315 (the incident this opens with) · #1331 / #1335 (identity — the first extraction) ·
[ADR-0021](0021-parse-v1-telemetry-contract-boundary.md) (the parse boundary) ·
[ADR-0027](0027-identity-model.md) / [ADR-0036](0036-sensor-identity-layers.md) (identity model)

---

## Context

### The incident that dated this ADR

On 2026-07-20 the v5 channel-key migration ran clean — all three axes verified, backup taken — and the live Home
immediately lost all eight probed plants. The mechanism: the Home joins cards on the payload's raw `sensor_id`
in `home_template.html`, boards still emitted v4 `s1..s4`, the registry had been re-keyed to `ch0..ch3`, and the
join found nothing. The host fold covered the parse and tier paths. **The Home's registry join was a second
identity path, and it did not fold.**

The migration was rolled back and the approval stands. What matters here is *where* that second path lived: in a
**template**. No import graph reaches it. No module boundary contains it. A layering rule written against Python
imports would have declared the tree clean while the defect sat in HTML.

### The measured condition

- **149 of 184 files** under `tools/analytics` manipulate `sys.path`.
- `pyproject.toml` sets `package = false`; nothing is importable by name.
- `dashboard.py` is **94 KB**; `serve.py` **65 KB**, with 200+ line GET and POST routers.
- Several Lab modules import the ~2,000-line `dashboard` module **to obtain two CSS constants.**

That last item is the diagnosis rather than another symptom. Importing two thousand lines to get a string means
the module has no seams — you cannot take a piece without taking the whole. Combined with path surgery, which
makes every reach invisible to ordinary tooling, **any module can import any other and nothing makes a bad reach
awkward.**

This is not tidiness. It is the mechanism behind the defect class this release is fixing: nothing made it
structurally awkward for the dashboard to keep reading the legacy static registry while the temporal registry
existed beside it. **Two truths coexisted because no boundary ever forced a choice.**

The counter-pressure is real and this ADR is bounded by it: refactoring is risk with no user-visible benefit,
taken mid-migration, by a small team. A plan that licenses unbounded restructuring is worse than no plan.

## Decision

### 1. Five layers, one direction

| Layer | Contains | May import |
|---|---|---|
| **0 · leaves** | design tokens/CSS, band definitions, the exception vocabulary, parse types, units | *nothing internal* |
| **1 · domain** | telemetry parsing (`parse_v1`), **identity/registry**, calibration | 0 |
| **2 · analysis** | segments, tiers, rollups, predictors | 0–1 |
| **3 · application** | card payload, dashboard context assembly | 0–2 |
| **4 · delivery** | HTTP routes, CLI entry points, templates, presentation | 0–3 |

### 2. The import rule

> **A module may import only from a strictly lower layer. Never upward, never sideways within layer 4.**

Mechanically checkable, which is the point — a boundary that depends on remembering is not a boundary. **DX
lands an import-graph lint in 0.8.1**, advisory first, enforcing once the tree satisfies it.

### 3. The companion rule — one implementation, any language, any surface

The import rule alone would have passed the tree that produced the #1315 incident, because the offending path
was a Jinja join in a template. So it needs a companion that is not about imports at all:

> **Identity resolution has exactly one implementation — in any language, on any surface.** A template, a SQL
> query, a JavaScript fragment, or a notebook that maps `(device, channel) → plant` is a second implementation
> and is a defect, however small.

Layer 4 includes templates deliberately, and templates may **consume** a resolved identity but never **compute**
one. The lint cannot enforce this on its own; the seam-conformance harness (#1338) is where it becomes testable,
and until then it is enforced at review.

### 4. Identity is a layer-1 module with exactly one public function

`resolve_plant(device_id, channel, at_time) -> plant_id | None`

Every consumer — dashboard, fleet polling, Home, tier queries, **templates via the payload** — resolves through
it, and the alternative paths are **deleted, not deprecated.** This is the extraction that makes the two-truths
failure structurally impossible rather than merely fixed, and it is the same work as #1331's interval join
and #1335's mapping UI. Doing it three times separately is how it stays broken.

### 5. Staging — the package flip is last, not first

1. **0.8.1 — leaves out.** Layer 0 into zero-import modules. Kills the import-a-module-for-a-constant pathology;
   changes nobody's workflow; near-zero risk.
2. **0.8.1 — the lint lands**, advisory then enforcing.
3. **0.8.2 — priority extractions**, ranked by risk of becoming unfixable:
   **identity resolution** (§4) · **`build_context`** (the card-payload path, mid-migration, where features keep
   landing) · **`serve.py` route table with one central policy** — which also carries the **Host/Origin check on
   state-changing routes**, since the inconsistent `_is_local()` means this module currently hides a *security*
   inconsistency, not merely a maintainability one.
4. **0.8.2 cut — package flip go/no-go**, an explicit decision rather than a drift. By then the leaves are out
   and identity is single-sourced, so `package = true` and removing path surgery is mechanical.

**The ordering deliberately inverts the obvious one.** Migrating to a package while two identity paths still
exist would package the confusion and call it progress.

### 6. Two guardrails on the work itself

- **No refactor without a named defect it prevents.** Stages 1 and 3 each have one on the record. An extraction
  that cannot name the defect it forecloses waits.
- **Characterization tests are each extraction's precondition — not the seam epic.** Pin the module's output
  (golden card payloads), then cut until it still matches. Seam-conformance tests (#1338) catch a *different*
  failure — two components disagreeing across a contract — and gating extraction on that epic would serialize
  0.8.2 behind one piece of infrastructure. **Different failure, different instrument.**

## Consequences

- Bad reaches become mechanically visible, then mechanically blocked.
- Identity has one answer, so a second cannot quietly appear — including in a template.
- 0.8.2 has a spec, so "is this extraction in scope?" has an answer that is not taste.
- Layer 0 is cheap and immediate; the expensive flip sits behind a real decision point.
- **Cost, stated honestly:** every extraction is churn against a mid-migration tree. §6 exists to bound it, and
  the lint's advisory phase exists so the rule does not block work before the tree can satisfy it.

## Rejected alternatives

- **Package migration first** (the external review's implied order). Rejected: packages the confusion.
- **Many small single-purpose files.** Rejected explicitly — the failure is dependency *shape*, not file size,
  and shattering modules worsens the graph while feeling productive.
- **The import rule alone, without §3.** Rejected by #1315: it would have declared the tree clean while a second
  identity path ran in a template.
- **Leave it; revisit at 1.0.** Rejected: the runway exists now, ahead of 0.9.x's watering-cycle theme. The
  defect this prevents is doing the work later under feature pressure.
- **Gate extractions on the seam epic.** Rejected in §6 — wrong instrument, and it serializes the release.

## Open (routed)

- **Maintainer** — ratify the layer table (§1), the import rule (§2), and the companion rule (§3).
- **`for:dx`** — the import-graph lint (0.8.1), advisory → enforcing.
- **`for:data`** — leaf extraction (0.8.1); the identity module (0.8.2, with #1331 / #1335).
- **`for:trellis`** — the 0.8.2-cut go/no-go on the package flip; §3's enforcement folded into #1338.

## Revisit triggers

- A second runtime joining the host layer (a service, a worker) — the layer table assumes one process.
- Any surface computing identity outside `resolve_plant` (§3) — that is the rule failing, not an exception.

— Trellis 🏛️
