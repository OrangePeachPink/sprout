# The attention model — one composed state, four tickets

**Status:** Design's proposed model for maintainer/gate ratification · **Owner:** Design ·
**Serves:** R11 (#1582 the composed state) · R12 (#1583 device-health vs plant-health) ·
G2 (#1584 early danger) · G3 (#1585 the calm signal) · consumed by G7 (#1587 the greenhouse
summaries) · adjacent to B6 (#1556 health promotion — coordinate, don't duplicate).

R11's complaint is the reason this document exists: *"there is no composed attention state an
operator can scan or act from."* Band mood carries how-wet, the exceptions lane carries what's
odd, the forecast carries when-next — and **nothing composes them into "does this need me."**

Building R11, R12, G2 and G3 as four independent surfaces would produce four overlapping
"which plants need you" widgets — which is R11's complaint again, one layer up. So the model
is designed once, here, and those four are its facets. Same discipline as the R3 confidence
vocabulary (`docs/design/foundations/confidence-vocabulary.md`, landing with #1580):
compose once, consume everywhere, never re-mint.

---

## 1. Two axes, never one ladder (this is R12)

The single most important rule, and the one the current surface breaks:

> **A plant's attention state and an instrument's condition are different axes.**
> A sensor that is unhappy must never render as a plant that is unhappy.

They are not two ends of one severity scale — a fault-flagged probe tells you *nothing* about
the plant, so ranking them together invents a claim. Two independent fields:

| axis | question | source |
|---|---|---|
| **plant attention** | does this *plant* need me, and how soon? | band mood + forecast + the #1497 exception labels |
| **instrument condition** | can I trust this reading at all? | quality/fleet-health rollups, SUSPECT classes |

**The precedence rule:** an instrument condition **suppresses** the plant attention state rather
than outranking it. A plant whose probe is faulted has **no** attention level — not "fine," not
"urgent" — because the input is untrustworthy. It reads *"I can't tell you about this one"* plus
the instrument condition. This is ADR-0028's first-class absence applied to attention: absence of
a trustworthy reading is stated, never defaulted.

## 2. The plant attention ladder — four levels

Orthogonal to the seven moods (a mood says how-wet; an attention level says what-to-do).
Ordered, and each earns its level from a distinct signal:

| level | reads as | earned by | ticket |
|---|---|---|---|
| **All clear** | *"nothing needs you until \<when\>"* | no plant at level 2+, and the soonest forecast is beyond the calm horizon | **G3** |
| **Watch** | *"\<plant\> in 2–3d"* | a known forecast inside the horizon — R3's runway + its FIRM/ROUGH/HAZY | R11 |
| **Needs you now** | *"water now"* | at or past the Thirsty entry edge (already shipped as D3) | R11 |
| **Heading for harm** | *"this one is getting worse faster than a normal dry-down"* | the #1497 exception labels — `rate_spike`, direction/rebound, floor-vs-rails | **G2** |

**Why "heading for harm" is a level and not just worse thirst (G2's whole point).** Ordinary
thirst is a *position* on the ladder; harm is a *trajectory* — accelerating, or falling toward a
rail rather than drying normally. A plant can be merely Content and still be on this level, and a
plant can be Parched on a normal curve and not be. Collapsing the two loses the only signal that
distinguishes "needs water" from "something is wrong."

## 3. G3 is affirmative, not the absence of alarm

*"For a calm character, 'nothing needs you until Thursday' is as valuable a prediction as a
warning."* So All clear is a **stated** thing with a **horizon**, not an empty state:

- it names **when** the calm ends (the soonest forecast beyond the horizon), because "all fine"
  with no time bound is unfalsifiable comfort;
- it degrades honestly: if no plant has a usable forecast, it says *"nothing needs you right now"*
  — the present tense it can actually support — never inventing a horizon;
- it is a **calm** rendering, chrome register, never a celebration. Sprout is fond, not perky.

## 4. G2 is a pull affordance — never a notification channel

Recorded because the review panel flagged it and it is easy to violate by accident:

**ADR-0033 rules a 30-second pull loop.** G2 therefore surfaces as an affordance **on the pull
surface** — the plant wears its own harm level, and the greenhouse summary counts it. It does
**not** introduce a push channel (no browser notification, no email, no webhook). If a push
channel is ever wanted, that is an **ADR conversation for Trellis first** (the push/pull
boundary), not a side effect of this ticket. #480's notification-medium question is the place
that decision belongs.

## 5. Where each level renders

One model, three surfaces, no re-derivation:

- **The plant card** wears its own level (the existing frame/state group — the level rides the
  *predicted* channel where it is a prediction, the state group where it is a present fact).
- **The greenhouse summary (G7)** counts the levels — *"1 needs you now · 1 heading for harm ·
  the rest fine until Thursday"* — and it **aggregates these words, defining none of its own.**
- **The Workbench** keeps the instrument axis in full detail (rollups, SUSPECT classes); the Home
  carries only the suppression + a plain instrument line (R12's separation, B6's promotion).

## 6. The rules a consumer must honour

1. **Two axes.** Never rank an instrument condition against a plant level; suppression only.
2. **One vocabulary.** These four level names, and R3's FIRM/ROUGH/HAZY for how-sure. A surface
   that needs a new word raises it here first.
3. **Never a mood colour for an attention level** (R8) — a level is not a reading.
4. **Never a horizon Sprout cannot support** — no forecast, no "until Thursday."
5. **Pull only** (§4) until an ADR says otherwise.

## 7. What it consumes (verified against the served payload, 2026-07-25)

The seam question put to Trellis is *"does the composed state consume the existing rollups and
exception labels, or duplicate them?"* — answered here from the artifact, so the read starts
from facts. **It consumes. One field is genuinely missing.**

| model element | the field that already exists | verdict |
|---|---|---|
| **Instrument condition** (R12) | `card.exception` = `{is, kind, reason}` — `fault` / `no_signal`, with its own reason string | **consume** — the axis is already computed and already separate from mood |
| **Needs you now** | `card.frame.mood` at/past the Thirsty edge | **consume** — D3 already ships on it |
| **Watch** | `card.next_need` = `{known, hours, hours_lo, hours_hi}` | **consume** — R3/R6 already ship on it |
| **All clear** (G3) | none needed — composed from the three above plus the soonest forecast | **derived**, no new data |
| **Heading for harm** (G2) | `segment_classifier.classify` (#1497) is imported by `card_context` but **no per-card classification reaches `/cards.json`** | ⚠ **the one real gap** — Data surfaces it, Design consumes it |

### The `urgency` field is a sort key, not a state — do not conflate them

`card.urgency` already exists and is simply `dryness`: a 0–1 position in the band envelope,
built to order the grid most-thirsty-first (#715/#747). It is **not** an attention level and must
not be renamed into one:

- it is continuous, not a level;
- it knows **only** dryness — nothing of the forecast, the exception labels, or the instrument;
- measured live: a **Parched** plant reads `0.404` and a **Thirsty** one `0.397` — nearly
  indistinguishable — while a plant heading for harm at merely **Content** reads `0.28` and
  therefore sorts *below both*. That inversion is precisely the failure G2 exists to catch.

So the attention model **composes signals `urgency` deliberately ignores**, and `urgency` stays
what it is: the tiebreak *within* a level. **R2 (#1579)** — the ranked predicted-urgency queue —
is the other consumer of this distinction; it should rank by attention level first and use
`urgency` only to order within one, rather than defining a third ranking.

## Open for ratification

- **The calm horizon's value** (what counts as "far enough away to relax"): 48h is my proposal —
  long enough that a daily glance suffices, short enough that it stays true. It wants a measured
  answer eventually (`backtest.py`) rather than a design opinion, so it ships as a named constant.
- **Whether "Heading for harm" outranks "Needs you now" in the summary's ordering.** My
  recommendation: yes — harm first, because it is the rarer and less recoverable case.

— Design 🔍
