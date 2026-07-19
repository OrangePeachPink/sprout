<!-- cspell:words drydown dracaena anthurium bromeliad y9d41p 8gtt1h openmeteo transpiration -->

# Extended in-situ dry-down (peak-summer) — 8 plants, last-watering → now — 2026-07-19

**This is the fresh current-fleet dry-down #995 has been waiting on — captured organically, not on a
bench.** The 2026-07-13 watering (plus the surrounding 07-10…07-14 pours) started a multi-day
dry-down that ran through to now with an **extended pause before re-watering**, pushing several
plants deep into the dry tail ("about to be not *tending well*"). It was captured **in-situ** — the
real boards, the real windowsill spots, nothing moved or touched — across **two boards and 8
plants**, under **peak July summer light**. From here the direct-southern light only decreases through
the year, so **this is the fastest-drying / highest-transpiration dry-down the fleet will see** — the
"hardest" case for the band model to resolve.

Firmware extracted each plant's series from **its last watering → now**; **Data derives the ratified
`boundary[]`** (the #995 seven-bracket sets) from it. Read-only from the data-branch archive; nothing
on the data branch was modified.

Refs: #995 (ratification) · #1174 (the bench dry-down this satisfies) · #1039 (band-model ruling) ·
sensor map #896 · anchors #898.

## Per-plant dry-down (`data/summary.csv`)

Capacitive: **higher raw = drier**. `wet` = the post-watering wettest reading; `now` = 2026-07-19.

| plant | board | watered (CDT) | duration | wet → now (raw) | rise | air / water anchor |
| --- | --- | --- | --- | --- | --- | --- |
| Pothos office | c5off1 | 2026-07-13 21:15 | 4.9 d | 1119 → 2003 | +884 | 2661 / 934 |
| Pothos small | c5off1 | 2026-07-10 12:47 | 8.3 d | 998 → 1972 | +974 | 2767 / 996 |
| Pothos XL | c5off1 | 2026-07-10 13:21 | 8.2 d | 969 → 1880 | +911 | 2742 / 968 |
| Bromeliad | c5off1 | 2026-07-10 12:55 | 8.3 d | 1029 → 1776 | +747 | 2792 / 1020 |
| Corn-plant (mini) | classic | 2026-07-12 ~19:00\* | 6.0 d | 1699 → 2382 | +683 | 3221 / 1086 |
| Anthurium (Hearts) | classic | 2026-07-12 ~19:00\* | 6.0 d | 1657 → 2237 | +580 | 3084 / 1042 |
| Pothos XXL | classic | 2026-07-10 ~19:00\* | 8.0 d | 1462 → 1684 | +222 | 2898 / 988 |
| Dracaena (cane) | classic | 2026-07-14 ~10:55\* | 4.3 d | 1293 → 1993 | +700 | 3190 / 1061 |

\* classic times are ±hours — see the cadence caveat below.

**The per-plant waterings genuinely stagger** (07-10 → 07-14), not one mass event — the C5 group got a
saturating soak 07-10 midday; office was topped up 07-13 evening; the classic pair (Corn/Anthurium)
~07-12; Dracaena 07-14. Each series is that plant's own last-watering → now.

## Two data qualities — read this before deriving boundaries

- **C5 plants (office / small / XL / Bromeliad — device `8gtt1h`): DENSE, 30 s.** Downsampled to
  2-min median bins here (3.2k–5.5k points); **the full 30 s is in the archive**. These are the
  **load-bearing series for interior band-boundary work** — clean drying arcs with diurnal detail.
- **Classic plants (Corn / Anthurium / XXL / Dracaena — device `y9d41p`): SPARSE, ~2 h** (10–22
  points). The **dry-down shape + endpoints are solid**, but the watering time is ±hours and the
  interior is coarse. **Use them for cross-board validation + the dry-end / wilt anchoring, not for
  fitting fine interior edges.** (Corn/Anthurium at ~2,200–2,400 now = the visible-wilt "Parched"
  pull-point from #995.)

## Two reconciliations worth recording

- **Corn was NOT last watered 07-11.** The data shows Corn drying steadily to a peak (~2,227) through
  07-11/12, then a **−528 watering drop by 07-13 00:00 UTC** (07-12 evening CDT), then the 6-day
  climb to 2,382 now. The "07-11 raw ~2,228" seen on the chart was its **dry peak just before** that
  watering. It's droopy because it's 6 days into drying (now Dry/Parched), not because it was skipped.
- **office "07-13 vs 07-14" was a timezone artifact.** Its single big watering (−954 → 1,098) is
  **07-14 02:15 UTC = 07-13 21:15 CDT**. The dashboard shows local (07-13); the raw UTC shows 07-14.
  Same event. All watering times in `summary.csv` are **CDT** to match the dashboard.

## The peak-summer-light context

No lux channel is logged, so "sunlight" here is **seasonal + diurnal context, not a measured value**:
this dry-down happened at the **July solstice-adjacent peak** of the fleet's direct southern exposure.
The dense C5 series carry the **diurnal drying oscillation** (visible day/night rate change); the only
logged weather context is `pressure_hpa` (openmeteo exterior). The seasonal point stands on its own —
**band edges derived from peak-light drying are the fast-transpiration envelope**; slower-light months
will dry more gently, so these edges are the aggressive end of the range.

## For Data (the hand-off)

Firmware provides the series + the watering detection + the sensor→plant map. **Data owns the
`boundary[]` derivation** and should:

1. Confirm each plant's exact watering cut against the **app's tuned detected-watering** signal (the
   naive last-big-drop detector here matches it, but the app is authoritative).
2. Confirm the plant↔sensor map against the **current registry** (#896 map is 2026-07-10; #921 edits
   may have moved things).
3. Lean on the **dense C5 arcs** for interior edges; use the **sparse classic** for dry-end + wilt
   anchoring + cross-board consistency (per the #898 linear map — validated near-perfect in the #1153
   suite).
4. Feed the ratified seven-bracket sets back to Firmware for the `boundary[]` update (the #1153
   parameterized suite is waiting — paste-constants-and-run).

## Provenance + PII

Extracted read-only from `.data-worktree/data/archive/` (devices `y9d41p` classic, `8gtt1h` c5off1);
no data-branch files modified. `cal_tier`: classic = channel-cal (`wipe_airdry_bench_20260628`), C5 =
board-cal. Raw counts, device ids, local timestamps, plant names, and weather pressure only — no MAC /
USB-instance IDs / hostnames / EXIF; RFC1918 IPs (ADR-0015 evidence-safe) are not needed here and are
absent.

— Firmware 🔧
