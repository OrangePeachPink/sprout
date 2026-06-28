# Release Checklist (pre-1.0 → public)

**Status:** living document — the single place pre-release "do before we ship / go public" actions are
captured so they don't get lost in a chat or a PR description. The **Publish-readiness epic (#59)** is
the vehicle that *executes* this list at release time; this doc is the source-of-truth list.

> **Convention:** any lane (or Workflow) that hits a "this has to happen before public/1.0" item adds a
> checkbox here with its originating `#ref`. Workflow keeps this current.

## Public-clean / no-PII (P0 — blocks public)

- [ ] **No-PII policy ratified** — ADR-0015 (Trellis-drafted, Workflow-placed + registered).
- [ ] **Untrack + retire `BACKLOG.md`** — carried 11 name-leak hits (done in the governance PR; it's
  now gitignored).
- [ ] **Scrub the name leak from `docs/design/_archive/*/HANDOFF.md`** (5 files) — preserved-provenance
  docs that still carry the maintainer's name.
- [ ] **Git-history scrub (`git filter-repo`)** before public — untracking removes the name from the
  *tree*, not from *history*. Decide: scrub, or accept and publish.
- [ ] **Secrets scan** — `gitleaks detect --no-banner` (or `trufflehog`) clean, current files *and* history.
- [ ] **Personal-info grep** — name / email / home-path / address fragments across files *and* history.
- [ ] **Location/coordinates grep** — no real lat/lon decimals, no committed `config/location.local.json`, no
  operator coordinates in tracked files *or* history. Templates carry placeholder city-center values only
  (PRD-0002 R6 / ADR-0013 §3 / ADR-0015).
- [ ] **`.gitignore` audit** — `.env*`, secrets, build outputs, `config/location.local.json`, local-only folders all covered.

## Legal & community-health

- [ ] **License decision + `LICENSE` file** (#37) — held until ~1.0; the long pole.
- [ ] **`CODE_OF_CONDUCT.md` + `SECURITY.md`** — contacts TBD (#122 landed the scaffolding).
- [ ] **`CONTRIBUTORS` / `AUTHORS`** — name the maintainer at first public release (resume/credibility).
- [ ] **`CITATION.cff`** — present (#122); confirm metadata before public.

## Release mechanism (ADR-0009)

- [ ] **Wire the changelog** — `git-cliff`-generated `CHANGELOG`, deferred to the first release (ADR-0002 #9 / ADR-0009).
- [ ] **Tag + `just ship`** — the ADR-0009 release ritual (CHANGELOG → tag → ship).
- [ ] **Versioning scheme** — confirm per ADR-0009 before the first tagged release.

## Branch protection & CI

- [ ] **Branch protection → "B"** — flip ruleset `18125071` to `required_approving_review_count: 1`
  once a second reviewer identity exists (today it runs at "A": PR-required, 0 approvals).
- [ ] **CI green** — `ci.yml` (#103) runs on the GitHub Pro allowance after the **July 1** Actions
  reset; merge #103 then (it's content-validated now).
- [ ] **No self-hosted runner on a public repo** — plants uses GitHub-hosted (`ubuntu-latest`), so it's
  clean; confirm before flipping visibility.

## Pages & presentation

- [ ] **Enable GitHub Pages** — `main` `/docs` (`.nojekyll` already in); serves the Design Library + a landing.
- [ ] **Social preview image** — upload at Settings → General → Social preview (not scriptable).
- [x] **Repo "presents correctly"** — linguist overrides + config (#139).

## Process / governance

- [ ] **Flip the ADR policy to append-only** — at 1.0 / first-public, per
  [ADR-0000 §4](../adr/0000-record-architecture-decisions.md); do the one-time "clean read" first.
- [ ] **Org migration** (#58) — optional; structure is owner-agnostic, so deferrable. URL / board / Pages re-point at transfer.
- [ ] **Confirm no ADRs left `Proposed`** that should be `Accepted`.

## Onboarding & contributor validation

- [ ] **Clean second-machine install test** (#186) — the "three installs → it works" claim verified on
  fresh hardware, docs-only, no undocumented step.
- [ ] **New-contributor field test** (#187) — a real novice completes a first PR cold; friction is
  captured and fixed (expect several rounds; first tester TBD).

---

*This list is the connective tissue for going public. Workflow keeps it current; #59 executes it.*
