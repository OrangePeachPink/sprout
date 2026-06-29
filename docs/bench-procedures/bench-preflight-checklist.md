# Sage bench preflight checklist

Use this before each Sage-guided bench session. It is deliberately short: the
goal is to prevent stale software, wrong serial ownership, wrong data source, or
unlabeled timing from contaminating evidence.

Refs #332

Companion doc: DX owns the process-facing bench preflight standard in
[`docs/process/BENCH_PREFLIGHT.md`](../process/BENCH_PREFLIGHT.md). This Sage
checklist is the bench-facing, session-start version.

## Quick preflight

| Check | What to confirm | Pass condition |
| --- | --- | --- |
| Session goal | What are we trying to learn? | One sentence hypothesis or question exists before touching hardware. |
| App/server state | Do today's host/dashboard/logger changes require a restart? | Sage says either "restart app/server first" or "current app/server is OK." |
| Firmware state | Does the ESP32 need a flash? | Sage says either "flash firmware first" or "current flashed firmware is OK." |
| Firmware banner | What code is on the ESP32? | Capture or note `fw`, `git`, build time, cadence, and COM port when available. |
| Serial owner | Who owns COM6 right now? | Exactly one owner: monitor logging, Experiment Capture, PlatformIO upload, or nothing. |
| Capture source | Is this real bench data or UI smoke data? | Real bench data uses `serial (device)`, not `synthetic`. |
| Cadence | What sample rate is intended? | Experiment cadence and monitor cadence are stated separately. |
| CSV contract | Is raw ADC preserved honestly? | `value` and `unit` columns stay empty for firmware rows; raw ADC is the measurement. |
| Time labels | Can a human reconstruct timing? | Notes use local Chicago time first; UTC is secondary machine time. |
| Physical state | What is actually connected? | Sensors are bench-wired; pumps/relay remain code-staged unless explicitly changed. |

## Restart versus flash

These are different operations.

- Restart the app/server when host, logger, dashboard, lab notes, or parser code
  changed, or when the browser looks stale.
- Flash the ESP32 only when firmware changed, Firmware asks for it, or the bench
  test explicitly needs a different firmware build.
- Restarting Sprout does not change the ESP32 firmware.
- Flashing the ESP32 does not update the dashboard or logger.

## Serial port ownership

COM6 can only have one active owner at a time.

Before starting an experiment capture:

1. Stop monitor logging if it is running.
2. Confirm the Experiment Capture source is `serial (device)`.
3. Start the capture.
4. After capture, restart monitor logging only if continuous background logging
   is part of the session plan.

Before flashing firmware:

1. Stop monitor logging.
2. Stop any active experiment capture.
3. Stop the Sprout server if it still holds the port.
4. Upload from PlatformIO.
5. Restart Sprout after upload if the dashboard/logger is needed.

## Do-not-proceed stop conditions

Pause and resolve before collecting evidence if any of these are true:

- The dashboard says data is stale and a fresh capture is needed.
- The source is `synthetic` for a real hardware experiment.
- COM6 is busy or PlatformIO cannot open the port.
- Firmware provenance is unknown for a test that depends on firmware behavior.
- The capture cadence is not the cadence named in the procedure.
- Water may have reached exposed electronics. Unplug USB power before touching or
  wiping the board.
- The test involves relay, pump, actuator wiring, watchdog, or `!water` commands
  and Veronica has not explicitly approved that hardware step.

## Evidence note shape

Use this shape in the lab notes or issue comment:

```text
Question:
Setup:
Local time:
Firmware/app:
Capture:
Facts observed:
Inference:
What this does not prove:
Next step:
```

- Sage
