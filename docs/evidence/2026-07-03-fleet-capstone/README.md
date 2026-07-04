# Fleet dashboard capstone — three MCUs, one dashboard — 2026-07-03

Bench evidence for the **Wave-1 integration capstone** (#584 / #486): three ESP32 boards
of three different chip families, each named and untethered on WiFi, all feeding the
**Sprout dashboard live at the same time**. This is the packet that ties the individual
board bring-ups (the sibling `2026-07-03-esp32-s3-native-usb/` and
`2026-07-03-esp32-c5-native-usb/` packets) into one working fleet, and records the
classic's toolchain re-test (#529) and the device-identity findings surfaced along the way.

Bench arrangement: maintainer = hands (cables, phone, power bricks, screenshots); Firmware
lane = brains-on-call (exact commands, watched serial/HTTP output, verdicts). Raw serial
logs and dashboard screenshots stay in the maintainer's local archive; MAC / USB instance
IDs are not reproduced here (ADR-0015 / ADR-0020, machine-checked by the identifier-guard,
issue #573). Private RFC1918 IPs are evidence-safe and kept.

## The fleet (settled this session)

| Name (`device_id`) | Chip | Board target | IP (WiFi) | Env sensors | Notes |
| --- | --- | --- | --- | --- | --- |
| `classic` | ESP32-D0WD-V3 | `esp32dev` | 192.168.68.87 | SHT45 + AS7263 | the skylight-confound instrument; only board with env |
| `s3-1` | ESP32-S3-N8R2 | `esp32s3` | 192.168.68.62 | — | generic clone, native-USB path (dead CH343 right port) |
| `c5off1` | ESP32-C5 (rev v1.2) | `esp32c5` | 192.168.68.85 | — | official Espressif DevKitC-1, dual-band WiFi 6 |

All three: firmware **0.7.0** (the merged multi-board build, #591 + #595), `time_source =
device_synced` (NTP-on-connect, #278), serving `GET /` + `GET /telemetry` over WiFi with no
cable (#276), auto-rejoin on power-cycle (#21).

## Device identity — named this session (`!name`, persisted to NVS)

Every board ships with the **same** default `device_id` ("Sprout ESP32" — all ESP32-family
chips derive it; see finding #601), so an unnamed fleet is indistinguishable. Each board was
given a unique identity over serial (`!name,<id>`, NMEA-checksummed, sanitized, written to
NVS so it survives reboots), then confirmed **on the wire** over WiFi:

```text
classic  -> GET http://192.168.68.87/telemetry  ->  plants.soil,2bf545,classic,0.7.0,...
s3-1     -> GET http://192.168.68.62/telemetry  ->  plants.soil,b23473,s3-1,0.7.0,...
c5off1   -> GET http://192.168.68.85/telemetry  ->  plants.soil,da935c,c5off1,0.7.0,...
```

Naming is **serial-only today** — a real usability gap for an untethered product, filed as
the naming-UI enhancement (#600).

## Classic toolchain re-test — Block D (#529)

The classic was re-onboarded and re-verified on the pinned pioarduino / IDF5 toolchain
(ADR-0024, migration #529):

- **D1 — safety wedge (`!wedge`):** **PASS.** The watchdog fires, the chip resets, and
  `allRelaysOff()` runs first on the reboot — the fail-safe property holds on the new
  toolchain. **Finding:** it fired at **~5.1 s**, not the **8.1 s** old-toolchain baseline,
  because IDF5 auto-initializes the Task Watchdog before `setup()`, so our
  `esp_task_wdt_init(8000 ms)` is rejected (`TWDT already initialized`) and the framework
  default (~5 s) stands. Not a safety regression (5 s is *more* aggressive than 8 s), but our
  configured value is silently ignored and the banner is dishonest → fix filed as #599.
- **D2 — ADC / classifier re-verification:** **PASS.** The soil ADC reads and the moisture
  classifier bands re-verified consistent on the new toolchain — visible live on the
  dashboard: classic's four channels read ~3,190–3,237 raw → `air-dry` / `Parched·Critical`,
  matching the ratified `esp32-classic` endpoints (`cal_verified=true`, #248).

Raw serial captures are in the maintainer's local archive (`_scratch/` capture scripts).

## The capstone — all three live in one dashboard (#486)

The local fleet registry (`config/devices.local.json`, gitignored) lists the three boards
with their `base_url`s. `serve.py`'s fleet poller (`FleetAdapter` → one `DeviceAdapter` per
served device, #277 / #553) polls each device's `/telemetry` **live** on load — no separate
logger, no new build. Launch is the normal one-click Sprout desktop icon (#151).

End-to-end poll proof (the exact path the dashboard runs) returned **4 live rows each from
all three distinct `device_id`s** — 12 rows, three cards' worth:

```text
rows polled per device_id (live):  classic: 4   s3-1: 4   c5off1: 4
distinct devices in poll: 3  (three cards)
```

Result: the dashboard renders **three "online · synced" cards** — classic, s3-1, c5off1 —
each with its four channels, feeding the shared calibration ladder and raw-trajectory
plots. Three chip families (Xtensa D0WD, Xtensa S3, RISC-V C5), one dashboard, live.

## Finding — device identity has no continuity across renames (#602)

The classic is one piece of silicon that has reported **three** identities over its life
(`plants_esp32_f4e9d4` → `Sprout ESP32` → `classic`). Because Sprout deliberately uses no
hardware anchor (#188 — no MAC/eFuse read), nothing links a board's old identity to its new
one, so its prior data is **orphaned** under the old names and the dashboard renders it as
extra "offline, last heard Nd ago" cards.

The prior-identity rows are **not** rewritten: the `Sprout ESP32` data lives in the
committed `.data-worktree` records store (hands-off) *and* the board genuinely reported that
name at that time — relabeling it would falsify the provenance chain. The correct fix is
**display-time coalescing** (declare a device's prior identities; unify at render, records
untouched), filed as #602. For a clean capstone screenshot tonight, the dashboard's `24h`
range view (both prior identities are 2–5 days old) shows only the three live boards — an
honest "last 24 h of the live fleet" view, not a data edit.

## Findings filed this session

| # | Title | Kind |
| --- | --- | --- |
| #598 | serve `plants.env` rows on `/telemetry` (SHT45/AS7263 are serial-only, invisible untethered) | feat |
| #599 | IDF5 auto-inits the task-WDT → our 8000 ms config is ignored (wedge fired ~5 s not 8 s) | fix |
| #600 | in-app UI to name/rename a device over WiFi (no CLI-while-tethered) | feat |
| #601 | default `device_id` collides across a fleet (every ESP32-family → "Sprout ESP32") | fix |
| #602 | device identity continuity — coalesce a board's prior identities into one card | feat |

Together, #600 / #601 / #602 are the **device-identity lifecycle** set (set it, keep it
unique, keep it continuous).

## Honest scope — what is NOT in this packet

No soil probes wired — the channel readings are **floating noise** on now-valid pins
(`SATURATED` / near-zero on s3-1 and c5off1; the classic's ~3,200 air-dry is the board's own
pins reading open). The capstone proves **three MCUs feeding one dashboard**, not real
moisture. No plant→channel assignments (`channels: {}` in the registry) — that is install-day
work. Deferred to the wired round: Block B (continuity of the S3/C5 candidate pin maps + real
probe sanity), Block C (sensor QA to ≥11 validated probes), and the yellow C5 clone (A6).

## Session provenance

Maintainer bench session, 2026-07-03. Facts here are serial-observed / curl-captured / poll-verified
at capture time; raw logs and screenshots kept in the maintainer's local archive.

Refs: #584 · #486 · #529 · #276 · #278 · #21 · #188 · #598 · #599 · #600 · #601 · #602.

— Firmware 🔧
