# Sprout docs — the front door

Sprout keeps two front doors, and they point at each other. This is the **words** one: a map to
every doc, organized by **who it's for**, so you land on the right page instead of guessing at a file
list. The **visual** one is the [**Sprout Design Library**](design/README.md) — the clickable index of
the whole design system.

> **In a hurry?** Jump to your lane:
> [🌱 Use Sprout](#-using-sprout) · [🛠 Contribute](#-contributing) · [🌍 Community](#-community) ·
> [🔧 Run the project](#-running-the-project-maintainer) · [📓 Reference & evidence](#-reference--evidence)

Every doc below names **who it's for** and **what it answers** — so a reader, a contributor, a
maintainer, and a curious community member each find their own path from one page.

---

## 🌱 Using Sprout

*Audience: you have (or want) a Sprout running and want it to work.*

| Doc | What it answers |
| --- | --- |
| [What you need](user/what-you-need.md) | The parts + tools to get started. |
| [Build & run](user/build-and-run.md) | Wire it, flash it, bring it up. |
| [What Sprout is telling you](user/what-sprout-is-telling-you.md) | Reading the moods, bands, and honest numbers. |
| [Trust your sensor](user/trust-your-sensor.md) | Why the readings are honest, and when to doubt one. |
| [Friendly troubleshooting](user/friendly-troubleshooting.md) | It's acting up — plain-language fixes. |
| [Operating collection](operating-collection.md) | Start/stop/reclaim collection headlessly, without the dashboard. |
| [Wiring](WIRING.md) · [Sensor calibration](SENSOR_CALIBRATION.md) · [Sensor QA](../SENSOR_QA.md) | The hardware specifics. |
| [Glossary](GLOSSARY.md) | Every Sprout term in one place (shared with contributors). |

---

## 🛠 Contributing

*Audience: you're changing code, docs, or firmware.*

| Doc | What it answers |
| --- | --- |
| [CONTRIBUTING](../.github/CONTRIBUTING.md) | **Start here** — the one path from idea to merge (~5 min). |
| [Developer front door](contributing/developer-front-door.copy.md) · [Your first PR](contributing/your-first-pr.md) | The gentle on-ramp. |
| [Contributors welcome](CONTRIBUTORS_WELCOME.md) | Where you fit, however you arrived. |
| [Arduino on-ramp](contributing/arduino-onramp-north-star.md) · [Arduino starter](contributing/arduino-starter.md) | New to microcontrollers? Graduate into the project. |
| [Firmware: FLASHING](FLASHING.md) · [BRINGUP](BRINGUP.md) · [PlatformIO troubleshooting](PLATFORMIO_TROUBLESHOOTING.md) | The firmware toolchain, first flash, and the dev-env gotchas. |
| [Architecture Decision Records](adr/) | *Why* things are the way they are — decisions of record (ADR-0000 → ADR-0028). |
| [AGENTS.md](../AGENTS.md) | Working rules for the AI agents in the lane workflow. |

---

## 🌍 Community

*Audience: you're here to talk, follow along, or use Sprout responsibly.*

| Doc | What it answers |
| --- | --- |
| [README](../README.md) | What Sprout is — the product front page. |
| [Discussions](community/discussions.md) | Where questions and "should we…?" ideas go. |
| [Release-notes voice](community/release-notes-voice.md) | How Sprout talks about what shipped. |
| [Changelog](../CHANGELOG.md) | What actually shipped, per release. |
| [Code of Conduct](../CODE_OF_CONDUCT.md) · [Security policy](../SECURITY.md) | The ground rules and how to report a concern. |

---

## 🔧 Running the project (maintainer)

*Audience: you cut releases, run the board, and steward the process.*

| Doc | What it answers |
| --- | --- |
| [Release cut checklist](process/RELEASE_CUT.md) | The turnkey per-release ritual (ADR-0009 §6). |
| [Release checklist (→ public)](process/RELEASE_CHECKLIST.md) | The one-time go-public gate (secrets/PII/license/CI). |
| [Adoption](process/ADOPTION.md) · [Bench preflight](process/BENCH_PREFLIGHT.md) | Bringing a machine/bench into the workflow safely. |
| [Design export contract](process/design-export-contract.md) | How design assets cross into the app. |
| [STATUS](STATUS.md) | The current-state snapshot. |
| [ADRs](adr/) | The decision log the whole project is built on. |

---

## 📓 Reference & evidence

*Audience: you need the hard specifics, the provenance, or a bench record.*

| Where | What it holds |
| --- | --- |
| [Hardware: BOARDS](hardware/BOARDS.md) · [watchdog-wedge verify](hardware/watchdog-wedge-bench-verify.md) | The board support matrix + bench-verification procedures. |
| [Telemetry schema](TELEMETRY_SCHEMA.md) | The canonical row contract (schema-v3). |
| [Bench procedures](bench-procedures/) | Preflight, environment-evidence, dry/wet run sheets, S3/C5 bring-up. |
| [Experiments](experiments/) | Bench-session logs + captured data records (raw evidence, preserved). |
| [Evidence](evidence/) | Intake + go-live evidence packets (photos, enumerations). |
| [Capacitive-sensor research](RESEARCH_capacitive_soil_moisture_sensors.md) | The sensor-domain background. |

---

## 🎨 The other front door — the Design Library

Everything **visual** — brand, voice, the living mark, motion, tokens, components — lives in the
[**Sprout Design Library**](design/README.md) (its clickable index is
[`Sprout Design Library.dc.html`](design/Sprout%20Design%20Library.dc.html)). Per
[ADR-0010](adr/0010-design-library-front-door.md): *if an asset is live, it's in the Library; if it
isn't, it's archived.* These two front doors link to each other — start at either, reach both.

---

## Gaps & the consistency pass

**Named gaps** (tracked so they don't hide):

- The dated `HANDOFF_2026-06-23*.md` notes at `docs/` root are one-off session handoffs, not living
  docs — archive candidates (they clutter the root of an otherwise audience-mapped tree).
- User docs are split between `docs/user/` and root-level `WIRING.md` / `SENSOR_CALIBRATION.md`;
  a future pass could consolidate the "run Sprout" path under one roof.
- Community/maintainer split is thin — several docs serve both; audience labels above are the
  primary reader, not the only one.

**The consistency pass — a standing DX duty.** Docs accrete per-PR with no one watching the whole,
which is how drift and contradictions creep in (the #677 and #690 passes both fixed drift a map would
have caught earlier). So: **once per release, DX runs a "docs don't lie about what's built" sweep** —
every front-page claim checked against shipped reality, every new doc slotted into an audience above,
every gap re-named. This front door is the checklist's home; keeping it true is the duty.

---

*This is the map; the [Design Library](design/README.md) is the gallery. Either door reaches both.*
