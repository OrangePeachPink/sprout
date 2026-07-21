# Platform metadata — the repo-side source of truth

Some of Sprout's public brand surface **is not a file**. Repository topics, the description,
the website field, and the social preview live as *uploaded platform state*: invisible to
`grep`, unreachable by CI, and — in the social preview's case — with no API at all.

That is the blind-spot class [#1403](https://github.com/OrangePeachPink/sprout/issues/1403)
names: the retired "refuses to lie" preview card survived every voice sweep because the sweeps
could only see files. **This file is the fix**: the canonical values live here, in the repo, so
the checklist has something to diff the live platform against.

**This file does not apply anything.** Topics and the rest are public brand metadata — the
maintainer applies them (a click, or `gh repo edit` with her word). Changing this file is a
proposal until she does.

## Repository topics

GitHub allows **20**; lowercase, digits and hyphens only.

**Canonical set — 15 topics** (proposed 2026-07-20, #1403; pending the maintainer's apply):

```text
esp32                 arduino               embedded
soil-moisture-sensor  plant-monitoring      plant-care
smart-garden          home-automation       gardening
houseplants           plants                local-first
self-hosted           offline-first         diy-electronics
```

### How to check the live set against this list

```bash
gh repo view --json repositoryTopics -q '[.repositoryTopics[].name] | sort | join("\n")'
```

### How to apply (maintainer)

```bash
gh repo edit --add-topic <topic>     # one at a time, or
gh repo edit --remove-topic <topic>
```

### Why these, and not others

Topics are **discovery surfaces, one per tag** — so the question for each is *"does someone
who would like Sprout actually type this?"*, not *"is this technically true of the code?"*

- **Hardware intent** (`esp32`, `arduino`, `embedded`, `soil-moisture-sensor`) — the people
  who already own the board. `esp32` is the single highest-value tag we hold.
- **The plant audience** (`plant-monitoring`, `plant-care`, `smart-garden`, `gardening`,
  `houseplants`, `plants`) — the audience that would love this and **will never type
  `esp32`**. Six of the twenty slots is a deliberate bet on them, not redundancy: someone
  browsing `houseplants` and someone browsing `smart-garden` are different people.
- **The differentiator** (`local-first`, `self-hosted`, `offline-first`) — what actually makes
  Sprout unusual now that the honesty framing is retired. `self-hosted` in particular is a
  large, active topic community whose values are exactly ours.
- **Adjacent** (`home-automation`, `diy-electronics`) — the Home Assistant and maker crowds.

**Deliberately not carried:**

| Not a topic | Why |
|---|---|
| `python`, `dashboard` | Implementation detail, and both are oceans — Sprout will never surface in either. A topic that cannot be found through is a slot spent on nothing. |
| `platformio` | A build system, not an audience. Anyone searching it arrives via `esp32` anyway. |
| `iot` | Generic, enormous, and **pointing the wrong way**: `iot` connotes cloud-connected devices, which is precisely what Sprout is not. Swapping it for `local-first` is a positioning fix, not just a tidy-up. |
| `smart-irrigation` | **Held until pumps ship** (v0.9.0). Autonomous watering is gated behind calibration and the safety bench, so the tag would claim a capability the project deliberately refuses to claim anywhere else. Re-add it the day it becomes true. |

Five slots stay free — headroom for `smart-irrigation`'s return and whatever the next real
audience turns out to be. Empty slots cost nothing; a tag nobody searches costs credibility.

## Other platform-uploaded surfaces

Tracked here as they are settled, so the checklist has one place to diff:

| Surface | Canonical source | API? |
|---|---|---|
| Repository topics | this file | `gh repo edit` |
| Social preview image | `docs/design/brand/social-preview.png` | **none — web UI only** |
| Description / website | *(not yet recorded here)* | `gh repo edit` |

— DX
