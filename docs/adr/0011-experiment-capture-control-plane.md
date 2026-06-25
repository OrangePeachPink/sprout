# ADR-0011 — Experiment capture control plane

**Status:** Proposed — *stub; decision pending the Experiment Capture Mode Discussion + Firmware input*
**Date:** 2026-06-25
**Owner:** Data lane + Firmware lane (co-authored — the browser→host seam)
**Lane:** data/analytics ↔ firmware (control seam)
**Relates:** [PRD-0001](../prd/0001-experiment-capture-mode.md) R4 · [ADR-0005](0005-application-surface-and-frontend.md)
(this is the "control-page framework" 0005 deferred) · [ADR-0001](0001-architecture-and-control-loop.md)

---

## Context

[PRD-0001](../prd/0001-experiment-capture-mode.md) R4 requires the operator to **start, stop, and
configure** an experiment capture **from the dashboard** — no agent in the loop. A browser cannot spawn or
signal a host process directly; it needs a **host-side control endpoint**. ADR-0005 named the dashboard as
read-only and explicitly *deferred* a control surface to a later ADR — this is that ADR.

Because a web page would be able to launch and stop host capture, this is a **local control-plane and
(local) safety decision**, not just a UI feature. The constraints below are non-negotiable inputs to the
decision; the chosen mechanism is **open pending Firmware's answer in the Discussion**.

### Constraints (hold regardless of mechanism)

- **Cannot touch Monitor mode.** The control plane must never start, stop, reconfigure, or interfere with
  the always-on baseline logger or the `logs/` path.
- **Localhost-only.** Bind to `127.0.0.1`; no remote control surface, no auth-bypass exposure.
- **Single-flight.** No double-start / orphaned captures; a capture is idempotent and has one owner.
- **Honest state.** The UI must reflect actual capture state (running / stopped / auto-stopped / errored),
  consistent with the disconnected-state honesty work (issue #48).

## Decision

**OPEN — to be filled after the Discussion, with Firmware confirming the seam.** Candidate options:

- **Option A — `serve.py` owns the control API.** `serve.py` grows `POST /capture/{start,stop,config}`
  that launches/stops the logger with the chosen params and the experiment folder. Data owns `serve.py`,
  but it would be commanding a logger process (Firmware territory) — needs a clean contract.
- **Option B — the logger owns the control surface; `serve.py` proxies.** The host logger exposes the
  control endpoint; the dashboard calls it (directly or proxied through `serve.py`). Keeps process
  lifecycle with its owner (Firmware).
- **Open sub-decisions:** who owns **auto-stop** (logger timer vs. control layer); how capture state is
  surfaced to the UI; how the constraint "cannot touch Monitor mode" is *enforced* (separate process /
  separate config / refusal guard), not just intended.

*(This section is intentionally a stub. The Discussion resolves the seam and Firmware confirms; the chosen
option and its contract are recorded here before any control-plane code lands.)*

## Consequences

*To be completed once the option is chosen.*

## Revisit triggers

- Remote or multi-device control is ever wanted → re-evaluate the localhost-only / no-auth posture.
- Monitor mode itself ever needs operator controls → reconcile with this control plane rather than forking it.
