# PRD: Public front door + launch surfaces

**Status:** Draft <!-- Draft → Accepted → Implemented -->
**Date:** 2026-07-14
**Owner:** DX lane (design: DesignQA · identity: Portfolio/resume lane · ADR: Trellis)
**Epic / issues:** *to be created — the FD-0…FD-7 epic this PRD spawns (see "Epic & slicing")*

---

## Problem

Sprout's public homepage (`https://orangepeachpink.github.io/sprout/`) is a 431-byte meta-refresh **stub
that redirects to the Design Library** (per ADR-0032 §4). A stranger who lands there gets bounced into a
brand/contributor artifact, not a front door. The repo also ships **no OpenGraph tags and no structured
data anywhere**, so every link we post renders a bare fallback card and search/AI crawlers can't build an
entity for the project or its maker.

This matters *now* because the launch process is being staged. Sprout's adoption comes from the
maker/hacker community (people who own an ESP32 and will actually flash it — Hackster/Hackaday), and every
build post, teaser, and maker-site link needs a real, polished, one-click-runnable destination to point
at. A Show HN or Hackaday feature that lands on a redirect stub wastes the shot. We need the front door —
and the invisible metadata layer behind it — built and ready *before* the cadence starts.

### GTM role (why this is the keystone)

For an OSS maker project, "go-to-market" is a **DX funnel** — `discover → understand → run → contribute` —
not a sales funnel. The scoreboard is builds, stars/forks, contributors, and (the biggest multiplier) Home
Assistant adoption; not revenue. This page is where that funnel begins, and — because GitHub owns the
`<head>` of repo pages — it's also the **only surface under our control** where share cards and the
identity graph can live. It is simultaneously the marketing front door and the canonical search/entity
anchor.

**Positioning is voice-led.** The differentiator is *craft and character* — the first-person plant voice,
the living animated mark, the per-zone mood system, the brand world — none of it copyable by dividing a
reading by 100. Reading a sensor accurately is table-stakes, not a differentiator; the app leads with the
character, never the calibration. Sprout still says "I'm not sure — check my sensor" — but that's the plant
speaking for itself, part of the character, framed as voice and never as a claim about anyone else. This is
a rhetoric decision, not a data-model change — bands-primary / %-as-labeled-index stays a valid engineering
choice.

## Goals

- Replace the redirect stub with a **first-class designed front-door hub** that routes every kind of
  visitor to the right entry point (try it, build with it, follow along, the design library).
- Ship the **invisible layer** — share cards + a structured-data identity graph — so every posted link
  renders well and resolves Sprout ↔ its maker as one entity.
- Make the page a **complete indexing package** (crawlable, assistive-device-ready, AI-readable).
- Do it as a **self-contained, brand-true asset** that arrives *with* the Sprout-looking product, and lay
  the maker-community launch surfaces so the cadence can start on the build-first gate.

## Non-goals

- **Not** a sales/marketing funnel, mailing list, or paid-acquisition surface.
- **Not** a LinkedIn/personal-brand surface — that's the Portfolio lane's lever (Veronica narrates Sprout
  as the builder; the plant's first-person voice belongs on Sprout's own turf). This PRD does not drive it.
- **Not** the Home Assistant integration — the biggest distribution multiplier, but a separate parallel
  product track that does not gate the front door.
- **Not** a change to the data model (bands-primary / %-as-labeled-index is unaffected).
- **Not** the brand-voice sweep of *professional* surfaces (vkhogue.com/LinkedIn keep their
  evidence/provenance doctrine — Portfolio's lane).

## Requirements

- **R1. Front-door hub replaces the stub.** A designed hub at the Pages root implementing the DesignQA
  brief's IA, with a **first-person voice spine** (Sprout narrates; only chrome — follow-along,
  design/brand, cite/about — speaks third person). Sections: hero, "what I do" (mood-as-character, *not* a
  scoreboard), try-me (flash), build-with-me (dev onboarding), how-I-read-soil (the Trust-Your-Sensor
  deep-dive, linked), where-I'm-growing (runs-today vs. roadmap), follow-along, design & brand,
  cite/about/license. The **living animated Sprout mark is in the hero** — non-negotiable for a first-class
  asset. Hero copy direction is locked (Sprout, first person; "See how I work" / "Flash me onto an ESP32");
  final strings are owned by the DesignQA brief.
- **R2. Zero external runtime dependencies.** Self-contained static HTML/CSS/JS. **No unpkg React** (the
  Design Library `.dc.html` pages load that per ADR-0032 §5; the hub must not inherit it) — fast,
  indexable, survives an unpkg outage. The living mark is **inline SVG + CSS keyframes**,
  `prefers-reduced-motion`-aware. Sole tolerable exception: Google Fonts with a system-font fallback.
- **R3. Share cards.** `<head>` OG + Twitter-card + meta-description block; `og:image` is a **raster**
  (1200×630, sourced from the Social Kit cover), kept **stable across deploys** (recrawl caches key off
  it); favicon from the Social Kit avatar.
- **R4. Identity graph.** JSON-LD `SoftwareSourceCode` with an `author → Person → sameAs` block: canonical
  **Veronica Hogue**, `url: https://vkhogue.com`, `sameAs` = the maker/dev/social profile nodes (Portfolio
  lane confirms the exact list against the deployed vkhogue.com graph). Identity is unaffected by the copy
  pivot; only the OG *description* strings re-sync when the voice-led copy lands.
- **R5. Indexing package.** `sitemap.xml`, `robots.txt`, and `llms.txt` at the site root; a Google
  Search-Console verification token placed in the head (Veronica owns the property + supplies the token).
- **R6. Accessibility + AI-readability.** Semantic landmarks, heading hierarchy, dark-theme contrast,
  visible focus, `lang`, and descriptive alt text everywhere (with a small canonical alt-text register).
  A Lighthouse accessibility run is an acceptance gate.
- **R7. Repo crosslinks.** README footer / CONTRIBUTORS / CITATION.cff carry the canonical author name +
  a link to vkhogue.com; README links out to the new front door; the front door links back into the repo's
  dev-onboarding. (Tactical detail: `docs/community/crosslink-checklist.md`.)
- **R8. How-I-read-soil deep-dive.** Realize `Sprout Trust Your Sensor` as a linked Pages surface — the
  hardware-quirk deep-dive the hub's "how I read soil" section points to.
- **R9. Maker profiles.** Flesh out the live Hackaday.io and Hackster.io placeholder profiles so they're
  build-log-ready and consistent with the identity graph.
- **R10. Launch-teaser assets staged.** Motion/social assets (Social Kit, motion pieces) authored and
  deploy-ready for the 0.9.x teaser window — *staged, not posted* (see the build-first gate).

## Acceptance criteria

- [ ] `https://orangepeachpink.github.io/sprout/` serves the designed hub (not a redirect); the Design
      Library remains reachable at its existing URL (nothing that linked to it breaks).
- [ ] The hub loads with **zero external runtime requests** (verifiable in devtools) except the allowed
      font; the hero animation runs from inline SVG/CSS and respects `prefers-reduced-motion`.
- [ ] **Google Rich Results / Schema validator** parses the JSON-LD, including a well-formed
      `author → Person → sameAs`.
- [ ] **LinkedIn Post Inspector** on the Pages URL renders the custom card (title, description, image with
      alt) — no fallback text.
- [ ] **Lighthouse accessibility** passes the agreed threshold on the front door.
- [ ] The repo **link-check gate** is green; the crosslinks resolve bidirectionally (each `sameAs` node
      links back to vkhogue.com).
- [ ] `sitemap.xml`, `robots.txt`, `llms.txt`, and the GSC token are served from the site root and the
      property verifies.
- [ ] The voice spine holds top-to-bottom: Sprout speaks first person; only chrome is third person; no
      surface preaches or leads with a virtue claim.

## Open questions

Resolved during the tri-lane handoff (2026-07-14) — recorded here; encoded in the epic by Workflow:

- **`sameAs` membership — DECIDED.** Minimal maker/dev/social subset on Sprout's block; the professional
  nodes (EY People, Credly) stay on the canonical vkhogue.com Person only. (Portfolio lane.)
- **First board drop — DECIDED.** The full FD-0…FD-7 epic is filed at once (the #1041 pattern); front-door-
  first is encoded as dependency links, not partial filing. (Workflow.)
- **HA integration — RULED.** Nothing in 0.7.x (no lab to test against; the kit box is unopened); possible
  0.8.x–0.9.x if the maintainer decides. Does not gate this PRD.

Still open:

- **Build-first sequencing.** Which release lands the branded (mood/character) dashboard — and therefore
  when FD-1 ships — resolves as that UI work (#875) lands. FD-1 designs to that target regardless.

## Out of scope / later

- `.github/FUNDING.yml` "Sponsor" button — held until a real support destination exists (not Hackaday/
  Hackster, which are follow/showcase, not funding).
- LinkedIn post templates and the professional-surface voice review — Portfolio lane, gated on the build.
- Home Assistant / ESPHome / MQTT-discovery integration — separate product track.
- Release-notes-as-indexed-pages discipline — a 1.0-window process note, not part of this build.

---

## Epic & slicing (FD-0…FD-7) — for Workflow

Per ADR-0003 §2, the epic is a **parent issue with native sub-issues**. Front-door-first: FD-1 is the
keystone; the rest hang off the page existing. Owners and issue-template fields below; slicing/tracer-bullet
decisions stay Workflow's.

| ID | Work | Requirements | Owner | `type:` / `area:` / `layer:` |
|----|------|--------------|-------|------------------------------|
| **FD-0** | Amend ADR-0010 + ADR-0032 (root = hub; Library becomes a linked destination) | R1 | Trellis/DesignQA + maintainer | task·docs / repo-tooling-docs / N/A |
| **FD-1** | Design (DesignQA) + build (DX) the front-door hub `docs/index.html` | R1, R2, R6 | DesignQA → DX | feature / analytics / host |
| **FD-2** | Head metadata + OG + JSON-LD identity graph | R3, R4 | DX (Portfolio confirms `sameAs`) | feature / repo-tooling-docs / host |
| **FD-3** | Indexing — sitemap / robots / llms.txt / GSC token / alt-text register | R5, R6 | DX (Veronica supplies token) | task·chore / repo-tooling-docs / host |
| **FD-4** | Repo crosslinks (README / CONTRIBUTORS / CITATION ↔ front door) | R7 | DX (DesignQA voice-check) | task·docs / repo-tooling-docs / N/A |
| **FD-5** | Realize `Trust Your Sensor` as a linked how-I-read-soil deep-dive Pages surface | R8 | DesignQA render | task·docs / analytics / N/A |
| **FD-6** | Flesh out Hackaday + Hackster maker profiles; build-log ready | R9 | DX / Veronica | task·chore / repo-tooling-docs / N/A |
| **FD-7** | Stage teaser/motion + Social Kit launch assets (0.9.x) | R10 | DesignQA | task·chore / analytics / N/A |

**Validation gate** (hangs off each FD): Rich Results · Post Inspector · Lighthouse a11y · link-check —
DX (+ Workflow if a CI step is added; no `pages.yml` edit is needed for the head block).

**Build-first gate:** surfaces (FD-2/3/4/6) may pre-build; the *posting cadence* (maker build logs,
teasers) unlocks only when the mood/character/voice ships in the app. FD-1 arrives *with* that branded
state, never in an interim Grafana-reflecting form.

**Ship-early:** the Tier 1 repo crosslinks (FD-4, see the checklist) are cheap, approved, and independent
of the hub design — they can ship first, in 0.7.x, to start earning backlinks while FD-1 is designed.

## Companion docs

- `docs/community/crosslink-checklist.md` — the tactical Tier 1–5 crosslink + metadata + indexing checklist
  behind FD-2/3/4.
- DesignQA FD-1 design brief — *(DesignQA authors in-repo; link once it lands.)*
