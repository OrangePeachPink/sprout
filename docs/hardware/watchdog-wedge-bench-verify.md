# Bench verify: watchdog wedge test + device-owned-time live check

**Date:** 2026-07-01
**Board:** classic ESP32-D0WD, COM6
**Firmware under test:** `git=e5ae530` (PR #518, merged as `749d69d`)
**Operator:** Veronica, hands-on / time-boxed bench window; Firmware lane ran the tests and captured
evidence.

Two bench sessions, same window, same board. Recorded here because the results only lived in GitHub
issue comments ([#518](https://github.com/OrangePeachPink/sprout/pull/518#issuecomment-4859820930),
[#93](https://github.com/OrangePeachPink/sprout/issues/93#issuecomment-4859892470),
[#191](https://github.com/OrangePeachPink/sprout/issues/191#issuecomment-4859947087)) until now —
this is the durable, repo-tracked copy.

## Session 1 — #278 device-owned time, live hardware confirmation

Flashed `esp32dev_env` (env sensors on) carrying the #278 device-seq/time-source telemetry fields.
Read serial for ~10s.

```text
# fw=0.7.0  git=e5ae530  built=Jul  1 2026 15:32:45
# time: source=device_uptime (no NTP/RTC yet, #21) - device_seq/time_source ride each row's payload
plants.soil,0dd136,Sprout ESP32,0.7.0,5000,UMLIFE_v2_TLC555,s3,origplant,soil_moisture,3006,,,OK,level=dry;role=disp;spread=26;gpio=36;device_seq=0;time_source=device_uptime*01
plants.soil,0dd136,...,s4,...,device_seq=1;time_source=device_uptime*58
plants.soil,0dd136,...,s1,...,device_seq=2;time_source=device_uptime*5F
plants.soil,0dd136,...,s2,...,device_seq=3;time_source=device_uptime*57
```

**Findings:**

- `device_seq` increments 0→1→2→3 correctly across the 4-channel sweep, exactly as designed (one
  tick per emitted soil row).
- `time_source=device_uptime` reported honestly on every row — no fabricated sync, matching the
  "omit `device_timestamp_utc` rather than guess it" design in `telemetry.c`.
- Env sensors (SHT45 ambient temp/RH, AS7263 NIR) unaffected, streaming normally alongside.

**Scope note:** this confirms the *field plumbing* on real hardware. It does not and cannot confirm
"untethered readings carry real UTC" — that's honestly still gated on WiFi/NTP (#21), which doesn't
exist yet. See #278's own acceptance-criteria discussion for the 2-of-3 breakdown.

## Session 2 — #191/#93 watchdog wedge test

Flashed `esp32dev_wdttest` (same `git=e5ae530`, `-D WDT_WEDGE_TEST`). Sent `!wedge*74` (the
XOR-checksummed command format the inbound serial parser requires) and read serial through the
reset.

```text
0.0s  # ack wedge ch0=ON - hanging the loop; watchdog must reset in <=8000ms
8.1s  E task_wdt: Task watchdog got triggered ... loopTask (CPU 1) ... Aborting.
8.2s  abort() was called ... Rebooting...
8.9s  # boot plants controller ... (fresh session_id=6a1108, device_seq resets to 0)
9.2s  # health: ch0=OK ch1=OK ch2=OK ch3=OK
13.5s normal telemetry resumes, all channels OK
```

**Acceptance criteria (from #191, quoting the issue directly):**

1. **Watchdog fires** — device resets within ~`WDT_TIMEOUT_MS` (8s) rather than hanging with outputs
   held. **PASS.** Fired at 8.1s against the 8000ms spec; confirmed via a fresh boot banner and a new
   `session_id` (proves a genuine reboot, not a soft reset).
2. **Fail-safe at boot** — meter each relay GPIO (25/26/27/32) at power-on, confirm all read
   de-energized (HIGH, active-low CW-022 convention) before the first sensor sweep. **NOT DONE.**
   This criterion explicitly requires a physical multimeter reading, and the bench board currently
   has no relay board wired at all — only the 2 I2C env sensors, 4 soil ADC pins, 3V3, and GND.
   `pump_set()` is a direct `digitalWrite(RELAY_PINS[ch], ...)` with nothing else in the signal path,
   so a clean reboot + resumed healthy telemetry is consistent with the GPIO returning to its safe
   level, but that is inference from source + recovery behavior, not a metered reading. The issue is
   explicit that this criterion is "gated on the rig + the maintainer" — it stays open.

**Net:** #93's software fail-safe (watchdog timing) has solid first-time hardware evidence. This
issue stays open pending an actual meter check on the four relay pins, whenever there's bench
time with a relay board and a multimeter in the loop.

## Board restored

After the wedge test, re-flashed `esp32dev_env` per standing instruction to leave the board in a
known-good state (env logging enabled, no wedge-test build active). Confirmed via serial: soil
channels + SHT45 + AS7263 all streaming normally, port released.

Refs #278 · #93 · #191 · PR #518

— Firmware 🔧
