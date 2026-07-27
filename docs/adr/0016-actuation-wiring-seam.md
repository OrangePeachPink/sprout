# ADR-0016 — Actuation wiring seam: the supervisor is the single sample & actuation authority

**Status:** Accepted (2026-06-27) — ratified by the maintainer (Veronica); Firmware + Data confirmed their
register rows (#94 / #232). Drafted by Trellis.
**Date:** 2026-06-27
**Owner:** Firmware lane / architecture (Data lane co-owns the telemetry-derivation + health-signal rows)
**Lane:** architecture / firmware (cross-lane: Data)
**Extends:** [ADR-0001](0001-architecture-and-control-loop.md) — this is the "Control wired (read-only →
actuating)" revisit that ADR-0001 anticipates.

---

## Context

[ADR-0001](0001-architecture-and-control-loop.md) set the control/observability split and the
closed-loop-on-soil-moisture design, and recorded that the irrigation supervisor (`firmware/lib/irrigation/`)
is host-tested but **not wired**. It named a revisit trigger: *"Control wired (read-only → actuating): revisit
when the supervisor is enabled on hardware."*

That moment is arriving in stages:

- **#222 (merged)** wired the **manual** bounded pulse (`!water` / `!stop`, the `pump_pulse` module) —
  operator-driven, not autonomous.
- The **autonomous** slice (call `irrig_tick` from the loop) is next, gated behind **#2** (health-veto) and
  the **#191** bench.

Wiring the supervisor surfaces two seam questions ADR-0001 left open — both **cheap to settle now and
expensive to retrofit** once code lands:

1. **Sampling ownership.** Today `main.cpp` runs its own cadence-gated telemetry sweep; the supervisor also
   wants to sample (via its `read_raw` callback). Two samplers double-read **and** break the supervisor's hard
   invariant "no probe is sampled while a pump runs."
2. **Actuation authority.** #222's `pump_pulse` drives relays directly; the supervisor's `set_pump` also drives
   relays. Two independent drivers can both energize a coil — violating "at most one pump" — and the
   supervisor's model of pump state diverges from the wire.

## Decision

**When the supervisor is wired, it becomes the single authority for both sampling and actuation in the control
loop.** Concretely:

1. **Single sample owner.** The supervisor owns ADC sampling via `read_raw`; the standalone telemetry sweep in
   `main.cpp` is removed. Telemetry rows are **derived from supervisor state** (`irrig_level` / `last_raw` /
   `last_spread` / `irrig_health_warn`) and emitted **only while `irrig_mode() == SYS_SAMPLING`** (pumps off),
   preserving invariant #2 structurally. The runtime cadence command (`!cad`) updates the supervisor's
   `sys.sample_period_ms`, not a separate gate.
2. **Single actuation authority.** All relay drives go through the supervisor. The manual pulse (`!water` /
   `!stop`) is expressed as a **forced-dose request into the supervisor**, not a second independent driver — so
   "at most one pump" and the hard max-on ceiling hold for operator and autonomous actuation alike.
3. **One health signal.** The same spread/health signal drives both the telemetry `quality_flag`
   (`SUSPECT` / `NO_SIGNAL`) and the supervisor's dose veto, so the log and the pump can never disagree (the
   **#2** seam).
4. **Pump-event logging is not sampling.** `plants.pump` events (`io.on_event`) are emitted during a dose; the
   "no sampling while watering" invariant constrains **ADC reads**, not serial output.

The framework-agnostic, host-testable core (ADR-0001) is preserved: `read_raw` / `set_pump` / `on_event` stay
the only Arduino seam, and the wiring path gets native tests (at-most-one-pump, no-sample-during-watering,
veto-blocks-dose, forced-dose-respects-ceiling).

### Rejected alternatives

- **`main.cpp` keeps owning sampling and feeds the supervisor cached values.** Rejected: duplicates the
  sampler, reintroduces the invariant-2 hazard, and splits cadence control across two owners.
- **Two relay drivers (pulse + supervisor) with ad-hoc coordination.** Rejected: no single source for
  pump state; "at most one pump" becomes a runtime race instead of a structural guarantee.
- **An auto/manual mode interlock** (only one path live at a time). Workable, but two safety-critical code
  paths to keep correct versus one authority — rejected for the simpler invariant.

## Consequences

- The supervisor's two hard invariants (≤ 1 pump; no sampling while pumping) hold **structurally**, for both
  manual and autonomous actuation — not by convention.
- Telemetry and control share one sample and one health signal, so the log always reflects what the pump
  actually saw.
- **Soil-row telemetry has intentional gaps during a dose:** rows emit only while `irrig_mode() == SYS_SAMPLING`,
  so `SYS_WATERING` / `SYS_SETTLE` windows produce pump events, not soil rows. Correct-by-design (invariant #2) —
  `TELEMETRY_SCHEMA` and any dashboard "missing data?" logic must **expect** the gap, not flag it (Firmware's
  flag on the Data row).
- The autonomous slice becomes a **disciplined refactor** (delete the second sampler; fold the pulse into the
  supervisor) rather than new logic — the brain is already built and host-tested.
- Small migration cost: the #222 manual-pulse path is re-expressed as a supervisor forced-dose, and `!cad` is
  pointed at `sys.sample_period_ms`.
- Provisional dose / soak / max-on config ships conservative until per-channel calibration (#170 / #192)
  tightens it.

## Revisit triggers

- **Per-channel calibration lands (#170 / #192):** dose thresholds + ceilings move from provisional to
  calibrated — revisit the config values (not this seam).
- **A second actuator class** (valves, lighting, a second relay board): revisit whether "single actuation
  authority" needs a per-actuator-class supervisor.
- **Remote / WiFi control of actuation is ever proposed:** the single-authority rule must absorb the remote
  path too (no out-of-band relay drive) — revisit.
