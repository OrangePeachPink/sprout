<!-- cspell:words drydown dracaena anthurium bromeliad y9d41p 8gtt1h openmeteo transpiration -->

# Extended in-situ dry-down (peak-summer) — 8 plants, dense — 2026-07-19

**This is the fresh current-fleet dry-down #995 has been waiting on — captured organically, not on a
bench.** Three watering sessions across 07-10…07-13 started multi-day dry-downs that ran through to
now with an **extended pause before re-watering**, pushing several plants deep into the dry tail
("about to be not *tending well*"). Captured **in-situ** — the real boards, the real windowsill spots,
nothing moved or touched — across **8 plants on both live boards**, under **peak July summer light**
(the fastest-drying / highest-transpiration window of the year; direct southern light only declines
from here). Firmware extracts each plant's series from its watering → now; **Data derives the ratified
`boundary[]`** (the #995 seven-bracket sets).

Refs: #995 (ratification) · #1174 (the bench dry-down this satisfies) · #1039 (band-model ruling) ·
sensor map #896 · anchors #898.

## Source note (thank you, Workflow)

An earlier cut of this packet read the wrong store — the intentionally-lagging `.data-worktree` data
branch, where the classic board looked sparse. **Workflow measured the host records and corrected it:
the canonical dense source is `logs/<device>_*.csv`, where BOTH live boards log via `wifi_poll` @ 30 s,
~13 k rows/day, unbroken through the window.** This packet is rebuilt from `logs/`. Stale off-fleet C5
segments (`n3jhsp`, Jul 7 + Jul 12 only) are **excluded** — no in-window data from the retired C5s.

## Per-plant dry-down (`data/summary.csv`)

Capacitive: **higher raw = drier**. `wet` = the post-watering wettest reading; `now` = 2026-07-19.
All times **CDT** (matches the dashboard).

| plant | board | watering session (CDT) | duration | wet → now | rise | air / water anchor |
| --- | --- | --- | --- | --- | --- | --- |
| Corn-plant (mini) | classic `y9d41p` | **07-11 21:09** | 7.4 d | 1809 → 2484 | +675 | 3221 / 1086 |
| Anthurium (Hearts) | classic `y9d41p` | **07-11 21:08** | 7.4 d | 1362 → 2287 | +925 | 3084 / 1042 |
| Pothos XXL | classic `y9d41p` | **07-10 11:40** | 8.8 d | 1621 → 1749 | +128 | 2898 / 988 |
| Dracaena (cane) | classic `y9d41p` | **07-13 21:15** | 5.4 d | 1013 → 2115 | +1102 | 3190 / 1061 |
| Pothos office | c5off1 `8gtt1h` | **07-13 21:15** | 5.4 d | 1119 → 2039 | +920 | 2661 / 934 |
| Pothos small | c5off1 `8gtt1h` | **07-10 12:47** | 8.8 d | 998 → 2002 | +1004 | 2767 / 996 |
| Bromeliad | c5off1 `8gtt1h` | **07-10 12:55** | 8.8 d | 1029 → 1792 | +763 | 2792 / 1020 |
| Pothos XL | c5off1 `8gtt1h` | **07-10 13:21** | 8.8 d | 969 → 1879 | +910 | 2742 / 968 |

**Waterings are SESSIONS, not per-plant scatter** (maintainer): plants watered within a few minutes
share one event. Three sessions here:

- **07-10 midday** — XXL (classic) + small / Bromeliad / XL (8gtt1h). 4 plants, ~8.8-day tails.
- **07-11 ~21:08 PM** — Corn + Anthurium (classic). ~7.4-day tails.
- **07-13 21:15 PM** — Dracaena (classic) + office (8gtt1h). ~5.4-day tails.

Each session spans both boards — consistent with watering across the sill in one pass.

## Both ADC envelopes are measured densely

- **Classic envelope** (`y9d41p`: Corn / Anthurium / XXL / Dracaena) — air anchors ~3,084–3,221.
- **Compressed envelope** (`8gtt1h`: office / small / XL / Bromeliad) — air anchors ~2,661–2,792
  (~17 % compressed). **`8gtt1h` self-identifies as `c5off1` on the wire** (`name=c5off1`) with a
  C5-class compressed envelope — so these four are plausibly **measured C5-class data**, which would
  let Data *validate* the #898 cross-board map (×0.803) against real readings rather than only derive
  through it. **Board-class flag:** Workflow's host-record read called `8gtt1h` classic-class/S3;
  the payload + registry call it `c5off1`. **Reconcile the board class** — it decides whether the C5
  brackets are measured or derived. Either way both envelopes are covered densely.

## Peak-summer-light context

No lux channel is logged, so "sunlight" here is **seasonal + diurnal context, not a measured value**:
this dry-down sits at the **July peak** of the fleet's direct southern exposure. The dense series carry
the **diurnal drying oscillation** (day/night rate change); the only logged weather context is
`pressure_hpa` (openmeteo exterior). **Band edges derived from peak-light drying are the
fast-transpiration envelope** — slower-light months dry more gently, so these edges are the aggressive
end of the range.

## For Data (the hand-off)

Firmware provides the dense per-plant series + the watering sessions + the sensor→plant map (confirmed
against the current registry `config/devices.local.json`). **Data owns the `boundary[]` derivation**:

1. Cluster cuts by **session** (07-10 / 07-11 / 07-13), not per-plant scatter.
2. Reconcile the **`8gtt1h` board class** (measured C5 vs classic-class) — it changes whether the C5
   seven-bracket set is measured here or derived via #898.
3. Feed the ratified sets to Firmware — the **#1153** parameterized cal-suite is paste-constants-and-run.

## Provenance + PII

Extracted read-only from the canonical `logs/<device>_*.csv` (devices `y9d41p`, `8gtt1h`); dense C5
downsampled to 2-min median bins for size (full 30 s in `logs/`). `cal_tier`: classic = channel-cal
(`wipe_airdry_bench_20260628`); `8gtt1h` = board-cal. Raw counts, device ids, local timestamps, plant
names, weather pressure only — no MAC / USB-instance IDs / hostnames / EXIF; RFC1918 IPs (ADR-0015
evidence-safe) are not needed here and are absent.

— Firmware 🔧
