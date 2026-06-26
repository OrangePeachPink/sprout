# ADR-0014 — Operator control plane (Monitor + Experiment under one plane)

**Status:** Proposed — *direction set by the Operator-Experience epic (#125); detail co-authored as the
slices land*
**Date:** 2026-06-26
**Owner:** Data lane
**Lane:** data/analytics (the operator control surface)
**Extends:** [ADR-0011](0011-experiment-capture-control-plane.md) (the experiment control plane),
[ADR-0005](0005-application-surface-and-frontend.md) (the launch seam §4–5).
**Relates:** [PRD-0003](../prd/0003-operator-experience.md).

---

## Context

[ADR-0011](0011-experiment-capture-control-plane.md) gave `serve.py` a localhost control plane that
launches a **bounded experiment capture** as its own process (the process owns the serial port; serve.py
never touches it). But Monitor mode — the always-on logger — stayed a **separate manual process**
(`just logger`), so the operator could not switch between logging and testing in-app, had to juggle COM6
by hand, and a stale server could block entry. [PRD-0003](../prd/0003-operator-experience.md) closes that.

## Decision

### 1. One control plane, both modes

`serve.py` owns the lifecycle of **both** modes — Experiment captures (`/capture/*`) **and** the Monitor
logger (`/monitor/*`) — launching each as its own process that owns the port. serve.py still never touches
the serial port itself. A `MonitorController` mirrors the experiment `CaptureController`: single-flight
`start` / `stop` / `status`, localhost-gated. Monitor mode is *continuous* (no duration / auto-stop); a
stop is a terminate (the logger flushes every row; the next start's archive step catches up).

### 2. The serial mutex governs the single COM6 holder

The advisory lock (#64/#83) + the OS-exclusive open guarantee that only **one** of {monitor, experiment}
holds COM6 at a time. `MonitorController.start` refuses while an **experiment** holds the port; the
experiment control plane already refuses while the **monitor** holds it. The Monitor⇄Experiment switch
orchestrates the **automatic handoff** (stop logging → run test → resume logging) on top of this mutex
(slice 4, #129) — the operator never touches the port.

### 3. Port-safe entry

`serve.py` **connect-probes** the fixed port before binding (reliable on Windows, where `SO_REUSEADDR`
would otherwise let a second server silently bind a port a zombie holds); a plain launch reports a busy
port, and the **launcher takes over** a stale Sprout server via its `/quit` endpoint
(`serve.py --restart`, #127) — no zombie can block entry, and the launcher self-updates so the icon
always serves current code.

### 4. Graceful + visible lifecycle

Every control path degrades to a clear message (never a raw error), and the running server is visible +
stoppable from the UI (#115 extended across the unified plane, slice 5 / #130) — so hidden zombies cannot
accumulate.

## Consequences

- Logging and testing are both one-click from the app; the operator never opens a terminal or touches COM6.
- The two modes share one control plane and one mutex, so they cannot fight over the port or double-bind.
- Entry is robust: stale code self-updates, a busy port is reported, and a zombie is taken over — not joined.
- The control surface stays localhost-only and process-isolated (serve.py launches; the child owns the port).

## Revisit triggers

- The Monitor⇄Experiment handoff needs richer state (paused/resuming) than start/stop → extend the status model.
- A second rig / port is added → the controllers + mutex generalize to per-port.
- Remote / multi-user access is wanted → that changes auth + the localhost gate (an ADR-0005 revisit).
