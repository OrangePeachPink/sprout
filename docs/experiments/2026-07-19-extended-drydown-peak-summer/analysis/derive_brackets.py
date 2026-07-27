#!/usr/bin/env python3
"""#995 / #1174 band-bracket derivation against the 2026-07-19 extended dry-down.
Both envelopes MEASURED (classic y9d41p + official C5 8gtt1h). Supersedes June.

Higher raw = drier. 7 in-soil bands wettest->driest: Soaked Wet Moist Ideal
Drying Dry Parched(->Faint). Envelope = [wet-floor .. Faint-ceiling]; 6 interior
cuts ride firmware boundary[] (descending wet->dry), the anchors bound it.
Water-anchor RULED A: Soaked-floor = wet-rail (coincident).
"""
# ruff: noqa: E501, SIM105 — one-shot derivation: readable print lines + a defensive parse

import csv
import statistics as st
from pathlib import Path

PK = Path("docs/experiments/2026-07-19-extended-drydown-peak-summer/data")
CLASSIC = [
    "p11_corn-plant-mini",
    "p06_anthurium-hearts",
    "p02_pothos-xxl",
    "p04_dracaena-cane",
]
C5 = ["p10_pothos-office", "p01_pothos-small", "p07_bromeliad", "p03_pothos-xl"]


def load(stem):
    rows = []
    with (PK / f"{stem}.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                rows.append(
                    {
                        "raw": int(r["raw_value"]),
                        "air": int(r["air_dry_raw"]),
                        "water": int(r["water_cup_raw"]),
                    }
                )
            except (ValueError, KeyError):
                pass
    return rows


def board(stems):
    per = {s: load(s) for s in stems}
    raws = [x["raw"] for s in stems for x in per[s]]
    airs = [per[s][0]["air"] for s in stems]  # per-channel cal anchor (constant)
    waters = [per[s][0]["water"] for s in stems]
    return per, raws, airs, waters


def pct(v, p):
    v = sorted(v)
    k = (len(v) - 1) * p / 100
    lo = int(k)
    return v[lo] if lo + 1 >= len(v) else v[lo] + (k - lo) * (v[lo + 1] - v[lo])


def summarize(name, stems):
    per, raws, airs, waters = board(stems)
    water = round(st.median(waters))
    air = round(st.median(airs))
    deepest = max(raws)  # driest reading reached (wilt coverage)
    print(f"\n===== {name}  (n={len(raws)} in-soil reads, {len(stems)} plants) =====")
    print(
        f"  water anchor (median per-ch): {water}   range {min(waters)}..{max(waters)}"
    )
    print(f"  air anchor   (median per-ch): {air}   range {min(airs)}..{max(airs)}")
    print(
        f"  dry-down span: min raw {min(raws)} (wettest) .. max raw {deepest} (driest)"
    )
    print("  per-plant driest (wilt reach):")
    for s in stems:
        print(f"    {s:24s} {max(x['raw'] for x in per[s])}")
    print(
        "  pooled percentiles:",
        {p: round(pct(raws, p)) for p in (1, 5, 10, 25, 50, 75, 90, 95, 99)},
    )
    return {"water": water, "air": air, "deepest": deepest, "raws": raws}


def bands_from_envelope(water, ceiling, cuts_frac):
    """6 interior cuts at the given envelope fractions (0=wet-floor..1=ceiling)."""
    span = ceiling - water
    return [round(water + f * span) for f in cuts_frac]


C = summarize("CLASSIC (y9d41p)", CLASSIC)
V = summarize("C5 (8gtt1h = c5off1)", C5)

# --- span ratio (the #898 x0.803 map is the span ratio) ---
span_c = C["air"] - C["water"]
span_v = V["air"] - V["water"]
print("\n===== ANCHOR-MAP FACTOR (measured) =====")
print(f"  classic span (air-water) = {span_c}   C5 span = {span_v}")
print(f"  measured factor C5/classic = {span_v / span_c:.4f}   (grill x0.803)")

# --- proposed Faint-ceiling: humane wilt-onset (measured), not the sensor max ---
# classic deepest 2484 (Corn) -> ceiling a touch above so it reads Faint.
CEIL_C = 2500
# C5 ceiling via the SAME envelope fraction the classic ceiling sits at, then compare
# to the map. classic ceiling fraction of classic envelope:
ceil_frac_c = (CEIL_C - C["water"]) / span_c
CEIL_V_mapped = round(V["water"] + ceil_frac_c * span_v)
print("\n===== FAINT-CEILING (humane wilt-onset) =====")
print(f"  classic deepest reached {C['deepest']} (Corn) -> propose ceiling {CEIL_C}")
print(f"  classic ceiling sits at envelope fraction {ceil_frac_c:.3f}")
print(
    f"  C5 deepest reached {V['deepest']} -> ceiling via same fraction = {CEIL_V_mapped}"
)

# --- interior cuts: 6 fractions of the in-soil envelope. Start from an even split and
#     nudge to the density (the wet-to-mid is dense; the dry end is thin). ---
FRACS = [i / 7 for i in range(1, 7)]  # even 7-way baseline (anchor-map consistent)
print("\n===== EVEN 7-WAY PARTITION (baseline) =====")
bc = bands_from_envelope(C["water"], CEIL_C, FRACS)
bv = bands_from_envelope(V["water"], CEIL_V_mapped, FRACS)
print("  classic interior cuts (asc):", bc)
print("  C5      interior cuts (asc):", bv)
print(
    "  C5 vs classic*factor check:",
    [
        f"{v} vs {round(c * span_v / span_c + V['water'] * (1 - span_v / span_c))}"
        for c, v in zip(bc, bv)
    ],
)

NAMES = ["Soaked", "Wet", "Moist", "Ideal", "Drying", "Dry", "Faint"]


def occ(raws, edges):
    return [sum(1 for r in raws if lo <= r < hi) for lo, hi in zip(edges, edges[1:])]


def proposal(ceil_c):
    """Even 7-way split of each board's OWN measured envelope; C5 ceiling at the same
    envelope fraction as classic's (cross-board = equal fractions, the anchor map)."""
    fc = (ceil_c - C["water"]) / span_c
    ceil_v = round(V["water"] + fc * span_v)
    bc = bands_from_envelope(C["water"], ceil_c, FRACS)
    bv = bands_from_envelope(V["water"], ceil_v, FRACS)
    ec = [C["water"], *bc, ceil_c]
    ev = [V["water"], *bv, ceil_v]
    oc, ov = occ(C["raws"], ec), occ(V["raws"], ev)
    print(f"\n########## CEILING {ceil_c} (classic) / {ceil_v} (C5) ##########")
    print("  band      classic[lo..hi] occ%    C5[lo..hi]   occ%")
    for i, nm in enumerate(NAMES):
        print(
            f"  {nm:8s} {ec[i]:5d}..{ec[i + 1]:<5d} {100 * oc[i] / len(C['raws']):4.1f}  "
            f"{ev[i]:5d}..{ev[i + 1]:<5d} {100 * ov[i] / len(V['raws']):4.1f}"
        )
    print(f"  firmware boundary[] classic (desc wet->dry): {bc[::-1]}")
    print(f"  firmware boundary[] C5      (desc wet->dry): {bv[::-1]}")


proposal(2500)  # measured humane wilt-onset (Corn 2487) — the lead
proposal(2800)  # ADR-0035 provisional harm boundary (June) — the alternative
