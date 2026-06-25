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

### Firmware detail — the `set_cadence` command (#63)

The capture process sets the experiment cadence with one host→device serial command; the device stays
firmware-timed (it free-runs the sweep, the host never polls).

**Grammar.** A single ASCII line, checksummed like the telemetry rows so a corrupted command can never
silently mis-set timing:

```text
!cad,<ms>*HH\n
```

- `!` marks a command — distinct from data rows (`plants.*`) and `#` headers.
- `<ms>` is the unsigned-integer sweep period.
- `*HH` is the 2-hex XOR over the body `cad,<ms>` (same algorithm as the row checksum) and is **required**;
  a bad checksum is rejected with the cadence unchanged.

**Acknowledgement** — on the device's existing `#` header stream, so the capture process knows it took:

```text
# ack cad=<ms> prev=<old> floor=<floor>      # accepted
# nak cad=<bad> err=<reason> floor=<floor>   # rejected - cadence UNCHANGED
```

`reason` is one of `checksum` / `range` / `parse`. The capture process waits for `ack`/`nak` before
treating the rate as changed.

**Valid range — a config-dependent floor.** Any integer ms in `[floor, 3_600_000]`. The device computes the
**floor from its current config** (channels x baud x burst) and rejects anything below it (`err=range`).
For the shipped 4-channel / 19200-baud / 100-sample monitor config the floor is **~500 ms** (the ~0.3 s
sweep plus headroom for the periodic header reprint), so the PRD's v1 tiers map cleanly: **5 s and 1 s are
comfortable, 0.5 s sits right at the floor** (accepted, with the margin reported in the ack). **Sub-second
(0.25 / 0.1 s) is rejected** in the shipped config and only becomes valid once the stretch config (115200
baud / 16–32-sample burst / single-channel) lowers the floor — the labeled stretch goal, bench-validated
after the baseline window.

**Mid-sweep change** is parsed but **applied at the next scheduling boundary** — never mid-row. The device
finishes the current burst, then the new period governs the next read; a row is never split or re-timed.

**Error, timeout, persistence.**

- Malformed / bad-checksum / out-of-range → `nak`, **cadence unchanged** (a bad command can never change
  timing — the safe default).
- The capture process waits `max(2x the current cadence, 1500 ms)` for the ack; on timeout it retries once,
  then surfaces "device not acking" rather than assuming the rate changed.
- Re-sending the same cadence is idempotent.
- Cadence is **RAM-only, not persisted** — a reboot (including the DTR reset on port-open, see the handoff
  detail) returns the device to its compile-time default (the monitor cadence), so a power-cycle can never
  leave it stuck sampling fast; the host re-applies the experiment rate after every open.
- The command is **cadence-only** — it cannot enable actuation, change band boundaries, or alter the schema.

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
