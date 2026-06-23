# Plants Project Backlog

**Scope of this list:** the whole `\plants\` project — on-device firmware, host-side capture/logging, downstream analytics, and data/product ideas. Not everything here is firmware. **Flash-gated items** (Section A, and the firmware parts of B/C/D) batch into the next flash (call it v0.4.0) at a *cycle boundary* — after the current drench-to-dry capture ends and you water again — never mid-capture, so the stream stays unbroken. **Host-side items** (the logger in B2/B3, all of Section E) aren't flash-gated and can be built anytime against the captured logs.

**How to use this list:** items are grouped into five sections and carry four fields each — `Status` (maturity / decision), `Priority` (rank within the section, P1 = do first), `Scope` (rough size), and `Where` (device / host / file / console). Within each section items are ordered by priority. Review them, flip `proposed` → `approved` / `rejected` / `deferred`, and add your own at the bottom. Cross-references use section IDs (e.g. B1).

**Scope scale (rough):** `XS` one-liner to an hour · `S` an evening · `M` a focused session or two · `L` a multi-session sub-project · `XL` a project in its own right.

---

# Section A — Control & firmware correctness
*The watering brain: safety, classification, on-device timing.*

## A1. Wire the health / spread veto into the irrigation supervisor, and surface it in the banner

**Status:** proposed — partially built (reference modules patched)
**Priority:** P1 (within section)
**Scope:** S — fold the existing `irrigation.c/.h` patch into the live firmware, set `max_health_warn`, add one banner field.
**Where:** behavior change in firmware; the health field is a print that goes to *file* always and is worth showing in the *console* too.

Have the supervisor consult the classifier's `health_warn` / spread before watering, and print health on the serial line. A floating or intermittently-shorted probe — the 4095-spread, incoherent-raw signature we saw on a live disconnect — can report a perfectly plausible "dry" level, and the current `wants_water()` checks faulted/soaking/level but never health, so a disconnected probe reading "dry" would trip the pump. The reference `irrigation.c/.h` already carry the fix: a per-read veto in `wants_water()` on `m.health_warn`, an optional sustained-fault latch via `cfg.max_health_warn` (mirrors `max_doses`, self-heals on a clean read), and a new `irrigation_health_warn()` accessor. Remaining work is to fold those into the live firmware: set `max_health_warn` (~3) in your cfg, and add the accessor to the serial banner so a floating probe announces itself instead of quietly reading "dry."

## A2. Raise the wet-floor boundaries so the waterlogged / submerged diagnostics can fire

**Status:** proposed — pending review
**Priority:** P2 (within section)
**Scope:** XS — edit the boundary array, re-confirm against the anchors.
**Where:** firmware classifier config (the boundary array); affects display/diagnostics, not the watering decision.

Move the bottom boundaries up — submerged ~1050, water-contact ~1100, overwatered ~1200 — replacing the current `1080 / 900 / 800`. Across all four probes the wettest physical reading is ~970–1018 in pure water and ~1140 in waterlogged soil, so the current `<900 / <800` diagnostic bands sit *below* the sensor's physical floor and can never trigger; today even full immersion reads "overwatered" (a display band) and the "probe is sitting in water / pot is flooded" alarm is effectively dead. Raising the floor makes that condition detectable again. Concretely, set the array to `3300 3050 2200 1750 1450 1200 1100 1050` — keep the validated dry side untouched. The wet bands will be narrow (≲ the ~60-count noise), so treat anything under ~1150 as one "too wet / check probe" condition and lean on `confirm_ms` to debounce; verified against the anchors, this maps moist-soil 1300 → well-watered, waterlogged 1140 → overwatered, and pure water 1010 → submerged-diagnostic.

## A3. Decoupled fast health / status tick

**Status:** proposed — pending review
**Priority:** P3 (within section)
**Scope:** M — dual-rate loop refactor; careful interaction with the no-sample-during-pump gate.
**Where:** firmware timing (fast tick) → status indicators (D3) + served page (D4) + console; full data rows stay at the slow log cadence.

Separate a fast health/liveness tick from the 30 s data-logging cadence, so indicators and connectivity update responsively without logging a full row that often. Why: 30 s is right for a slow soil process but sluggish for a status LED/display or an "is it alive / is a probe floating" check — you want quick feedback there, and the status hardware in D3 depends on it. How: run a lightweight heartbeat on a short interval (1–5 s) — it doesn't need a full 100-sample soil burst, just a cheap liveness/spread/connectivity check — feeding the indicators and any served page, while full data rows keep writing at the slow cadence to avoid bloating the log. Respect the no-sample-during-pump rule for any ADC touch; if you ever want the fast health in the log too, give it its own `record_type=health` at its own rate rather than speeding up the soil rows.

---

# Section B — Logging pipeline & data integrity
*Capture format, robustness, schema, output cleanliness. The keystone is the schema decision (B1).*

## B1. Self-describing log header (metadata spec)

**Status:** proposed — pending review
**Priority:** P1 (within section)
**Scope:** M — design the schema + `record_type`, emit a self-describing header, handle it host-side.
**Where:** see per-line tags below — B2 and C1 implement parts of this; this is the consolidated spec.

Make the log fully self-describing so a parser and a cold-open future-you never have to guess. The governing rule: if a field changes how a *row is interpreted* (boundaries, cfg, schema) it goes in both the file and the periodic console header; if it's pure *provenance* (git hash, MAC, build time, tz) it's file-only, because a human glancing at the console never needs it re-shown.

**File header — write once, parser + archivist facing:**
- Column-schema line — names, units, types, delimiter (e.g. `# columns: record_type,millis_ms,iso_ts,session_id,sensor_id,name,gpio,raw,level,role,spread,health`). Highest-leverage single addition, especially as the format changes: a declared schema lets one parser read a v0.3.2 and a v0.4.0 file without guessing. **Include a `record_type`/`source` discriminator from day one** (`soil` is the only type initially) so the format is born able to carry heterogeneous rows — env, weather, and other future layers (Section C) — at independent cadences without a painful mid-history migration. Type-specific fields go either in a column superset (simple, header widens per new sensor) or a compact `key=value` payload column (header stays stable, infinitely extensible — preferred for an exploratory data layer); low-cadence layers forward-fill onto soil rows by UTC timestamp at analysis time. Clean alternative: one file per stream, each with a fixed simple schema, joined on the UTC timestamp — keeps every schema trivial at the cost of more files. (See C2 — this same `record_type` + timestamp contract is what makes the HotBoxAQ cross-reference work.)
- Log/schema format version.
- Firmware version + git commit hash (+ `dirty` flag) + build date/time — ties the data to the exact source that produced it.
- Absolute log-start wall-clock + host timezone / UTC offset — the anchor that makes `millis()`/uptime convertible to real time, and the offset kills the tz ambiguity.
- Board identity — chip model, MAC (a free unique board id for the multi-ESP32 future), chip rev, flash size, CPU MHz.
- ADC config — ADC1, 12-bit, attenuation, and whether eFuse/Vref cal is on or off; this defines what the raw 0–4095 scale *means* for cross-board/cross-run comparison.
- Per-sensor block — `id → gpioNN/adc1_chN → short name → per-channel bounds`, plus placement (depth, pot/plant). Shared with C1.
- Run label / experiment description — the free-text "what was this run?" tag.
- Capture-tool identity + version — pio monitor vs. host logger vN (B2).
- Column legend — `raw = trimmed-mean counts; spr = range of kept set; health = ok|WARN`.

**Console header — terse, re-printed periodically, live human facing:**
- Firmware version (short), sensor # + GPIO, boundary array, the few cfg values you watch (cadence, deadband, spr_warn), the column header row, and a one-token run label. Nothing static or provenance-y.

**Both** (file once with units, console periodically terse): firmware version, sensor id/GPIO, boundary array, cfg essentials, column header row, run label.

Top three by leverage if trimming: the column-schema line (parse robustness across the coming format changes), the git commit hash (data↔code provenance), and run label + UTC offset (the two things you wished you'd captured this cycle). One ambient nuance for later: if you ever add a temp/RH sensor, constant-ish values belong in the header, but since RH drives the air-dry baseline and drifts over a multi-day run, you'd want it as per-row *columns*, not header.

## B2. Host-side logger script (dense file / simplified console split)

**Status:** proposed — pending review
**Priority:** P2 (within section)
**Scope:** M — a new pyserial logger that owns the port, with the file/console split and rotation hooks.
**Where:** host PC; this *is* the mechanism that lets *file* and *console* diverge.

Replace `pio device monitor --filter log2file` with a small Python logger (pyserial) that owns the serial port. The problem it solves: `log2file` is a tee — console and file receive identical bytes, so the stock monitor can't give you a dense analysis file and a clean human console at the same time, and filters like `time` apply to both equally. A host script reads each line the firmware emits, writes the full dense record to the file (with a host wall-clock timestamp prepended — B3), and prints a trimmed, pretty subset to the console. With it in place you also get two log-hygiene wins for free: write the repeated `cal bounds…/cfg…` header *once* at the top of the file (it's useful in the console, pure noise in the file), and drop the legacy `moist%` column from the file (it's the misleading old linear map) while optionally keeping it in the console for at-a-glance intuition. Note: switching to this — like any reopen of the port — will toggle DTR/RTS and reset most ESP32 boards, so it lands at a cycle boundary with the rest of v0.4.0, not mid-capture.

## B3. Real wall-clock timestamp on each line (host-side preferred)

**Status:** proposed — pending review
**Priority:** P3 (within section)
**Scope:** S — a host-side stamp inside the logger (UTC).
**Where:** host capture → full ISO-8601 stamp in the *log file*; short `HH:MM:SS` to the *console*.

Stamp each row with an actual date-time so the log is self-dating instead of relying on filename-boot-time plus uptime. The key realization: the host PC receiving the USB stream already has a clock, so the timestamp can be added host-side as each line arrives — zero firmware change, no WiFi, no RTC. The only cost is the gap between sample instant and line-arrival at the host (milliseconds over USB on a 30 s cadence, negligible), and B4's `millis()` column covers exact relative timing regardless. Implement it via the host logger (B2); PlatformIO's built-in `--filter time` is the zero-code shortcut but can't feed only the file (see B2). On-device time (SNTP-at-boot over WiFi, or a DS3231 RTC for offline) drops to a *fallback*, worth it only if time ever needs to be embedded at the source — e.g. logging to an on-device SD card with no host attached.

## B4. Monotonic `millis()` column in the log line

**Status:** proposed — pending review
**Priority:** P4 (within section)
**Scope:** S — one firmware field plus 64-bit wrap handling.
**Where:** firmware emits it → *log file* only (omit from console).

Add a raw `millis()`-since-boot integer column alongside the existing pretty `+0d hh:mm:ss` uptime field. The current time field is human-formatted, and a single serial glitch can mangle a digit — we've watched the `EF BF BD` replacement runs land on the index/whitespace, and the same could hit a time digit — whereas a bare integer is exact, monotonic, and trivially machine-parseable. It also pairs with the boot timestamp embedded in the log filename to reconstruct true wall-clock for any row in post-processing. Implementation is a one-field print: emit the `uint32` tick you already have as its own column and keep the formatted uptime for eyeballing. One caveat to note in a comment: `millis()` rolls over at ~49.7 days, so use a 64-bit accumulator (or just document the limit) if a single run could ever go that long — handled properly in B5.

## B5. Extended-duration logging (past the `millis()` rollover and beyond)

**Status:** proposed — pending review
**Priority:** P5 (within section)
**Scope:** L — small-but-critical timing audit + rotation + auto-reconnect + session id + UTC + watchdog, across firmware and host.
**Where:** firmware (timing audit, `millis()` wrap handling, boot/session id, watchdog) + host logger (rotation, auto-reconnect, UTC, monotonic clock) + schema (session-id column, UTC — B3/B2/B1).

Support continuous capture over weeks-to-months, past the uint32 `millis()` rollover (2^32 ms ≈ 49.71 days). The named limit is the smaller half: once B3 makes the host wall-clock stamp the authoritative time axis, the device counter wrapping no longer touches the file's primary timeline — it only affects the raw `millis()` column and the firmware's own timers. The concrete work:

- **Firmware timing audit (rollover-safe) — the silent failure.** Confirm every `millis()`-delta (the sample scheduler and the classifier's `confirm_ms`/persistence timers) uses the unsigned `(now - last) >= interval` idiom, which wraps correctly, *not* `now >= last + interval`, which overflows and quietly stalls sampling at ~day 49.7 with no error in the log. Highest priority *within this item* because it fails invisibly — and it protects the control loop, not just logging.
- **`millis()` column wrap-safety.** If you keep the raw column (B4), accumulate it into a 64-bit value (detect wrap: `current < previous` → carry the high word) so it stays monotonic instead of resetting every 49.7 days. uint64 ms doesn't wrap for ~585 million years.
- **Authoritative time in UTC + a monotonic relative clock.** Log UTC, not local, so a multi-week run never hits a backward 1-hour jump or a duplicated hour at the DST transition (which would wreck time-series alignment). For a relative axis that survives even NTP step corrections, also record the host's monotonic clock (`time.monotonic()`) alongside the UTC stamp. Ties to B3 and B1.
- **Log rotation (host logger, B2).** Roll by day or size with date-stamped filenames, re-emitting the full B1 header at the top of each segment so every file is independently self-describing; optionally gzip closed segments. Caps file size and limits a corruption or disk-full to one segment instead of the whole run.
- **Continuity + explicit reboots.** Host logger auto-reconnects if the port drops; every row carries a boot/session id (resets each device boot) so a reboot — which a host reconnect usually triggers via DTR/RTS — appears as a clean session boundary, not a silent discontinuity. For a permanent install, consider disabling the board's auto-reset on connect so host hiccups don't reboot the device at all.
- **Device long-uptime hygiene.** Feed the hardware watchdog and keep the sample/print loop allocation-free so months of uptime don't accrete heap fragmentation or a leak.

This is an extension of the logging cluster (B1/B2/B3/B4): it adds the session-id column to the schema and rotation/reconnect to the host logger, and the firmware timing audit is independent and worth doing regardless.

## B6. Eliminate / reduce the serial output noise (the `?` runs)

**Status:** proposed — pending review
**Priority:** P6 (within section)
**Scope:** S–M — baud drop + sacrificial preamble + lossless host decode + optional per-line CRC.
**Where:** firmware (baud, sacrificial preamble, flush, optional per-line CRC) + host logger lossless decode (B2).

Root-cause and reduce the `EF BF BD` / replacement-char noise. Recap of what it is: U+FFFD replacement chars the monitor writes when it can't UTF-8-decode a byte — i.e. occasional UART framing glitches at the *start* of a print burst after the 30 s idle, rendered lossy by the decoder. A high-quality USB cable doesn't address either cause (burst-start framing or a lossy decode). Fixes, cheapest first: (1) drop the baud — zero throughput pressure at 30 s cadence, so 115200 → 9600/19200 buys large timing margin and likely ends the framing errors outright; (2) emit a sacrificial sync byte / leading newline at the start of each burst so the first, most glitch-prone byte isn't a data byte; (3) decode latin-1/bytes in the host logger (B2) so a stray byte is one recoverable char, never a replacement-char run; (4) add a per-line checksum/CRC so the parser deterministically detects and drops a corrupted line; (5) once relays/pumps switch nearby this will try to return via EMI — a ferrite, clean grounds, and the lower baud + CRC make it a non-event. Net target: effectively zero, self-healing where any remains.

## B7. Cosmetic banner spacing fix (the `27502400` run-together)

**Status:** proposed — pending review
**Priority:** P7 (within section)
**Scope:** XS — one-line format-string fix.
**Where:** firmware banner line (appears in both); mostly a *file*-header concern once the host script renders the console.

Fix the missing separator in the cal-bounds banner so the boundary list prints as discrete numbers (`2200 1750 …`) instead of running two values together as `22001750` / `27502400`. It's purely cosmetic with zero impact on the readings, but it makes the header harder to read and, more to the point, harder for a parser to split the boundary array reliably. The fix is a one-liner: add the missing space/delimiter in the `printf` / `Serial.print` format string for the boundary list. Trivial — good to fold into the same flash as everything else rather than spend a boot on it alone.

---

# Section C — Sensing & data enrichment
*Expanding what gets measured and recorded — the multivariate dataset.*

## C1. Multi-sensor logging to a shared file, with pin awareness and plant-name mapping

**Status:** proposed — pending review
**Priority:** P1 (within section)
**Scope:** M — multi-channel sample loop, per-sensor identity, long-format rows, plus a per-pin verification calibration task.
**Where:** firmware emits per-sensor id + GPIO/ADC channel each sample; *log file* gets a per-sensor metadata block in the header plus sensor-id and short-name columns per row (long/tidy format); *console* shows a compact per-sensor block keyed by plant name. The id → pin → name mapping belongs in both.

Extend logging from the single-GPIO36 rig to all four channels in one shared file. Use a long/tidy layout — one row per sensor per sample, each row carrying a sensor id and the plant's short name — rather than a wide `raw1..raw4` row: it matches how the supervisor already samples (one channel at a time, never concurrent, so each sample really is its own event), scales without reformatting if a fifth channel ever appears, and keeps each row self-contained so a pasted partial chunk still names the plant without needing the header. Each sensor records the GPIO/ADC channel it's wired to, declared in a per-sensor header block (`id → gpioNN / adc1_chN → short name → optional per-channel boundaries`), because ADC pins are not interchangeable: each ESP32 ADC1 channel can carry its own offset and gain, and this cycle's "four probes agree within ~100 counts" result was measured with *every probe on GPIO36* — so pin-to-pin variation is still an unmeasured variable. Recording the pin lets you attribute any divergence to pin vs probe vs plant, and the classifier's existing per-channel `mcfg` already lets you carry different boundaries per pin if a quick same-probe/same-water check across the four pins shows they need it (add that check as a calibration task when the four-up harness is wired). The sensor→name table is firmware config — a short, space-free name per channel, re-set when you repot or swap — emitted to the file header and shown periodically in the console; the same identity layer also upgrades fault/health output from "channel 2" to "pothos (sensor 2, GPIO39)", which is far more useful when something floats or faults while unattended. Optionally tag the four rows of one sampling sweep with a shared cycle counter so they group cleanly in analysis even though their per-row timestamps differ by the few hundred ms it takes to read them in turn.

## C2. Cross-project schema compatibility (plants ↔ HotBoxAQ)

**Status:** proposed — pending review (architectural)
**Priority:** P2 (within section)
**Scope:** S — mostly a contract/design decision (timestamp + `record_type` + location id), touching both repos lightly.
**Where:** a shared logging contract across both repos; mandatory layer = UTC timestamp + `record_type` + location/device id; nice-to-haves on ingest/fields/units.

Design a shared minimal schema contract so `\plants\` and `\hotboxaq\` data are cross-referenceable and can be co-deployed (e.g. both on the south kitchen ledge for a month). Why: overlapping sensors already exist (CO2/VOC) and there's a real experiment in mind; fixing the contract before either project locks in history makes a future join trivial instead of a migration. Having now compared the two raw-row schemas, they are already ~80% the same shape, so this is a short reconciliation, not a redesign — and several items below are places HotBoxAQ's more-mature data design improves plants on its own merits, not just compatibility tax. Keep the contract to the minimum mandatory set so neither project is over-constrained.

**Reconciliation checklist (from the plants ↔ HotBoxAQ schema diff):**
- **Timestamp contract (mandatory).** Same UTC ISO-8601 format and millisecond precision in both (HotBoxAQ's `…123Z`), offset recorded once in the header, local derived. Plants' B3 is already on this path.
- **Shared `record_type` namespace (mandatory).** HotBoxAQ adds the row-level discriminator it currently lacks; namespace a shared registry (`plants.soil`, `aq.gas`, `aq.env`) so a merged file is unambiguous.
- **Aligned identity columns (mandatory).** Both carry `device_id` + session/boot id + sensor/channel id + position/name. HotBoxAQ adds `session_id` (it needs it for long runs anyway — B5); plants adopts `device_id`.
- **`{raw_value, value, unit}` triple (borrow from HotBoxAQ).** Plants adopts it so a soil row (`raw_value`=ADC, `value`=level/%, `unit`) is the same schema as a gas row.
- **Shared `quality_flag` enum (borrow from HotBoxAQ).** Adopt `OK / WARMING / BASELINE_LEARNING / SUSPECT / SATURATED / ESTIMATED / NO_SIGNAL / ERROR`; plants' spread-WARN → `SUSPECT`, floating probe → `NO_SIGNAL`, railed ADC → `SATURATED`. Richer than plants' binary `ok|WARN` and improves plants' own diagnostics.
- **Shared context columns.** `temp/rh/pressure_context` names + units agreed, so co-deployed env sensors populate both files identically.
- **Event overlay (borrow from HotBoxAQ).** Adopt its `event_id` + event-metadata table in plants; a watering/fault becomes a joinable event, unifying it with gas exposures (and giving D1's pump log its event shape).
- **Format hygiene.** Shared delimiter, null token, header block, and the raw-immutable → parquet/DuckDB analysis tier (HotBoxAQ's data plan specs this well; plants adopts it). One loader reads both.

**Gas channels — direct vs. join:** keep plants firmware lean. Of the HotBoxAQ array, only CO2 (strong), VOC/HCHO (the "do plants scrub the air" experiment), and maybe NH3 have plant-physiological meaning; the rest (CO, NO2, CH4, H2, H2S, smoke, odor) are AQ/event channels with no plant signal. None drive a watering decision, so none belong on the plant board — co-deploy HotBoxAQ on the same ledge and join on timestamp in post for the full gas context. The reconciliation above is what makes that join trivial.

## C3. Local weather capture (host-side, low cadence)

**Status:** idea — not scheduled (capture for schema-proofing)
**Priority:** P3 (within section)
**Scope:** S — a scheduled host fetch, parse, and write.
**Where:** host-side internet pull → `record_type=weather` rows in the shared file (or a sibling `weather.log`).

Pull local outdoor weather and log it as its own low-cadence stream, for seasonal and front-driven context the onboard sensors can't see. Frequency: hourly is the sweet spot — station observations rarely refresh faster than ~10–15 min and the soil process moves over days, so hourly catches frontal swings without logging noise (3-hourly would smear them). Source: NWS/NOAA `api.weather.gov` is free and resolves to ~2.5 km gridpoints (well past city-level — good Chicago coverage), and personal-station networks (Weather Underground PWS, Ambient Weather, CWOP) get hyperlocal if a nearby station exists. Fields: outdoor temp, RH, dewpoint, pressure, wind speed/dir, cloud cover, precip rate + accumulation, conditions text, solar radiation if offered, plus sunrise/sunset. Where: pure host-side — a small scheduled fetch writes `record_type=weather` rows into the shared file (or a sibling `weather.log`), zero device involvement. Placement note: these plants sit in a full south-facing kitchen window box in Chicago with direct maximum exposure, so unlike a typical interior houseplant they get strong solar gain, real photoperiod, and genuine thermal swings off the glass — which makes this weather/solar layer (and C4's light/UV) *high-value* here, not marginal context. Still pair it with the onboard sensors (the actual microclimate the plant feels) rather than treating outdoor conditions as a substitute.

## C4. Additional environmental sensors (onboard ambient layer)

**Status:** idea — not scheduled (capture for schema-proofing)
**Priority:** P4 (within section)
**Scope:** L — multiple I2C sensors, wiring, drivers, per-sensor cadence; incremental (add one at a time).
**Where:** device emits as `record_type=env` rows at a slower cadence; carried by the B1 schema discriminator.

Log ambient/environmental conditions alongside the soil readings so the dataset becomes multivariate — you can correlate dry-down rate with temp, RH, light, and more, explain the diurnal overshoot, and separate the plant's microclimate from the room. Most candidates are cheap I2C and share one bus: BME280/BME680 (air temp + RH + barometric pressure, BME680 adds VOC/gas), a light sensor (BH1750 lux, or TSL2591 for high dynamic range — but PAR/PPFD beats lux for plant-meaningful light), UV (the AS7331 family you already run on VantiScope), and a natural tie-in, the AS7341/AS7343 spectral sensors you work with, to log the *actual* light spectrum (sunlight vs grow-light vs cloudy window) rather than a single lux number. High-value extras beyond the obvious list: soil temperature (waterproof DS18B20 — drives evaporation and uptake, decouples from air temp, arguably more useful than air temp here); board/chip temperature (the ESP32 ADC drifts with temperature, so logging it lets you thermally correct the soil raw or attribute a shift to electronics vs soil); CO2 (SCD40, drives photosynthesis, swings indoors); and control-side telemetry — reservoir/tank level (real empty-tank detection, ties to `max_doses` and D2) and pump volume or run-time per dose (correlate watering against the moisture recovery that follows — see D1). Where: device emits these as their own `record_type=env` rows at a slower cadence (1–5 min is plenty; they don't need 30 s), carried by the B1 schema discriminator. Note: CO2/VOC overlap the HotBoxAQ inventory — coordinate via C2 so the same physical sensors and field names serve both projects.

## C5. Calendar / temporal review fields (derived analysis layer)

**Status:** idea — recommend derive-at-analysis, not raw-log columns
**Priority:** P5 (within section)
**Scope:** XS — a derived load-time transform; no firmware.
**Where:** analysis layer (host/notebook), not the device or the row schema.

Day-of-week, month, day-of-year, season, hour-of-day, daylight flag — for slicing by natural cycles (summer vs winter, day vs night) without hand-rolling date math each time. Recommendation: keep these *out* of the raw log and materialize them as a derived analysis layer, because they're 100% reconstructable from the UTC timestamp and storing them invites redundancy on every row plus definitional drift (when does "summer" start — solstice, June 1, meteorological?). A tiny load-time transform (one pandas block or a saved helper) adds `season`/`month`/`hour`/`is_daylight` columns canonically on read, so the summer-vs-winter compare is one line and the raw log stays lean and unopinionated. The only case for a token in the raw file is wanting it grep-able by period without tooling — then a single cheap `yyyy-mm` is fine as a convenience, not a source of truth.

---

# Section D — Actuators, status & connectivity
*Physical outputs, local HMI, and remote awareness/control.*

## D1. Full pump / actuator logging

**Status:** proposed — pending review
**Priority:** P1 (within section)
**Scope:** S–M — emit pump-event rows from the supervisor FSM, plus a run-time→volume calibration.
**Where:** firmware/supervisor emits pump events as `record_type=pump` rows → file; live state to console + status display (D3).

Build a complete pump log — right now nothing records what the pumps actually do, so the dataset has a moisture half with no actuator half. Log every pump event: channel/plant, start and stop (or start + duration), estimated volume, dose index within the watering cycle, the trigger (which level/threshold fired it), the pre- and post-water readings (the soil's response after the soak lockout), and any fault (`max_doses` dry-run, health veto, timeout). Why: with it you can see dose→recovery dynamics, catch a failing pump as its volume-per-runtime drifts, reconcile dispensed volume against tank drawdown (D2), and audit every watering decision after the fact. How: the supervisor already owns the FSM and the dose/fault counters, so emit a `record_type=pump` row at each state change; a calibrated mL/sec converts run-time to volume with no extra hardware, or add an inline flow sensor for ground truth.

## D2. Tank level sensing + refill reminders

**Status:** proposed — pending review
**Priority:** P2 (within section)
**Scope:** M — level sensor + threshold + alert + pump gate.
**Where:** firmware (level sensor + thresholds) → `record_type=tank` rows + alerts via status (D3) and served page (D4); gates the pump.

Measure reservoir level and warn before it runs dry. Why: this is the biggest open hole in unattended operation — today an empty tank only surfaces indirectly as a `max_doses` dry-run fault *after* the pump has already run dry; a real level reading lets you warn ahead and stop the pump from dry-running. How: pick a sensing method — float switch (cheap, single low threshold), ultrasonic (contactless, continuous), load cell/weight under the reservoir (continuous, nothing in the water, good for a sealed tank), or a capacitive/optical probe — log level or low/empty state as `record_type=tank`, raise a refill reminder at a threshold through the status indicators and served page, and gate the pump below empty. Pairs with pump logging (D1): dispensed volume should track tank drawdown, and a mismatch flags a leak or a stuck pump.

## D3. Local status indication / HMI (OLED, e-ink, LEDs, buzzer)

**Status:** idea/proposed — pending review
**Priority:** P3 (within section)
**Scope:** L — OLED + e-ink drivers, UI layout, refresh logic, status LEDs.
**Where:** firmware drives displays/LEDs over I2C/GPIO; fed by the fast health tick (A3).

Add at-a-glance local status using hardware you already have — small I2C OLED(s) and a larger e-ink/epaper panel — plus optional LEDs and a buzzer. Why: a glanceable display turns "is everything ok / what needs water / when's the next watering" into a look instead of a log dig — exactly the affordance a busy schedule needs. How, matching each display to its strength: e-ink/epaper for the persistent dashboard (per-plant levels, next-watering-due, last action, active warnings) — slow refresh suits slowly-changing status and it holds the image with no power; OLED for live/animated detail (current channel, real-time reading, a recent-history sparkline); status LEDs for instant per-channel state (green ok / amber needs-water / red fault-or-floating); buzzer reserved for critical only (tank empty, hard fault), if at all. Driven by the fast health tick (A3) so it's responsive; mind I2C addresses, since the env sensors (C4) share the bus.

## D4. WiFi connectivity, resilience & served status page

**Status:** idea/proposed — pending review
**Priority:** P4 (within section)
**Scope:** XL — WiFi management, web server + UI, auth, safe command routing, offline resilience.
**Where:** firmware (WiFi mgmt, web server, RSSI logging) → served UI + `record_type=net` rows; control endpoints honor the safety interlocks.

Use the ESP32's WiFi to serve a status page and remote controls, with logged connectivity and graceful offline behavior. Why: a phone-friendly page showing levels, next-watering-due, warnings, and a manual "water plant 3 now" button is the remote-awareness layer for when you're not home — which is most of the point of the build. How: serve a lightweight local web UI (status + manual actions); log RSSI/connection state (a `record_type=net` row or a status field) to see signal quality and dropouts over time; and critically, keep watering fully functional offline — WiFi is for telemetry and convenience, never a dependency of the safety loop — reconnecting automatically when it drops. Any manual command must route through the same interlocks as autonomous watering (single-pump, sample gate, health veto, soak lockout) so a button press can't bypass safety, and put at least basic auth on the control endpoints since they live on your LAN. Ties to B3 (NTP) and B5 (reconnect resilience).

## D5. Full-spectrum grow lighting (seasonal supplementation) — idea

**Status:** idea — low priority (current plants don't need it)
**Priority:** P5 (within section)
**Scope:** M — LED strip driver + schedule + log; low priority.
**Where:** actuator; firmware drives LED strips on a schedule → `record_type=light` log; closes a loop with C4's light/PAR sensors.

Optional actuated full-spectrum LED lighting for seasonal grow supplementation, leveraging your LED experience. Why: the south window is strong but seasonal, and short Chicago winter days could be supplemented to hold growth; logged as an actuator it also lets you correlate light dose with plant response. How: full-spectrum strips on a scheduled or closed-loop driver (photoperiod + intensity, optionally responsive to measured PAR/season from C4), logging on/off, spectrum, and intensity as a `record_type=light` stream — mirroring the pump actuator+log pattern. Reality check (yours): the current collection are hardy survivors that don't need it, so this is speculative and low-priority — captured for completeness and because the actuator/log shape is reusable.

# Section E — Analytics, prediction & data products
*Host-side / downstream: turning the logs into review, forecasts, and care guidance. Not firmware — not flash-gated; build anytime against captured logs.*

## E1. Development & monitoring UI (desktop console)

**Status:** proposed — near-term likely build
**Priority:** P1 (within section)
**Scope:** L — a desktop app spanning live view + history view + a constants/ranges editor; build it incrementally.
**Where:** host PC app; consumes the host-logger stream (B2) and the log files; reads/writes the firmware constants from A2/B1; the local-development sibling of the deployed served page (D4).

A desktop UI that replaces "scrolling serial bleeps, grepping log files, and coming to an agent every time" with a real window into the system — and, as channels and pumps multiply, the cockpit for developing, debugging, and tuning it. Three jobs. (1) **Live monitor** — every channel's current reading / level / spread / health at a glance (the multi-sensor view C1 produces), live strip-charts, pump + tank + connectivity status, color-coded health; far better than the serial monitor once you're past 2 channels. (2) **History & review** — load the logs and browse dry-down curves, overlays, and the E2 analytics interactively instead of hand-rolling a notebook each time; this is where the analytics actually surface to you. (3) **Constants & ranges editor** — the high-value one for your workflow: view and edit the cfg constants and the per-channel boundary array, ideally by *dragging the level boundaries directly on a chart of real readings* (you set these by hand this cycle — doing it visually against live and historical data is the natural upgrade), with the tool emitting the new values to paste into firmware, or later pushing them to the device over serial/WiFi so you can tune without a reflash. Plus a **debugging surface**: a decoded view of the raw stream with `record_type` rows broken out, fault/health events highlighted, and the serial-noise/CRC drops (B6) flagged rather than silently mangled. Build order that pays off early: live monitor first, then the constants editor, then fold in the history/analytics views. Stack-wise it's host-side — Python with a GUI, or a local-served page that reuses D4's frontend — with the B2 host logger as the natural backend. Relationship to D4: D4 is the *deployed, remote* status/control page served from the ESP32 for everyday use; this is the *local engineering console* for building, debugging, and tuning. Overlapping frontend, different jobs; they can share components.

## E2. Review analytics & historical feature set (histograms, charts, trend stats)

**Status:** idea — host-side analytics
**Priority:** P2 (within section)
**Scope:** M — a feature-extraction pass over the logs + a charting/notebook or dashboard layer; incremental.
**Where:** host-side post-process; surfaces inside the E1 UI's history view and/or an optional served dashboard (D4).

Turn the raw logs into review. The descriptive layer is mostly what you expected — histograms (reading distributions, watering-interval and dry-down-rate distributions), charts (the dry-down curve, multi-day and multi-plant overlays, the diurnal overshoot, summer-vs-winter via C5's calendar fields), and trend stats (rolling dry-down rate, drift in the field-capacity reading, a per-plant baseline/"fingerprint"). Underneath it sits the piece that quietly makes everything else easy: a **historical feature set** — one row per watering cycle with engineered features (dry-down rate, time-to-needs-water, field-capacity reading, post-water recovery, ambient means during the cycle) — mirroring HotBoxAQ's event-feature-table idea (C2) but for plant cycles. That feature table is the shared substrate: it powers the charts, simple anomaly flags ("this dry-down is unusual for this plant → heat / root issue / sensor drift"), the seasonal comparison, and the E3 predictor. No heavy ML — this is the histograms-and-trends layer you called — but building the per-cycle feature set deliberately (rather than re-deriving from raw each time) is what keeps the rest cheap.

## E3. Next-watering predictor (per-plant forecast + predicted-vs-actual loop)

**Status:** idea — host-side analytics (the one predictive piece worth doing)
**Priority:** P3 (within section)
**Scope:** M — per-plant curve fit + forecast + a tracking/refinement loop; pure post-process. Builds on E2.
**Where:** host-side post-process on the logs; surfaces a "due in ~N days" estimate to the E1 UI, the status display (D3), and the served page (D4).

Forecast when each plant crosses "needs water." Fit each plant's dry-down (a per-plant rate, or a band-local curve), predict the threshold crossing, surface "Plant 3: ~2.5 days" on the display/served page, then track predicted-vs-actual and let the error refine the model. What makes it real rather than cute: the dry-down rate is itself a function of the weather/light/temp you're logging (C3/C4), so it's a tiny per-plant system-ID with a seasonal input that sharpens as the dataset deepens — squarely your kind of problem. Low-commitment by construction: pure host-side (zero firmware/embedded risk, build anytime), and it degrades gracefully — a dumb per-plant average interval is already useful as a cold start. Consumes E2's per-cycle feature set; can take a variety prior from E4 to cold-start before enough history exists.

## E4. Plant variety / species care-reference lookup (future — scope-questionable)

**Status:** idea — future; flagged for a scope-test shakedown
**Priority:** P4 (within section)
**Scope:** M–L — a local care-reference dataset (or external API), a variety field at placement, and the mapping into thresholds/tips.
**Where:** host-side reference data + a variety field captured at sensor placement (extends C1's name assignment).

When you place a sensor and assign its short name (C1), also capture the plant variety, and look up an expected-care reference — watering amount/frequency, target moisture band, placement tips, summer/winter preferences. Value: variety priors personalize per-channel thresholds (a succulent and a fern want very different target moisture, so this could seed per-channel `mcfg` boundaries and intervals) and give the E3 predictor a cold-start estimate before history accrues. Source: a small local reference table of your actual plants is the cheap version; an external plant-care database/API is the rich version. Scope honesty (your framing): this is the item that drifts out of the instrumentation/control lane toward a "plant-care app," and it earns its place only if it feeds back into the *control/data* loop — seeding thresholds, cold-starting the predictor — rather than becoming a tips feature for its own sake. The defensible subset that would survive a scope test is probably just "variety → initial moisture band + expected interval"; the placement-tips and seasonal-prefs content is the optional nice-to-have to weigh separately.

---

## Your additions (to review / expand)

*Drop new ideas here as one-liners; we'll expand each into the full shape (Status / Priority / Scope / Where + paragraph) and file it into the right section when you're ready.*

- 
- 
- 
