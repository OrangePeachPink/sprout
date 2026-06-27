# PRD: Operator Experience — one launcher, in-app mode switching, no manual port juggling

**Status:** Implemented (2026-06-26 — Operator Experience epic #125 + slices #126–#130 shipped via PRs #131/#132/#135/#145/#146)
**Date:** 2026-06-26
**Owner:** Data lane (with Firmware + Design)
**Epic / issues:** *cut from this PRD via `/to-issues` into tracer-bullet slices*
**Relates:** [ADR-0005](../adr/0005-application-surface-and-frontend.md) (launch seam §4–5),
[ADR-0011](../adr/0011-experiment-capture-control-plane.md) (the control plane this extends),
[PRD-0001](0001-experiment-capture-mode.md) (Experiment mode), the monitor logger (`tools/logger/`).

---

## Problem

Running Sprout is still fragile, and the maintainer hit every sharp edge in one night:

- **Entry isn't robust.** The launcher ran the local clone as-is, so a behind-`main` clone served a stale
  dashboard; worse, a **leftover `serve.py` zombie squatting on port 8765** (a previous session's detached
  process that never died) silently blocked every relaunch — the browser kept landing on the dead old
  server, which threw a raw `Unexpected token '<'` capture error.
- **The two modes are disconnected.** *Monitor* mode (the always-on logger) is a **separate manual process**
  (`just logger`), while *Experiment* mode (bounded captures) runs from the dashboard. There is no in-app
  way to switch between logging and testing.
- **The serial port is juggled by hand.** To run a serial test the operator must remember to stop the
  logger first so COM6 is free — there is no automatic handoff, so it is easy to get a confusing refusal.

The result: too many ways to end up with a stale, broken, or port-blocked app, and no single "enter the
app → switch modes → set up a test → it just works" flow.

## Goals

- **One launcher that just works** — a double-click always lands on a **working, current** dashboard. No
  stale code, no zombie, no port conflict, no terminal.
- **In-app mode switching** — start/stop **logging** and start/stop **testing** from inside the app, with a
  single obvious Monitor ⇄ Experiment control.
- **Automatic port handoff** — the app manages COM6. Switching to a test stops logging, frees the port,
  runs the test, and resumes logging — the operator never touches the port.
- **It never crashes at the operator** — every control path degrades to a clear message, never a raw error.

## Non-goals

- Not a rewrite — this **extends** the existing control plane
  ([ADR-0011](../adr/0011-experiment-capture-control-plane.md)), it does not replace it.
- Not remote / multi-user access (an ADR-0005 revisit trigger, separate decision).
- Not a packaged / tray app — deferred per [ADR-0005](../adr/0005-application-surface-and-frontend.md) §7.
- Not watering/actuation control — that is Firmware's separate epic.

## What already exists (this epic is mostly glue)

- Experiment **control plane** — start/stop captures from the dashboard (#66/#81/#85, ADR-0011).
- The **serial mutex + advisory lock** — monitor and experiment can never both hold COM6 (#64/#85).
- The **test-setup form** + source/port selector (#98/#105); **graceful** capture errors (#115).
- The **launcher** (#102) + **self-update** (#119, in flight); the **fixed-port SSOT** (#86).

The gap is: the control plane only manages *experiment* captures (not the *monitor* logger), there is no
mode switch, the handoff is manual, and the launcher can still serve stale or be port-blocked.

## Requirements

- **R1 — Port-safe entry.** Launching when a server already holds the fixed port must **not** silently serve
  a stale instance. `serve.py` detects port-in-use and reports it clearly (and/or the launcher frees a stale
  Sprout server first). A zombie can never block entry. *(The exact failure the maintainer hit.)*
- **R2 — Self-updating launcher.** The launcher runs `git pull --ff-only` on start (#119), so the icon always
  launches the current code. Non-fatal offline.
- **R3 — In-app Monitor control.** The control plane gains **monitor start/stop** — the dashboard can start
  and stop the always-on logger, the same way it launches a capture (`serve.py` owns the lifecycle, the
  spawned process owns the port; localhost-gated).
- **R4 — Mode-switch UX.** A single, obvious **Monitor ⇄ Experiment** control that shows the active mode and
  switches in one action. Design owns the visual model.
- **R5 — Automatic COM6 handoff.** Switching Monitor → Experiment (and back) is **automatic**: stop logging
  → free the port → run the test → resume logging, built on the existing mutex + advisory lock. The operator
  never touches the port.
- **R6 — No raw crashes.** Every control path degrades gracefully (extend #115's pattern to monitor control).
- **R7 — Visible, stoppable lifecycle.** The running server is visible and stoppable from the UI (the Stop
  control) — no hidden, forgotten zombies.

### Lane split

- **Data:** the control-plane extension (monitor start/stop), `serve.py` port-safety, the mode-switch UI +
  handoff orchestration, graceful errors. Authors the operator-control ADR when the control-plane slice is cut.
- **Firmware:** launcher robustness (self-update #119 + freeing a stale server), the runner.
- **Design:** the Monitor ⇄ Experiment mode-switch UX (states + the toggle), token-faithful.

## Acceptance criteria

- [ ] **One double-click → a working, current dashboard, every time** — no stale code, no zombie, no port
      conflict, no terminal step. A stale/zombie server **cannot** block entry (R1/R2).
- [ ] The operator can **start and stop the monitor logger from the dashboard** (R3).
- [ ] The operator can **switch Monitor ⇄ Experiment in-app**, and the **COM6 handoff is automatic** — no
      manual port juggling, no remembering to stop the logger (R4/R5).
- [ ] **No raw error ever reaches the operator** from any control path (R6).
- [ ] The running server is **visible and stoppable** from the UI; no hidden zombie can accumulate (R7).
- [ ] Monitor mode and the baseline logging path remain **behaviourally unchanged** when driven the old way
      (`just logger` still works); this adds control, it does not break the existing path.

## Phasing (tracer bullets)

The build order, cut into slices via `/to-issues`, each a `Refs` PR through the gate:

1. **Robust entry** — R1 + R2: self-updating launcher (#119) + `serve.py` port-safety (a busy port reports
   clearly / the launcher frees a stale server). **First win: the icon always opens a working current
   dashboard** — the maintainer's nightly pain, gone.
2. **In-app Monitor control** — R3: extend the control plane to start/stop the logger; a Monitor start/stop
   control in the dashboard. Authors the operator-control ADR (extends ADR-0011).
3. **Mode switch + automatic handoff** — R4 + R5: the Monitor ⇄ Experiment toggle + the automatic COM6
   handoff via the existing mutex.
4. **Polish + graceful** — R6 + R7: graceful errors across the unified control plane, the visible/stoppable
   lifecycle, and the unified operator UX.

## Out of scope / later

- A tray / packaged app, remote access, and watering-actuation control — separate, later decisions.
- Multi-device / multi-port operation — the handoff generalizes later if a second rig is added.
