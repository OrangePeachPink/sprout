<!-- markdownlint-disable -->
# Raw bench-session findings log — 2026-07-10 (verbatim, maintainer-caught confounds)

This is the unpolished, at-the-bench annotation log. The README narrates it; this file preserves the
raw calls as they were made (some later superseded — kept for provenance, not sanded off).

## HEADLINE: probe re-insertion shifts reading ~+470 raw (placement dominates)

Clean placement-disturbance measurement (UNWATERED plants, no soil change): pulling a probe for the
air/cup step and re-inserting it shifted the in-soil reading DRIER by ~+450-490 raw with NO change to
the soil:
  - Corn (#1, classic s1):      1800 -> 2254  (+454)
  - Anthurium (#3, classic s3): 1709 -> 2198  (+489)
That is LARGER than most of today's watering responses -> probe placement/contact is a DOMINANT
variable, moving the reading nearly a full band. Direction (drier) fits: re-inserted probe = looser
soil contact / air gaps -> less capacitance -> higher raw.
Confounded controls (watered, for contrast): XXL 1802->1536 (-266, watering dominated); Dracaena cane
1245->1455 (+210, placement-drying partially offset the 1c).
IMPLICATIONS: (1) per-sensor calibration is placement-SPECIFIC -- re-seating invalidates the in-soil
baseline; (2) every dose-response is confounded by placement (cf. the XXL pour-location catch); (3)
proves #381 (probe-orientation) + #829 as critical. Maintainer's experiment idea.

## REFINEMENT (maintainer): the "placement disturbance" headline is 3 confounds, not 1

The +470 conflates THREE distinct variables, all changed by a single pull-and-reinsert; we did NOT
isolate them:
  1. PLACEMENT LOCATION - where the probe re-enters: center vs edge; near/far from a prior well-watered
     spot; distance from the watering source point.
  2. SOIL DISTURBANCE - even the SAME spot reads differently: loosened soil on re-insertion vs the prior
     firmer/settled insertion (air gaps, contact area).
  3. INSERTION DEPTH - how deep the probe goes back in (the bottom half of the blade is the measuring
     element per the 07-04 depth sweep, so depth is high-leverage).
So +470 is their COMBINED effect, not "placement" alone. LESSON: once a probe is calibrated and a good
FIRST placement is chosen, keep it STABLE/STATIC - minimize pulls/re-inserts, since each perturbs all
three. Corollary: the #829 air/cup pull by design disturbs the in-soil baseline; the anchors describe
the SENSOR, but the in-soil reading must be re-established (and left alone) after any pull.

## Data-integrity: XXL bench-artifact dip (maintainer-caught)

XXL (p02, classic .87) trajectory shows a dip to ~2050-2150 around 10:05-10:15 CDT that is NOT a
watering response -- it is a BENCH ARTIFACT from the #599 wedge session (classic on USB: reflashed
wedgetest -> monitor -> wedge/reset -> reflash shipping -> brick; each reboot re-reads the ADC cold +
settles). LABEL that window bench-disturbed, exclude from dose-response. The real XXL watering = 1.5 cup
at ~15:32Z (10:32 CDT), which post-dates the dip.

## XL environmental lift (maintainer-caught)

XL rose ~2050 -> ~2148 around 10:30 CDT UNWATERED, on the C5 (untouched by the wedge work -> NOT a bench
artifact). Likely non-soil driver: temperature / solar irradiance on the ledge (morning sun). Effective
pre-water baseline for the 10:40 watering = ~2153 (not the 15:27Z 2069). Flag for v0.8.0 Predict:
capacitive raw has an environmental (temp/solar) component that a classifier must separate from soil
moisture. C5 die_temp at capture = 23.70C (chip self-heat, weak proxy).

## XXL pour-LOCATION confound (maintainer-caught, CRITICAL)

The XXL 2nd-dose fast response (2079 -> 1991, -88 in ~1 min) is CONFOUNDED and most likely
POUR-LOCATION dominated, NOT priming. The window sill is high and the XXL is the tallest pot, so normal
XXL pours are BLIND (maintainer can't see over the pot) -> water lands at an unknown spot. For this 2nd
dose the maintainer climbed onto the countertop to SEE the pour and got the water MUCH closer to the
probe. Water at the probe reaches it in ~1 min; water elsewhere redistributes slowly (the 1st dose's
~35-min path). #381/#829 'response = water-path/placement, not dose' live. Explains the XXL's
historically erratic response: every prior XXL pour had an uncontrolled pour-location variable. CORPUS
FLAG: do NOT train a 'priming/2nd-dose-is-fast' feature on this; pour location is an uncontrolled
confound and this 2nd dose is the ONLY one poured AT the probe. My earlier 'priming' attribution is
superseded by the maintainer's observation.

## Braided Dracaena (p05, sensorless) - novel redistribution technique

Had the expected inter-pot water (its root growth between inner/outer pots is its primary uptake path).
Instead of ADDING water, poured the existing inter-pot water out, re-seated the inner pot, and re-poured
that SAME water over the top of the rootball+minimal soil to try broader rehydration coverage. NO NEW
WATER. Likely reflowed back to the inter-pot reservoir where the roots feed. A coverage experiment, not
a watering.

## Sensorless plants (ADR-0028, no probe by design)
- p08 Cactus - 2in pot, minimal soil (left windowsill)
- p09 Succulent / aloe-ish - 2in pot, mostly rootbound (right windowsill)
- p05 Braided Dracaena - entirely rootbound, dense hard rootball, cannot insert a probe (right windowsill)
