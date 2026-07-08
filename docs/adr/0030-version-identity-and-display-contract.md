# ADR-0030 — Version identity, build provenance & display contract

**Status:** Proposed — *drafted by Trellis (2026-07-07) from #831 during the v0.8.0 bench gap. **Never Accepted
here**; the maintainer ratifies the scheme and sets scope at v0.8.0 planning.* This ADR lays out the options so
planning is a short decision, not a discovery.
**Date:** 2026-07-07
**Owner:** Trellis (architecture) — the identity/display scheme; cross-lane build below
**Lane:** architecture (cross-lane: Firmware · Design · Workflow)
**Elaborates:** [ADR-0009](0009-versioning-and-release-policy.md) (the version *number* policy — one product
SemVer line + bump discipline). This ADR adds the layer 0009 does not cover: the *identity, provenance, and
display* of versions — how a build is uniquely named, and how a human reads the fleet's version state off the UI.
**Relates:** #831 (this) · #719 (the version-resolution cue that surfaced it) · #812 / #683 (retired-device
status-honesty family) · #302 (OTA — made a build-identity receipt urgent) ·
[ADR-0025](0025-config-provenance.md) (`config_id`) · [ADR-0020](0020-network-identity-and-credentials.md) /
[ADR-0027](0027-identity-model.md) (no hardware-derived identity)

---

## Context

The 2026-07-06 reflash surfaced a version-legibility failure. From the maintainer, at the bench:

> "We revved firmware and the board shows both 0.7.0 and 0.8.0, none are 0.7.1, no build number or hash, and I
> can't tell the OTA changed anything because it put the same build on. The serial contract isn't on the UI at
> all. Server and app version numbers aren't consistent and I can't tell which piece is versioned by what."

Each symptom has a verified root cause (#831):

1. `PLANTS_FW_VERSION="0.7.0"` was never bumped — the release ritual syncs the constant *at the cut*, but the
   coordinated reflash happened *before* the cut, so boards run v0.7.1 behaviour labelled `0.7.0`.
2. `0.8.0` is a **ghost** — it is not in source; it is historical rows from a retired dev rig, and the masthead
   "fw mixed" cue counts a retired device's old data as live fleet state (the #812 / #683 family).
3. The "app" version is the firmware constant read by the host — one value, two names, misleading.
4. The wire `schema_version` (the data contract) is displayed nowhere.
5. There is **no build-instance identity** — no git hash, no build timestamp — so an OTA that re-pushes identical
   source is invisible by construction; the only receipt tonight was the uptime reset.

ADR-0009 governs the version *number* (one SemVer line, when to bump MAJOR/MINOR/PATCH). It does not answer *how a
build is uniquely identified*, *where each versioned thing is displayed*, or *what proves an OTA took*. That is
this ADR.

## The packaging fork (present, don't decree — planning rules)

Where this decision lives is a real fork the maintainer/Workflow should rule:

- **A — a new ADR-0030 that *elaborates* ADR-0009 (recommended).** Rationale: (a) ADR-0009 is Accepted and
  Workflow-owned — a new ADR avoids editing a ratified cross-lane record; (b) version *identity/provenance/display*
  is a genuinely distinct concern from version *number policy*, and single-concern ADRs are the house style (the
  same reason ADR-0029 is not folded into ADR-0027); (c) it is substantial enough (a six-row inventory + an
  owner-constant rule + a display contract + a bump-ordering rule + an OTA-receipt requirement) to stand alone.
- **B — fold it into ADR-0009 as a new §7.** Keeps all versioning in one file (discoverability); Workflow already
  owns 0009 and the fw-constant sync lives there (§3/§6). Cost: it edits an Accepted ADR and mixes number-policy
  with identity/display.

**Recommendation: A.** If planning prefers consolidation, collapsing this into ADR-0009 §7 at ratification is a
clean move Workflow owns. The content below is identical either way.

## Decision (proposed)

### 1. Inventory — name every versioned thing, one owner constant + one authoritative display each

The anti-drift rule: each versioned entity has exactly **one** source-of-truth constant and **one** authoritative
display location. No version value is computed in two places under two names (symptom 3).

| # | Versioned thing | Single owner constant (source of truth) | Bumps when | Authoritative display |
|---|---|---|---|---|
| 1 | Product / release | the GitHub milestone + release tag `vX.Y.Z` (ADR-0009 §5) | at the release cut (ADR-0009 §6) | masthead: "Sprout vX.Y.Z" |
| 2 | Firmware semver | `PLANTS_FW_VERSION` (`firmware/include/config.h`) | **before** a coordinated reflash | Diagnostics per-board; masthead live-fleet fw summary |
| 3 | Firmware build-instance id | `GIT_REV` short-hash + build timestamp (`__DATE__ __TIME__`) — already in the serial header `git=` / `built=` | **every build** (a rebuild changes it by construction) | Diagnostics per-board; the OTA receipt |
| 4 | Wire schema | `PLANTS_SCHEMA_VERSION` (`config.h`) | per data-contract bundle epic (#739-style) | Diagnostics: wire row |
| 5 | Config id | `config_id` (firmware-computed hash, ADR-0025) | when a reading-shaping setting changes | Diagnostics per-board |
| 6 | Server / app | a distinct server build id (the host serves) — **not** the firmware constant (fixes symptom 3) | on host deploy | Diagnostics: server row |

The semver (row 2) answers *what release-family a board runs*; the build-instance id (row 3) answers *which exact
build* — they are different questions and both are needed. `schema_version`, `config_id`, and the server build are
today invisible on the UI and must appear on the Diagnostics table.

### 2. Build-instance identity is mandatory — it is the OTA receipt

SemVer alone cannot distinguish two builds, so it cannot prove an OTA took (symptom 5). The **build-instance id**
(git short-hash + build timestamp) can:

- a **source change** changes the hash;
- a **rebuild of identical source** still changes the timestamp.

**Requirement:** after any OTA push — *same-source pushes included* — the UI must show a **changed build-instance
id**. The uptime reset is not a receipt (it happens on any reboot, OTA or not). Firmware verifies what the serial
`git=` field actually embeds (a real short-hash, and a dirty-tree marker when the build is not from a clean commit)
and surfaces it; the host renders it on Diagnostics and, after a push, as the receipt the maintainer reads.

### 3. Bump ordering — the defect that fired this ADR

Symptom 1 is an **ordering defect**, not a missing value. The rule:

- **Firmware semver (`PLANTS_FW_VERSION`) bumps in the reflash-prep commit, before the first board is flashed** —
  not at the release cut afterwards. A coordinated reflash ships new behaviour; the label must move with it.
- **Wire schema (`PLANTS_SCHEMA_VERSION`) bumps with its data-contract bundle epic** (#739 pattern), before the
  emit reflash.
- **Product/release tag is cut last** (ADR-0009 §6), once the milestone is complete.
- **Build-instance id is automatic**, every build — nothing to remember.

Consequence: "firmware constant synced *at* the release cut" (ADR-0009 §3/§6.4) is refined to "synced *before a
coordinated reflash*, which is at or before the cut" — the reflash, not the tag, is the moment boards get the new
behaviour, so the label must lead the reflash.

### 4. Visibility contract (Design owns the treatment)

- **Masthead** = product version + a **live-fleet** firmware summary (coherent, or "fw mixed"), with
  **retired/archived devices excluded** from the mixed-cue (symptom 2 — the ghost `0.8.0` is a retired rig's data;
  reuse the #683 retire-device filter). The masthead is the *glance*.
- **Diagnostics** = the full table — per-board fw semver + build-instance id + `schema_version` + `config_id` +
  server build. One authoritative place where every version value lives.
- This mirrors ADR-0028's stance: the served surface is authoritative and the glance is a redundant summary of it,
  never a second source of truth.

### 5. The coherence test (acceptance, from #831)

From the UI alone, the maintainer must be able to answer, each mapping to one inventory row:

1. *What release is this?* → row 1 (masthead).
2. *What exact build is each board running?* → rows 2 + 3 (Diagnostics).
3. *Did my last OTA take?* → row 3 (the changed build-instance id).
4. *What wire schema is flowing?* → row 4 (Diagnostics).
5. *Is the fleet coherent?* → the masthead live-fleet cue, retired excluded.

## Consequences

- One place to look (Diagnostics) for every version value; one glance (masthead) for release + fleet coherence.
- An OTA is now falsifiable: no changed build-instance id means the push did not take.
- The retired-device ghost stops polluting fleet coherence (the mixed-cue reads live devices only).
- The bump-ordering rule removes the mislabel-on-reflash class of defect at its source.
- No new hardware identity is introduced — the build-instance id is git/build-derived, honouring ADR-0020 /
  ADR-0027 (no MAC/chip-id identity).

## Rejected / deferred alternatives

- **Split into per-component version lines (firmware / host / ml).** Out of scope — that is ADR-0009's own revisit
  trigger, a different decision. This ADR keeps 0009's single product line and only adds the identity/display layer
  over it.
- **Hardware-anchored build id (MAC / chip id).** Rejected — violates ADR-0020 (no hardware network identity) and
  ADR-0027 (identity is minted, not hardware-derived). The build-instance id is git/build metadata, not a device id.
- **Uptime / reboot as the OTA receipt.** Rejected — a reboot happens on any reset; it cannot distinguish an OTA
  from a power-cycle. Only a changing build-instance id is a real receipt.

## Open (routed)

- **Firmware:** verify `GIT_REV` / the serial `git=` field embeds a real short-hash (+ a dirty-tree marker); own
  the build-instance id emit and the OTA-receipt guarantee (build-id changes on every push).
- **Design (DesignQA on treatment):** the masthead live-fleet-fw cue with retired excluded, and the Diagnostics
  version-table layout.
- **Workflow:** the bump-ordering is a release-ritual change (fw-constant-before-reflash) — owns the ritual doc.
  **Live now:** the v0.7.1 reflash is mislabelling boards under symptom 1; the fix is code (bump the constant +
  exclude retired from the cue), Firmware/Workflow-owned — this ADR only records the scheme (see the #831 design
  note for the live flag).
- **Trellis:** ratify the assembled scheme; the packaging fork (§ above) is planning's to rule.

— Trellis 🪴
