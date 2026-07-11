# ADR-0030 display-contract conformance audit — 2026-07-10

**Author:** Trellis · **Issue:** #831 · **Governs:** [ADR-0030](../adr/0030-version-identity-and-display-contract.md)
(version identity, build provenance & display contract) · **Scope:** v0.7.2
**Verdict:** SUBSTANTIALLY CONFORMS — the six-row inventory is surfaced with one owner-constant + one authoritative
display each, and **the maintainer's added AC (Diagnostics shows the server's running git hash) is met.** **One gap:
`config_id` (inventory row 5) is parsed but surfaced on no display** — routed to Data below. #831 closes when
`config_id` reaches Diagnostics.

"Trellis owns the contract conformance; lanes build their surfaces" (Workflow re-scope). This audit is the
conformance record; the one build it surfaces is routed, not done here.

---

## Inventory conformance (ADR-0030 §1)

| # | Versioned thing | Owner constant | Authoritative display | Conforms? |
|---|---|---|---|---|
| 1 | Product / release | `PRODUCT_VERSION` (pyproject `version`, `provenance.py`) | masthead + provenance panel | ✅ |
| 2 | Firmware semver | `PLANTS_FW_VERSION` (`config.h`) → `meta.fw` | masthead (fleet fw) + Diagnostics device row | ✅ |
| 3 | Firmware build-instance id | `meta.git` (fw git short-hash from the banner) | Diagnostics `p.device` (`device … git … run`) | ✅ |
| 4 | Wire `schema_version` | `meta.schema_version` (from the header) | Diagnostics (`schema_version …`) | ✅ |
| 5 | `config_id` | `config_id` (firmware-computed, ADR-0025) | **none** — parsed by `parse_v1`, surfaced nowhere | ❌ **gap** |
| 6 | Server / app build-instance | `server_provenance().app_git_sha` (`_BOOT_SHA`) | Diagnostics `p.server` + the restart cue | ✅ |

## The maintainer's added AC — MET

> *"every surface answers 'what exactly am I running' to build-instance granularity, firmware AND the served
> dashboard (Diagnostics shows the server's running git hash), so 'is the feature in my loaded build?' is a glance."*

`provenance.server_provenance()` already returns `app_git_sha` (**what the server is actually running**, frozen at
import) alongside `head_git_sha` (what's checked out now) and a **`stale`** flag; the template renders a
**"newer build — restart the Monitor"** cue (#719) when the running server predates the checked-out code. That is
exactly the intra-release "did the flash / did the feature land in my loaded build?" glance — **conforming.**

## Other ADR-0030 rules

- **Masthead = product + live-fleet fw, retired excluded (§4):** ✅ — `_fw_masthead`/version-resolution excludes
  `retired` devices from the fw-mixed cue (#856), so the ghost `0.8.0` from a retired rig no longer pollutes fleet
  coherence.
- **Bump-ordering + the live all-boards-`0.7.0` mislabel (§3, symptom 1):** this is the **cut ritual** (bump
  `PLANTS_FW_VERSION` before the coordinated reflash), tracked on Firmware's `firmware/0.7.1-version-relabel`
  branch (#902) — a live code/release fix, **not a display-contract gap.** Out of this audit's scope; noted for
  completeness.

## The one gap → routed

- **Data (dashboard surface):** surface **`config_id`** on the Diagnostics panel (it is already parsed by
  `parse_v1` and rides `meta`; the panel just needs to show it, per-device, next to `schema_version`). This is the
  only inventory row without an authoritative display. Small host-side add; ping Trellis to conformance-check it
  against ADR-0030 §1 row 5.

**Nothing else owed for the display contract.** Five of six inventory rows conform, the added server-git-hash AC is
met, and the retired-exclusion holds; the lone `config_id` surface is routed to Data.

— Trellis 🪴
