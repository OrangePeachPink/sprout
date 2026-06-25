# Design-lane handoff — the Design Library as the `docs/design/` entry point

**From:** Design lane · **Date:** 2026-06-24 · **Re:** visual design-system index + the new pitch-deck template
**Flow:** I zip → Veronica relays to a proxy → the proxy places each file per the manifest and commits.

The visual library that catalogs every Sprout design page, packaged to **ship inside `docs/design/`** as the
design-system's official entry point — open it and click through to any page. Card links are rewritten to the
pages' real repo subpaths (`sprout-v2/`, `sprout-v3/`, `brand/`). It also carries the **new pitch-deck
template** and its **editable PowerPoint**, which weren't in the repo yet.

---

## Manifest — place every file exactly here

| In this zip | → Destination in repo | What / why |
|---|---|---|
| `docs/design/Sprout Design Library.dc.html` | `docs/design/Sprout Design Library.dc.html` | **The index.** A visual bookmark of all 15 pages across five shelves, each with screenshot, the living-mark badge, title, filename · version, and a what/when/where/how blurb. Links point into the subfolders (see mapping). |
| `docs/design/Sprout Deck Template.dc.html` | `docs/design/Sprout Deck Template.dc.html` | **NEW.** Reusable, branded pitch-deck template — ten master layouts on `deck-stage`. Presents live, prints to PDF, exports to PPTX. |
| `docs/design/Sprout Deck Template.pptx` | `docs/design/Sprout Deck Template.pptx` | **NEW.** Editable PowerPoint export of the template (10 native slides + speaker notes, ~195 KB). |
| `docs/design/library/thumbs/*.png` | `docs/design/library/thumbs/` | 15 card thumbnails the index references. |
| `docs/design/support.js` | `docs/design/support.js` | Claude Design runtime for the `.dc.html` index. Byte-identical to the copies in `sprout-v2/` etc. — included so the index renders from `docs/design/` root. Skip if you keep a single shared copy. |
| `docs/design/deck-stage.js` | `docs/design/deck-stage.js` | Deck runtime for the template (same dedup note). |

## Card-link mapping (rewritten in the index)

The index assumes the pages live where the v1/v2/v3 deliveries placed them. If any committed path differs,
fix that one `href` in the index:

- `sprout-v2/` — Design System (+ `.html` standalone, `-print`), Plant Design System, Brand World, Brand
  Identity, Personality Directions, Plant POV, Loader, Day in the Life, On Stage, Deck (+ `-print`), Social Kit
- `sprout-v3/` — v3 Personality Layer, `sprout-mark-demo.html`
- `brand/` — Brand Guidelines
- `docs/design/` root (siblings of the index) — Deck Template (`.dc.html` + `.pptx`)

## Repo notes

- **Entry point:** this is meant to be the design folder's front door. Optional: add a line to
  `docs/design/README.md` — *"Visual index: open `Sprout Design Library.dc.html`."* — so it's linked from the
  GitHub-rendered folder view (a `.dc.html` needs the runtime to render, so it's an open-locally page, not a
  GitHub-rendered one).
- **No v1/v2/v3 page is modified** — the index only links to them. The only new pages are the Deck Template and
  its PPTX.
- Not backlog/issues (no-fly). Largest file is the `.pptx` (~195 KB); nothing needs Git LFS.

Suggested commit: `docs(design): add visual design library index + pitch-deck template & pptx`.
