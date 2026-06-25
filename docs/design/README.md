# Sprout design system · v1

The styling foundation for the plants project's dashboards and UI. A warm "lush + control-room" system
built specifically for a four-channel soil-and-watering controller at high data density, with full light
and **soil** (dark) themes. This is the source of truth for color, type, spacing, components, and -
importantly - *how a moisture reading is honestly represented*.

Origin: exported from [Claude Design](https://claude.ai/design) as a developer handoff. This v1 folds in
the analytics-thread review - the five instrument components plus the raw-vs-percentage correction.

**Visual index:** open [`Sprout Design Library.dc.html`](Sprout%20Design%20Library.dc.html) — the design
folder's front door: a clickable bookmark of every Sprout design page across v1, v2, v3, and brand.

**Runtime:** how the `support.js` runtime is versioned across these folders → [RUNTIME.md](RUNTIME.md).

> A broader **v2 brand delivery** (brand world, decks, social kit, narrative pieces, expanded system) was
> added 2026-06-23 alongside this folder — see [the Design Library](Sprout%20Design%20Library.dc.html). It is additive; this v1
> remains the source of truth for the dashboard/instrument UI.

## What's here

| File | What it is |
| --- | --- |
| [`sprout-design-system.dc.html`](sprout-design-system.dc.html) | The full design source - every token, component, and both in-context dashboards. The authoritative spec; read it top to bottom. Needs `support.js` (same folder) to render in the design tool. |
| [`support.js`](support.js) | Runtime for the `.dc.html` source (Claude Design). |
| [`sprout-tokens.css`](sprout-tokens.css) | The core tokens as ready-to-use CSS custom properties. Lift them directly; toggle `data-theme="dark"` for soil mode. |
| [`screenshots/`](screenshots/) | Rendered previews - `top` (cover), `personality` / `personality-dry` (the mood system), `ladder` (the calibration range ladder). |

## The non-negotiable principles

From the source's "Reading the signal" section and the dashboard team's data-integrity review. Build to
these:

- **Raw counts + band are the truth; a percentage is not.** The instrument value is inverted ADC raw
  (higher = drier). Any 0-100 figure is a clearly-labelled *relative index* between the wet/dry
  calibration anchors - never presented as VWC.
- **Mood/state derives from the calibrated band, never from the index.** A reading is one of seven
  bands; the band drives the mood, the status color, and any automation.
- **Every number is mono, right-aligned, tabular** (`--font-data` / JetBrains Mono). Data should always
  look like data.
- **State is color.** The `--st-*` and `--band-*` tokens name meaning; never recolor a band.

## How to use it

- **Tokens:** import or copy `sprout-tokens.css` and reference the variables. Fonts: Baloo 2 (display),
  Hanken Grotesk (UI), JetBrains Mono (data) - via Google Fonts or self-hosted.
- **Components:** recreate the components from the `.dc.html` source in whatever stack fits the target,
  matching the visual output rather than porting the prototype's structure. The analytics dashboard (E7)
  is self-contained HTML + Chart.js (the source's "Tokens for engineering" section carries Chart.js
  notes); a future served control page (D4) is React + TypeScript + Tailwind.
- **View it:** the screenshots give the gist; open `sprout-design-system.dc.html` (with `support.js`) in
  the design tool for the live, interactive version.

## Mapping to this project's data

The UI bands map 1:1 onto the firmware's seven-level enum; the names differ (friendly UI vs. engineering),
and the raw boundaries in the source are **placeholders** - the real per-pin numbers come from calibration.

| Sprout UI band | Firmware level (`moisture_classifier`) |
| --- | --- |
| Saturated | submerged |
| Wet | overwatered |
| Moist | well watered |
| Ideal | OK |
| Drying | needs water |
| Dry | DRY |
| Parched | air-dry |

The UI shows the friendly band names; firmware keeps its enum; boundary values come from the calibration
work and the A2 / 7-band reconciliation (see [`../../BACKLOG.md`](../../BACKLOG.md)).

## Status

**v1** - first version, ready for teams to build against. Covers foundations (color, type, space, radius,
elevation), the plant-personality mood system, the component library, data visualization, two in-context
dashboards (light + dark), and the five instrument components: dense data grid, analysis chart,
calibration range ladder, distribution + integrity, and engineering tokens.
