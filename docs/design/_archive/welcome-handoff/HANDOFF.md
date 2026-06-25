# Design-lane handoff — the repo-home welcome ("a day in the life of Sprout")

**From:** Design lane · **Date:** 2026-06-24 · **Re:** the animated welcome for the repository home
**Flow:** I zip → relay to the commit-proxy → the proxy places each file per the manifest, commits after review.
(Repo stays read-only for Design; this lands via the proxy, not a direct push.)

> The welcome gift from the onboarding note — seeded as an Ideas Discussion, vision owned by Design. It's a
> self-running "day in the life" built to draw people in the moment they land on the repo: Sprout wakes at
> dawn, a rain passes through, the midday sun arcs over, dusk settles, and it sleeps — with the **honest
> instrument reading the soil right beside the plant** the whole time. Additive; it touches nothing in the
> dashboard/instrument system.

---

## Manifest — place every file exactly here

| In this zip | → Destination in repo | What / why |
|---|---|---|
| `docs/design/Sprout Welcome.dc.html` | `docs/design/Sprout Welcome.dc.html` | The **source of truth** — the live Design Component. Renders with the existing `docs/design/support.js` (already in that folder; not re-shipped). |
| `docs/design/Sprout Welcome (standalone).html` | `docs/design/Sprout Welcome (standalone).html` | **Self-contained** single file (runtime + fonts inlined). Opens offline in any browser — this is what you record for the README and what you can link as the live page. |
| `docs/design/Sprout Design Library.dc.html` | `docs/design/Sprout Design Library.dc.html` | **Updates the existing file** — adds the Welcome bookmark to the *Motion & character* shelf and bumps the page count (15 → 16). |
| `docs/design/library/thumbs/welcome.png` | `docs/design/library/thumbs/welcome.png` | Thumbnail for the new library card (909×540, 27 KB). |

Suggested commit: `docs(brand): add animated repo-home welcome + library bookmark`.

## Putting it on the README

GitHub READMEs don't run JavaScript, so the embed is a **looping image/video**; the live page is **linkable**.
Pick one:

1. **Record a loop (recommended).** Open `Sprout Welcome (standalone).html`, let one full day play, and screen-record
   ~one loop. Export a **GIF** (simplest) or an **MP4 / WebM** (crisper, smaller) and commit it as
   `docs/design/welcome.gif` (or `.mp4`). Then at the very top of `README.md`:
   ```html
   <p align="center">
     <a href="docs/design/Sprout Welcome (standalone).html">
       <img src="docs/design/welcome.gif" alt="A day in the life of Sprout" width="100%">
     </a>
   </p>
   ```
   (A `<video autoplay loop muted playsinline>` works in GitHub Markdown too, if you prefer MP4.)
2. **Link only.** Keep the current static hero and add a one-line link to the live standalone page for anyone
   who wants to watch it move.

**Loop length:** ~26s by default (one calm, ambient day). For a snappier README GIF, shorten it — see the tweak below.

**Capturing a specific frame** (for a social still or a fixed hero): set `localStorage` key
`sprout_welcome_freeze` to a value `0`–`1` (0 = midnight, 0.5 = midday, 0.83 = dusk) and reload — the scene holds
at that time of day. Set it back to `""` to resume the loop.

## What's intentional (so it survives edits)

- **Honesty thread, kept whole.** Mood is a 1:1 function of the **calibrated moisture band** (one of seven),
  never of the 0–100 figure. The card labels the data plainly — `RAW · HIGHER=DRIER` and `INDEX · RELATIVE` —
  and the rain genuinely raises the soil index before the plant perks up. This is ADR-0007 §5 on screen.
- **Character beside the instrument, never inside it.** The plant (character) and the readout card (instrument)
  sit side by side, both reading the same band — the ADR-0007 §6 boundary, made literal. No character inside the
  numbers.
- **Tokens & type are the system's.** Leaf / Sprout / the seven `--band-*` colors, Baloo 2 · Hanken Grotesk ·
  JetBrains Mono — all consumed, not redefined (ADR-0004).
- **Reduced-motion is honored.** `prefers-reduced-motion` freezes a calm midday frame; no motion.
- **An occasional companion bloom.** Now and then (~1 in 3 loops, lightly randomized — not every time) a second
  sprout rises after the rain and both open a small flower. A quiet reward for anyone who lingers; it's never the
  default state. (Adapted from the "blooming after a rain" idea — kept calm, no slapstick.)

## Tweakables (code-level, on the Design Component)

Three props on the root, for whoever generates the capture:

- `loopSeconds` (8–60, default 26) — day length. Drop to ~12–16 for a tighter README GIF.
- `showReadout` (default on) — show/hide the instrument card.
- `showCaption` (default on) — show/hide Sprout's first-person line.

Copy text (the captions, "Hi, I'm Sprout.", the honesty footnote) is editable in place. All lines follow the voice
rules — first person, fact then feeling, one line, no fake numbers.

## Notes for the Workflow lane

- Nothing here gates anything; it's additive brand polish. Place it whenever convenient.
- The library bookmark + thumb are a paired update — keep them together.
- If you'd like the loop pre-rendered as a committed GIF/MP4 rather than recorded on your side, say the word and
  I'll spec exact frames/length for it.
