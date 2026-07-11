# ADR-0032 — GitHub Pages serving for the Design Library

**Status:** Accepted — *records the maintainer's already-executed ruling on #876 (Pages enabled 2026-07-09;
decisions 1–5 confirmed in-thread). Drafted by Workflow to close #876's AC-3 record gap — this ADR transcribes
the decision, it does not make one.* · **Amended 2026-07-11 (#271, Firmware-authored, maintainer-ratified):**
source flips from branch-deploy to **GitHub Actions deploy** so the web-flasher's binary artifacts can ship —
see [Amendment](#amendment--2026-07-11-271-pages-moves-to-actions-deploy). Decisions 2–7 unchanged.
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

## Amendment — 2026-07-11 (#271): Pages moves to Actions deploy

**Supersedes Decision 1.** The revisit trigger *"Pages ever needs a build step → switch source to GitHub
Actions mode"* fired. Firmware-authored per the maintainer's #271 ruling; Trellis conformance-checked,
maintainer-ratified. Decisions 2–7 (the `.nojekyll` HTML-only serving boundary, link policy, root redirect,
the accepted unpkg runtime, no custom domain, indexing) are **unchanged** — this is a serving-*mechanism*
change, not a content or policy one.

**What changes.** Source flips from *"Deploy from a branch (`main` / `/docs`)"* to **GitHub Actions deploy**
(`.github/workflows/pages.yml`). One workflow deploys the identical `docs/` tree — so the design library
serves **byte-identically** — plus the web-flasher's factory bins + a combined board-aware manifest, as part
of the same Pages artifact.

**Why a build step is now required (#271 / ADR-0026 D6).** The web-flasher (ESP Web Tools) must fetch the
factory `.bin` **same-origin** — GitHub's release-asset CDN sends no `access-control-allow-origin`, so a
browser `fetch()` from the Pages origin is blocked (empirically confirmed, #271). The bins can't live in git
either: ~1.2 MB (classic) + ~1.3 MB (C5), over the repo's `check-added-large-files` 1024 KB guard, and Pages
does not serve git-LFS (it serves the pointer). **Actions deploy is the only path** that is same-origin,
un-bloated, and CORS-free: the bins are **CI-built into the deploy artifact, never committed.**

**Post-merge maintainer step (one-time, like a key ceremony):** flip **Settings → Pages → Source → GitHub
Actions**. Until the flip, the workflow's *build* succeeds (bins + artifact) but the *deploy* step reports the
site isn't Actions-configured — so `workflow_dispatch` it once to prove the build, flip the setting, then
re-dispatch (or push) to publish. The legacy branch deploy keeps serving until the flip → **no serving gap.**

**Acceptance test (unchanged in spirit).** DesignQA's post-deploy render pass is the gate: the design library
must render byte-identically from the new origin. Close criterion for #271: a browser flash works end-to-end
on the classic from the live Pages origin.

**Flasher currency.** The deployed flasher serves the **`main`-HEAD** firmware (rebuilt each deploy). The
signed-release distribution (#302 / ADR-0026 D2, #989) remains the separate *authenticated* channel; the web
flasher is the unauthenticated first-flash on-ramp. Release-pinning the flasher bins is a noted follow-up.

## Consequences

- Every push to `main` triggers a `pages-build-deployment` Actions run — **non-blocking and not a quality
  gate**; do not mistake it for a CI failure surface. *(Post-#271: the deploy is the `pages` Actions workflow;
  its `build` job IS a real check, but design-content correctness is still verified by render pass, not by
  "the job went green.")*
- Render verification is the real acceptance test for design-page changes: these pages render via
  client-side JS, so "the file merged" ≠ "the page renders" — verify per **folder family** at the live
  URL (the #886 sparkline defect was invisible until Pages made rendering observable).
- Unpublishing is one settings action (Settings → Pages) — reversible, no data loss.

## Revisit triggers

- A custom domain is wanted → decision 6, mirror the existing org precedent.
- unpkg outage, or supply-chain posture tightens → vendor React/ReactDOM locally (decision 5's follow-up).
- Pages ever needs a build step (bundling, hashing) → switch source to GitHub Actions mode and re-visit
  decision 1.
