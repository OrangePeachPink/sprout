# What Sprout is telling you

Sprout doesn't show you a percentage. It shows you a **band** — a named, calibrated moisture zone — and speaks
for the plant in the first person. This guide explains what each band means, what the number *actually*
represents, and when to trust it (or run a recalibration).

> **Short version:** the band name and mood are the truth. The 0–100 number is a useful index, not a lab
> reading. If the band matches what you see in the pot, everything is working.

## The seven bands

Sprout classifies soil into seven bands from wettest to driest. The two outer bands are **diagnostic** — they
signal unusual states more than everyday moisture.

| Band | Mood | What it means | What to do |
| --- | --- | --- | --- |
| **Saturated** | soaked | Standing water or a fresh heavy soak. The sensor sees the wet floor of its range. | Give it time. If it persists, check drainage. |
| **Wet** | refreshed | Freshly watered, soil is at or near field capacity. Good — the goal after a watering. | Nothing — let it absorb. |
| **Moist** | thriving | Healthy, well-hydrated soil. The plant is happy here. | Nothing. This is where you want it. |
| **Ideal** | content | A good moisture level for most plants between waterings. | Nothing — it's in the zone. |
| **Drying** | thirsty | Soil is losing moisture; watering soon is a good idea for most plants. | Water now or in the next day. |
| **Dry** | parched | Too dry for most plants; ready for water. | Water now. |
| **Parched** | faint | The sensor is reading near air-dry levels — this can mean extremely dry soil **or** that the probe isn't in contact with soil. | Check probe placement first. Then water if it's clearly in soil. |

> **On the diagnostic bands (Saturated and Parched):** these bracket the real soil range. Saturated is
> expected right after a deep watering and clears on its own. Parched is the one to watch — if a probe goes
> Parched without an obvious drought, the probe may have shifted out of the soil, or the soil has pulled away
> from it as it dried out.

## What the 0–100 number actually is

Sprout shows a 0–100 index alongside the band. That number is **not volumetric water content** — it is a
*relative position* on a scale calibrated to this specific sensor in this specific setup:

- **0** is your sensor's reading in saturated soil (the wet anchor).
- **100** is your sensor's reading in dry air (the dry anchor).

The index is useful for tracking trends — "it's been creeping up from 60 to 80 over three days" — but its
absolute value is meaningless across different sensors or even after repotting. A 70 on one probe isn't the
same moisture level as a 70 on another.

**The band is the truth. The number tells you where in that band you are.**

Sprout's documentation, voice, and automation all follow the band — never the raw number. The index is labeled
*relative* in the dashboard precisely so there's no confusion about what it represents.

## When to trust it vs. when to recalibrate

Trust the reading when the band matches what you observe. If a probe says **Dry** and the soil in that pot
genuinely feels and looks dry, the sensor is doing its job.

**Recalibrate when the band and reality diverge** — for example:

- The probe says **Ideal** but the plant is clearly wilting.
- The probe stays in **Parched** even after a thorough watering and visual check that the probe is seated in
  soil.
- The whole scale feels shifted — readings that should be **Moist** after watering only reach **Drying**.

Calibration drifts because the dry/wet anchor readings shift with: soil type and compaction, root density
(roots around a probe raise its baseline), temperature, and seasonal air humidity. It's not a defect — it's the
sensor responding to a changed environment. Re-running the dry-air and wet-soil calibration anchors corrects it.

> Even a perfectly calibrated sensor can't fix a lying sensor. If something seems systematically wrong, run
> the **[3-minute board check](trust-your-sensor.md)** first — especially Flaw 3 (the hidden ungrounded
> resistor), which causes a board to return the same stale number regardless of soil state.

## This is Sprout's reading chain

```text
probe reading  ->  seven calibrated bands  ->  mood + first-person voice  ->  (once calibration passes) a pump
```

Every step from the probe outward is based on the **band**, not the raw number. That's the design: if the band
is right, everything downstream is right.

---

*The reading explainer for the User Front Door (issue #143). A later Design pass adds the band color chips
and Sprout's visual mood marks — the words and the structure are here.*
