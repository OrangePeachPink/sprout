# Safety-gate run sheet — watchdog + fail-safe actuator-off

**One execution-ordered sheet for the maintainer's bench slot** — the on-device proof of the two
independent guards that must exist *before* the first pump is wired: the **task watchdog** (a wedged
loop resets instead of stranding a pump on) and the **fail-safe off** (every relay reads de-energized
after any reset, before the first sensor sweep). The firmware and the relay-polarity convention are
already in the tree; this sheet is how the bench *verifies* them.

Refs #93 (the safety gate) · #191 (classic re-qualification / bench verify) · #215 (energized-level convention)

> **Why this gate is load-bearing:** the moment a relay drives a pump, a crash / hang / brownout
> mid-pulse must not leave a pump energized — that is an overwatered plant or a pumped-dry reservoir,
> unattended. Autonomous dosing ships **disarmed** (`irrig_set_autonomous(false)`), so nothing waters
> until this gate passes AND the bench arms it with `!auto`.

## Scope

**Classic ESP32 (the qualified board, `esp32dev`).** One physical board, USB serial @ 19200. **No pump
and no water this session** — this verifies the *electrical* fail-safe (relay pins) and the *watchdog
reset*, both with a meter/scope and the serial banner, not a pump. The C5/S3 re-run is a later slot
once they carry the same env.

Run §1 → §2 → §3 in order. §1 needs only a multimeter; §2 needs a one-time throwaway reflash; §3 is a
continuity/polarity check you do **before** any pump ever connects.

---

## §0 Pre-flight

- [ ] Board powered over USB only; **no relay board / no pump connected yet** for §1–§2.
- [ ] Serial monitor open @ **19200** (`pio device monitor -e esp32dev` or your terminal).
- [ ] Note the classic relay GPIOs from the firmware — **ch0..ch3 = GPIO 25 / 26 / 27 / 32**
      (`include/config.h`, `BOARD_CAP.relay_pins`). These are the pins you meter in §1.
- [ ] Confirm the running build echoes the safety banner on boot:
      `# safety: fail-safe OFF (4ch CW-022 active-low, off=HIGH)  task-wdt=<N>ms …`
      — that single line asserts all three conventions this sheet verifies.

## §1 Fail-safe off — relays read de-energized after reset, before the first sweep (AC2)

The convention: the **CW-022 board is active-LOW** — driving the GPIO **LOW energizes** the coil, so
**de-energized = HIGH** (`RELAY_OFF_LEVEL = HIGH`, `include/config.h`). `allRelaysOff()` runs **FIRST**
in `setup()` (`src/main.cpp:1000`), before the first ADC sweep.

- [ ] Meter each relay GPIO to GND: **DC volts**, board just reset, *during* the first second of boot.
- [ ] **Each of GPIO 25 / 26 / 27 / 32 reads HIGH (~3.3 V) = de-energized** before any sweep line prints.
- [ ] Press EN/reset a few times: the pins return to HIGH **every** time, with no LOW glitch that would
      pulse a coil. (A brief indeterminate state at the very first instant of power-on is the pin's
      power-on default, not a drive — what matters is `allRelaysOff()` lands HIGH before the loop starts.)

| Relay ch | GPIO | Expected at boot (de-energized) | Measured | Pass |
| --- | --- | --- | --- | --- |
| ch0 | 25 | HIGH (~3.3 V) |  | ☐ |
| ch1 | 26 | HIGH (~3.3 V) |  | ☐ |
| ch2 | 27 | HIGH (~3.3 V) |  | ☐ |
| ch3 | 32 | HIGH (~3.3 V) |  | ☐ |

## §2 Watchdog — a wedged loop resets the chip (AC1)

A dedicated throwaway build exposes `!wedge`, which **strands ch0 + hangs the loop** so the task
watchdog *must* fire. **Never ship this env** — `!wedge` only exists under `-D WDT_WEDGE_TEST`.

- [ ] Flash the wedge-test build: `pio run -e esp32dev_wdttest -t upload --upload-port <COMx>`.
- [ ] On boot it prints: `# *** WDT WEDGE-TEST BUILD (esp32dev_wdttest) *** !wedge strands ch0 …`.
- [ ] Note the watchdog timeout from the banner (`task-wdt=<N>ms`, `WDT_TIMEOUT_MS`).
- [ ] Send **`!wedge`** over serial. The loop hangs (telemetry stops).
- [ ] **Within ≈ the watchdog timeout, the chip resets** — the boot banner reappears on its own, no
      button press. That reset is the pass: a wedged loop cannot hold outputs.
- [ ] **Optional stronger proof (pump-off-on-hang):** with a relay board connected and ch0's coil
      observable (meter/LED, still no pump), confirm ch0 is **not left energized** through the hang —
      the reset drops it back to de-energized HIGH (this is §1 re-asserted through a crash path).
- [ ] **Reflash a ship build afterwards** (`pio run -e esp32dev -t upload`) — the wedge env must never
      remain on a board that will ever see a pump.

| Step | Expected | Observed | Pass |
| --- | --- | --- | --- |
| `!wedge` sent | telemetry stops (loop hung) |  | ☐ |
| after ~`WDT_TIMEOUT_MS` | chip resets, boot banner reprints unaided |  | ☐ |
| ch0 through the hang | never latched energized; returns HIGH on reset |  | ☐ |
| ship build reflashed | `esp32dev` back on the board |  | ☐ |

## §3 Relay wiring / polarity convention — wire it to match the firmware (AC3)

**Do this before a pump ever connects.** The firmware is authoritative; the wiring must match it.

- [ ] **Module:** CW-022 4-channel relay board, **active-LOW**. GPIO **LOW = energized**, **HIGH =
      de-energized** (`RELAY_ACTIVE_LOW = true`, `RELAY_ON_LEVEL = LOW`, `RELAY_OFF_LEVEL = HIGH`).
- [ ] **Pin map (classic):** ch0→GPIO25, ch1→GPIO26, ch2→GPIO27, ch3→GPIO32 (strapping pins
      0/2/12/15 and input-only 34/35/36/39 are deliberately avoided).
- [ ] **Continuity-check** each header pin → its intended GPIO with a meter before trusting silkscreen.
- [ ] **Confirm polarity with the relay board alone** (click / LED / meter), pump **disconnected**:
      `!water 0` (or the bench dose command) should **energize** ch0 (pin goes LOW, relay clicks in);
      `!stop` returns it to de-energized HIGH. Only after this is confirmed does a pump go on ch0.
- [ ] Record the observed idle level + which command energized which channel in the evidence table.

---

## Evidence

Capture per the [environment-evidence procedure](environment-evidence-procedure.md): the boot banner
(shows `task-wdt=…`, the safety line), a photo of the meter reading HIGH on each relay pin at boot,
and the serial capture of the `!wedge` → auto-reset sequence. File under
`docs/evidence/<date>-safety-gate/` and link it back on **#93** / **#191**.

**Gate outcome:** #93's ACs 1–2 are *code-present today*; this sheet is their on-device proof. When
§1–§2 pass on the classic board, #93 is bench-complete and the actuation epic (#94 / #215) may arm
autonomous dosing behind the remaining pump-bench steps. AC3 (the convention) is satisfied in
`include/config.h` and re-verified physically in §3.
