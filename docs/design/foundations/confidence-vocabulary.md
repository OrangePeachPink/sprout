# The confidence vocabulary — how sure a prediction is, in Sprout's voice

**Status:** ratified form, R3 (PRD-0009 Accepted 2026-07-24) · **Owner:** Design · **Consumed by:**
R6 (the forecast on the chart) · R11 (attention states) · G2 (early danger) · G3 (the calm signal) ·
G7 (the greenhouse summaries) · R4 (the track record, when it surfaces).

The maintainer's ruling was *"have Design invent a range or numeric amount of a presentation array
that is appropriate."* PRD-0009 fixed the **contract**, not the form: the cue rides the **predicted
channel** (never a mood — R8), is legible at card size, and degrades into the readiness states (R5)
rather than inventing a confident-looking value where the model has none. This document is the form.

**This is the one place the vocabulary lives.** Any surface that needs to say *how sure* consumes it
from here — never re-minted per surface. A second confidence vocabulary able to disagree with this
one is the failure this file exists to prevent.

---

## The form: the interval is the confidence

The model **already computes an interval** — `forecast.py` derives `hours_lo` / `hours_hi` from the
drying slope ± its standard error, and `card_payload` carries them onto the card. Until R3 the card
rendered only the midpoint (`next water ~2d`) and threw the interval away.

So the form is not invented; it is the honest interval, shown:

| the model says | the card says |
|---|---|
| `53.3 h [47.6 – 60.5]` | **next water 2–3d** |
| `9.1 h [8.6 – 9.7]` | **next water 9–10h** |
| `41 h`, no interval | **next water ~2d** *(midpoint only — never a fabricated range)* |

**The width carries the confidence.** A narrow span *is* the claim "I'm fairly sure"; a wide span *is*
"this is loose." Showing the span says it without asserting a precision the fit does not have — and it
needs no numeric scale a plant would never speak (`±6h at r²=0.82` is instrument register, not voice).

Sub-36-hour predictions read in **hours**, longer ones in **days** — the same threshold the
watered-ago line already uses, so the two halves of the water story stay in one register.

## The word: a bounded set of three

One word rides beside the figure, as a chip in the **predicted (violet) channel** — the same shape as
the `DETECTED` / `MANUAL` provenance chips, so it reads as provenance-about-a-number, not as a mood.
It is derived from the interval's **relative width** `w = (hi − lo) / midpoint`:

| relative width | chip | what it honestly means |
|---|---|---|
| `w ≤ 0.15` | **FIRM** | the drying rate is steady; the span is tight |
| `w ≤ 0.50` | **ROUGH** | a real trend, loosely bounded — treat the range as the answer |
| `w > 0.50` | **HAZY** | the fit is weak; the range is wide enough that only the horizon is useful |
| no interval | *(no chip)* | a midpoint with no computable span makes no how-sure claim |

Three, not five: at card size a fourth gradation is unreadable, and a scale invites false precision on
a rate that is **provisional pre-calibration** anyway (`next_need.confidence == "provisional"` today).

**Why these words.** They describe *the reading*, not the plant's feelings — so they never collide
with the seven moods (Soaked → Faint), which is R8's boundary. They are plain, calm, and short enough
to sit beside a figure at card size. "HAZY" over "UNSURE" deliberately: the haze is in the picture,
not a confession of incompetence — self-candor is a trait, never an apology.

## Where it degrades (R5, not a fake number)

When there is **no** statistically real fit, no interval and no word appear. The line falls through to
the readiness states instead — the truth per state, never a confident-looking placeholder:

- *still learning its rhythm* — genuinely collecting history
- *holding steady — no dry-down to measure yet* — measured flat; more time yields no slope
- *not enough to call it yet* — any other declined reason the payload reports

And a plant already **at or past Thirsty** shows **water now** — the mood is the authority there and
the forecast defers to it (no ETA to a boundary already crossed).

## The rules, for the surfaces that consume this

1. **Predicted channel only.** Figure and chip both live in the violet forecast channel. Never a band
   colour, never a mood word — a prediction is not a reading (R8).
2. **Never invent a span.** No interval in the payload ⇒ midpoint only, no chip.
3. **Never dress a decline as a value.** No fit ⇒ the R5 readiness line, not a wide range.
4. **One vocabulary.** Consume `FIRM / ROUGH / HAZY` and the interval formatter from the card surface;
   a greenhouse-level summary (G7) aggregates these words, it does not define new ones.

— Design 🔍
