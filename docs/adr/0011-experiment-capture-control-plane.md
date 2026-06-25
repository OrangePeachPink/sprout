# ADR-0011 — Experiment capture control plane

**Status:** Proposed — *direction agreed (Firmware, Discussion #57); full decision detail co-authored when
sub-issues are cut*
**Date:** 2026-06-25
**Owner:** Data lane + Firmware lane (co-authored — the browser→host seam)
**Lane:** data/analytics ↔ firmware (control seam)
**Relates:** [PRD-0001](../prd/0001-experiment-capture-mode.md) R4/R10 · [ADR-0005](0005-application-surface-and-frontend.md)
(this is the "control-page framework" 0005 deferred) · [ADR-0001](0001-architecture-and-control-loop.md)

---

## Context

[PRD-0001](../prd/0001-experiment-capture-mode.md) R4 requires the operator to **start, stop, and
configure** an experiment capture **from the dashboard** — no agent in the loop. A browser cannot spawn or
signal a host process directly; it needs a **host-side control endpoint**. ADR-0005 named the dashboard as
read-only and explicitly *deferred* a control surface to a later ADR — this is that ADR.

Because a web page would be able to launch and stop host capture, this is a **local control-plane and
(local) safety decision**, not just a UI feature.

### Constraints (hold regardless of mechanism)

- **Cannot touch Monitor mode.** The control plane must never start, stop, reconfigure, or interfere with
  the always-on baseline logger or the `logs/` path.
- **Localhost-only.** Bind to `127.0.0.1`; no remote control surface, no auth-bypass exposure.
- **Single-flight.** No double-start / orphaned captures; a capture is idempotent and has one owner.
- **Honest state.** The UI must reflect actual capture state (running / stopped / auto-stopped / errored),
  consistent with the disconnected-state honesty work (issue #48).

## Decision

**Option A, refined (agreed with Firmware, Discussion #57). Detail co-authored at sub-issue cut.**

1. **`serve.py` owns the operator control API** — `POST /capture/{start,stop,config}` (localhost-only).
   It validates the request and **launches a separate, bounded capture process**; it does **not** touch the
   serial port or the data itself.
2. **The capture process owns the device.** That child process holds the serial port, issues the
   `set_cadence` command, applies the chosen cadence/subject/labels, and writes the **isolated**
   `experiments/<experiment_id>/` file. Keeping the port and data out of `serve.py` means the web server
   never sits between the device and its bytes.
3. **Auto-stop is capture-process-owned and fail-safe** — the bounded duration is enforced by the capture
   process's own timer, so it stops itself **even if `serve.py` or the browser dies**. A manual stop
   (via the control API) is a secondary signal.

### The invariant this ADR encodes — serial-port mutual exclusion

Only one process can own COM6. **An experiment capture must not start while Monitor mode holds the port**,
and vice-versa. The control API refuses a start with an honest message unless the monitor has released the
port. This is *how* the "cannot touch Monitor mode" constraint is enforced — by exclusion, not intention —
and it is why real experiments naturally wait until after the baseline window and the probes are pulled
(PRD-0001 R10).

### Lane split

- **Data:** the `serve.py` control API, capture-process launch/lifecycle, request validation, and surfacing
  capture state to the UI.
- **Firmware:** serial-port ownership semantics and the `set_cadence` runtime serial command (cadence is
  firmware-timed; the host never polls).

*(To finalize when sub-issues are cut: the control-API request/response contract, the capture-process
lifecycle + state file the UI reads, and the precise port-handoff / refusal protocol between monitor and
experiment.)*

## Consequences

- The operator gets in-screen capture control without the web server ever owning the serial port or data.
- The baseline is protected **by construction** (the mutex), not by discipline.
- Captures are robust to a dead browser/server (fail-safe auto-stop) — no orphaned runs holding the port.
- A new host process type (the capture process) enters the system; its lifecycle and state surface need a
  defined contract (deferred to the sub-issue detail).

## Revisit triggers

- Remote or multi-device control is ever wanted → re-evaluate the localhost-only / no-auth posture.
- Monitor mode itself ever needs operator controls → reconcile with this control plane rather than forking it.
- The port-handoff protocol proves fragile in practice → revisit how monitor/experiment exclusion is
  coordinated (e.g. an explicit broker).
