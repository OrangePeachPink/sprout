<!-- cspell:words UMLIFE pioarduino esptool eFuseCal DevKitC dracaena anthurium bromeliad rootbound -->
<!-- cspell:words reinsert reinsertion espota RFC ratiometric silkscreen prewire -->

# Bench closeout — watering dose-response + per-sensor air/cup re-characterization + C5 portability — 2026-07-10

Bench evidence for the **v0.7.1 firmware finish-lane**, captured the day after the in-place fleet reflash
to v4 (`git 2f463d2`). One long session covered four jobs at once, all on the two deployed boards over
WiFi (no re-flash, no re-wire): a **watering dose-response** round, a **per-sensor air-dry + water-cup
re-characterization** (#829), the **first deployed-state C5 portability read** confirming the C5's
compressed ADC (#621 / #767), and a clean **probe-placement disturbance** measurement. It also nails down
the full **sensor → plant → lane → channel → GPIO map** for all 11 plants (resolving the #896 nomenclature
collision).

Private RFC1918 IPs are evidence-safe and kept (ADR-0015). No MAC / USB-instance IDs / EXIF appear here.

## Session arrangement

- **Maintainer = hands** (watering, probe pulls/dunks/re-seats, pour-location control).
- **Firmware lane = brains-on-call** (armed a per-channel sweep logger against each board's `/telemetry`,
  extracted air/cup anchors, watched for confounds, recorded).
- **Boards**: classic ESP32 (`device y9d41p`, `192.168.x.87`, left sill) · official ESP32-C5
  (`device 8gtt1h`, `192.168.x.85`, right sill). Both on the shipping 30 s sweep cadence
  (`READ_INTERVAL_MS=30000`) — polled read-only over HTTP, nothing re-flashed.
- **Anchor method**: pull probe → wipe → ~40 s in open air (air-dry) → ~40 s in a common water cup
  (water-cup) → wipe → re-insert. The logger dedups on `device_seq`; air = the settled high plateau
  before the cup, cup = the settled low.

## The complete sensor → plant map (resolves #896)

The `s#` label was overloaded across four layers; this pins all four. On the **classic**, physical
label and firmware lane happen to align (#1↔s1); on the **C5** they do **not** (physical s05 rides
firmware lane s3). Anchor columns are today's raw values.

### Classic — `device y9d41p` (.87), left windowsill

| Physical label | Plant | FW lane | MCU ch | GPIO | air-dry | water-cup |
| --- | --- | --- | --- | --- | --- | --- |
| #1 | p11 Corn-plant (mini) | s1 | ch2 | GPIO34 | 3221 | 1086 |
| #2 | p02 Pothos (XXL) | s2 | ch3 | GPIO35 | 2898 | 988 |
| #3 | p06 Anthurium (Hearts) | s3 | ch0 | GPIO36 | 3084 | 1042 |
| #4 | p04 Dracaena (cane) | s4 | ch1 | GPIO39 | 3190 | 1061 |

### C5 — `device 8gtt1h` (.85), right windowsill

| Physical label | Plant | FW lane | MCU ch | GPIO | air-dry | water-cup |
| --- | --- | --- | --- | --- | --- | --- |
| s05 | p01 Pothos (small) | s3 | ch0 | GPIO1 | 2767 | 996 |
| s06 | p07 Bromeliad | s2 | ch3 | GPIO6 | 2792 | 1020 |
| s07 | p03 Pothos (XL) | s4 | ch1 | GPIO4 | 2742 | 968 |
| s08 | p10 Pothos (office) | s1 | ch2 | GPIO5 | 2661* | 934 |

### Sensorless by design (ADR-0028)

| Plant | Why | Sill |
| --- | --- | --- |
| p05 Braided Dracaena | entirely rootbound; dense hard rootball won't take a probe | right |
| p08 Cactus | 2" pot, minimal soil | left |
| p09 Succulent (aloe-ish) | 2" pot, mostly rootbound | right |

`*` s08 air ran ~60 counts low from an early-start (probe not fully wiped/settled); see #829 note below.
Full mapping + anchors: [`data/sensor_map.csv`](data/sensor_map.csv).

## #829 — per-sensor air/cup re-characterization (drift check)

### Classic drift vs the 2026-06-28 characterization

Per-sensor, not board-wide — the four classic probes drifted with distinct character over ~12 days
(and one full reflash):

| Probe | air 06-28 → 07-10 | Δair | wet 06-28 → 07-10 | Δwet | character |
| --- | --- | --- | --- | --- | --- |
| #1 Corn | 3086 → 3221 | +135 | 958 → 1086 | +128 | offset up (whole scale) |
| #2 XXL | 3120 → 2898 | −222 | 900 → 988 | +88 | compression |
| #3 Anthurium | 3123 → 3084 | −39 | 969 → 1042 | +73 | ~stable dry, wet up |
| #4 cane | 3096 → 3190 | +94 | 970 → 1061 | +91 | offset up |

The wet floor rose on **all four** (+73…+128) — consistent with residual surface film / probe-corrosion
progression (#657, the deployed s1–s4 show corrosion; spares s5–s12 are pristine). This is exactly the
drift #829 exists to catch.

### C5 portability — the compressed ADC, confirmed deployed (#621 / #767)

Same physical probes (s05–s08), measured on the **C5** today vs their values on the **classic** QA
station (2026-07-04). The C5 reads a **compressed, lower** range — and it's remarkably **consistent
across all four probes**, i.e. a board-level constant, not per-probe:

| Probe | classic air → C5 air | Δair | classic wet → C5 wet | Δwet | compression |
| --- | --- | --- | --- | --- | --- |
| s05 | 3083 → 2767 | −316 | 938 → 996 | +58 | −17% |
| s06 | 3112 → 2792 | −320 | 977 → 1020 | +43 | −17% |
| s07 | 3069 → 2742 | −327 | 871 → 968 | +97 | −19% |
| s08 | 3077 → 2661 | −416* | 890 → 934 | +44 | −21%* |

`*` s08's early-start shaved its air; via the 07-04 C5 anchor (2724) it's ~−16%, in line with the others.
**Today's C5 numbers match the 07-04 install-day C5 continuity packet closely** (e.g. s06 today 2792 /
1020 vs 07-04 2792 / 1022) — so the C5 anchors are **stable from bench to deployed, no drift**. That
stability is what makes them trustworthy enough to set (see #767 below).

## #767 — C5 calibration: measured, proposed, and a wiring finding for the SET

The C5's air/wet endpoints are now bench-measured **and** confirmed stable (today ≈ 07-04). Because the
compression is a **board-level constant (~17%)**, the C5 calibration is best modelled as a single
board-level transform of the classic's shared band boundaries, not four per-probe cals.

**Proposed C5 board `cal_boundary`** — the classic board baseline `{3050, 2140, 1830, 1520, 1150, 1050}`
linear-scaled onto the C5's measured envelope (air 2740, wet 980):

```text
C5 cal_boundary ≈ {2740, 1939, 1666, 1394, 1068, 980}   (dry-rail … wet-rail, descending raw)
```

**Wiring finding — why the SET is a seam change, not a value edit.** Tracing the cal path:
`firmware/src/main.cpp` (~L950) does `memcpy(g_mcfg[ch].boundary, SENSOR_CAL_BOUNDARY[ch], …)` for
**every** board. `SENSOR_CAL_BOUNDARY` lives in `calibration.h` — a **generated, Data-owned, classic-only**
table ("do NOT hand-tune — REGEN via the #192 workbench") — and it **overwrites** the
`BOARD_CAP.cal_boundary` default that the static config seeds from `board_capability.h`. Net effect: the
**C5 currently runs the classic per-channel cal values**, on its compressed scale, flagged provisional
only by `cal_verified=false`. So **editing the C5's `board_capability.h` `cal_boundary` would be a silent
no-op** — the memcpy clobbers it.

The correct SET is a small **board-aware cal-selection seam**: when `!BOARD_CAP.cal_verified`, source
`g_mcfg[ch].boundary` from `BOARD_CAP.cal_boundary` (the per-board cal) instead of the classic
`SENSOR_CAL_BOUNDARY[ch]`. That makes the proposed C5 values above actually take effect, keeps the classic
path unchanged, and preserves the "generated/Data-owned" boundary of `calibration.h`. It is a **Firmware +
Data change requiring the native pinning test + a flash-verify**, so it is deliberately **not** shipped in
this closeout.

**Disposition:** the **capture** half of #767 (the hardware-gated bench measurement) is **done and
durable** here. The **set** half — the seam change + the C5 values + `cal_verified` flip — is teed up with
the mechanism and data in hand, and should ride as a Firmware+Data change through Needs Verification
(recommend v0.8.0; maintainer's call at cert time whether to split #767 or re-milestone it).

## Watering dose-response (v0.8.0 "Predict" corpus)

Full log with maintainer confound annotations: [`data/doses.csv`](data/doses.csv),
[`data/NOTES.md`](data/NOTES.md). Baselines are the board's pre-pour raw; final = the 18:34Z snapshot.

| Plant | Dose | Baseline | Final raw / band | Note |
| --- | --- | --- | --- | --- |
| p10 office | ¾ cup | 2366 | 1594 / OK | tray filled to a good level |
| p02 XXL | 1.5 + 0.5 ≈ 2 cup | 2270 | 1524 / OK | tall deep pot, slow percolation |
| p03 XL | 1.25 cup | 2153† | 1907 / needs-water | env-lifted baseline; slow uptake |
| p07 Bromeliad | ⅓ cup (rosette) | 2164 | 1902 / needs-water | into central rosette, not soil; s2 lags |
| p04 cane | 1 cup | 1932 | 1433 / well-watered | shallow pot, visible (controlled) pour |
| p09 aloe | <⅛ cup | sensorless | — | sip; hand-watered |
| p08 cactus | <⅛ cup | sensorless | — | sip; hand-watered |
| p05 braided | 0 (redistribution) | sensorless | — | no new water; coverage experiment |

Four maintainer-caught confounds are annotated in `NOTES.md` and **must ride with this data into any
classifier training** — they are the difference between signal and artifact:

1. **XXL bench-artifact dip** (~10:05–10:15 CDT): the #599 wedge/reflash cycle cold-cycled the classic's
   ADC — exclude that window, it is not a watering response.
2. **XL environmental lift** (unwatered +~100 at ~10:30): temperature / solar on the ledge — capacitive
   raw carries a non-soil environmental component a classifier must separate.
3. **XXL pour-location** (CRITICAL): the fast −88 "2nd-dose" response was **pour location** (poured *at*
   the probe from the countertop), not priming — my earlier "priming" read is **retracted**. Every prior
   blind XXL pour had an uncontrolled location variable. Do **not** train a "2nd-dose-is-fast" feature.
4. **Braided-Dracaena redistribution**: no new water; existing inter-pot water re-poured over the top.

## Placement-disturbance finding (the session's headline)

A clean, deliberate measurement on **unwatered** plants (no soil moisture change): pull a probe for the
air/cup step, re-insert, compare. Data: [`data/placement_disturbance.csv`](data/placement_disturbance.csv).

| Plant | pre-pull | post-reinsert | Δ | watered? |
| --- | --- | --- | --- | --- |
| Corn #1 | 1800 | 2254 | **+454** | no |
| Anthurium #3 | 1709 | 2198 | **+489** | no |
| XXL #2 | 1802 | 1536 | −266 | ~2 cup (watering dominated) |
| cane #4 | 1245 | 1455 | +210 | 1 cup (placement offset the dose) |

Re-inserting a probe shifted the reading **~+470 raw drier with no change to the soil** — larger than
most of the day's *watering* responses. It is **not** one effect but **three confounds** the maintainer
correctly separated: **(1) placement location**, **(2) soil disturbance** (looser re-inserted contact),
**(3) insertion depth**. The lesson is a design rule: **once a probe is calibrated and well-placed, keep
it static** — every pull perturbs all three, and the #829 air/cup pull *by design* invalidates the
in-soil baseline (the anchors describe the sensor; the in-soil reading must be re-established and left
alone). This is direct field proof of why #381 (probe orientation) and #829 matter, and argues for the
fixed-placement jig the 07-04 packet already flagged as future work.

## Final post-watering snapshot (all sensors re-seated)

Captured `2026-07-10T18:34:43Z`, after every probe was back in place.
Data: [`data/final-post-water-snapshot.csv`](data/final-post-water-snapshot.csv).

| Plant | raw | band |
| --- | --- | --- |
| Corn (mini) | 2238 | dry‡ |
| Anthurium (unwatered) | 2202 | dry‡ |
| Pothos small | 1977 | needs water |
| Pothos XL | 1907 | needs water |
| Bromeliad | 1902 | needs water |
| Pothos office | 1594 | OK |
| Pothos XXL | 1524 | OK |
| Dracaena cane | 1433 | well watered |

`‡` **Read with care:** the two *unwatered* plants (Corn, Anthurium) read "dry", but they were
placement-disturbed by the #829 pull (+454 / +489 above), so ~half a band of that "dry" is the
re-insertion artifact, not real drying. The **watered** plants landed correctly (office/XXL OK, cane
well-watered; XL/Bromeliad still climbing as water redistributes). Watering worked; the snapshot is a
faithful *post-disturbance* state, not a clean pre-vs-post dose delta.

## Honest scope — what this is and isn't

- **Re-characterization, not a fresh cal cut.** #829 confirms drift + the C5 compression; the C5 cal-set
  (#767) is proposed here and routed to Data, not silently shipped.
- **Cup floors are not soil values.** A probe in a cup is fully immersed; in a pot it isn't. The anchors
  bracket each sensor's raw range; they are not target soil readings.
- **The dose-response is confounded** (placement, pour-location, environment) — usable as corpus **only**
  with the annotations carried. Raw preserved; nothing sanded off.
- **Absolute C5 band accuracy still pending** Data's cal verification (`eFuseCal=off`, provisional).

## Prior evidence this builds on (dynamic range + sensor tests)

- **C5 compressed ADC, install-day capture** — `docs/evidence/2026-07-04-c5-official-continuity/` (the
  s5–s8 C5 anchors + the "~300 counts below classic" statement this packet confirms deployed).
- **Classic per-sensor QA (s1–s12)** — `docs/evidence/2026-07-04-sensor-qa-and-characterization/` and
  `docs/experiments/data/20260704_sensor_qa_characterization/` (the classic air/wet values used for the
  portability deltas).
- **Common-cup air/water anchors method** — `docs/experiments/2026-06-26_common-cup-air-water-anchors.md`.
- **06-28 per-channel characterization** — the classic drift baseline (`SENSOR_CAL_*` in `calibration.h`).
- **Prewire dry-down prediction** — `docs/experiments/2026-07-04_prewire_drydown_prediction.md` (the
  "C5 raw reads ~300 counts compressed" prediction).
- **07-06 watering dose-response report** — PR #844 (the 24 h + 48 h response time series this round
  extends).
- **Board / cross-board raw doctrine** — ADR-0019, ADR-0022 (cal confidence vocabulary), ADR-0029 and
  ADR-0031 ("raw is per-board, not cross-comparable; different ADCs / dynamic ranges").

## Provenance

Firmware bench session, 2026-07-10 (the day after the 2026-07-09 fleet reflash). All values are
serial-/HTTP-observed on the live boards at capture time; per-sample sweep streams are in the
maintainer's local archive. Scratch data recovered from a `/c/` path-mangling shadow tree (native-Python
vs Git-Bash mount) and reconciled — values verified against the live extraction output.

Refs: #829 · #767 · #621 · #896 · #599 · #381 · #657 · #844 · ADR-0015 · ADR-0019 · ADR-0022 · ADR-0028
· ADR-0029 · ADR-0031.

— Firmware 🔧
