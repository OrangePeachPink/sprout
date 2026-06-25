<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/design/brand/readme-hero.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/design/brand/readme-hero-light.png">
    <img src="docs/design/brand/readme-hero.png" alt="Sprout — plants that finally have a voice" width="100%">
  </picture>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-34A853" alt="MIT license">
  <img src="https://img.shields.io/badge/platform-ESP32-17B6C4" alt="ESP32">
  <img src="https://img.shields.io/badge/firmware-v0.7.0-8BD24F" alt="firmware v0.7.0">
  <img src="https://img.shields.io/badge/soil-honest-E8703A" alt="honest by default">
</p>

> **Hi, I'm Sprout.** I keep a windowsill of plants properly watered — and I tell you, in plain words, how
> each one is doing. No guesswork, no fake percentages: I read the soil honestly and speak for the plant.

---

## What Sprout is

Sprout is a small, honest, **automatic plant-care system** for a windowsill: capacitive soil-moisture probes
and a little pump, driven by an **ESP32**, with a **Python** logger and analytics behind it and a served
**dashboard** out front. It watches the soil, classifies it into seven calibrated moisture bands, and (once
calibration is in) waters before a plant is ever in trouble.

It's a learning-and-portfolio build, made to be **enjoyable to run and trustworthy to read** — process and
tooling sized to match, not over-engineered.

## How it works

```
   probe          ESP32             classifier            Sprout
   ─────          ─────             ──────────            ──────
   capacitive  →  raw ADC count  →  seven moisture   →   a mood, a first-person line,
   soil read      (higher = drier)  bands (calibrated)   and — when ready — a pump
```

The chain is deliberately honest: **raw counts and the calibrated band are the truth.** Any 0–100 figure is a
clearly-labelled *relative* index between the wet/dry anchors — never presented as real volumetric water
content. A plant's mood, its status color, and any watering all derive from the **band**, never from that
index.

## A look

<p align="center">
  <img src="docs/design/screenshots/personality.png" alt="Sprout's plant-personality mood system" width="82%">
</p>

<p align="center"><sub>The live dashboard (light + soil mode) serves at <code>tools/analytics/serve.py</code>; the design system &amp; mood system live in <a href="docs/design/">docs/design/</a>.</sub></p>

## The brand

Sprout isn't a readout — it's a **character**. The plant speaks for itself, in the first person, calm and
honest. The full identity, voice rules, the living mark, and the seven-band mood system are in the brand
guide:

- **[Brand guide](docs/design/brand/BRAND.md)** — voice, the living mark + motion, the mood↔band system, the
  character↔instrument boundary.
- **[Design system](docs/design/)** — tokens (`sprout-tokens.css`), instrument components, and the
  [v3 personality layer](docs/design/sprout-v3/).
- Decisions of record: **[ADR-0007 (brand &amp; voice)](docs/adr/0007-brand-guidelines.md)** ·
  **[ADR-0008 (personality layer)](docs/adr/0008-design-system-v3-personality-layer.md)**.

## Honest by default

A few principles the whole system is built to, so the data can always be trusted:

- **Raw + band = truth;** a percentage is a labelled relative index, never VWC.
- **Mood &amp; automation follow the calibrated band,** never the index.
- **Every number is mono, right-aligned, tabular** — data looks like data.
- **Gaps are surfaced, not smoothed** — the dashboard shows what the capture actually contains.

## Where to look

| Area | Path |
| --- | --- |
| Firmware (ESP32 / PlatformIO) | [`firmware/`](firmware/) |
| Host logger &amp; analytics | [`tools/`](tools/) |
| Design system &amp; brand | [`docs/design/`](docs/design/) |
| Decisions of record (ADRs) | [`docs/adr/`](docs/adr/) |
| Wiring · telemetry · calibration | [`docs/`](docs/) |

## Status

Currently **read-only observation** — four co-located probes capturing a full day at a time. Watering is
intentionally gated behind real per-probe calibration (the safety-first order: *make watering correct before
it's possible*). The firmware roadmap and current standing live in the
[handoff notes](docs/HANDOFF_2026-06-23.md).

---

<p align="center"><sub>Sprout · plants with a pulse · <b>tend well.</b></sub></p>
