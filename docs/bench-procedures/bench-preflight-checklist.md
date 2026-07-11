# Bench Preflight — Run Checklist (the "run" half of the #332 pair)

> **The at-the-bench run-table + evidence-note template.** The *explain* half — *why* each seam matters,
> grounded in real sessions — is [`docs/process/BENCH_PREFLIGHT.md`](../process/BENCH_PREFLIGHT.md). This
> one *runs*; that one *explains*. **Keep them in sync** — if a seam changes here, update it there.
>
> **Capability-stage vocabulary** (Sage's): *code-staged → bench-wired → dry-verified → wet-verified →
> plant-deployed → autonomous-enabled.*

## Announce (state these at the top of the block — §0)

- [ ] **Board / `device_id`** on the bench, and its **capability stage**.
- [ ] **What's running:** app/server vs firmware — two different machines (§1).
- [ ] **Which port**, and **who owns it** — exactly one process (§2).
- [ ] **Capture source:** real wired hardware, not a synthetic/stub feed (§3).
- [ ] **Cadence** now on the device, and whether it's `temp` (session-only) or persisted (§4).

## Run-table (tick each before any evidence row counts)

| # | Gate | Check | ✓ |
|---|---|---|---|
| 1 | App ≠ flash | restarting the server did **not** reflash the board (different machines) | ☐ |
| 2 | Port owner | exactly **one** process on the serial port (monitor **or** logger, not both) | ☐ |
| 3 | Real source | readings are from the wired probe, not a synthetic/stub feed | ☐ |
| 4 | Cadence on purpose | `!cad` set deliberately; note `temp` vs persisted (persisted survives reboot) | ☐ |
| 5 | Banner (after any flash) | boot banner shows the expected `fw=` / `git=` / `board=` | ☐ |
| 6 | Raw-only CSV | `raw_value` is the evidence column — no smoothed/derived value passed off as raw | ☐ |
| 7 | Local-time labels | timestamps carry the local offset, not bare/ambiguous | ☐ |

## One-line gate

> Before any evidence row counts: **one board named · one port owner · real source · cadence-on-purpose ·
> banner-verified · raw column honest · time labeled.** If any is unknown, the block is not yet running.

## Evidence-note template (paste into the session log, per block)

```text
board / device_id : <id>           capability stage : <code-staged|bench-wired|dry-verified|...>
running           : <app|firmware>  fw=<ver> git=<sha>   port owner : <process>
cadence           : <ms> <temp|persisted>               capture source : <real probe|cup|air>
local-time offset : <e.g. CDT -05:00>                   evidence file  : <path>
what this block proves : <one line>
confounds noted   : <placement | pour-location | environmental | bench-artifact | none>
raw column        : raw_value (honest, unsmoothed)
```

---

*Companion: [`docs/process/BENCH_PREFLIGHT.md`](../process/BENCH_PREFLIGHT.md) — the **explain** half (#332).
This is the **run** half.*
