# Crosslink + metadata checklist (front-door epic)

**Status:** Draft · **Date:** 2026-07-14 · **Owner:** DX lane
**Parent:** [`docs/prd/0008-public-front-door.md`](../prd/0008-public-front-door.md) (FD-2 / FD-3 / FD-4)

The tactical, paste-ready detail behind the PRD's crosslink, metadata, and indexing requirements. Tiers map
to epic sub-issues. **Tier 1 is the ship-early item** — cheap, approved, independent of the hub design.

**Canonical author name = "Veronica Hogue"** everywhere it's an authorship node. `url: vkhogue.com` is the
strong identity key; the name string is the assist. Copy pivot note: retire competitive-honesty phrasing
("never a fake %", "refuses to lie") from OG/description strings; **identity nodes are unaffected.**

**Audience anchor for all description / keyword copy:** write to the *plant/data overlap* — "plant people
who love data, and data people who love plants" (grill ruling #1039; see the PRD's **Audience** note). OG
descriptions and `keywords` lead with the instrument (readings, the calibrated band, the mood wall) *and*
the character — never a generic gardening pitch.

---

## Tier 1 — repo crosslinks · FD-4 · SHIP FIRST (0.7.x)

Additive backlinks; one small PR, ~5 lines across 3 files. Public-voice surfaces → DesignQA voice-check.

**1A. `README.md` footer** (~L245) — link the name to the site, canonical spelling:

```html
<p align="center"><sub>Built in the open by
<a href="https://vkhogue.com">Veronica Hogue</a>
(<a href="https://github.com/OrangePeachPink">@OrangePeachPink</a>) · source under
<a href="LICENSE">MIT</a>.</sub></p>
```

**1B. `CONTRIBUTORS.md` maintainer line** (~L9):

```markdown
- **Veronica Hogue** ([@OrangePeachPink](https://github.com/OrangePeachPink) ·
  [vkhogue.com](https://vkhogue.com)) — lead maintainer and initial developer: firmware,
  host tooling and analytics, the design system, and the engineering process.
```

LinkedIn stays out of repo files (path exists via vkhogue.com — Portfolio lane's boundary).

**1C. `CITATION.cff` authors** (replace the `OrangePeachPink` placeholder + its TODO comment):

```yaml
authors:
  - given-names: "Veronica"
    family-names: "Hogue"
    website: "https://vkhogue.com"
    alias: "OrangePeachPink"
```

Housekeeping (not brand): bump `version:` to match the release at land time.

**Copyright NOTICE line** ("Veronica K. Hogue and Sprout contributors", README + LICENSE): recommend
**leave as-is** (full legal name in a copyright notice is correct; bridged by the site link everywhere
else). Unify to "Veronica Hogue" only if the maintainer wants one string.

---

## Tier 2 — maker row + funding

**2B. Front-door "follow along" row** (also usable as a README row) — text links, descriptive anchors
(a11y over icon-only badges):

```html
<p align="center"><sub>Follow the build:
<a href="https://hackaday.io/OrangePeachPink">Hackaday</a> ·
<a href="https://www.hackster.io/OrangePeachPink">Hackster</a> ·
<a href="https://vkhogue.com">vkhogue.com</a></sub></p>
```

**2A. `.github/FUNDING.yml`** — HOLD. Hackaday/Hackster are follow/showcase, not funding; wait for a real
support destination (Ko-fi / GitHub Sponsors), then point the Sponsor button at that.

---

## Tier 3 — Pages head metadata + identity graph · FD-2

Goes in the front-door `<head>` (needs FD-1 to exist). OG strings → DesignQA voice-check; retire the
honesty-hook phrasing.

**3A. Share cards** — `title` / `description` / `canonical` / `og:*` / `twitter:card`; `og:image` a stable
1200×630 raster (Social Kit cover); favicon (Social Kit avatar).

**3B. Identity graph** — the single highest-value entity move; add the `author` block to the JSON-LD:

```json
"author": {
  "@type": "Person",
  "name": "Veronica Hogue",
  "url": "https://vkhogue.com",
  "sameAs": [
    "https://www.linkedin.com/in/vkhogue",
    "https://github.com/OrangePeachPink",
    "https://github.com/vkhogue",
    "https://huggingface.co/OrangePeachPink",
    "https://huggingface.co/vkhogue",
    "https://hub.docker.com/u/orangepeachpink",
    "https://www.hackster.io/OrangePeachPink",
    "https://hackaday.io/OrangePeachPink"
  ]
}
```

`author.url → vkhogue.com` is the entity edge (canonical Person carries the full professional `sameAs`,
incl. EY/Credly). Docker uses the **profile** form `/u/orangepeachpink`, not `/repositories/`. Portfolio
lane **decided** the node list: this minimal maker/dev/social subset only — EY People + Credly stay on the
canonical vkhogue.com Person, not here.

---

## Tier 4 — accessibility + AI-readability · FD-1 / FD-3

- Alt text on every image (hero, cards, badges); a small canonical alt-text register.
- Semantic landmarks, heading hierarchy, dark-theme contrast, visible focus, `lang`; Lighthouse a11y gate.
- `llms.txt` at the site root (concise machine description + key URLs).
- README first-paragraph plain-text-survivability pass — reads as one clean sentence after markup is
  stripped (what scrapers, snippets, and screen readers consume). Check the *current* intro first; rewrite
  (if needed) is public voice → DesignQA.
- Doc tables (sensor matrices, pin maps) with proper header rows.

---

## Tier 5 — indexing package · FD-3

- `<meta name="google-site-verification">` (Veronica supplies the token; DX places it) — the repo URL
  can't be a GSC property, the Pages URL can.
- `sitemap.xml` + `robots.txt` at the site root.

---

## Validation (run after any land)

- [ ] Repo `link_check` gate green — no new broken internal links.
- [ ] Google Rich Results + Schema validator — JSON-LD incl. `author` parses.
- [ ] LinkedIn Post Inspector on the Pages URL — custom card renders, no fallback.
- [ ] Bidirectional resolve — each `sameAs` node links back to vkhogue.com.
- [ ] Lighthouse a11y on the front door.

## Cross-lane status

- Reciprocal `sameAs` on vkhogue.com — **done** (Portfolio lane, 10 nodes deployed). Nothing owed from DX.
- `rel="me"` (verified bidirectional identity) — nice-to-have; park with the front-door build.
- ORCID — parked.
