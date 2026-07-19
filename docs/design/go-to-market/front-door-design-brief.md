# Sprout front door — design brief (FD-1)

> **Status:** DesignQA design input for the GTM / front-door epic (FD-0…FD-7). Cross-lane aligned in chat
> (DesignQA · DX · Portfolio/Resume · Trellis · maintainer) — **not yet sliced**. Workflow assembles the epic
> and cuts tracer bullets; this brief is FD-1's design spec and carries the render-1:1 copy deck. Nothing here
> promotes the surface — see [§9 build-to-the-landing](#9-sequencing--build-to-the-landing).
>
> **Owner:** DesignQA (design + voice + copy) · **Builds:** DX (`docs/index.html`) · **Voice authority:**
> [BRAND.md](../brand/BRAND.md) · **Decisions of record:** [ADR-0004](../../adr/0004-design-system.md)
> (design system) · [ADR-0007](../../adr/0007-brand-guidelines.md) (brand & voice) ·
> [ADR-0010](../../adr/0010-design-library-front-door.md) +
> [ADR-0032](../../adr/0032-github-pages-design-library-serving.md) (the front-door / Pages chain FD-0 amends).

---

## 1. What FD-1 is

The Sprout **front door** — the live GitHub Pages root (`docs/index.html`) — built as a **first-class,
single-voice hub**, not a bin of reused components. It replaces the meta-refresh redirect stub
([ADR-0032 §4](../../adr/0032-github-pages-design-library-serving.md)): the root becomes the hub that *links
to* the design library (library URL unchanged), and it is the one surface with full `<head>` control, so it is
simultaneously the marketing front door and the SEO/entity anchor (FD-2).

It routes every kind of visitor to every entry point — try it, build with it, follow it — while **Sprout
narrates the whole page in first person**. It is designed and built **to the aimed-at, Sprout-voiced product**
that the current release cycle lands, and sequenced to arrive *with* it — never a stopgap that reflects the
interim dashboard.

## 2. Locked decisions (canonical source)

These were decided in cross-lane review and govern every downstream slice. Do not re-litigate in-issue.

1. **Voice-led, not honesty-led.** Sprout's differentiator is its **voice · living mark · mood system · brand
   world** — craft and character, hard to copy. It is **not** "honesty" and **not** the calibration math
   (bands vs. a 0–100 index is a valid engineering choice, not a moral one, and not a differentiator).
2. **The two-honesties rule.** *Retire* competitive honesty as a hook anywhere it appears ("refuses to lie,"
   "fake % vs. real signal," "the honesty thread") — it casts shade, isn't true (every sensor's numbers are
   honest), and doesn't differentiate. *Keep* **self-candor** as a voice trait — Sprout humble about **its
   own** state ("I'm not sure — check my sensor"; "I can't water you yet"). Every honesty line must point
   **inward**. The moment a line points outward, it's the wrong kind.
3. **Sprout is the hero, first person.** Per [BRAND.md](../brand/BRAND.md) — "a living, animated character,
   the hero of every surface." The page speaks **as** Sprout; only chrome speaks third-person.
4. **First-class asset.** Intentional purpose, full top-to-bottom continuity, one voice — assembled from
   real sources + net-new hero, not thrown together.
5. **Scope boundary.** This brief and its brand direction stop at **Sprout's edges**. It does not touch
   Veronica's professional surfaces (vkhogue.com / LinkedIn / résumé), where the evidence/provenance doctrine
   is a genuine differentiator the Resume lane keeps.

## 3. Positioning (voice-led)

> **Sprout is the plant that talks back.** Four plants, four moods, one voice — local-first on an ESP32. It
> tells you how it's doing in its own words, and it's honest enough to say when it isn't sure.

The honesty clause points **inward** ("when *it* isn't sure") — character, not comparison. It can be cut
entirely; the first sentence carries the pitch.

## 4. Voice architecture — the character↔marketing boundary

The continuity spine is what makes this a *designed asset* rather than an assembly: **Sprout narrates in first
person; only chrome speaks third-person.** This is the sibling of the character↔instrument boundary DesignQA
already owns ([BRAND.md §6](../brand/BRAND.md)).

- **Sprout's voice (first person):** hero, "what I do," "try me," the trust teaser, "where I'm growing."
- **Chrome (third-person, minimal):** follow-along link row, design-library link, cite/about/license.

Voice is a **Phase-A design input**, not a late string-check. Mood/voice strings derive from
[BRAND.md §2 & §4](../brand/BRAND.md) (the band→mood→voice table) and the
[Plant POV](https://orangepeachpink.github.io/sprout/design/voice/Sprout%20-%20Plant%20POV.dc.html) cards,
which already embody the corrected positioning (every line inward self-candor, zero shade — no rework).

## 5. Information architecture

One voice, top to bottom. The hub is an **assembly + net-new hero** — re-sourced correctly (the onboarding
`Sprout Front Door` is the *first-run device-setup wizard*, **not** a landing hub; it is not a source here).

| # | Section | Voice | Source |
|---|---------|-------|--------|
| 1 | **Hero** — Sprout introduces itself + the **living animated mark** | Sprout | net-new + the mark |
| 2 | **What I do** — every plant its own mood, shown as character (not a fake-% scoreboard) | Sprout | [Deck](https://orangepeachpink.github.io/sprout/design/go-to-market/Sprout%20Deck.dc.html) · [Plant POV](https://orangepeachpink.github.io/sprout/design/voice/Sprout%20-%20Plant%20POV.dc.html) |
| 3 | **Try me — one-click flash** → `docs/flash/` | Sprout invites | flasher exists |
| 4 | **Build with me** — clone → dashboard, `just`, good-first-issues | Sprout bookends → contributor register | [Developer Front Door](https://orangepeachpink.github.io/sprout/design/onboarding/Sprout%20Developer%20Front%20Door.dc.html) |
| 5 | **How I read the soil** — trust deep-dive (linked) | Sprout teaser | [Trust Your Sensor](https://orangepeachpink.github.io/sprout/design/onboarding/Sprout%20Trust%20Your%20Sensor.dc.html) |
| 6 | **Where I'm growing** — runs-today vs. roadmap, in character | Sprout | net-new (status = character) |
| 7 | **Follow along** — Hackaday · Hackster · vkhogue.com | chrome | Social Kit row |
| 8 | **Design & brand** → design library (URL unchanged) | chrome | existing |
| 9 | **Cite / about / license** — maintainer → vkhogue.com; JSON-LD author block in `<head>` | chrome | net-new + entity graph (FD-2) |

The **fake-% vs. real-signal contrast visual is out** (it was the retired honesty wedge made graphic). §2 is
**a plant with a mood, in its own words** — Sprout's face + its current feeling + a plain reading, optionally
cycling the moods.

## 6. Copy deck (render 1:1)

Real strings, not lorem. DX renders these into `docs/index.html` 1:1; DesignQA owns the words **and** the
render/tokens for this surface. `[ … ]` = a button/link.

### Hero — *locked*

> **Hi — I'm Sprout.**
> I look after four plants and tell you how each one's really doing — in my own words. When I'm thriving,
> I'll say so. When I can't feel my sensor, I'll say that too.
> `[ Flash me onto an ESP32 ]` · `[ See how I work ]`

### 2 · What I do

> **Every plant, its own mood.**
> I read the soil in four pots and give each one a *feeling*, not just a figure — thriving, content, thirsty.
> Watch me shift: teal when I've just had a drink, amber when I'm ready for the next one.

### 3 · Try me

> **Plug me in and I'll start watching.**
> Got an ESP32 and a soil sensor? Flash me straight from your browser — one click, no toolchain, about a
> minute. Then I'll introduce myself to your plants.
> `[ Flash me now ]`

### 4 · Build with me

> **Want to help me grow?**
> I'm the friendliest repo you'll contribute to today. Clone me, run `just`, and my dashboard's up in about
> five minutes. There's a good-first-issue with your name on it.
> `[ Start in five minutes ]` · `[ Good first issues ]`

### 5 · How I read the soil

> **How do I know what I'm feeling?**
> The same soil can read differently depending on where the probe sits — so I've learned to trust the
> position, not the label. Want to see how I check myself? I wrote it down.
> `[ Read: can you trust your sensor? ]`

### 6 · Where I'm growing

> **What I can do today — and what's next.**
> Right now I can watch your plants and tell you how each one feels, live. I can't water them myself yet —
> that part's still growing in, and I won't pretend otherwise. Follow along and watch me get there.
> `[ See the roadmap ]`

### 7 · Follow along *(chrome)*

> **Follow the build.** · Hackaday · Hackster · vkhogue.com

### 8 · Design & brand *(chrome)*

> **Peek behind the leaves.** The whole design system — my voice, my moods, my colors — is open too.
> `[ Open the design library ]`

### 9 · About & credit *(chrome)*

> Sprout is an open-source project by **Veronica Hogue** (vkhogue.com), MIT-licensed. `[ Cite this project ]`
> · `[ View the code ]`
>
> *(The machine-readable JSON-LD `author` block lives in this page's `<head>` — the Resume lane owns the node
> list; leave the slot, don't fill it. See [§10](#10-cross-lane-seams).)*

## 7. The living mark & the self-contained-animation constraint

The **animated Sprout mark belongs in the hero** — it is the one place the living character must appear, and
for a first-class asset it is non-negotiable ([BRAND.md §3](../brand/BRAND.md)).

**Hard constraint (design + build):** the hub is **self-contained static HTML with zero external runtime**.
The design-library `.dc.html` surfaces load React from `unpkg.com` at render time
([ADR-0032 §5](../../adr/0032-github-pages-design-library-serving.md)); the front door **must not** inherit
that, so it stays fast, indexable, and outage-proof. Therefore:

- The hero mark is **inline SVG + CSS `@keyframes`** (sway/breathe per BRAND.md), **not** a scripted or
  fetched component. Honor `prefers-reduced-motion` (static mark, no motion).
- Any mood-cycling in §2 is CSS/inline only.
- The **only** tolerated external request is Google Fonts (Baloo 2 · Hanken Grotesk · JetBrains Mono) **with
  a system-font fallback** so the page is fully legible if fonts fail.

## 8. Design acceptance criteria

- **Tokens:** all color/type consumed from [`sprout-tokens.css`](../tokens/sprout-tokens.css) — never
  redefined ([ADR-0004](../../adr/0004-design-system.md)).
- **Theme:** light + soil/dark, driven by the token dark set.
- **Accessibility (acceptance gate):** semantic landmarks, one `<h1>` + correct heading order, `lang="en"`,
  visible focus, AA contrast in both themes, alt text on every image → Lighthouse a11y passes.
- **Responsive:** single-column mobile → multi-section desktop; no horizontal scroll; the hero mark scales.
- **Brand assets:** the **Sprout avatar** and **cover header** (landing via PR #1066) are the favicon and
  `og:image` source — reuse, don't recreate.
- **Voice conformance:** every first-person line points inward (self-candor), zero outward comparison; chrome
  stays minimal and third-person.
- **Self-contained:** no external runtime deps (§7).

## 9. Sequencing — build to the landing

FD-1 is designed and built **to the aimed-at Sprout-voiced product** and **sequenced to land with it** — not
stood up in an interim, Grafana-looking form and merely held from promotion. Concretely:

- The hub designs to the landed brand/voice; its **"See how I work" link resolves to a Sprout-looking
  dashboard**, which the current release cycle delivers.
- **§6 "Where I'm growing"** carries honest product-state *in character* (predict in progress; watering gated
  behind its safety issues) — the real roadmap, not a "the app isn't Sprout yet" apology.
- **Promotion** (the posting cadence — build logs, teasers) is a **separate, later** gate the maker-site lane
  owns; it unlocks only when the character/mood/voice actually ships in the app. Building the hub now is fine;
  pointing an audience at it waits for the product to be Sprout.

## 10. Cross-lane seams

- **DX** builds `docs/index.html` from §6 and the §5 IA; owns FD-2 head metadata, FD-3 indexing, FD-4
  crosslinks, and the zero-runtime AC as a shared build constraint.
- **Resume/Portfolio** owns the §9 (About) **author block** node list (`author.sameAs`) and the visible
  maintainer credit target — DesignQA leaves a clean slot, does not fill it. **Handshake:** when this copy
  deck lands, DesignQA pings Resume to re-sync the `og:description` strings + the maker-bio clause in one pass
  (the author-identity graph itself is unaffected by the copy pivot).
- **Trellis** owns **FD-0** — the ADR amending the [0010](../../adr/0010-design-library-front-door.md) +
  [0032](../../adr/0032-github-pages-design-library-serving.md) chain (root = hub, library becomes a linked
  destination; library URL unchanged). Maintainer-merged per the ADR pre-launch amend policy. Runs alongside
  FD-1.
- **Maker-site lane** owns promotion (§9) and FD-6 profiles/build-log.

## 11. Scope fence (explicitly out)

- The retired honesty wedge, in copy **or** visual (the fake-% contrast graphic).
- Any external runtime dependency on the hub (§7).
- Any treatment of LinkedIn as a Sprout-conversion funnel — that's the Resume lane's brand lever, separate
  metrics.
- Veronica's professional evidence/provenance doctrine — untouched (§2.5).
- Slicing / tracer-bullet definition — Workflow's, not this brief's.

## 12. Map to the FD-0…FD-7 epic (design-lane view)

Front-door-first; everything hangs off the hub existing. Ownership from the design lane's seat — Workflow sets
final slice boundaries.

| FD | Item | Lead | DesignQA role |
|----|------|------|---------------|
| FD-0 | ADR amend (0010 + 0032) | Trellis + maintainer | co-author the render-surface framing |
| FD-1 | Front-door hub | **DesignQA** design → DX build | this brief + copy deck; render + tokens |
| FD-2 | Head metadata + OG + JSON-LD | DX + Resume confirm | supply OG "pulse" headline + `og:image` (cover header) |
| FD-3 | Indexing (sitemap/robots/llms.txt/alt) | DX | alt-text register for hub images |
| FD-4 | Repo crosslinks (Tier 1) | DX | voice-check any README hero copy |
| FD-5 | Trust deep-dive live on Pages | **DesignQA** render | realize Trust Your Sensor as a linked surface |
| FD-6 | Maker profiles + build-log | Maker-site lane / maintainer | brand assets (avatar/header, shipped #1066) |
| FD-7 | Teaser / motion deploy (later) | **DesignQA** | gated on the build-first / promotion gate (§9) |

**OG / social headline** (FD-2, DesignQA-supplied): *"Your plants have a pulse. I'm the one who tells you."* —
the strongest social card line; use it there, not as the on-page hero.
