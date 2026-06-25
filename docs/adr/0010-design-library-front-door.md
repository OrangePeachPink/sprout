# ADR-0010 — The Design Library is the single front door for design assets

**Status:** Accepted (Workflow-drafted; Design-lane owns + ratifies) · convention maintainer-approved 2026-06-25
**Date:** 2026-06-25
**Owner / Lane:** Design
**Relates to:** ADR-0004 (design system) · ADR-0007 (brand & voice) · ADR-0008 (personality layer)

## Context

The design system has grown to dozens of assets across many surfaces and several generations
(v2 → v3, where v3 is *additive over* v2, not a replacement). Without one rule, contributors have to
guess which version is current, and drift creeps in. The Sprout Design Library has become a single
browsable index of every active asset; we make that the durable convention.

**What counts as a "design asset":** the entries the Library surfaces — pages, tokens, components,
motion, the decisions of record, and the public community/GitHub surfaces. The Library is a *curated
view*: it may index assets in their canonical repo homes (ADRs in `docs/adr/`, community surfaces in
`.github/` and `docs/community/`), not only files under `docs/design/`.

## Decision

1. **The Sprout Design Library is the single front door for every active design asset.** If it's live,
   it's surfaced in the Library. If it isn't in the Library, it's archived.
2. **Supersede, never delete.** Replaced assets move to `_archive/` with a SUPERSEDED banner and a
   pointer to their current counterpart — out of the active path, kept as history.
3. **Consistency is a gate, not an afterthought.** Anything added or updated passes the brand
   consistency pass: **voice · color/tokens · the living mark · type · soil mode · the honesty rule
   (raw + band = truth) · the character↔instrument boundary · reduced-motion · the *tend well* sign-off.**
   A significant change re-triggers the pass and is logged in the changelog, so the "how" stays teachable.
4. **The consistency pass is a criterion *inside* the verification gate.** When a design deliverable lands
   as a proxy PR, "passed consistency" is something the reviewer confirms before merge — not a separate,
   parallel process. The **Brand Consistency Pass page is the reviewer's rubric** (it states the standard
   and teaches by example).
5. **The repo mirrors the Library.** `docs/design/` is the public-facing front door; the commit-proxy keeps
   it synced. An asset isn't "current in the repo" until its PR merges.
6. **The Library index updates in the same PR as the asset.** Adding or superseding an asset includes its
   Library card change in the same change — the front door never lags the content behind it.
7. **Explorations kept for rationale stay labeled.** A superseded *and* inactive asset goes to `_archive/`.
   A superseded-but-pedagogical exploration (e.g., a rejected direction that explains *why* a decision was
   made) may remain surfaced in the Library under an explicit **exploration / history** label, linked from
   the relevant ADR, and clearly marked not-for-building.

## Consequences

- New contributors get one answer: "need a design asset? It's in the Library, and it's current."
- Archives accumulate but never confuse — banner-marked and out of the path.
- The proxy carries a sync duty: the repo's front door must not lag the tool's Library.
- Design work flows through the same Issue → PR → gate pipeline, with consistency as an added check.
- The v2→v3 generations are presented by *function* (shelves), not by version label, so the "which
  version?" question disappears; the additive v3-over-v2 story lives in ADR-0008 and the v3 page.

## How to apply

- **Add an asset:** put it in the Library; run the consistency pass; update the Library card in the same PR via the proxy.
- **Supersede one:** move the old to `_archive/`, banner it SUPERSEDED, point to the new, log the changelog.
- **Significant change:** re-run the consistency pass; add a changelog entry explaining what & why.
- **Keep an exploration visible:** label it *exploration/history* in the Library and link the ADR that decided it.
