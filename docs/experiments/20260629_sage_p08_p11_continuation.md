# P08-P11 bench continuation - findings

**Date:** 2026-06-29 local CDT
**Lane:** Sage
**Authority:** BENCH EVIDENCE, monitor-log bounded.
Machine sidecar: [`20260629_sage_p08_p11_continuation.json`](20260629_sage_p08_p11_continuation.json).

## Scope

This file continues the 2026-06-29 Sage bench survey after the recovered P01-P07
thread evidence. P08-P11 are tracked here to keep the P01-P07 recovery report
focused on the broken-thread reconstruction.

Primary source log so far:

- `logs/Sprout ESP32_20260629_180631.csv`

## P08 notes

P08 is a very small cactus. The user recalled that it may have been listed as a
"moon cactus" when purchased. Description before measurement: green triangular
base/rootstock, pink round top with peaks, one larger pink round dome, and three
smaller pink round domes off the side. Treat "moon cactus" / grafted cactus as
likely but not confirmed.

Care-history note: P08 is normally allowed to dry to fully dry, and watering is
usually only a few drops when it is watered at all.

Setup:

- Only a limited probe placement is possible because the pot/plant is very
  small.
- `s1` and `s3` were inserted in the pot and reading live.
- User confirmed `s1` and `s3` had real soil contact.
- Orientation note: `s3` had its front side facing soil/dirt and its back side
  near the pot wall. `s1` was reversed: its back side faced soil/plant, while
  its front side faced the pot wall. This was accidental placement, not an
  intentional test.
- `s2` and `s4` should be treated as open-air references unless later notes say
  they were moved into soil.
- At about 16:10 local, the user pulled the inner pot from the outer pot and
  began a small watering because P08 had not been watered in a long time.
- Watering update: about 1/4 cup was applied, and some excess leaked into the
  temporary bench bowl fixture.
- Orientation check update: at 16:17 local, `s1` was pulled and reinserted with
  its orientation switched. This is exploratory only: pulling/reinserting can
  change contact, depth, local soil packing, and water path.

Monitor-log tail at 2026-06-29 16:06:27 local:

| Sensor | Raw | Band | Interpretation |
|---|---:|---|---|
| s1 | 3274 | air-dry | In P08 pot, but reading like fully dry soil/open air |
| s2 | 3169 | air-dry | Open-air reference unless later corrected |
| s3 | 3176 | air-dry | In P08 pot, but reading like fully dry soil/open air |
| s4 | 3183 | air-dry | Open-air reference unless later corrected |

Interpretation: if `s1` and `s3` have real contact, the cactus medium is
reading essentially air-dry. That can be normal and healthy for this plant type,
but the user's care-history judgment is that P08 is due for a very small
watering. This should be documented as a **micro-dose cactus watering**, not a
houseplant rescue pour.

Post-water tail at 2026-06-29 16:12:32 local:

| Sensor | Raw | Band | Interpretation |
|---|---:|---|---|
| s1 | 2921 | dry | Inserted; moved wetward but still dry |
| s2 | 3191 | air-dry | Open-air reference |
| s3 | 1977 | needs water | Inserted; clear local wetward response |
| s4 | 3154 | air-dry | Open-air reference |

Interpretation: the watering reached the `s3` local zone first and only weakly
reached the `s1` local zone by this point. The response difference may reflect
local wetting path, pot-wall proximity, insertion angle/depth, or probe
front/back orientation. It should not be treated as a clean front/back sensor
test because those variables are confounded. The bowl leakage means 1/4 cup was
already enough to exceed the tiny pot's immediate holding capacity or flow
through part of the medium. No additional water should be added during this
segment; let the inner pot drain fully before returning it to the outer pot.

Exploratory `s1` orientation-switch tail:

| Time local | s1 raw | s1 band | s3 raw | s3 band | Note |
|---|---:|---|---:|---|---|
| 16:17:12 | 3071 | dry | 1377 | well watered | immediately after/near orientation switch |
| 16:18:37 | 3139 | air-dry | 1482 | well watered | `s1` did not show a wetward jump in first ~90 s |

Interpretation: after the `s1` flip, `s1` still read dry/air-dry while `s3`
remained much wetter. This does not prove one side is blind, because the flip
also changed insertion/contact. It does strengthen the case for a controlled
front/back orientation test later in uniform soil.

Dashboard trace note: the blue `s1` trace shows a small disturbance at the
pull/reinsert point, then returns to roughly its prior dry/air-dry neighborhood
rather than stepping down toward the wetter `s3` region. This visual pattern is
consistent with a handling transient, not a clear wet-contact response.

Remaining markers:

- P08 pull/prep transition started around 16:24 local. Final removal/contact
  condition still pending if observed.
- Final runoff/bowl estimate if easy.

## P09 notes

P09 is a small succulent. Visual description before measurement: aloe-like but
not specifically Aloe vera; many thinner and more numerous leaves/spines,
roughly 50 small 2-3 inch long leaves/spines in an approximately 2.5 inch
diameter pot. The rich dark green leaves come from three central cores. The
leaves have small white polka-dot-like points that are actually tiny soft
spines/points and are gentle to touch. Exact ID unconfirmed.

Setup:

- P09 had essentially no open soil area for a normal probe insertion.
- User observed that the soil is essentially entirely consumed by the
  roots. Treat P09 as rootbound / root-dominated unless a later inspection
  corrects that.
- At 16:28 local, the plant was lifted out of the soil enough to place one
  probe between the root ball and surrounding soil.
- Treat this as a **rootball-interface measurement**, not a normal in-soil
  insertion and not a calibration-quality dry baseline.
- The active physical probe was not explicitly named in the user note, but log
  behavior strongly indicates `s3`: `s3` stepped from open-air/air-dry behavior
  into a stable dry-band reading while `s1`, `s2`, and `s4` remained air-dry.

Selected monitor-log samples around the 16:28 placement:

| Time local | s1 raw/band | s2 raw/band | s3 raw/band | s4 raw/band | Interpretation |
|---|---|---|---|---|---|
| 16:28:07 | 3419 / air-dry | 3156 / air-dry | 3020 / air-dry | 3173 / air-dry | pre/early placement tail |
| 16:28:17 | 3414 / air-dry | 3154 / air-dry | 2925 / dry | 3171 / air-dry | `s3` enters dry band |
| 16:29:02 | 3418 / air-dry | 3157 / air-dry | 2921 / dry | 3172 / air-dry | `s3` stable dry; others open-air-like |
| 16:30:17 | 3394 / air-dry | 3156 / air-dry | 2944 / dry | 3172 / air-dry | `s3` still dry after settling |
| 16:31:52 | 3400 / air-dry | 3158 / air-dry | 2949 / dry | 3176 / air-dry | `s3` remains dry during rootbound inspection |

Gentle watering began at 16:32 local after the settle period. Amount pending.
Initial response:

| Time local | s3 raw | CSV `level` tag | Interpretation |
|---|---:|---|---|
| 16:32:47 | 2948 | dry | pre-response / still stable at dry rootball-interface baseline |
| 16:32:52 | 1967 | dry | large wetward step, about -981 raw from 16:32:47 |
| 16:32:57 | 1327 | dry | very large wetward step, about -1621 raw from 16:32:47 |

Water-balance update: less than 1/4 cup was applied, and water started flowing
out the bottom essentially immediately. This is strong evidence of very low
retention or a fast bypass/drainage path in the root-dominated pot.

Drainage/redistribution tail after the initial wetward spike:

| Time local | s3 raw | CSV `level` tag | Interpretation |
|---|---:|---|---|
| 16:33:07 | 1669 | OK | rebound upward from wet spike |
| 16:33:27 | 1932 | needs water | continued upward rebound |
| 16:34:02 | 2210 | dry | fast return toward drier raw counts |
| 16:34:12 | 2261 | dry | still trending drier after runoff |
| 16:38:32 | 2599 | dry | late rebound plateau after drainage/redistribution |
| 16:39:42 | 2598 | dry | stable late plateau before possible handling |
| 16:39:47 | 3082 | dry | jump upward; possible probe pull/handling if confirmed |

Interpretation of watering response: raw counts show water reached the `s3`
rootball-interface zone quickly, then the local zone rapidly rebounded toward
drier raw counts as water drained or redistributed. The CSV `level` tag changed
from `dry` to `OK` to `needs water` and back to `dry` during this transient, so
for this segment the raw ADC trajectory is the primary evidence; the emitted
band/tag should be treated cautiously until the display/firmware band semantics
are reconciled.

Dashboard screenshot evidence: [`assets/20260629_p09_s3_rootball_response.png`](assets/20260629_p09_s3_rootball_response.png).

Closeout call: P09 has enough evidence for a one-plant rootbound succulent
water-response characterization. The `s3` path shows a dry rootball-interface
baseline, a sharp wetward hit during gentle watering, immediate bottom flow, and
a measurable rebound/redistribution path. This is sufficient to stop the P09
segment, reseat the dampish rootball base back into the inner pot without the
probe, wipe the probe, let the probe return toward air-dry, and prep P10. This
is not a calibration endpoint because the placement was rootball-interface,
one-probe, and root-dominated.

Interpretation: the rootball/soil interface around the inserted probe is dry,
but this plant class and this placement geometry need careful interpretation.
The reading is useful evidence that P09 is not locally wet at the rootball
interface, but it is not enough by itself to decide watering volume. Because
the pot is root-dominated, the sensor is likely characterizing the plant's
rootball and remaining thin substrate film more than bulk potting mix. Avoid
forcing more probes into this pot; that would likely damage roots or change the
sample more than it improves the measurement.

## P10/P11 office-cared comparator notes

P10 and P11 are a different cohort from the earlier rescue/dry-baseline plants.
Both were recently brought home from the user's office after about four years
there. Care history: regular approximately 1 cup watering once per week for the
duration, missing only a few weeks around holidays over the four years.

Shared pot construction:

- Both P10 and P11 have inner pots.
- Both sit in outer pots with terra cotta bases that act as built-in outer drip
  trays.
- The terra cotta itself is probably not a meaningful soil-moisture exchange
  mechanism because the plants still have inner plastic liners, so there is no
  direct soil-to-terra-cotta contact.
- The built-in base tray is still behaviorally important: if initial watering
  runs through, water can sit in the base and allow some slow rewetting/resoak
  from below.

Measurement implication: for P10/P11, record both the soil/probe response and
the tray/base state. Runoff into the outer tray does not automatically mean
water is wasted; it may become a short-term rewetting reservoir. That also means
standing water in the outer base can confound later soil readings if the inner
pot has been sitting over retained water.

Probe reset before P10: by 16:46 local, all four channels had returned to
air-dry/open-air behavior after the P09 segment. Representative tail at
16:46:32 local: `s1=3449`, `s2=3153`, `s3=3156`, `s4=3172`, all emitted as
air-dry.

## P10 notes

P10 is another pothos, but much better cared for and tended than the earlier
rescue pothos plants. Treat P10 as an office-cared pothos comparator with a
known long-term weekly watering routine and with possible tray-mediated resoak
behavior.

Planned handling:

- If possible before watering, check whether the outer base already has any
  standing water or dampness.
- If the inner pot is moved out of the outer pot, record that state because it
  removes the tray/resoak mechanism from the measurement.
- Place probes across the pot as evenly as feasible, but do not force placement
  through dense roots.
- Watering, if performed, should record surface pattern, amount, first runoff
  timing, and whether water remains in the outer tray.

Probe-in settling baseline:

- At about 16:47 local, probes were inserted into P10 and left to settle for a
  soil baseline.
- Log behavior suggests staggered physical placement as probes were inserted:
  `s1` began moving down around 16:47:02, `s2` around 16:47:12, `s3` around
  16:47:22, and `s4` around 16:47:32.
- By 16:47:57 local, `s2`, `s3`, and `s4` had stabilized in the emitted `dry`
  band, while `s1` remained high and emitted `air-dry`.

Representative settling tail:

| Time local | s1 raw/band | s2 raw/band | s3 raw/band | s4 raw/band | Interpretation |
|---|---|---|---|---|---|
| 16:46:32 | 3449 / air-dry | 3153 / air-dry | 3156 / air-dry | 3172 / air-dry | pre-P10 air reset |
| 16:47:22 | 3298 / air-dry | 2644 / dry | 2509 / air-dry | 3174 / air-dry | staggered insertion in progress |
| 16:47:37 | 3292 / air-dry | 2659 / dry | 2488 / dry | 2405 / dry | `s2/s3/s4` now reading dry-band soil contact |
| 16:47:57 | 3289 / air-dry | 2647 / dry | 2484 / dry | 2394 / dry | settling baseline; `s1` may be shallow/weak contact |

Interpretation: P10 is reading much drier than its better care history might
make us expect, at least at the current probe locations. Since `s1` remains
air-dry while the other three channels settle into dry-band soil contact, treat
`s1` as questionable contact or a very dry local zone unless physical placement
confirms otherwise. Let the baseline settle a little longer before watering.

`s1` reseat check:

- User reseated `s1` and asked for a 30 second response check.
- `s1` showed only a weak downward raw drift and remained emitted `air-dry`.
- The first checked 30 second span moved from about `3345` at 16:51:17 to
  `3329` at 16:51:47. By 16:52:12 it reached `3318`.
- `s2`, `s3`, and `s4` stayed stable in the dry band during the same window.

Interpretation: `s1` did respond slightly, but not enough to call it a good
soil-contact baseline. Keep `s1` marked marginal/questionable unless physical
placement confirms it is firmly seated in soil.

Stable pre-water comparison before P10 watering:

- By about 17:00 local, P10 had a stable pre-water baseline.
- Representative tail at 16:59:57 local: `s1=3251` air-dry, `s2=2676` dry,
  `s3=2361` dry, `s4=2362` dry.
- Because `s1` remained marginal/questionable after reseating, the main P10
  soil comparison should use `s2/s3/s4`: mean about `2466` raw, median about
  `2362` raw.

Comparison to earlier pothos plants before watering:

| Plant | Pre-water basis | Reliable raw comparison | Interpretation |
|---|---|---|---|
| P01 | Clean dry-baseline experiment before slow no-runoff watering | pre-water medians `s1=2110`, `s2=2164`, `s3=2189`, `s4=2098`; mean about `2140` | P10 reliable channels are drier than P01's dry baseline |
| P02 | Parched rescue pothos; monitor fallback had air-to-prewater/contact transition | pre-water interval medians around `3073-3179` with multiple air-dry channels | P10 is much less parched than P02 |
| P03 | Parched rescue pothos; dry-settle window before first runoff | dry-settle medians around `3011-3255`, with air-dry/dry channels and contact transition | P10 is much less parched than P03 |
| P10 | Office-cared pothos, pre-water at about 17:00 | reliable `s2/s3/s4` around `2361-2676`; `s1=3251` but marginal/contact-questionable | Dry and due for water, but not rescue-parched |

Watering call: start with gentle distributed top watering. Because P10 has the
outer base/tray affordance, record first runoff timing and whether water remains
in the tray for resoak. Pause after first runoff rather than treating runoff as
immediate waste.

P10 watering start:

- Watering started at 17:06 local.
- The plant has rich foliage that makes it difficult to get water directly to
  the soil surface and distribute it evenly, so this is an obstructed
  distributed top-watering attempt.
- First response appears at `s3`, followed by `s4`; `s2` moved modestly, and
  `s1` remained mostly unchanged and still contact-questionable.

Initial watering-response samples:

| Time local | s1 raw/band | s2 raw/band | s3 raw/band | s4 raw/band | Interpretation |
|---|---|---|---|---|---|
| 17:05:57 | 3093 / air-dry | 2651 / dry | 2359 / dry | 2357 / dry | final pre-water tail |
| 17:06:57 | 3070 / air-dry | 2656 / dry | 2358 / dry | 2358 / dry | still near dry baseline |
| 17:07:02 | 3065 / air-dry | 2419 / dry | 1447 / dry | 2337 / dry | first strong wetward hit at `s3`; modest `s2` movement |
| 17:07:07 | 3029 / air-dry | 2420 / dry | 1705 / dry | 1809 / dry | `s4` now wetward too; `s3` rebounding/redistributing |

Interpretation: water reached one local path near `s3` quickly, then reached
or redistributed toward `s4`. `s2` moved less, and `s1` still does not provide
clean wetting evidence. Because foliage limits surface access, this segment is
likely to show local wetting paths rather than uniform top-water coverage.

P10 first runoff / tray-fill observation:

- At about 17:08 local, after about 1 cup applied, water started filling the
  tray under the inner pot.
- This is the first visible tray-fill point for P10.
- At about 17:15 local, the retained tray water was estimated at about 1/4 inch
  in an approximately 1 inch deep tray. This suggests the 1 cup volume was about
  right for the plant/pot, even though local soil conditions remained uneven.
- At about 17:40 local, when P10 was removed from the bench, all visible tray
  water had been reabsorbed into the pot system. User described the extra tray
  water as approximately 1 cm, fully taken back up between the 17:06 watering
  start and 17:40.
- Because the outer tray is part of this pot's normal watering affordance, the
  recommended action is to pause and allow resoak from the tray/inner pot
  rather than immediately add more water.

Representative tray-fill tail:

| Time local | s1 raw/band | s2 raw/band | s3 raw/band | s4 raw/band | Interpretation |
|---|---|---|---|---|---|
| 17:07:57 | 3019 / air-dry | 2758 / dry | 2672 / dry | 1955 / needs water | `s4` remains wettest; `s3` rebounding drier |
| 17:08:07 | 3006 / dry | 2789 / dry | 2765 / dry | 1931 / needs water | tray-fill period; `s1` starts entering dry band |
| 17:08:17 | 2868 / dry | 2819 / dry | 2952 / dry | 1929 / needs water | `s4` wet zone persists; other channels drier/rebounding |
| 17:08:22 | 2827 / dry | 2834 / dry | 3038 / dry | 1926 / needs water | strong cross-channel heterogeneity at first tray fill |

Interpretation: P10 accepted about 1 cup before tray fill began, but the probe
response is still heterogeneous. `s4` is the most clearly wetted local zone,
`s3` saw an early pulse and then rebounded upward/drier, and `s2`/`s1` remain
comparatively dry. This supports a preferential-flow / uneven surface-access
story under dense foliage. Pause for tray-mediated resoak before adding more.

Dashboard screenshot evidence:
[`assets/20260629_p10_uneven_post_watering.png`](assets/20260629_p10_uneven_post_watering.png).

Operator-distribution note: after the 1 cup watering, the user reported that
they were able to gently move foliage out of the way and believed the water was
spread around the plant reasonably well. Despite that, the dashboard and log
show obviously uneven soil conditions. At about 17:10:27 local, the channels
were `s1=2693` dry, `s2=3054` dry, `s3=3151` air-dry, and `s4=2088` needs
water. This is over 1,000 raw counts of spread after a careful watering attempt.
The unevenness persisted in the live tail: at about 17:14:07 local, the channels
were `s1=2810` dry, `s2=3097` air-dry, `s3=3173` air-dry, and `s4=2067` needs
water, still about 1,106 raw counts from wettest local zone to driest local zone.
Interpretation: the unevenness should not be attributed only to poor surface
coverage. P10 has real microzone/preferential-flow behavior after watering,
likely influenced by foliage obstruction, root/soil structure, pot geometry,
and the tray-mediated drainage/resoak path.

P10 segment closeout:

- At 17:21 local, probes were pulled from P10, wiped dry, and left to air dry
  while P11 was prepared.
- Pulling the probes produced significant clumps/globs of moist soil stuck to
  the sensors, requiring wiping them off before drying. User observed this as
  the strongest soil-structure/moist-clumping response of the plants tested so
  far.
- Fact: P10 soil physically clumped on the probes after watering. Inference:
  P10 likely has better retained moisture / soil cohesion than the rescue
  pothos plants, even if the potting medium appears similar. Hypothesis:
  repeated over-dry cycles in the rescue plants may have reduced their ability
  to rewet, clump, and hold moisture, producing more bypass/channeling behavior.
- Untested destructive speculation: removing plants/roots and fully rewetting,
  stirring, and soaking the soil might restore some moisture-holding behavior,
  but this would risk or kill the plants and is not planned as a bench test.
- Treat 17:21 local as the P10 measurement boundary. Later readings belong to
  probe handling / air reset / P11 setup unless explicitly marked otherwise.

## P11 notes

P11 is the second office-cared plant from the same long-term care environment.
User described it at closeout as looking like an approximately 8-10 inch tall
miniature corn plant, but wider, with no corn stalks and with the first leaves
emerging at the base rather than above a bare lower stalk. Identity remains
unconfirmed.

P11 pre-insertion air reset:

- At about 17:39 local, after P10 pull/wipe/dry time and while P11 was being
  prepared, all four probes were stable in air-dry territory.
- Representative 17:39:42 local sample: `s1=3545` air-dry, `s2=3319` air-dry,
  `s3=3157` air-dry, and `s4=3055` air-dry.
- Interpretation: probes are dry/stable enough to start P11 insertion evidence.
  Per-channel open-air offsets remain visible, especially `s1` reading higher
  than the other channels.

P11 insertion / dry settling baseline:

- At about 17:43 local, probes were inserted in P11 and settling to soil-level
  readings with no watering yet.
- Representative 17:43:22 local sample: `s1=3169` air-dry, `s2=2874` dry,
  `s3=2804` dry, and `s4=2831` dry.
- Interpretation: `s2`/`s3`/`s4` are credible dry soil-contact readings. `s1`
  remains high/air-dry-ish and should be treated as contact-questionable unless
  physical placement confirms firm contact. Reliable-channel mean for
  `s2`/`s3`/`s4` is about 2,836 raw, drier than P10's reliable pre-water
  baseline.
- After additional undisturbed settling, `s1` also entered the dry band.
  Representative 17:54:52 local sample: `s1=2978` dry, `s2=2732` dry,
  `s3=2763` dry, and `s4=2913` dry. Interpretation: P11 has a stable dry
  no-watering baseline across all four channels.

P11 watering-method note:

- User reports P11 has a peak/top center plant core that is normally watered
  from above and allowed to hold water briefly, then slowly drain downward as if
  catching rainfall. That center/core reservoir only holds about 1/8 cup.
- Normal watering amount for P11 is about 1 cup, similar to P10.
- Bench plan: begin with the normal center/core fill amount, pause briefly to
  observe any delayed soil response, then continue toward the normal total dose.
  This preserves plant-normal watering while separating the center-core pathway
  from the broader watering response.
- Watering started at 17:57 local. Pre-response sample at 17:57:12 local was
  still stable/dry: `s1=2955`, `s2=2742`, `s3=2761`, `s4=2942`.
- Initial center/core fill response was localized: by 17:57:17 local, `s4`
  dropped to `2286` while `s1`, `s2`, and `s3` remained near dry baseline.
- At about 17:59 local, user switched the remaining approximately 3/4 cup to
  distributed soil-surface watering to reduce isolated pockets around the
  sensors. Around that transition, the response began broadening: at 17:59:22
  local, `s3=1972`, `s4=2319`, `s1=2713`, and `s2=2663`.
- At about 18:01 local, user reported P11's tray filling further, estimated at
  about 1/2-3/4 inch full. Live readings remained highly uneven: at 18:01:42
  local, `s3=1299` well-watered while `s4=2377`, `s1=2624`, and `s2=2849`
  remained dry. Interpretation: stop/pause watering and let the tray act as a
  resoak reservoir; do not chase the remaining dry channels with more water
  while the tray is already substantially filled.
- Monitoring checkpoint at 18:06 local: `s3=1321` well-watered, `s4=2476`
  dry, `s1=2514` dry, and `s2=2998` dry. Interpretation: P11 remained highly
  non-uniform several minutes after watering. No more water should be added
  during this checkpoint; continue observing tray-mediated resoak and local
  redistribution.
- Monitoring checkpoint at 18:08 local: `s3=1330` well-watered, `s4=2480`
  dry, `s1=2455` dry, and `s2=3004` dry. Interpretation: P11 had not equalized
  in the short term. `s1`/`s4` drifted somewhat wetter than baseline, but `s2`
  remained dry/high while `s3` stayed well-watered.
- Resoak checkpoint at 18:16 local, about 15 minutes after the tray-fill pause:
  `s3=1340` well-watered, `s4=2444` dry, `s1=2238` dry, and `s2=3085`
  air-dry. Interpretation: P11 still had not equalized. `s1` drifted much
  wetter than baseline, `s4` stayed moderately wetward of baseline, `s3`
  remained well-watered, and `s2` stayed high/dry-air-ish. Treat this as
  persistent microzone / placement / pathway evidence, not as a signal to add
  more water.
- Final closeout at 18:24 local: user called the full bench suite complete.
  P11 had soaked back up about 2/3 of the water that had been in its overflow
  tray, but not all of it. Representative pre-pull log sample at 18:24:07 local:
  `s1=1850` needs water, `s2=3196` air-dry, `s3=1355` well-watered, and
  `s4=2274` dry. Interpretation: even after partial tray resoak, P11 remained
  strongly non-uniform.
- Final screenshot evidence:
  [`assets/20260629_p11_final_resoak_closeout.png`](assets/20260629_p11_final_resoak_closeout.png).
- Sensors were pulled and wiped dry at 18:24 local. Treat readings after the
  pull as handling / air-reset evidence, not P11 soil state.

Session milestone:

- At 18:24 local, the full plant backlog / greenhouse had received at least an
  initial watering pass and the bench suite was called complete.
- User noted the rigorous walk-through, sensor observation, and evidence logging
  took about 6 hours, while the same physical watering without evidence capture
  would normally be a 3-5 minute exercise.
- Automation implication: a mature Sprout experience should preserve the
  important decisions from this manual run--pause after runoff/tray fill, avoid
  chasing dry single-channel readings, and respect plant-specific watering
  pathways--without imposing this evidence-capture overhead on every watering.

- Sage
