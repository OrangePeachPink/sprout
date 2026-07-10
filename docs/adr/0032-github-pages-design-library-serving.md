# ADR-0032 — GitHub Pages serving for the Design Library

**Status:** Accepted — *records the maintainer's already-executed ruling on #876 (Pages enabled 2026-07-09;
decisions 1–5 confirmed in-thread). Drafted by Workflow to close #876's AC-3 record gap — this ADR transcribes
the decision, it does not make one.*
**Date:** 2026-07-10
**Owner:** DX (serving + link policy) · DesignQA (render surface)
**Lane:** dx (cross-lane: design)
**Extends:** [ADR-0010](0010-design-library-front-door.md) (the Design Library is the design front door —
this gives it a rendered public address)
**Relates:** #876 (this decision) · #885 (link repoint + root landing) · #886 / #895 (first
live-render defect class caught *because* pages now render) · #59 (go-public epic)

---

## Context

GitHub renders `.html` files as **source, never as pages** — so the visual Design Library
(33 `.dc.html` files under `docs/design/`) was unreadable at github.com: every brand/concept link showed
raw HTML. The repo was already prepped for the native fix: `docs/.nojekyll` existed, and the `support.js`
render runtime is co-located in every design folder. The gap was serving.

## Decision

1. **Source: "Deploy from a branch" — `main` / `/docs`.** No Actions build step; `.nojekyll` serves the
   static files as-is (correct for custom-element HTML + client-side render). Site root:
   `https://orangepeachpink.github.io/sprout/`.
2. **Serving boundary: Pages is for the HTML assets only.** `.nojekyll` means markdown is served **raw**
   on Pages — so `.md` viewing stays on github.com, and nothing may link a reader to
   `github.io/…/*.md`. One file, one canonical viewer.
3. **Link policy: live docs point at rendered pages; history stays point-in-time.** Every live markdown
   `.dc.html` link is an absolute Pages URL (spaces `%20`-encoded). Historical documents —
   `docs/adr/**`, `docs/design/_archive/**`, dated `HANDOFF_*` — keep their repo-relative links:
   repointing decisions-of-record is falsifying them.
4. **Root landing:** `docs/index.html` is a minimal meta-refresh redirect into the Design Library, using a
   **relative** URL so it survives a future custom domain. No 404 at the site root.
5. **Runtime dependency (accepted deliberately):** `support.js` fetches React/ReactDOM from `unpkg.com` at
   render time — no SRI, no version pinning, no offline render. Accepted for a public showcase; this is a
   *known, chosen* tension with local-first doctrine, and vendoring React locally is the standing
   follow-up option if the dependency ever misbehaves.
6. **Custom domain: not now.** Noted as a future option; the org already has a working Pages +
   custom-domain precedent to mirror.
7. **Search indexing: accepted.** The site is a showcase; no robots controls.

## Consequences

- Every push to `main` triggers a `pages-build-deployment` Actions run — **non-blocking and not a quality
  gate**; do not mistake it for a CI failure surface.
- Render verification is the real acceptance test for design-page changes: these pages render via
  client-side JS, so "the file merged" ≠ "the page renders" — verify per **folder family** at the live
  URL (the #886 sparkline defect was invisible until Pages made rendering observable).
- Unpublishing is one settings action (Settings → Pages) — reversible, no data loss.

## Revisit triggers

- A custom domain is wanted → decision 6, mirror the existing org precedent.
- unpkg outage, or supply-chain posture tightens → vendor React/ReactDOM locally (decision 5's follow-up).
- Pages ever needs a build step (bundling, hashing) → switch source to GitHub Actions mode and re-visit
  decision 1.
