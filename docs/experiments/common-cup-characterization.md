# Common-cup characterization — procedure

A turnkey bench procedure for capturing the **moisture-band states** in one cup of soil, so the
[calibration workbench](../../tools/analytics/calibration.py) (#192) can propose the **A2 band
boundaries** from real per-state centres. Desk-prepped so the bench is fill-in, not improvisation.

## Why common-cup

All four probes sit in **one cup of the same soil at the same moisture**, so the only thing that varies
between them is the **probe + ADC pin** — not the plant or the microsite. That decouples *sensor/pin
variance* (what we're calibrating) from *plant/placement variance* (a separate question). The result
feeds the **A2 calibration reconciliation** — the dashboard ladder is "placeholders pending A2"
(currently `cal bounds(dry>wet): 2760 2140 1830 1520 1260 1030`).

## What you need

- The 4-probe rig on **COM6**, all four probes in **one cup** at the **same depth**.
- The Sprout dashboard open (double-click the icon → `http://127.0.0.1:8765`).
- Time for the dry-down (or force the states): the cup goes **saturated → … → air-dry**.

## The states (wet → dry)

| State (capture subject) | uiBand | fwLevel | how to reach it |
| --- | --- | --- | --- |
| `common_cup_saturated` | Saturated | submerged | standing water in the cup |
| `common_cup_wet` | Wet | overwatered | just-watered, no standing water |
| `common_cup_moist` | Moist | well watered | a few hours after watering |
| `common_cup_ideal` | Ideal | OK | the comfortable middle of the dry-down |
| `common_cup_drying` | Drying | needs water | surface dry, getting thirsty |
| `common_cup_dry` | Dry | DRY | clearly dry through |
| `common_cup_airdry` | Parched | air-dry | fully dried out (also the "probe may not be in soil" band) |

You don't need all seven in one session — even **3–4 well-separated states** (e.g. wet / ideal / dry /
air-dry) give the workbench enough to propose meaningful boundaries. More states = finer boundaries.

## Capture each state (in the dashboard)

For each state, in the **Experiment Capture** panel:

1. Bring the cup to the state (water, or wait for the dry-down to reach it).
2. **subject** = `common_cup_<state>` (from the table — the naming keeps them recognizable and easy to group).
3. **sample rate** `0.5 s`, **duration** `60 s`, **source** `serial (device)`, **port** `COM6`.
4. **Start capture** → watch the live trajectory; it lands isolated in `experiments/<id>/`.

Leave the always-on **Monitor** logging running if you want the continuous dry-down recorded too — the
handoff frees COM6 for the capture and resumes logging after.

### Which probe defines the interior boundaries (Firmware guidance)

The shared band boundaries (A2) should come from a **clean probe**. From the air/water anchors,
[**s2 (GPIO 35) reads wet-biased**](2026-06-26_common-cup-air-water-anchors.md) — so when the dry-down
sweeps the interior bands (Moist / Ideal / Drying / Dry), **derive those A2 anchors from a clean probe
(s3 or s4)**, not from the 4-probe average, so s2's offset doesn't skew the shared boundaries. **Track s2
separately** as the per-channel-offset case — that is **C1 / #170** (per-channel calibration), distinct from
the A2 boundary reconciliation. (Capture all four as usual; just anchor the boundaries on the clean probe.)

## Turn the captures into a candidate calibration

Once you've captured the states, at the desk (no rig needed):

```text
python tools/analytics/analysis_store.py            # build the DuckDB store from the captures
python tools/analytics/calibration.py               # propose per-band centres + boundaries
python tools/analytics/calibration.py --export      # write reports/calibration_candidate.json
```

The workbench groups the readings by their observed band, orders them wet→dry by raw median, and
proposes each boundary as the **midpoint** between adjacent states' centres. Review them in the `/lab`
detail view too (see [the analytics README](../../tools/analytics/README.md)).

## Hand off to Firmware (the A2 handshake)

`reports/calibration_candidate.json` is **PROPOSED, not authoritative**. Hand it to Firmware to
**ratify**: they weigh it against the current placeholders + their own bring-up, and the agreed set
becomes the new `cal bounds(dry>wet)`. That's the A2 reconciliation
([ADR-0006](../adr/0006-data-architecture.md) §5–6).

## After: write the findings

Drop a paired findings report in this folder (`*.md` + `*.json`, per the [README](README.md)):
hypothesis, method, per-state mean raw / spread / settling, and the proposed anchors — the durable
record of what this characterization concluded.
