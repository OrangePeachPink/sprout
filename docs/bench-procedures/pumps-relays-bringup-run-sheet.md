# Pumps + relays bring-up run sheet (0.9.0 readiness)

**One execution-ordered sheet for the maintainer's bench slot** — unbox, standalone-test, and
power-plan the pumps and relays so the v0.9.0 Water wave lands on prepared hardware. This is
**standalone characterization** (bench PSU + meter + manual switching); it does **not** connect a
pump to an MCU-driven relay. That step waits on the safety gate.

Refs #1451 · #93/#191 (the safety gate — passes FIRST) · #215 (energized-level
convention) · #94 (the actuation epic this readies)

> **⚠️ Order of operations, non-negotiable.** No pump connects to a relay the MCU drives until
> **#191 passes** (watchdog resets a wedged loop + relays read de-energized at boot —
> [safety-gate-run-sheet.md](safety-gate-run-sheet.md)). This sheet is the *standalone* half:
> characterize the parts on a bench supply so the numbers exist when the gate opens. The two can
> run in either order; the **connection** of the two is gated.
>
> **⚠️ Power rule (AGENTS current-budget).** Pumps and relay coils are driven from **their own
> supply rail, NEVER the MCU's 3.3 V/5 V rail.** A pump inrush or a stalled motor will brown out
> the ESP32 and reset it mid-dose. The only wire shared with the MCU is **common ground** (so the
> relay control logic references the same 0 V). Deciding this rail is §3 and it is the load-bearing
> AC.

---

## §0 Pre-flight

- [ ] **Bench PSU** with current display (the FNIRSI on the bench), set to the pumps' rated voltage
      before connecting — confirm the rating on the pump body/listing first (§1).
- [ ] **Multimeter** for coil/continuity checks; **known-good pump tubing + a water cup** for a wet
      run only AFTER the dry electrical checks pass.
- [ ] **Do NOT connect anything to the ESP32 this session.** Relays are switched by hand (a jumper
      to the control pin at 3.3 V, or the module's own test), pumps run straight off the PSU.

## §1 Pumps — standalone characterization

- [ ] **Unbox + identify:** record the pump type (diaphragm/peristaltic), the **rated voltage**, and
      any printed current/flow spec. Photograph the body markings.
- [ ] **Dry idle draw:** PSU at rated V, pump dry (no water), record the **running current**. Stop
      quickly — most small pumps should not run dry for long.
- [ ] **Wet running draw:** prime with tubing into a water cup, record the **steady running
      current** and a rough **flow** (mL over 10 s → mL/s). This is the number the dose math needs.
- [ ] **Stall/inrush note:** briefly pinch the outlet tubing and watch the current jump — record the
      **stall current** (the worst case the power rail must survive). Do not hold it stalled.
- [ ] Cross-check against the firmware ceiling: a dose is bounded by **`PUMP_PULSE_MAX_MS = 5000`**
      (hard, < the 8 s watchdog). At the measured flow, note how much water a max pulse moves — sanity
      that 5 s can't overflow a small pot.

| pump | rated V | dry A | wet A | stall A | flow (mL/s) |
| --- | --- | --- | --- | --- | --- |
| #1 |  |  |  |  |  |
| #2 |  |  |  |  |  |
| #3 |  |  |  |  |  |
| #4 |  |  |  |  |  |

## §2 Relays — standalone characterization

The firmware convention (already shipped): the **CW-022 board is active-LOW** — control pin **LOW =
energized (pump ON)**, **HIGH = de-energized (pump OFF)** (`RELAY_ON_LEVEL = LOW`,
`RELAY_OFF_LEVEL = HIGH`, `include/config.h`). Classic control pins are **GPIO 25 / 26 / 27 / 32**.

- [ ] **Coil draw per channel:** energize each relay (drive its control pin LOW — a jumper from GND
      through the module's IN pin, or the board's own test), meter the **coil current** the driving
      rail must supply. Four channels may energize together — record the **sum**.
- [ ] **Switching verified:** with the PSU across the relay's COM/NO (a pump or a dummy load),
      confirm the load switches ON at control-LOW and OFF at control-HIGH. Listen for the click,
      confirm with continuity or the load.
- [ ] **Idle state matches firmware:** control pin **HIGH → load OFF**. This is what `allRelaysOff()`
      drives at boot; a board wired opposite would run every pump at power-on.
- [ ] **Opto-isolation / JD-VCC jumper:** note whether the CW-022's JD-VCC jumper is fitted (coil
      power shared with logic) or removed (isolated coil supply) — this decides §3's ground/rail plan.

| relay ch | GPIO | coil A (each) | switches at LOW? | OFF at HIGH? |
| --- | --- | --- | --- | --- |
| ch0 | 25 |  | ☐ | ☐ |
| ch1 | 26 |  | ☐ | ☐ |
| ch2 | 27 |  | ☐ | ☐ |
| ch3 | 32 |  | ☐ | ☐ |

## §3 Power plan — the load-bearing AC

- [ ] **Sum the budget:** worst-case = (all four pumps' **stall** A) + (all four relay coils' A).
      Real doses are one channel at a time, but the supply must survive a simultaneous stall + the
      inrush without sagging.
- [ ] **Pick the supply:** a dedicated pump/relay rail at the pumps' rated voltage, rated **≥ the
      worst-case budget with margin.** Record make/model + rated A.
- [ ] **Never the MCU rail.** The ESP32 keeps its own supply. The pump rail and the MCU share
      **only common ground** so the relay control logic references the same 0 V.
- [ ] **Flyback/back-EMF:** confirm each pump has a flyback diode (the CW-022 relay contacts + the
      pump motor — a motor without a snubber will arc the contacts and inject noise). Add one if the
      pump has none.
- [ ] **Write the decided plan into the findings** (§5): supply, rails, budget, grounding.

## §4 Wiring plan (draft — no MCU connection yet)

- [ ] **Channel → pump map:** which relay channel (GPIO 25/26/27/32) drives which pump → which plant.
      Draft it; it becomes the deployment record.
- [ ] **Connector strategy:** how pumps + the pump rail land on the relay board (screw terminals,
      JST); keep the MCU control ribbon separate from the pump-power wiring.
- [ ] **Label everything** so the §1/§2 numbers stay attached to the physical channel at deploy.

## §5 Findings → docs/

- [ ] Fold the §1–§4 tables + the decided power plan into `docs/hardware/` (a `PUMPS_RELAYS.md` or
      the existing hardware notes) and link them on **#1451**. The power-plan decision is the AC that
      unblocks the v0.9.0 Water wave — capture it as a decision, not just a measurement.
- [ ] Photograph the bench setup + the wired relay board for the deployment record.

**Gate outcome:** when §1–§3 are recorded and the power plan is written, #1451's ACs are met and the
pump hardware is ready for the actuation epic (#94) — which still only arms after the #191 safety
gate passes and the maintainer runs `!auto`.
