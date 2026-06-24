# ADR-0005 — Application surface & frontend

**Status:** Accepted (2026-06-24)
**Date:** 2026-06-24
**Owner:** Data lane
**Lane:** data/analytics (host application surface)
**Elaborates:** [ADR-0002](0002-process-tiers.md) #5 (Running the app), #17 (Frontend stack — Data half).
**Consumes:** [ADR-0004](0004-design-system.md) (Design's token/component system + consumption contract)
when present.

---

## Context

The host side of Sprout has grown a real user-facing surface: a four-channel analytics dashboard
(served live and as a self-contained static file), per-plant forecasting views, calibration and
data-quality panels, time-range and per-channel controls. More host UI is coming — operator/control
views (manual "water plant 3," tank/pump status, settings) as the actuator and connectivity work
lands.

Left unmanaged, that growth produces the classic failure mode: a pile of mismatched pages on different
ports, launched different ways, styled inconsistently — "which tab/port was the thing I wanted?" This
ADR makes the deliberate choice for **how host functionality is presented and built**, before the
sprawl happens. It records the served-app **runtime/stack** (ADR-0002 #17, Data half) and the operator
**launch** model (ADR-0002 #5) — two facets of one surface.

## Decision

### 1. One application surface (durable principle)

**All host functionality presents as a single, integrated, consistent console** — analytics now,
operator/control views folded in later — never a pile of separate pages, ports, or stacks. There is
**one application**, one launch UX, one visual language. New host capability is added *into* this
surface, not alongside it.

### 2. Frontend stack: vanilla, no build step

The application is **vanilla HTML / CSS / JS + Chart.js**, with **no build step, no bundler, no
framework**. It ships as a self-contained artifact (Chart.js vendored and inlined) that opens offline,
and is also served live for in-place refresh. Rationale: boring-first and local-first — a
single-operator local console gains nothing from an SPA toolchain and loses the "one file you can open
offline" property. (A framework is *earned* later by a named interactivity/state gap — see triggers.)

### 3. Consumes the Sprout design language (does not own it)

The app **consumes** the design system: it imports the tokens (`docs/design/sprout-tokens.css`) and the
component patterns, so the UI stays consistent regardless of which view or process serves it. Per the
ADR-0002 row #17 split, **Design owns the token/component system and the consumption contract
(ADR-0004 / #18); this lane owns the application that consumes it.** New tokens are *requested from
Design*, not invented here.

### 4. Operator launch UX (ADR-0002 #5)

Operator self-serve, never "ask an agent to start the server":

- **Fixed port** (8765) so the operator always knows the URL.
- **Operator-launched** via a single command.
- **In-UI stop** — a control in the app (a `localhost`-gated shutdown endpoint) so the operator can
  stop it from the UI, not only by hunting down a terminal.

### 5. The launch seam (#5 ↔ ADR-0002 #4)

The application exposes a **stable launch entrypoint** (`tools/analytics/serve.py`). The **task runner
(`just start`, ADR-0002 #4, Firmware lane) invokes that entrypoint** — it does not re-implement the
launch. Co-built seam: **Data owns the entrypoint + fixed port + in-UI stop; Firmware owns the runner
plumbing.**

### 6. Read-only safety boundary

The host application is **read-only with respect to capture and hardware**: it reads `logs/` and the
archive, never the serial port, and never the firmware. Any future control action (manual watering)
routes through the firmware's own safety interlocks — the UI is a client, never a bypass.

### 7. The control-page framework is deferred

If/when a device-served or richer **control page** is actually built, its stack (React + TS + Tailwind,
or otherwise) is a **separate, later decision in its own ADR** — we are not ratifying a framework we do
not yet need. Whatever it is, it must still present as part of the **one application surface** (§1):
consistent language, one launch model — not a mismatched second UI.

## Consequences

- Host functionality reads as one coherent console, not a sprawl of pages/ports.
- Zero build friction; the analytics artifact stays openable offline as a single file.
- Visual consistency is guaranteed by consuming Design's tokens rather than re-styling per view.
- The launch model is unambiguous and operator-owned, with a clean Data ↔ Firmware seam.
- A future control UI has a bounded decision: its own ADR for stack, but it must fold into this surface.

## Revisit triggers

- The app needs interactivity/state that vanilla makes genuinely painful → a framework is *earned* by
  that named gap (new ADR), still feeding the one surface.
- A device-served control page is actually built → record its stack in its own ADR.
- The single self-contained file grows unwieldy → consider a minimal build step (still no SPA).
- Remote / multi-user access is wanted → that changes auth, hosting, and safety — a new decision.
