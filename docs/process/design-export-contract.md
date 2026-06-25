# Design export contract

How the Design lane packages a design-system export so the ingest agent and the Workflow fold-in stay
frictionless. Pairs with [ADR-0010](../adr/0010-design-library-front-door.md) (the Library is the single
front door) and the per-export `_INGEST.md` manifest.

## What to ship

- **`docs/design/` only** — the Design lane's content: the front door, the shelves
  (`tokens/ components/ foundations/ brand/ voice/ motion/ go-to-market/ merch/`), `runtime/`, `library/`,
  and `_archive/`.
- **A `docs/_INGEST.md` manifest** — the placement map, the rules, and the gate instructions for the ingest.

## What NOT to ship

- **`docs/adr/`, `docs/community/`, `.github/`, the root `README.md`.** These are other lanes' canonical
  files. The Library *links* to them in place (ADR-0010 §7); it does not carry them. Your authoring tool
  mirrors the whole repo (structure A) so the Library's links resolve in preview — that is correct, but the
  **export must be scoped to `docs/design/`**. Shipping the others risks clobbering the authoritative repo
  versions, which are more complete and may be lint-fixed.

## Conventions to keep (these were right)

- The shelf structure, with **per-folder `support.js`** (`runtime/` holds the canonical source; refresh all
  copies together on a runtime bump).
- **Repo-relative links** within `docs/`; the **`OWNER/REPO` placeholder** for github.com UI links (the
  ingest swaps it at land/publish).
- **`_archive/`** holds superseded content, each banner-marked, with its own `README.md`.
- The **`_INGEST.md` manifest** teaches the gate: one consolidated PR, `Refs` the design issues, evidence to
  **Needs Verification**, never auto-merge, never the ingest closing it.

## Get these right (the friction this cycle surfaced)

- **`docs/design/README.md` = a thin pointer to the Library**, not a flat-file index. A folder README whose
  job is *"the front door is the Sprout Design Library, here are the shelves"* can never go stale.
- **`_INGEST.md` filenames and URLs must match what actually ships** (e.g. `.dc.html`, not `.html`).
- **If an export moves or renames existing files, include an old to new path map in `_INGEST.md`** so the
  ingest can fix any references that point at the old paths.
- **Active `.md` files must pass the repo's markdownlint** (line length, blank lines around headings and
  lists). `_archive/` is exempt — Workflow excludes `docs/design/_archive/**` from the linter so frozen
  provenance is never reformatted.

## The consuming side (ingest + Workflow)

- **Ingest** places `docs/design/` only, leaves `docs/adr/` and `docs/community/` exactly as the repo has
  them, and lands one consolidated PR (`Refs` the design issues) that stops at **Needs Verification** — the
  reviewer merges and closes, never the ingest.
- **Workflow** folds in the non-design pieces with that PR: `docs/.nojekyll`, the `CONTRIBUTING` move to
  `.github/`, the `docs/design/_archive/**` markdownlint exclusion, and any cross-reference fixes.

---

*Maintained by the Workflow lane. Update it when a future export surfaces a new reconciliation pattern.*
