# ESP32-C5 (official DevKitC-1) — 4-channel soil continuity — 2026-07-04
<!-- cspell:words DevKitC KITC esptool eFuseCal dunk immersion submerged overwatered nonce silkscreen -->
<!-- cspell:words breadboard dupont ratiometric deasserted TLC UMLIFE cad RFC antenna -->

Bench evidence for **full soil-channel continuity** on the official Espressif **ESP32-C5-DevKitC-1**
(`device_id 8gtt1h`, name `c5off1`) — all four soil channels wired to validated probes s5–s8 and verified
end-to-end (air-dry → dunk swing → recovery), plus a both-ends saturation bounding. MAC / USB instance IDs are
redacted (ADR-0015 / ADR-0020, identifier-guard #573). Private RFC1918 IPs are evidence-safe and kept.

Bench arrangement: maintainer = hands (meter, probes, wiring, dunks); Firmware lane = brains-on-call (serial
commands, watched output, verdicts, an audible GO-beep to sync each dunk). Read over serial (CP210x, COM11) at a
session-only fast cadence (`!cad,2000,temp`), no-reset opens (DTR/RTS deasserted). This is **install-day** bench
work — the last gate before probes go into plants.

## Board (settled — reset banner)

| Field | Value | How |
| --- | --- | --- |
| Identity | `device_id=8gtt1h` name `c5off1` | boot banner (#601 mint) |
| Chip / target | ESP32-C5 / `esp32-c5`, fw 0.7.0 (`git f469007`) | banner |
| ADC | ADC1, 12-bit, 11 dB, **eFuseCal=off** | banner |
| Board cal | **PLACEHOLDER** (classic endpoints, not bench-verified for C5) | `calibration.h` / #443 |
| WiFi | connected, `192.168.x.85` | banner |
| Default cadence | 30 000 ms (bumped to 2 000 ms for this session) | banner / `!cad` ack |

## Power verified by meter (before any probe)

The board sits antenna-up / USB-down in a breadboard. Power pins were **meter-confirmed**, not assumed:

- **L1 = 3V3** — DC volts, positive lead on L1 / negative on R1 read **+3.332 V** (correct polarity, healthy rail).
- **R1 = GND**.
- Distributed to breadboard rails for the 4-sensor fan-out: **3V3 → row 30, GND → row 25** (re-metered +3.332 V
  to confirm the jumpers carry the rails).

## Pin map (B1) + probe wiring

Firmware soil map (self-reported): `ch0=GPIO1 · ch1=GPIO4 · ch2=GPIO5 · ch3=GPIO6` (UMLIFE_v2 / TLC555). On the
official DevKitC-1 those GPIOs are silkscreen-labeled, so the map is trustworthy on sight (verified: GPIO1 at L6,
GPIO6 at L7; GPIO4/5 on the right column J3).

**Channel ≠ probe (ADR-0027):** the firmware prints each socket by its fixed *channel* name (`s3/s4/s1/s2`); the
mobile physical probes are s5–s8. Physical wiring this session:

| Physical probe | GPIO (position) | Channel | Firmware name |
| --- | --- | --- | --- |
| s5 | GPIO1 (L6) | ch0 | s3 |
| s6 | GPIO6 (L7) | ch3 | s2 |
| s7 | GPIO4 (J3) | ch1 | s4 |
| s8 | GPIO5 (J3) | ch2 | s1 |

## B2 — all 4 channels air-dry live

Each bare channel floated at raw ~0–177 / SATURATED; the instant a probe drove it, the channel snapped to a
stable air-dry reading:

| Probe | Air-dry raw | Q |
| --- | --- | --- |
| s5 | 2779 | OK |
| s6 | 2792 | OK |
| s7 | 2765 | OK |
| s8 | 2724 | OK |

All four within ~68 counts — a tight, healthy cluster; every channel receives a real signal. (Bonus: confirms
the 3V3 rail delivers under a real 4-sensor load.)

## B3 — dunk swing (solo, beep-coordinated)

Each probe dunked solo, an audible GO-beep syncing the timing. Every channel swings hard into wet and recovers:

| Probe | Air-dry | Wet floor | Swing |
| --- | --- | --- | --- |
| s5 | 2787 | 1072 | 1715 |
| s6 | 2818 | 1082 | 1736 |
| s7 | 2776 | 971 | 1805 |
| s8 | 2738 | 948 | 1790 |

All four swung ~1700–1800 counts and recovered to air-dry. **Continuity is proven on every channel.** (The
classifier `level` lag — one sample behind raw on the transient — showed up again; harmless, documented in #660.)

## Both-ends bounding — near-full saturation

The solo dunks sat at ~65–70 % immersion; a top-off to ~95–100 % (resting in the cup) pulls the floor lower and
bounds the wet extreme:

| Probe | Solo sat (65–70 %) | Near-full sat | Δ |
| --- | --- | --- | --- |
| s5 | 1072 | 991 | −81 |
| s6 | 1082 | 1022 | −60 |
| s7 | 971 | 946 | −25 |
| s8 | 948 | 910 | −38 |

Two things fall out: a **~112-count per-sensor spread** at near-full (910–1022) — real probe personality, the
argument for per-probe cal (#621); and the **variable top-off deltas (−25 to −81)** confirming, once more, that
**immersion depth is the dominant variable** — the same finding as the s12 depth sweep (#660), now on C5 silicon.

## Honest scope — what this is and isn't

- **Continuity, not calibration.** The C5's ADC reads air-dry ~300 counts *below* the classic (2775 vs ~3100)
  and its wet floor higher — that's the uncalibrated ADC (`eFuseCal=off`, placeholder cal #443), not a wiring
  issue. Absolute values are the job of #443; this packet proves the *paths work*.
- **Cup floors are not soil values.** A probe in a water cup is fully immersed; a probe in a pot is not. The
  operational in-soil readings come at install and supersede these bench floors.
- **The fast cadence is session-only** (`!cad,...,temp`) — reverts to the 30 s default on reset / power-cycle.
- **This is the OFFICIAL DevKitC-1** (silkscreen-labeled, low continuity risk). The yellow `KITC-A` clone (the
  `N/15` ambiguity) is verified in its own packet.

## Session provenance

Firmware bench session, 2026-07-04 (install day). Facts are serial-observed on COM11 (CP210x) at capture time;
raw per-sample streams kept in the maintainer's local archive. The board went to brick + WiFi after capture.

Refs: #584 · #443 · #621 · #573 · #660 · ADR-0027 · ADR-0022.

— Firmware 🔧
