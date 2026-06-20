# Wiring & Power - plants controller

**Last updated:** 2026-06-20
**Status:** design baseline, pre-bring-up. **Nothing is wired yet.** Pin numbers and the relay
trigger polarity are *candidates to confirm at the bench* (see "Open items" at the end).

Captures the electrical plan for the 4-sensor / 4-pump auto-watering build: classic ESP32
(`ESP-32D`), 4x UMLIFE capacitive sensors (TLC555, QA-passed - see `../SENSOR_QA.md`), 4x submersible
DC pumps, and a `CW-022` 4-channel opto-isolated relay board.

---

## 1. Power architecture - single-supply baseline

For the proof-of-concept we run **everything from one 5 V USB wall adapter** plugged into the ESP32,
and tap the ESP32's `5V` pin to feed the relay board and the pumps. Fewest cables, and one common
ground for free.

Three invariants that hold regardless of power source:

1. **One common ground** - every ground ties together (ESP32, relay, sensors, pump returns, supply -).
2. **Pump current stays out of the ESP32's logic/regulator.** In this baseline it *does* flow through
   the board's `5V` pin + protection diode, which is acceptable for these tiny, one-at-a-time pumps
   **with the protection parts in Section 6**. (If the ESP32 ever resets on a pump start, see Section 8.)
3. **Right voltages** - ESP32 is *fed* 5 V (USB) but *thinks* in 3.3 V logic; sensors run at 3.3 V
   (output 0-3.0 V); relay coils + pumps run at 5 V (pumps tolerate 2.5-6 V, so ~4.7 V off the 5V pin
   is fine).

**Adapter:** 5 V, **2 A** (headroom for WiFi current spikes). One pump at a time keeps total draw ~0.5 A.

---

## 2. The three domains

| Domain | Flow | Carries |
|---|---|---|
| **SENSE** | sensors -> ESP32 | tiny analog signals in |
| **CONTROL** | ESP32 GPIO -> relay INs | tiny logic signals out |
| **ACTUATE** | 5 V -> relay contacts -> pumps | the real pump current (never through ESP32 logic) |

---

## 3. Connection map (net list)

**Power nets (all sourced from the one 5 V adapter via the ESP32):**

- `5V`  : ESP32 `5V` pin -> relay `VCC` -> each relay `COM` (x4)
- `3V3` : ESP32 `3V3` pin -> each sensor VCC (red) (x4)
- `GND` : ESP32 `GND` -> relay `GND` -> each sensor GND (black) -> each pump (-) black -> adapter (-)
  - one common ground; use a **distribution hub** - breadboard rail for bring-up, terminal strip / protoboard for the permanent build

**Signal nets:**

- sensor `AOUT` (yellow) x4 -> ESP32 ADC1 inputs
- ESP32 GPIO x4 -> relay `IN1..IN4`
- relay `NO` x4 -> pump (+) red x4

**Per pump (off by default):**

```
5V ---------> COM
NO ---------> pump red (+)
NC ---------> (unused)
pump black (-) ---> common GND
```

---

## 4. Candidate pin map

Confirm and finalize at wiring; then update `firmware/include/config.h` to match.

| Function | ESP32 pin | Notes |
|---|---|---|
| Sensor 1 AOUT | GPIO36 (VP) | ADC1, input-only |
| Sensor 2 AOUT | GPIO39 (VN) | ADC1, input-only |
| Sensor 3 AOUT | GPIO34 | ADC1, input-only |
| Sensor 4 AOUT | GPIO35 | ADC1, input-only |
| Relay IN1 | GPIO25 | digital out |
| Relay IN2 | GPIO26 | digital out |
| Relay IN3 | GPIO27 | digital out |
| Relay IN4 | GPIO32 | digital out (ADC1-capable; could move relays to GPIO16-19 to free GPIO32 for a 5th sensor later) |

Rules baked in: sensors on **ADC1** (ADC2 is unusable while WiFi is on); relay pins avoid the
**strapping pins** (0, 2, 5, 12, 15) and the **input-only** pins (34-39).

---

## 5. Connector reference

| Connection | Connector / method |
|---|---|
| Sensor <-> ESP32 | JST-PH 2.0 (3-pin) at the sensor; far end onto ESP32 header (verify far end) |
| ESP32 <-> relay 6-pin header (`GND IN1 IN2 IN3 IN4 VCC`) | DuPont jumper wires |
| Relay contacts <-> pumps & 5 V | screw terminals - bare stripped wire, no connector |

- Sensor leads: **red = VCC, black = GND, yellow = AOUT**.
- Relay output terminals are **NO / COM / NC** - the middle is **COM** (switch common), **not ground**.
  Confirm order by silk or continuity (at rest: COM<->NC closed, COM<->NO open).
- `JD-VCC` <-> `VCC` jumper: leave **ON** for the single-supply baseline (coils + logic both off 5 V).

---

## 6. Protection parts (recommended insurance) - all in the `parts` inventory

Tame the pump motor's inrush/noise on the shared 5 V rail and protect the relay contacts:

| Part | Spec | Placement | Inventory source |
|---|---|---|---|
| Bulk capacitor | 470-1000 uF electrolytic, **16 V or 25 V** | across 5 V <-> GND near the relay | `consumable-capacitor-electrolytic-633` (0.1-2200 uF assortment) |
| Decoupling cap (optional) | 0.1 uF ceramic (`104`) | across 5 V <-> GND alongside the bulk cap | `consumable-capacitor-ceramic-900` or `capacitor-sunfounder-kepler-104` |
| Flyback diode x4 | 1N4007 (or 1N5819 Schottky) | across each pump, **band/cathode -> + (red)** | `diode-sunfounder-kepler-1n4007` (5 pcs) or `consumable-diode-kit-200` |

Electrolytic polarity: the **stripe = (-)** leg; its (-) goes to GND. Confirm a 470-1000 uF @ >=16 V is
actually in the assortment box when you pull it (the kit is not itemized in the app).

---

## 7. Power budget

One pump at a time (enforced in software):

- ESP32: ~0.15-0.25 A (bursts ~0.5 A on WiFi TX)
- 1 relay coil: ~0.07-0.08 A
- 1 pump: ~0.18 A (+ brief motor inrush)
- **Total ~0.5 A typical, ~1 A transient** -> a 2 A adapter is comfortable.

---

## 8. Escalation path (only if the ESP32 resets when a pump fires)

The shared-rail risk is a brownout/reset on pump start - **not** damage. If it happens, climb only as
far as needed:

1. Add/confirm the **bulk cap + flyback diodes** (Section 6). Usually fixes it.
2. Increase the bulk cap (1000 uF+) and shorten the 5 V leads to the relay.
3. Give the **pumps their own 5 V feed** (second adapter or dual-port charger), grounds still common -
   the original two-supply plan. Pump current then bypasses the ESP32 entirely.

---

## 9. Deferred to a later iteration (v2)

- **Sensor waterproofing** - conformal-coat / epoxy the upper sensor board (corrosion is a weeks+
  concern). For the POC, just don't insert past the max line.
- **Battery / cordless** - easiest is a USB power bank (regulated 5 V, like a wall adapter). A bare
  18650 / 1S LiPo suits the pumps directly but needs a boost for the ESP32. Not for v1.
- **More than 4 plants** - v1 covers 4 sensed/watered plants or zones; expansion needs more relay
  channels + ADC pins (or an analog multiplexer).
- **Low-water cutoff** - reservoir level sensor (float switch preferred) -> ESP32 input -> block pumps
  when dry. Design this in the water/reservoir step.

---

## 10. Open items to confirm before / at wiring

- [ ] Sensor cable **far ends** (DuPont / bare / other?) and **pump wire ends**
- [ ] On hand: **DuPont jumpers** + a **hub** (breadboard / terminal strip)
- [ ] Relay **terminal order** (continuity: COM<->NC closed at rest)
- [ ] Relay **active-LOW** trigger confirmed (powered click-test); `JD-VCC` jumper left ON
- [ ] A **470-1000 uF @ >=16 V** cap confirmed present in the assortment
- [ ] Finalize the pin map and update `firmware/include/config.h`
