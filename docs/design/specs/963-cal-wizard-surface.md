# The owner-cal wizard — surface spec against the merged receipt

**Issue:** #963 · **Status:** spec, for build · **Lane:** Design-QA 🔍
**Binds to:** `cal_receipt.py` (merged) — `stored` / `pushed` / `confirmed`, `Receipt.is_live`

---

## The question this answers

I asked, when the wizard was still blocked: *what does the surface do when the board
isn't reachable at bench time?* The architecture answered it — three states, with
`stored` as the honest terminal for a serial-only board. This spec is my half of that
answer: **how those states render without lying in either direction.**

Two failure modes, and the second is the one that gets missed:

1. **Implying failure while `confirmed` is pending.** She calibrates, sees anything
   short of a tick, and concludes the wizard didn't work — when `stored` means the cal
   exists, survives restarts, and works with no board at all.
2. **Implying pending when the state is terminal.** `evaluate()` returns `pushed` for
   three materially different situations, and **two of them can never reach
   `confirmed`**. A spinner on those is a promise the system cannot keep.

## The ruling: `stored` is a success state, not a partial one

The wizard's job is to capture an envelope and make it durable. `stored` completes that
job. Push and confirmation are **enrichment of a finished thing**, not conditions of
success — so the result screen's headline reflects `stored` and never withholds
completion pending a board.

This is the same posture as #822's honest declines and #1229's retained glug state: say
what *is* true, never imply what isn't, in either direction.

## The result screen

**Headline — always, the moment the record is written:**

> **Saved.** This sensor has its own envelope now.

Then one calm line about the board, in the **chrome register — never a state colour**.
Nothing on this screen needs her action, so nothing on it earns amber or red.

| Receipt | The line | Why |
|---|---|---|
| `stored` (not pushed) | *Living on this computer. Your board keeps using bench calibration until this reaches it.* | True and complete. Names what the board is doing meanwhile, so the gap isn't a mystery. |
| `pushed`, awaiting a WiFi row | *Sent to the board — waiting for it to report back.* | Genuinely in progress. No spinner-of-doom; the wizard is closable. |
| `pushed`, **serial-only board** | *Sent. This board reports over USB, so it can't confirm back — that's expected, not a problem.* | **Terminal, not pending.** `cal_src` rides WiFi rows only; waiting is waiting forever. |
| `pushed`, **no provenance on the profile** | *Sent. There's no provenance recorded for this calibration, so there's nothing to match against.* | **Terminal, and fixable** — offer "add provenance", the one action that changes it. |
| `confirmed` | *Your board is using it.* | The only state that means what people assume "saved" means. |

**Never:** a spinner on either terminal row · a red or amber treatment on any row ·
a percentage or progress bar (there is no measurable progress) · the word *failed* for
any state the contract produces.

## After the wizard closes

Confirmation arrives by telemetry, minutes later — **after** she's dismissed the modal.
So the state cannot live only in the wizard.

- The **channel row in the registry editor** carries the current receipt state, using
  the same five renderings.
- The transition to `confirmed` is **quiet** — the row updates, nothing announces
  itself. A toast for "the thing you already did is still fine" is noise.
- The tier chip is **untouched** by all of this (ruling A, #963): it stays scope-only
  (`channel-cal | board-cal | uncalibrated`); receipt state is a separate axis and never
  becomes a fourth chip value.

## Re-push, and what we don't do

- A `pushed`-but-unconfirmed row offers **"send again"** — explicit, hers to press.
- **No silent auto-retry.** A background retry that sometimes fixes it is how you get a
  system whose state nobody can explain.
- **No timeout that flips to failure.** If it hasn't confirmed, the honest statement is
  *"sent; not seen in a reading yet"* — a fact with no expiry attached. Inventing a
  deadline invents a failure.

## Absence, as everywhere else

A channel with no owner cal shows **nothing** here — it's not a warning state. The
standing calibrate offer (§5.4 of the #1335 spec) is the entry point; this surface only
ever describes a calibration that exists.

## Build notes

- `Receipt.is_live` is the single predicate for "actually running"; no surface
  recomputes it.
- **no-provenance is bindable** — `expected_cal_src is None` identifies it cleanly.

### One real gap, measured not guessed — `for:data`

I ran `evaluate()` across all five situations. **A serial-only board and a board that is
merely still-reporting produce byte-identical receipts:**

| situation | state | expected_cal_src | observed_cal_src |
|---|---|---|---|
| pushed, WiFi board, no row yet | `pushed` | `owner-field` | `None` |
| pushed, **serial-only board** | `pushed` | `owner-field` | `None` |

Same branch, same fields, same `detail`. So the surface **cannot** tell *"waiting, will
confirm shortly"* from *"will never confirm"* — and would show a waiting line forever to
a serial-only board. That is precisely the failure this spec exists to prevent, arriving
from the direction nobody was watching.

Two ways to close it:

- **A — the receipt carries transport awareness** *(my recommendation)*. `evaluate()`
  already knows the profile; giving it the channel's transport (or an explicit
  `confirmable: bool`) makes the distinction data rather than inference. One field,
  and every surface gets it right for free.
- **B — the surface resolves it** from the device registry's `transport` / `rssi`
  presence. Workable, and I can ship it — but it is a second place that reasons about
  what a board can do, which is the shape of defect ADR-0038 exists to prevent.

I'd rather not ship B quietly. Until it's ruled, the surface renders the **waiting**
line for both, which is wrong-but-harmless for serial-only (it says "waiting", not
"failed"), and I'll switch to the terminal copy the moment the distinction is available.

---

*Ratified inputs: #963 ruling A (chip stays scope-only) · the merged `cal_receipt`
contract · ADR-0028 (absence is first-class) · the #822 honest-decline pattern.*
