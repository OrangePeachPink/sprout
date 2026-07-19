<!-- cspell:words drydown y9d41p 8gtt1h Anthurium Dracaena Bromeliad -->

# #995 / #1174 band-bracket derivation — the ratified seven-bracket sets

**Data lane, 2026-07-19.** The ADR-0035 seven in-soil bands (Soaked → Faint) re-derived
against the fresh in-situ extended dry-down (this packet), **superseding the June corpus**.
Both envelopes **measured** (classic `y9d41p` + official C5 `8gtt1h`). Reproduce with
`python analysis/derive_brackets.py` from the repo root.

Higher raw = drier. The seven bands live on the **in-soil envelope** `[wet-floor .. Faint-ceiling]`;
the **6 interior cuts** ride firmware `boundary[]` (descending, wet→dry); the anchors bound
the envelope. **Water-anchor RULED A (#1174):** Soaked-floor = wet-rail (coincident).

## Measured envelopes (median of the per-channel cal anchors)

| board | water anchor | air anchor | span | dry-down deepest reached |
| --- | --- | --- | --- | --- |
| classic `y9d41p` (Corn/Anthurium/XXL/Dracaena) | **1052** | 3137 | 2085 | **2487** (Corn) |
| C5 `8gtt1h` = c5off1 (office/small/Bromeliad/XL) | **982** | 2754 | 1772 | 2099 (small) |

## Method

1. Pool each board's in-situ in-soil reads (classic n≈19.9k, C5 n≈21.4k, 30 s cadence,
   5.4–8.8-day tails, three watering sessions).
2. **Faint-ceiling = the measured humane wilt-onset**, not the sensor max. Classic deepest
   is Corn **2487** ("about to be not tending well", README) → **ceiling 2500**. This
   **supersedes ADR-0035's provisional 2800** (which came from a *deliberate* XXL over-dry —
   the opposite of humane). See the occupancy proof below.
3. **Even 7-way split of each board's own measured envelope.** Even-by-moisture (not
   equal-frequency) keeps the mood stable — a slow dry-down that sat 62 % of the time in the
   healthy Moist/Ideal middle should read "content/thriving," not flip bands on noise.
4. **C5 measured independently** from its own envelope; ceiling at the same envelope
   *fraction* as classic's (0.694), so a classic "Faint" and a C5 "Faint" are the same soil
   state. The ×0.803 map is then a **check**, not an input (below).

## The ratified sets (ceiling 2500 / 2213)

| band (mood) | CLASSIC `y9d41p` | C5 `8gtt1h` | classic occ% |
| --- | --- | --- | --- |
| **Soaked** (soaked) | 1052 – 1259 | 982 – 1158 | 1.4 |
| **Wet** (refreshed) | 1259 – 1466 | 1158 – 1334 | 3.0 |
| **Moist** (thriving) | 1466 – 1673 | 1334 – 1510 | 34.6 |
| **Ideal** (content) | 1673 – 1879 | 1510 – 1685 | 27.3 |
| **Drying** (thirsty) | 1879 – 2086 | 1685 – 1861 | 13.7 |
| **Dry** (parched) | 2086 – 2293 | 1861 – 2037 | 15.2 |
| **Faint** (faint) | 2293 – 2500 | 2037 – 2213 | 4.9 |

Firmware `boundary[]` (descending, wet→dry) — paste into the #1164 fixtures:

- **classic** `{2293, 2086, 1879, 1673, 1466, 1259}`
- **C5** `{2037, 1861, 1685, 1510, 1334, 1158}`

## Why 2500, not 2800 — the occupancy proof

The fresh dry-down settles the ceiling that the June proposal had to leave provisional:

| ceiling | classic **Faint** band | Faint occupancy |
| --- | --- | --- |
| **2500** (measured wilt-onset) | 2293 – 2500 | **4.9 %** — Corn's 2487 reads Faint ✓ |
| 2800 (ADR-0035 provisional) | 2550 – 2800 | **0.0 %** — nothing reached 2550 ✗ |

At 2800 the driest band is a **dead zone**: the humane operator re-waters at ~2487, so
"Faint" would be a mood she never triggers. 2500 is the humane-calibration doctrine
(ADR-0035 §4) made literal — calibrate to where plants actually get, never the sensor's
harm max.

## The ×0.803 map — validated as a check, and it moved

The #898 cross-board map assumed factor **0.803**. Against the freshly-measured **dual**
envelope it is **0.850** (classic span 2085, C5 span 1772 → 1772/2085 = 0.850). The
divergence is the **classic water anchor**: measured **1052** here vs the map's implied ~978
(June). At mid-range the 0.803 map undershoots the measured C5 cuts by ~30 counts.

**This is a check-finding, not a crutch:** both columns above are measured from their own
envelopes, so cross-board is exact by construction.

> **RESOLVED (#1215, ratified 2026-07-19 — Firmware's reconciliation, maintainer-agreed):
> both pairs are valid for their jobs; the cross-board factor is interval-dependent (ADC
> compression isn't perfectly linear rail-to-rail).**
> **0.803 with the 978 cup rail = the full rail-to-rail envelope** — the probe-in-water
> exception threshold interval (#1152's layer). · **0.850 with the 1052 in-soil wet
> floor = the ladder interval** — the Soaked floor correctly above free water; the
> interval the seven-band re-partition (this derivation) lives on. Neither overwrites
> the other.

## Honest coverage caveats

- **Wilt-end is thin by design.** Faint is 4.9 % (classic) / 2.3 % (C5) — the humane fleet
  spends little time at wilt-onset. The wet→mid bands (Soaked … Dry) are densely measured;
  the Faint band is anchored to the *observed* deepest, not the sensor extreme.
- **C5 dry-end thinner still** — C5 reached only 2099 (fraction 0.63 vs classic's 0.69), so
  the C5 Dry/Faint cuts lean on the shared envelope fraction more than on C5 density.
- **Peak-summer light** = the fast-transpiration envelope; slower-light months dry gentler,
  so these edges are the aggressive end of the range (README).
- **Species/survivor spread** persists (XXL is hardy, read shallow); per-instance refinement
  stays a later registry+cal-chain job. Humane wilt-onset is the only capture target.
