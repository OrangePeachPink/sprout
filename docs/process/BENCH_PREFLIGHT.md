# Bench Preflight Checklist (sensor-capture sessions)

**Status:** living document — the short list Sage runs (or hands Veronica) **before** each bench block, so a
capture is never wasted on a stale server, the wrong source, a busy port, or an unintended cadence. Grounded in
the 2026-06-28 bench session, where every one of these seams showed up for real.

> **Scope:** this is the preflight for **sensor capture** — the rig that is *bench-wired and trusted today*
> (ESP32 + four capacitive probes on the breadboard). Pumps and the relay board are **code-staged only**
> (not connected, never powered). When relay/pump sessions begin, the **dry-safety preflight**
> ([#191](https://github.com/OrangePeachPink/plants/issues/191) ·
> [#93](https://github.com/OrangePeachPink/plants/issues/93) ·
> [#215](https://github.com/OrangePeachPink/plants/issues/215) ·
> [#2](https://github.com/OrangePeachPink/plants/issues/2)) gates that separately — this checklist does
> **not** cover actuation.
>
> **Capability-stage vocabulary** (Sage's, used throughout): *code-staged → bench-wired → dry-verified →
> wet-verified → plant-deployed → autonomous-enabled.* Probes are **bench-wired**; pumps/relay are
> **code-staged**.
>
> **Companion doc — the two #332 checklists work as a pair:** this is the **process reference** — *why* each
> seam matters, grounded in real sessions. For the **quick at-the-bench run-table and the evidence-note
> template**, see Sage's bench checklist:
> [`docs/experiments/bench-preflight-checklist.md`](../experiments/bench-preflight-checklist.md). This one
> *explains*; that one *runs*. Keep them in sync.

---

## 0. State Sage announces before the block

Sage states these out loud (or in the session log) at the top of every bench block, so there's no ambiguity
about what's running:

- [ ] **Restart the app/server?** yes / no — and why.
- [ ] **Flash firmware?** yes / no — and the git rev you expect to land.
- [ ] **Capture source:** serial device (real) — *never synthetic for real data*.
- [ ] **Cadence:** the intended sample interval, set on purpose (see §4).
- [ ] **Port owner:** which single process holds the board's COM port for this block.

---

## 1. App/server restart  ≠  firmware flash  (two different machines)

These are routinely confused; they touch different things. Decide each independently.

- [ ] **App/server restart** — `just start` (it serves + opens the dashboard; `--restart` takes over a stale
  server, [#127](https://github.com/OrangePeachPink/plants/issues/127)). This restarts the **Python host app
  only**. It does **not** touch the ESP32. Do this when the served code changed or a server is stale.
- [ ] **Firmware flash** — `just flash` (`pio run -t upload`). This changes what runs **on the ESP32** and
  needs the board connected + your OK. Do this only when firmware changed.
- [ ] After a flash, **confirm the boot banner** before trusting data (see §5).

**Stop condition — stale server:** if the dashboard is serving old behavior (a code change isn't showing),
the server is stale → `just start` (it restarts). Don't capture against a stale server.

## 2. Serial port owner — exactly one process at a time

Only **one** process can hold the board's COM port. The contenders all want it:

- `just logger` — the always-on **monitor** capture (`tools/logger/plants_logger.py`).
- `just experiment` — a **bounded, isolated** capture (`tools/capture/experiment_capture.py`).
- `just flash` — **PlatformIO upload** needs the port too.
- the PlatformIO/Arduino **serial monitor**, if open.

Rules:

- [ ] Decide the **single owner** for this block before starting.
- [ ] An **isolated experiment** capture and the **monitor** logger cannot both run — starting an experiment
  leaves a gap in the monitor log (this is expected; the 2026-06-28 monitor log had a hole exactly where the
  isolated experiment ran).
- [ ] **Stop the logger/monitor before flashing** — upload needs the port. Restart capture after the banner
  check.

**Stop condition — port busy:** a "port in use / access denied" error means another process owns it. Find and
stop that process; do not fight it with retries.

**Known trap — an orphaned logger can outlive the window that started it**
([#493](https://github.com/OrangePeachPink/plants/issues/493)). Closing the browser tab/window does **not**
currently signal `plants_logger.py` / `experiment_capture.py` to stop — only an explicit **`/quit`** click
does. A closed window can leave a **headless** logger process running for hours, silently holding the port,
invisible in Task Manager (it has no window and a generic `python.exe` name). If "port busy" persists after
closing every visible window:

```sh
just processes
```

**Find** any live Sprout-spawned process by PID + role (Monitor / Experiment) — one command, no manual
forensics (`tools/analytics/sprout_processes.py`, #500). Read-only; it only reports. To **stop** a confirmed
orphan by its PID:

```powershell
Stop-Process -Id <ProcessId> -Force
```

*(The manual find-by-command-line PowerShell this section used before `just processes` existed:
`Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='pythonw.exe'" | Where-Object
{ $_.CommandLine -match 'plants_logger|experiment_capture' }` — kept here only as a fallback if `just
processes` itself is unavailable.)*

This is a workaround, not a fix — the real fix (an actual close-signal + a server-side liveness self-shutdown)
is tracked on #493 (Data). Once that lands, this section retires.

## 3. Capture source — real, not synthetic

- [ ] Source is **serial device** (the real ESP32). Confirm before recording.
- [ ] The **synthetic/demo source** exists for UI development only — it produces plausible-looking numbers
  that are **not** from the board.

**Stop condition — synthetic selected for real data:** if the source is synthetic (or the dashboard is in a
demo mode) and you intend to capture real plant/sensor evidence → **STOP** and switch to serial device. A
synthetic row that lands in an evidence folder is a provenance break.

## 4. Cadence — set it on purpose (it persists on the device)

The biggest live gotcha from 2026-06-28: **the experiment cadence is written to firmware NVS and persists.**
The experiment UI is **not** a per-run setting — it changes the device cadence *until changed again*. After a
0.5 s experiment, the next monitor log **inherited 0.5 s** and produced very dense files
([#82](https://github.com/OrangePeachPink/plants/issues/82) tracks fast-cadence quality).

- [ ] **Choose an intentional cadence** before any long monitor logging (e.g. 5 s for hours-long holds; 0.5–1 s
  only for short transition tests).
- [ ] **Confirm the live cadence in the boot banner**: `cadence_ms=NNNN (nvs)` — the `(nvs)` value is what the
  device will actually use, including for the *next* monitor session.
- [ ] If you ran a sub-second experiment, **reset the cadence deliberately** afterward and re-confirm the
  banner before walking away from a long log.

**Sub-second note:** 0.5 s is *usable but not lossless* — expect occasional ~856 ms sweep gaps and some dropped
rows. Fine for short transitions; measure, don't assume, for anything tighter.

## 5. Firmware banner check (after any flash)

After flashing, read the fresh boot/provenance banner from a monitor log and confirm:

- [ ] `fw=` firmware version matches what you intended.
- [ ] `git=` short rev matches the build you flashed (the **experiment CSV only carries `firmware_version`,
  not the git rev** — the **monitor log** is the source of post-flash git provenance).
- [ ] `health: ch0..ch3=OK` — all four channels healthy.
- [ ] `safety: actuators fail-safe OFF ... pump=manual(!water) bounded<=5000ms` — actuation still safe-off
  (pumps are code-staged; this line must stay this way until a dry-safety session deliberately changes it).
- [ ] `cadence_ms=NNNN (nvs)` is the cadence you want (see §4).
- [ ] **`cal bounds(...)` line is readable** — a corrupted-looking cal-bounds banner is a flag
  ([#295](https://github.com/OrangePeachPink/plants/issues/295)); calibration provenance must stay legible.

## 6. Raw-only CSV contract — `raw_value` is the evidence column

Firmware does **not** emit a real engineering `value`/`unit`; the calibrated **band + `raw_value`** are the
truth (the 0–100 index is a labelled relative position, never VWC). Capture CSVs must obey this:

- [ ] `value` is **empty** in every row.
- [ ] `unit` is **empty** in every row.
- [ ] `quality_flag` is `OK` (note and investigate any non-OK).
- [ ] Treat **`raw_value`** as *the* evidence column; ignore any processed `value`/`pct`.

**Stop condition — contract violation:** a capture with **populated `value`/`unit`** predates or violates the
raw-only contract → **exclude it from evidence** (on 2026-06-28 the `common-cup` capture was dropped for
exactly this: non-empty `value/unit` + only 3 sweeps). Refs
[#294](https://github.com/OrangePeachPink/plants/issues/294) /
[#307](https://github.com/OrangePeachPink/plants/issues/307).

## 7. Local-time labels

- [ ] Label every capture **local time first, UTC second** — e.g. `13:02 local / 18:02 UTC` — matching the
  bench-session log style.
- [ ] Dashboard local-time-first labels are tracked in
  [#328](https://github.com/OrangePeachPink/plants/issues/328); until that lands, keep writing both by hand so
  bench screenshots and the log read the same.

---

## One-line gate

> **Server fresh? Right firmware (banner checked)? Source = serial? Cadence on purpose (banner says so)? One
> port owner? Raw-only contract holds? Times in local-first?** — if any answer is "no / not sure," fix it
> before you record, not after.

---

*Bench preflight checklist ([#332](https://github.com/OrangePeachPink/plants/issues/332)) — the **process**
half of the pair; Sage's [bench checklist](../experiments/bench-preflight-checklist.md) is the **run** half.
DX-drafted from the 2026-06-28 bench session; **Sage owns the bench-accuracy review** — physical/port/cadence/
banner facts are Sage's to confirm or correct. Pairs with the dry-safety preflight (#191/#93/#215/#2) for the
future actuation sessions this list intentionally does not cover.*
