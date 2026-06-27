# Start Here — for Developers

> **Copy deck for the Developer Front Door (#136).** Design renders these words into the page shell
> (`.dc.html`, the way the User Front Door shipped in #180); this Markdown is the *source of the copy*. The
> section headings below map to page sections.

## Hero

**Sprout — the friendliest repo you'll contribute to today.**

A small, honest, self-watering plant project: embedded C on an ESP32, Python on the host, and a design system
that actually gets eaten as dogfood. However you arrive — fixing a typo, wiring a sensor, or just curious —
there's a place for you. *Tend well.*

## What Sprout is

Sprout keeps houseplants alive and is honest about how. It reads soil moisture, will water on a schedule it can
defend, and never pretends a reading is better than the sensor that made it. It's also a teaching project: every
part is built to be picked up, understood, and improved by the next person — including you.

## How it's built (find your corner)

Four areas, each contributable on its own:

- **Firmware** — the ESP32 controller (C / PlatformIO): sensing, the watering logic, the safety gate.
- **Capture** — host-side logging that turns the serial stream into honest, timestamped data.
- **Analytics** — the dashboard and the analysis tier that make the data readable.
- **Design** — the Sprout design system and the front doors (this page is one of them).

Not sure where you fit? That's exactly what Discussions are for.

## Where work lives

One clean path from idea to merge:

- **Discussions** — questions and "should we…?" ideas. No setup question is too small.
- **Issues + [the board](https://github.com/users/OrangePeachPink/projects/2)** — concrete, shippable work; look
  for **`good first issue`**.
- **Pull requests** — your change; we squash-merge to one tidy commit.
- **The verification gate** — merging a PR doesn't auto-close its issue. A reviewer confirms the change did what
  was asked, *then* closes it. That human confirmation is the point — it's how Sprout stays honest about what's
  really done versus merely merged.

## Start in about five minutes

```text
git clone https://github.com/OrangePeachPink/plants && cd plants
uv sync                     # the exact, locked dev environment
uv run pre-commit install   # the quality checks run themselves on every commit
just start                  # launch Sprout — opens the dashboard
```

Prefer zero install? Open it in **GitHub Codespaces** — the environment builds itself in the browser.

## Then what

- **Your first change, walked through gently** → the [first-contribution guide](your-first-pr.md).
- **The full contributor reference** → [`CONTRIBUTING.md`](../../.github/CONTRIBUTING.md).
- **Why things are the way they are** → the [ADRs](../adr/).
- **Run the checks exactly like CI does** → `just check`.

## The promise

Sprout designs the *arrival* for everyone who shows up — designers, the people who run it, and you, the
developer. Most projects make you fend for yourself at the door; this one made you a place. Welcome in. 🌱

---

*Source copy maintained by DX (#136, under the Contributor Experience epic #133). Design owns the rendered page
shell and tokens; these are the words that fill it.*
