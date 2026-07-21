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

**Canonical set — 20 topics** (maintainer-ruled 2026-07-20, #1403). **All 20 slots are
now used** — a future addition means dropping something.

```text
esp32                 arduino               embedded
platformio            soil-moisture-sensor  moisture-sensor
capacitive-sensor     datalogger            plant-monitoring
plant-care            smart-garden          smart-irrigation
gardening             indoor-gardening      houseplants
plants                home-automation       local-first
self-hosted           diy-electronics
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
- **Adjacent** (`home-automation`, `diy-electronics`, `datalogger`) — the Home Assistant
  and maker crowds, plus the instrumentation people. `datalogger` is the only tag here
  that describes what Sprout does *today* with no roadmap in it: the host logger writes
  timestamped, rotating, self-describing CSVs, which is precisely that.

### Sizing: why small topics, not big ones

Topic pages rank by **stars**, so a 3-star repo only *surfaces* on small topics. Measured
2026-07-20 via `gh api "search/repositories?q=topic:<t>&per_page=1" -q .total_count`:

| Topic | Repos | What it buys |
|---|---|---|
| `indoor-gardening` · `capacitive-sensor` | 4 · 4 | Page one guaranteed — but so small there may be little traffic to place in |
| `houseplants` | 27 | Page one, and the least technical audience we reach |
| `smart-garden` · `plant-care` · `plant-monitoring` · `moisture-sensor` | 53 · 83 · 96 · 99 | **The working band** — confirmed live on the topic pages |
| `soil-moisture-sensor` · `datalogger` | 204 · 200 | Findable |
| `gardening` · `plants` · `diy-electronics` | 399 · 876 · 587 | Moderate |
| `local-first` · `self-hosted` | 10.8k · 22.9k | Buried for browsing — carried for **filter-match** (`topic:local-first topic:esp32`), a different job |

Carrying a tag never hurts placement on any other tag, so the only scarce resource is the
slot count.

**Deliberately not carried:**

| Not a topic | Why |
|---|---|
| `python`, `dashboard` | Implementation detail, and both are oceans — Sprout will never surface in either. A topic that cannot be found through is a slot spent on nothing. |
| `iot` | 28k repos: unreachable by browsing, and **pointing the wrong way** — `iot` connotes cloud-connected devices, which is precisely what Sprout is not. Re-adding it for filter-match was considered and declined: topics are visible brand text on the card, `local-first` and `iot` side by side read as a contradiction, and four hardware tags already cover any plausible hardware filter. |
| `irrigation` (292) | Right size, but it doubles down on the not-yet-shipped watering capability — see the `smart-irrigation` ruling below. |
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
| **Gravatar** (avatar + profile shown beside commits on some surfaces) | `docs/design/brand/` mark assets | **none — gravatar.com only** |
| **Hackaday.io** project blurb + profile | the maker-profile copy deck | **none — web UI only** |
| **Hackster.io** project story + profile | the maker-profile copy deck | **none — web UI only** |

**Third-party unfurl caches are a fourth kind of stale**, and not fixable from here: after
the social preview is re-uploaded, LinkedIn holds its copy roughly a week, and Slack and
Discord cache too. Any link shared before the change keeps rendering the old card until it
expires. The one worth acting on is a **LinkedIn Featured** entry — removing and re-adding
the link forces a fresh scrape, and that is a surface with a reader on the other end.

— DX
