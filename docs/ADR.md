# Architecture Decision Record - plants

**Status:** Accepted
**Date:** 2026-06-21
**Scope:** The single, combined ADR for the `plants` project. This is a deliberately simple,
single-developer, local auto-watering controller; it does not warrant a numbered series of ADRs, so
this one record holds the whole architecture and the reasoning behind it.

---

## Context

A window-ledge plant waterer for **hardy, non-fussy plants**. The real problem being solved is
**consistency** - the plants do fine with regular water and suffer mainly from being forgotten.
Guiding values: boring-first, baseline-first, local-first, and "a small thing that works and is honest
about what it doesn't know."

---

## Phase 1 - the decision (what we are building)

### Hardware
- **MCU:** classic ESP32 (`ESP-32D`), 3.3 V logic, WiFi/BT, ADC1 for analog sensing.
- **Sensing:** 4x UMLIFE capacitive soil moisture sensors (TLC555, QA-passed; see `SENSOR_QA.md`).
  **Soil moisture is the only control input.**
- **Actuation:** 4x submersible DC pumps switched by a `CW-022` 4-channel opto-isolated relay
  (active-LOW, 5 V coils).
- **Display:** 1x SH1106 128x64 I2C OLED for status / last-watered / errors. **Observability, not control.**
- **Power:** single 5 V / 2 A USB adapter via the ESP32 `5V` pin (single-supply baseline), one common
  ground, with bulk-cap + per-pump flyback-diode protection. Detail + escalation path in `WIRING.md`.

### Control architecture
- **Closed-loop on soil moisture only.** Per zone: a "dryish" threshold triggers a **fixed pump dose
  (milliseconds)**, empirically tuned over the first 2-3 cycles. The loop is **self-correcting** - an
  imperfect dose is fixed on the next check.
- **Slow check cadence** (every few hours) - which also provides the **post-water settle / lock-out**
  for free (water needs minutes to reach the sensor; re-reading too soon would over-water).
- **Safety:** max pump run-time cap; low-water reservoir cutoff (planned); per-zone calibration +
  threshold; **one pump at a time**.
- **No environmental sensors in the control loop** (temperature, humidity, light, UV). Soil moisture is
  the *integrated output* of all of those, so measuring the inputs to *predict* watering need is
  redundant when the output is measured directly.

### Separation of concerns (the core principle)
The **control path** (soil -> pump; simple, human-tunable) is **decoupled** from the **observability
path** (OLED now; logging later). Observability can grow without ever touching the control loop.

### Software / toolchain
- **PlatformIO** project in `firmware/` (board `esp32dev`, Arduino framework). The Arduino-IDE option
  was dropped in favor of PlatformIO for in-repo build config + pinned dependencies.
- **Config-driven** (`firmware/include/config.h`): pins, thresholds, calibration, dose times.
- Module shape: a lean **control** module; a **display** module (U8g2 / SH1106); a **stubbed, optional
  telemetry** hook.

### Scope boundary for Phase 1
- 4 sensed/watered plants **or zones** (a zone = several similar pots on one pump+sensor, fed the same dose).
- **Sensor waterproofing deferred** (POC: just don't insert past the max line).
- **Battery deferred** (wall power; a USB power bank if cordless is ever wanted).

---

## Alternatives considered

- **Add environmental sensors to the watering decision.** Rejected for control: with direct
  soil-moisture feedback, environmental inputs are redundant (they matter only via their effect on soil
  drying, which is measured directly). They remain valuable as **Phase 2 logging-only** inputs - never
  prescriptive.
- **Open-loop / scheduled watering** (fixed timer, no sensor). Rejected: less robust than closed-loop;
  can't adapt to real conditions; the whole point is to respond to actual dryness.
- **Two separate power supplies up front.** Deferred: the single-supply baseline is simpler; the
  two-supply design is the documented escalation if brownouts appear (`WIRING.md` Section 8).
- **Arduino IDE / dual-toolchain layout.** Rejected in favor of a clean PlatformIO project.

---

## Consequences

- The firmware stays small and the watering behavior is easy to reason about and hand-tune.
- Adding sensors, logging, dashboards, or more zones later is **additive** and does not disturb control.
- The system runs **headless and offline-capable**; WiFi is used for clock/timestamps and (future)
  notifications, not for the watering decision.

---

## Phase 2 - possible future enhancements (not committed)

- **Logging & data visibility:** timestamped soil readings + pump events to local storage
  (LittleFS / SD) and/or pushed to a local server / MQTT; a small status dashboard (ESP32-served web
  page or an external logger).
- **Data mining & correlation:** add the on-hand environmental sensors (temp / humidity / light / UV)
  as **logging-only** inputs; retrospective analysis (e.g., did hot/dry weeks drive more watering?).
  Three-layer data model (raw -> normalized -> features). Still non-prescriptive.
- **More plants / zones:** beyond 4 needs a larger relay board + more ADC channels or an analog
  multiplexer (e.g., CD74HC4067). The I2C bus (GPIO21/22) is already available for expanders/devices.
- **Remote monitoring / notifications:** WiFi push (low water, faults), phone/web status (Flaura-style).
- **Time-aware behavior:** NTP clock (already used for display timestamps) -> optional "water at dawn"
  rule (needs no sensor).
- **Power independence:** battery / power bank / solar for cordless operation.
- **Reliability / UX:** RTC for offline timekeeping; OLED burn-in mitigation; enclosure; OTA updates.
