# Platform metadata — the repo-side source of truth

Some of Sprout's public brand surface **is not a file**. Repository topics, the description,
the website field, and the social preview live as *uploaded platform state*: invisible to
`grep`, unreachable by CI, and — in the social preview's case — with no API at all.

That is the blind-spot class [#1403](https://github.com/OrangePeachPink/sprout/issues/1403)
names: the retired "refuses to lie" preview card survived every voice sweep because the sweeps <!-- voice-guard: allow -->
could only see files. **This file is the fix**: the canonical values live here, in the repo, so
the checklist has something to diff the live platform against.

**This file does not apply anything.** Topics and the rest are public brand metadata — the
maintainer applies them (a click, or `gh repo edit` with her word). Changing this file is a
proposal until she does.

## Repository topics

GitHub allows **20**; lowercase, digits and hyphens only.

**Canonical set — 16 topics** (maintainer-ruled 2026-07-20, #1403):

```text
esp32                 arduino               embedded
platformio            soil-moisture-sensor  plant-monitoring
plant-care            smart-garden          smart-irrigation
home-automation       gardening             houseplants
plants                local-first           self-hosted
diy-electronics
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
- **The differentiator** (`local-first`, `self-hosted`) — what actually makes
  Sprout unusual now that the honesty framing is retired. <!-- voice-guard: allow --> `self-hosted` in particular is a
  large, active topic community whose values are exactly ours.
- **Adjacent** (`home-automation`, `diy-electronics`) — the Home Assistant and maker crowds.

**Deliberately not carried:**

| Not a topic | Why |
|---|---|
| `python`, `dashboard` | Implementation detail, and both are oceans — Sprout will never surface in either. A topic that cannot be found through is a slot spent on nothing. |
| `iot` | Generic, enormous, and **pointing the wrong way**: `iot` connotes cloud-connected devices, which is precisely what Sprout is not. Swapping it for `local-first` is a positioning fix, not just a tidy-up. |
| `offline-first` | Dropped in favour of keeping `platformio` — near-synonymous with `local-first`, so it was the cheapest of the two to lose. |

**Two maintainer rulings on this set**, recorded so they are not re-litigated:

- **`platformio` stays.** DX proposed dropping it as "a build system, not an audience"; the
  maintainer kept it. It is true, it is a real if smaller topic community, and it costs one slot
  of twenty. `offline-first` was dropped instead — near-synonymous with `local-first`, so it was
  the cheaper of the two to lose.
- **`smart-irrigation` stays.** DX flagged it as claiming a capability gated behind calibration
  and the safety bench, and recommended holding it until pumps ship. **Ruled the other way:**
  topics are loose by convention and it is genuinely where the project is going. Not an
  oversight — a decision.

Four slots stay free. Empty slots cost nothing; a tag nobody searches costs credibility.

## Other platform-uploaded surfaces

Tracked here as they are settled, so the checklist has one place to diff:

| Surface | Canonical source | API? |
|---|---|---|
| Repository topics | this file | `gh repo edit` |
| Social preview image | `docs/design/brand/social-preview.png` | **none — web UI only** |
| Description / website | *(not yet recorded here)* | `gh repo edit` |

— DX
