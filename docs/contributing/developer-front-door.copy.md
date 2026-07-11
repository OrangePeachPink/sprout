# Developer Front Door — section copy (#136)

> **Copy deck, not the page.** Design renders this into
> `docs/design/onboarding/Sprout Developer Front Door.dc.html` (served `.dc.html`, sibling to the User Front
> Door). Structured as a **hero paragraph + 6 sections** to map 1:1 onto the shell. DX owns the words; Design
> owns the render and the tokens.

## Hero

**Start Here for Developers.**

Sprout is a small, honest, self-watering plant project — and the friendliest repo you'll contribute to today.
However you arrive — fixing a typo, wiring a sensor, or just curious — there's a place for you. *Tend well.*

## 1. What Sprout is

Sprout keeps houseplants alive and stays honest about how: it reads soil moisture, waters on a schedule it can
defend, and never pretends a reading is better than the sensor that made it. It's a teaching project too — we eat
our own dogfood, so every part is built to be picked up, understood, and improved by the next person (yes, you).

## 2. Pick your lane

Work is split into areas you can take on independently:

- **Firmware** — the ESP32 controller (C / PlatformIO): sensing, watering logic, the safety gate.
- **Capture** — host-side logging that turns the serial stream into honest, timestamped data.
- **Analytics** — the dashboard and analysis tier that make the data readable.
- **Design** — the Sprout design system and the front doors (this page is one).

Not sure where you fit? That's what Discussions are for.

## 3. The work loop & the gate

How a change flows, idea to merge:

- **The ladder** — bigger work goes **PRD → ADR → issue → PR**: a PRD frames the *what* and *why*, an ADR records
  the decision, issues cut it into shippable pieces, and a PR delivers each one.
- **Your PR** — branch from `main` (`type/short-desc`), open a PR linking the issue with **`Refs #N`** (not
  `Closes #N`), and squash-merge to one tidy commit.
- **The verification gate** — merging doesn't auto-close the issue; a reviewer confirms it did what was asked,
  *then* closes it (ADR-0003 §8). That human confirmation is the point — it's how Sprout stays honest about
  what's really done.

New here? The gentle, walked-through version: [your first contribution](your-first-pr.md).

## 4. Set up your bench

*(Placeholder — the exact commands finalize when the setup epic (#113) and launcher (#151) land; wire the real
links in then.)*

Three installs and it works:

```text
git clone https://github.com/OrangePeachPink/sprout && cd plants
uv sync                     # the exact, locked dev environment
uv run pre-commit install   # the quality checks run themselves on every commit
just start                  # launch Sprout — opens the dashboard
```

Prefer zero install? Open it in **GitHub Codespaces** — the environment builds itself in the browser.

**On the firmware side, it's just as gentle — and there's no Arduino IDE.** The ESP32 firmware is a
**PlatformIO** project (it builds the Arduino framework underneath, so you write Arduino-API code without the
IDE or a cross-compiler). **Two first-class routes:** **VS Code + PlatformIO** locally, or **GitHub Codespaces**
in the browser — pick whichever fits. Either way the commands are the same: `just build` (compile) ·
`just test-native` (test — no board) · `just flash` (upload). Only the flash step needs a board on USB;
everything else, including CI, runs hardware-free. First flash? [FLASHING.md](../FLASHING.md) walks you in.

## 5. Where the work lives

- **Discussions** — questions and "should we…?" ideas. No setup question is too small.
- **Issues + [the board](https://github.com/users/OrangePeachPink/projects/2)** (Project #2) — concrete,
  shippable work. Start with **`good first issue`**.
- **Pull requests** — your change, one reviewable idea each.

## 6. Onward

Links that exist today:

- [README](../../README.md) — the project overview and quickstart.
- [Architecture decisions](../adr/0000-record-architecture-decisions.md) — why things are the way they are.
- [SECURITY.md](../../.github/SECURITY.md) — how to report a vulnerability.
- [Project status](../STATUS.md) — where things stand right now.
- [Your first contribution](your-first-pr.md) — the first-PR walkthrough.
- [Contributors Welcome](../CONTRIBUTORS_WELCOME.md) — where outside help is especially wanted, and how to start.

---

*Source copy maintained by DX (#136, under the Contributor Experience epic #133). Section order and titles above
are authoritative — replace the provisional shell titles with these. Design lays the prose into the shell.*
