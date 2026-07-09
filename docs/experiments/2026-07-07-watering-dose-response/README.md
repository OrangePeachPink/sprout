# Watering dose to response — 2026-07-06/07 (first watering since #379)

Bench session (Firmware operator + maintainer). The parched windowsill fleet was hand-watered with
**measured US-cup doses**, one plant at a time, and Sprout captured each plant's soil response over WiFi
at 30 s. This is the first watering session since #379 (2026-06-29 characterization). Analysis surfaces
(DuckDB view, per-plant arc chart) are tracked as #834's children #835 / #836; this packet is the raw
evidence + the operator write-up.

Higher raw = drier. Bands are per-board provisional (calibration #170; the C5's real anchors are #667,
wired in by #767). Doses are measured cups from a 2-cup kitchen cup.

> **DATA QUALITY WARNING — p02 (XXL) sensor fault.** The p02/s2 probe threw **erroneous readings** in the
> dose-3 window: with **no watering** after the ~00:20Z pour, it swung **661 (submerged) at ~02:00Z → ~2840
> (dry) at ~02:23Z** — a jump soil cannot make untouched. **All p02 dose-3 data is unreliable and marked
> suspect.** The "priming worked / submerged" conclusion an earlier draft drew from it is **RETRACTED** (see
> the priming section). Raw values are preserved as-is — they ARE the evidence of the fault. Every OTHER
> plant's data is unaffected. Maintainer-caught, 2026-07-08.

## Trajectory (baseline to acute to 90 min to ~22 h to ~24 h)

| Plant | Pot | Dose (total) | Baseline | Acute | 90 min | ~22 h | ~24 h | Band |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| p02 Pothos XXL | 10in | 1.5c + 1c primed | 2945 | 2135 | 2368 | 2423 | **661 (BAD)** | SENSOR ERROR - see warning |
| p03 Pothos XL | 9in | 1.25c | 2334 | 2240 | 2053 | 1961 | 1949 | needs water |
| p04 Dracaena | 8in* | 0.75c | 2700 | 2389 | 1855 | 1607 | 1623 | OK |
| p10 Pothos office | 6in | 0.5c | 2446 | 1714 | 1848 | 2012 | 2023 | needs water |
| p07 Bromeliad | 4.5in | 0.25c | 2213 | 2065 | 2134 | 2136 | 2132 | needs water |
| p11 Corn-plant mini | 6in | 0.5c | 2012 | 1455 | 1442 | 1486 | 1486 | well watered |
| p06 Anthurium (unwatered) | 5in | - | ~1489 | - | 1489 | 1522 | 1533 | well watered |
| p01 Pothos small (unwatered) | 6in | - | ~1565 | - | 1565 | 1591 | 1576 | OK |

`*` p04's effective volume is far smaller than 8 in (dead rootballs fill ~2/3; ~1 in decorative moss top).

## Findings across four dimensions

### Water (uptake to the probe)

Delayed **deep** uptake dominated: the Dracaena and XL kept wetting for the full ~22 h as water migrated to
probe depth (the acute readings badly understated them). The mini took up and held. The big hydrophobic
Pothos pots retained little on cold top-pours.

### Drying

The office Pothos ran a textbook ~1-day cycle (dry to OK to needs-water). The two unwatered probes drifted
only +26 to +44 raw over 24 h — a clean ambient-drying baseline that a watered plant's drift is measured
against.

### Soil distribution (redistribution)

The headline for the schema: **pot size + soil conditioning, not dose, decide whether water reaches the
probe over a day.** Same-ish doses produced opposite fates (see #675 for the pot/soil registry evidence:
nominal-vs-effective pot volume, three drainage pathologies, conditioned-vs-drought soil).

### Sensor integrity and drift

Every trajectory was monotonic-ish and physically sensible. Zero SENSOR_FAULT flags all session. Unwatered
drift was small and consistent (one direction). The XL faithfully tracked its slow deep-wetting — the
earlier "won't budge" was a borrowed-endpoint label artifact plus hydrophobic soil, not a stuck probe
(resolved with its own #667 anchors). This is a clean drift baseline for the #829 burn-in retest.

## The priming result — RETRACTED (p02/s2 sensor fault)

**CORRECTION (2026-07-08, maintainer-caught).** An earlier draft made this the session headline: that a
primed 4th cup cracked the hydrophobic XXL pot and drove it to "submerged (661)." **That is withdrawn — it
rested entirely on a faulting sensor.**

The maintainer confirmed **no watering happened** after the ~00:20Z dose-3 pour, yet p02/s2 read **661
(submerged) at ~02:00Z then ~2840 (dry) ~23 min later** — soil cannot swing like that untouched. So the
**entire XXL dose-3 trajectory (the 1704 acute dip, the 661 "submerged") is UNRELIABLE and NOT a finding.**
The priming hypothesis is **untested here** — the instrument on this plant could neither confirm nor deny it.

Likely cause: probe-head/electronics **water contamination** from the repeated watering (the same failure
mode as sensor #1 in `SENSOR_QA.md`). Action: dry + re-verify the p02/s2 probe; fold into the #829 retest.
The raw CSVs keep the erroneous values as-is (they ARE the evidence of the fault), flagged in-file.

## Doctrine note

No invented normalized value is used anywhere here — raw + calibrated band are the truth (ADR-0004). The
open question of honest cross-board/per-sensor band display on one chart is tracked at #832. Boards report
`fw=0.7.0` while running v0.7.1 code; that version-string identity gap is tracked at #831.

## 48-hour (2-day) follow-up (captured 2026-07-09T02:22Z, ~48 h post-pour)

Snapshot: `48h-2day-2026-07-09.csv`. All plants reading sensibly; slow drying across the 24 h to 48 h window, as expected.

| Plant | 24 h | ~48 h | 48 h band | 2-day trend |
| --- | --- | --- | --- | --- |
| p02 XXL | *(24 h = sensor fault)* | **2092** | needs water | **recovered** — first clean post-fault reading; soil-feel + tray corroborate |
| p03 XL | 1949 | **1967** | needs water | ~flat, holding needs-water |
| p04 Dracaena | 1623 | **1729** | OK | slow drying, holding OK |
| p10 office | 2023 | **2227** | dry | dried into DRY — the ~2-day cycle bottoming out |
| p07 Bromeliad | 2136 | **2138** | needs water | flat — **stagnant pot; probe may mislead, investigate in person before watering** |
| p11 mini | 1486 | **1601** | OK | slow drying (well-watered to OK) |
| p06 Anthurium* | 1533 | **1617** | OK | unwatered slow-dry baseline |
| p01 small* | 1576 | **1625** | OK | unwatered slow-dry baseline |

Notes for the next session:

- **p02 XXL recovered** from the 24 h probe fault (probe-head contamination, dried off overnight) — the
  ~2092 / needs-water reading is trustworthy and matches the soil-feel + tray. See the self-heal closure on #834.
- **The three Pothos (XXL, XL, office)** are all in needs-water/dry — the planned watering targets tomorrow.
- **p07 Bromeliad** reads needs-water, but its watertight/stagnant pot can hold standing water in the
  inner/outer gap while the probe sits in a dry pocket — flagged for an **in-person investigation** before
  any watering (do not dose off the sensor).
- Unwatered baselines (p06, p01) drifted only slightly over 48 h — the ambient 2-day drying rate.

## Data files

Per-plant 30 s response curves (isolated captures) plus three fleet snapshots:

- `p02-pothos-xxl.csv`, `p02-pothos-xxl-d2.csv`, `p02-pothos-xxl-d3.csv` — the XXL across all three pours
- `p03-pothos-xl.csv`, `p03-pothos-xl-d2.csv` — the XL
- `p04-dracaena-cane.csv`, `p04-dracaena-cane-d2.csv` — the Dracaena
- `p07-bromeliad.csv`, `p10-pothos-office.csv`, `p11-corn-plant-mini.csv` — single-dose plants
- `22h-snapshot-2026-07-07.csv`, `24h-final-2026-07-08.csv`, `48h-2day-2026-07-09.csv` — fleet-wide snapshots

Columns: `ts_utc, device_seq, raw, band` (per-plant) and `plant_id, plant, board_octet, channel, raw, band`
(snapshots). RFC1918 IPs retained (evidence-safe, ADR-0015); no MACs.

## Refs

- #834 — the watering-session roll-up this packet lands under (children #835 DuckDB view, #836 arc chart)
- #379 — the prior watering/characterization session
- #667 / #767 / #170 — C5 real anchors + calibration
- #675 — pot/soil profile-registry evidence
- #829 / #832 / #831 — burn-in retest, honest band display, version identity

— Firmware (bench operator)
