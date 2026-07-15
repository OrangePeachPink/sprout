# ADR-0034 — The Pages root is Sprout's public front door (amends ADR-0032; reconciles ADR-0010)

**Status:** Accepted — *records the maintainer's **locked** #1069 front-door IA decision (do-not-relitigate);
Trellis-drafted for the record, Design-QA co-authors the render-surface framing (§3). **V1** — maintainer-merged;
must land **before** the hub deploys to the root (FD-0 gates FD-1's root deploy, #1070).*
**Date:** 2026-07-12
**Owner:** Trellis (architecture) — the serving / IA amendment. Design-QA co-authors §3 (render surface).
**Lane:** architecture (cross-lane: Design-QA · DX serves the hub, #1071)
**Amends:** [ADR-0032](0032-github-pages-design-library-serving.md) §4 (root landing — **superseded**) and §5
(unpkg exception — **scoped to the library**) · reconciles [ADR-0010](0010-design-library-front-door.md) (the
single design front door)
**Relates:** #1070 (FD-0, this) · epic #1069 (the public front door) · #1071 (FD-1 hub build) · PRD-0008 ·
the FD-1 design brief §IA

---

## Context

The ADR chain says the Design Library is the design front door (ADR-0010) and the Pages **root** is a minimal
meta-refresh **redirect stub** into it (ADR-0032 §4). The #1069 front-door epic **inverts the public IA:** the
root becomes Sprout's public marketing hub; the library becomes a linked destination at its unchanged URL. The
maintainer **locked** this direction (#1069's decisions are do-not-relitigate). This ADR records the amendment so
the chain stays coherent before FD-1 (#1071) builds against it. Per the pre-launch amend policy, a structural
change to an Accepted ADR is recorded as a **new amending ADR**, not a silent in-place edit — the lineage stays
readable to an outside visitor.

## Decision (recorded)

### 1. The Pages root is the public front door — supersedes ADR-0032 §4

- ADR-0032 §4 (root = a `docs/index.html` meta-refresh redirect stub into the Library) is **superseded.** The root
  (`/`, `docs/index.html`) now serves the **Sprout-voiced public hub** (FD-1, #1071) — the first surface a visitor
  meets. It is a real designed page, not a redirect.
- The **Design Library keeps its unchanged URL** (`docs/design/…`) and stays fully served (ADR-0032 §1–3, §6–7
  unchanged); it becomes a **linked destination from the hub**, not the root.
- Still **no 404 at the root** (ADR-0032 §4's guarantee holds) — now because the root is a real page rather than a
  redirect.

### 2. Two front doors, reconciled — one line on ADR-0010

ADR-0010 ("the Design Library is the single front door") is **reconciled, not overturned:** the Library remains the
**design** front door — the single home for every active design *asset* (ADR-0010 unchanged) — while the Pages
**root** is the **public** front door (the marketing hub for a human visitor). Two audiences, two doors; ADR-0010's
"single front door" is now scoped to *design assets*, and this ADR is its cross-reference.

### 3. The hub is zero-external-runtime — ADR-0032 §5's unpkg exception does NOT extend to it

- Per locked decision #1069.5: the hub runs on **inline SVG + CSS keyframes**, `prefers-reduced-motion`-aware, with
  **no CDN scripts** and no external runtime. **Google Fonts with a system fallback is the sole tolerable
  external.**
- ADR-0032 §5's deliberate unpkg/React exception is **scoped to the Library** (a showcase with a knowingly-chosen
  local-first tension). It is **explicitly NOT inherited by the hub.** The hub is the public first render — it must
  be self-contained, fast, and honest to local-first doctrine; if it ever needs JS it is inline or vendored, never
  a CDN fetch. This tightens, not loosens, the §5 posture at the highest-visibility surface.

## Consequences

- FD-1 (#1071) builds the root hub against a **ratified IA**; the Library serving is untouched, so nothing there
  regresses.
- The **root deploy waits on this ADR merging** (FD-0 gates the root deploy) **and** the landing gate
  (#1069.6 build-to-the-landing — "See how I work" resolves to a Sprout-looking dashboard, not the interim panel).
- The public first render carries **no external-runtime dependency** — the hub can't be slowed or broken by a CDN
  outage, and it holds the local-first line ADR-0032 §5 deliberately relaxed for the internal showcase.
- The ADR chain reads as one lineage: **0010** (design front door) → **0032** (library serving) → **0034** (public
  front door).

## Rejected / not-relitigated

- The **#1069 locked decisions are not re-opened here** (voice-led framing, locked hero/OG strings, promotion gate,
  sameAs, HA ruling, etc.). This ADR records **only** the serving / IA amendment FD-0 owns.
- **Keep the redirect stub; put the hub at a sub-path.** Rejected — the root is the highest-value public surface;
  a redirect there wastes the first impression (#1069 IA).
- **Extend ADR-0032 §5's unpkg exception to the hub "for convenience."** Rejected — locked decision #5; the public
  front door is precisely where the external-runtime tension is least acceptable.

— Trellis 🪴
