# Multi-plant dry/wet baseline run sheet

Use this run sheet when bringing plants to the bench one by one for dry baseline
and post-water captures. It favors consistency over perfect botany: temporary
plant IDs, repeatable probe placement, local-time notes, and raw ADC evidence.

Refs #333

## Plant IDs

Assign temporary IDs in bench order:

| Plant ID | Description | Notes |
| --- | --- | --- |
| `P01` | First plant tested today | Use even if the plant is unnamed. |
| `P02` | Second plant tested today | Continue sequentially. |
| `P-cactus` | Cactus exception | Use one probe if four will not fit. |
| `P-succulent` | Succulent exception | Use zero or one probe if the pot is too crowded. |

If a plant later gets a real name, keep the temporary ID in notes so old captures
still join cleanly.

For a full greenhouse pass, keep the sequential ID even when the plant has a
known common name. The bench ID is the data join key; the common name is context.

## Standard capture settings

For ordinary plant baseline work:

| Field | Dry baseline | Post-water check |
| --- | --- | --- |
| Source | `serial (device)` | `serial (device)` |
| Sample rate | `1 s` | `1 s` |
| Duration | `180 s` | `180 s` |
| Monitor logging | Off during capture | Off during capture |
| Notes time | Local Chicago time first | Local Chicago time first |

Use `0.5 s` only for fast transition tests, not routine plant baselines.

## Probe placement convention

Use four probes when the pot safely allows it.

| Channel | Position | Record |
| --- | --- | --- |
| s1 GPIO34 | front / north | Depth, angle, and distance from stem. |
| s2 GPIO35 | right / east | Depth, angle, and distance from stem. |
| s3 GPIO36 | back / south | Depth, angle, and distance from stem. |
| s4 GPIO39 | left / west | Depth, angle, and distance from stem. |

If the plant shape makes front/back/right/left awkward, use clock positions
instead, such as 12, 3, 6, and 9 o'clock.

Record the microsite (the specific spot in the pot) for each probe. A single pot
can contain dry pockets, wet paths, roots, air gaps, and runoff channels at the
same time, and that disagreement is evidence rather than noise.

Also record probe validity. If a probe has poor soil contact, shallow insertion,
root-mass contact, or cannot fit in the pot, say whether Data should include
it in the plant-level view.

## Dry baseline procedure

1. Run the [bench preflight checklist](bench-preflight-checklist.md).
2. Assign the plant ID.
3. Photograph the plant and pot if visual evidence matters.
4. Record visible state before watering.
5. Wipe probes dry if they were recently in water or another pot.
6. Insert probes to a consistent safe depth. Do not force probes through roots or
   crowded soil.
7. Wait 2 minutes for mechanical settling.
8. Capture dry baseline: `P##_dry_baseline_<short-note>`.
9. Inspect channel spread. If one probe is wildly different, note whether it may
   be a real microsite, shallow insertion, air pocket, root contact, or probe
   placement issue.
10. Do not water until the dry baseline capture is complete.

## Watering and post-water procedure

1. Record watering action before watering:
   - water amount if measured
   - approximate amount if not measured
   - top-water, bottom-water, mist, or other method
   - whether runoff occurred
2. Water the plant.
3. Leave probes in place if safe and practical.
4. Wait 10 to 15 minutes for the first post-water capture unless the plant/pot
   needs a different settling time.
5. Capture post-water: `P##_post_water_<minutes>m`.
6. If readings still move rapidly, add a second post-water capture at 30 to 60
   minutes.
7. Before pulling probes, record the pull time and whether the reading is still
   drifting, settling, or rebounding toward dry.

## Cactus and succulent exceptions

- Do not force four-probe cross-validation into a crowded pot.
- For cactus, use one probe where it fits safely and record the exact position.
- For succulent, skip probing if insertion would damage the plant or disturb the
  pot too much.
- If only one probe is used, the run can describe that plant but cannot estimate
  cross-pot microsite spread.
- If a probe is inserted between a root mass and pot wall, label that contact
  plainly. It is useful evidence, but not the same as open soil contact.

## Run sheet template

Copy this block once per plant.

```text
Plant ID:
Plant type/name if known:
Pot size/material:
Drainage:
Visible plant state:
Soil surface state:
Recent watering history:

Environment:
- Local time:
- Light/skylight state:
- ESP32 exposure:
- Room/cup/soil temperature if measured:

Probe placement:
- s1 GPIO34:
- s2 GPIO35:
- s3 GPIO36:
- s4 GPIO39:

Dry baseline:
- capture id:
- local start time:
- settings:
- raw medians:
- spread:
- probe inclusion:
- anomalies:

Watering action:
- local time:
- amount:
- method:
- runoff:
- notes:

Post-water:
- capture id:
- local start time:
- minutes after watering:
- settings:
- raw medians:
- spread:
- wettest observed window:
- pull/removal window:
- probe inclusion:
- anomalies:

Evidence:
- photo paths:
- related issue/comment:

Interpretation:
- facts:
- inference:
- what this does not prove:
- next test:
```

## Data handoff

For Data, the minimum join keys are:

| Field | Example |
| --- | --- |
| plant_id | `P01` |
| phase | `dry_baseline`, `post_water_15m` |
| capture_id | `20260628_...` |
| local_time | `2026-06-28 18:42 CDT` |
| probe_map | `s1 front, s2 right, s3 back, s4 left` |
| watering_action | `top-water, approx 250 mL, no runoff` |
| anomaly_tags | `air-pocket?`, `root-contact?`, `single-probe-only` |
| probe_inclusion | `s1 include, s2 exclude-poor-contact` |
| watering_start | `2026-06-29 17:06 CDT` |
| peak_window | `2026-06-29 17:09-17:14 CDT` |
| pull_window | `2026-06-29 17:21 CDT` |

For a computable handoff, create or update a tracked evidence package under
`docs/experiments/data/<session-id>/` with raw slices, event/window tables, a
manifest, and a README. The Markdown narrative remains the lab notebook; the CSV
package is what lets Data regenerate the plant-level arc without re-reading the
prose.

— Sage
