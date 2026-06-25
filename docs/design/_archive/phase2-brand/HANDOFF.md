> ⚠️ **SUPERSEDED — archived 2026-06-25.** Archeology only; do not build from this. The entire v3 set (tokens,
> the mark component, motion, the JSON maps, the v3 page, ADR-0008) lives in current, aligned form in the
> **Sprout Design Library** under *Tokens, code & components* and *Voice & personality*. Kept only as history.

# Design-lane handoff — Phase 2: the v3 personality layer (ACCEPTED — ready to commit)

**From:** Design lane · **Date:** 2026-06-24 · **Re:** design system v3 — personality layer + refined soil mode
**Flow:** I zip → Veronica relays to a proxy coding agent → the proxy places each file per the manifest,
applies the repo edits, and commits.

> **Status: Accepted.** The v3 personality layer **and** the v1 soil-mode token change were reviewed and
> approved on 2026-06-24. This package is ready to commit as-is. Does **not** touch the backlog or GitHub
> issues (no-fly). All files are text/HTML/JS/JSON/CSS; **no binaries, nothing needs Git LFS.**

---

## Manifest — place every file exactly here

| In this zip | → Destination in repo | What / why | Who consumes |
|---|---|---|---|
| `docs/design/sprout-tokens.css` | `docs/design/sprout-tokens.css` | **REPLACES the existing file.** Identical to v1 except the `[data-theme="dark"]` block, whose neutrals are refined to cool green-charcoal (the approved soil-mode change). Light mode + all `--st-*` / `--band-*` colors unchanged. | Data, all UI |
| `docs/design/sprout-v3/README.md` | `docs/design/sprout-v3/README.md` | v3 overview (Accepted), invariants, deltas, rationale. | Workflow, Design |
| `docs/design/sprout-v3/mood-band-map.json` | `docs/design/sprout-v3/mood-band-map.json` | **Canonical** 1:1 band→mood map. | **Data** (band→mood) |
| `docs/design/sprout-v3/sprout-mark.js` | `docs/design/sprout-v3/sprout-mark.js` | Living mark as a drop-in custom element `<sprout-mark band="…">`. Vanilla, reduced-motion aware. | **Data** (hero/empty/ambient) |
| `docs/design/sprout-v3/voice-strings.json` | `docs/design/sprout-v3/voice-strings.json` | First-person line pool, keyed by mood + surface. | **Data**, GitHub surface (Phase 3) |
| `docs/design/sprout-v3/sprout-motion.css` | `docs/design/sprout-v3/sprout-motion.css` | Sway/breathe/droop/bob keyframes for hand-rolled marks. | anyone animating a bespoke mark |
| `docs/design/sprout-v3/sprout-mark-demo.html` | `docs/design/sprout-v3/sprout-mark-demo.html` | Standalone page running the real component in all 7 states. | reviewers, devs |
| `docs/design/sprout-v3/Sprout v3 Personality Layer.dc.html` | `docs/design/sprout-v3/Sprout v3 Personality Layer.dc.html` | Living visual record: before/after, deltas, 7 states, refined soil mode. | reviewers |
| `docs/design/sprout-v3/INCORPORATION.md` | `docs/design/sprout-v3/INCORPORATION.md` | **For-lanes** adoption note (Data + Firmware). | **Data + Firmware** |
| `docs/design/sprout-v3/support.js` | `docs/design/sprout-v3/support.js` | Claude Design runtime for the `.dc.html` (byte-identical to the v1/v2/brand copies). | runtime only |
| `docs/adr/0008-design-system-v3-personality-layer.md` | `docs/adr/0008-design-system-v3-personality-layer.md` | The ADR ratifying v3 (Accepted). | all lanes |

> Note: the soil-mode change ships **inside `sprout-tokens.css`** (one tokens file) — there is no separate
> `sprout-soil-mode.css`.

## Repo edits to apply

1. **Replace** `docs/design/sprout-tokens.css` with the version in this zip (only the dark block changed).
2. **Add the register row** in `docs/adr/0000-record-architecture-decisions.md`:
   ```
   | [0008](0008-design-system-v3-personality-layer.md) | Design system v3: the personality layer | **Accepted** | Design lane / design |
   ```
3. **Optional link:** in `docs/adr/0002-process-tiers.md`, link area #18's row to ADR-0008 alongside the
   existing ADR-0004 / ADR-0007 links. No other `0002` change.
4. **No other v1/v2 edits** — everything else is additive new files.

Suggested commit (Conventional Commits, per ADR-0002 #9): `feat(design): add v3 personality layer + refine
soil-mode dark neutrals (ADR-0008)`.

## For the lanes (the binding rules — see `INCORPORATION.md`)

- **Data:** read `mood-band-map.json` to turn a band into a mood; drop `<sprout-mark>` onto hero/empty/loading
  surfaces; pull copy from `voice-strings.json`. **Keep the dense numeric readouts mark-free.** Soil mode
  needs nothing extra — the refined neutrals are already in `sprout-tokens.css`.
- **Firmware:** no code change — the map keys off the existing seven-level enum. On A2, only the band column
  of `mood-band-map.json` moves; coordinate that edit with Design (it owns the map).
- **Token contract (ADR-0004) holds:** color/type consumed from `sprout-tokens.css`.

## Heads-up acknowledged

The Firmware-lane markdown-lint normalization may reflow tables in my brand/v3 markdown — understood as a
content-neutral style pass; no action needed from me.

## After this

I **hold for the no-fly lift + assigned issues**, with **Phase 3** (GitHub-facing surface: README hero, social
preview, issue-form voice, label palette, CONTRIBUTING/PR voice, Discussions copy, release-notes tone) ready
to co-build on the locked brand.
