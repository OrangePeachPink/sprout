# Telemetry schema & cross-project logging contract

**Status:** v1 draft (2026-06-23). This is the canonical row/file contract for `plants` logging,
and the **cross-project contract** that makes `plants` and the sibling air-quality project data joinable (backlog
**C2**). It consolidates the B1 self-describing-header spec and the C2 reconciliation checklist.

**Who leads:** plants has live captured data and a working device logger; the sibling air-quality project's schema
(the sibling project's data plan) is **approved but unimplemented** (Phase P5) with open decisions
(`DEC-004`: no `record_type`, no `session_id`, undefined null/delimiter/header). So this contract
**adopts the sibling air-quality project's field names where they exist** and **proposes** the additions it still lacks.
Items marked **[propose→sibling-AQ]** are things the sibling air-quality project should adopt for the join to work.

**Schema version:** `schema_version=1`. Bump on any breaking column change; the version is written
in every file's header block so one loader can read mixed-version history.

---

## 1. Principles

- **Long/tidy, one row per sensor-channel per sample.** Never a wide `raw1..raw4` row. Each row is
  self-contained — a pasted fragment still names its sensor. Matches how the firmware samples
  (one channel at a time) and how the sibling air-quality project's rows are shaped.
- **Raw is immutable.** `raw_value` (ADC counts) is never rewritten. `value` is the interpretation
  and may change as calibration improves; both are kept so history can be re-derived.
- **Time is host-authoritative.** The device has no RTC and WiFi is off, so it cannot know UTC. The
  host logger stamps `timestamp_utc` as each line arrives (negligible USB latency at a 30 s cadence);
  `millis_ms` carries exact *relative* device timing. On-device time (SNTP/RTC) is a future fallback
  only if logging without a host (e.g. SD card).
- **Device owns measurement + identity; host owns time + file format.** The MCU emits a compact
  machine line; the host logger adds the time/sequence columns, writes the canonical CSV file, and
  renders a pretty console (the B2 file/console split).
- **`record_type` from day one.** A namespaced discriminator on every row so heterogeneous streams
  (soil, env, pump, gas, weather) coexist in one file at independent cadences with no migration.

---

## 2. The row schema (canonical file column order)

CSV, RFC-4180 quoting, comma-delimited. **Null = empty field** (nothing between the commas).
`origin` = who fills the column: **dev** (MCU serial line) or **host** (logger). `shared` = part of
the cross-project core both repos carry.

| # | column | origin | shared | example | notes |
| --- | --- | --- | --- | --- | --- |
| 1 | `record_type` | dev | yes **[propose→sibling-AQ]** | `plants.soil` | namespaced; see §3 |
| 2 | `timestamp_utc` | host | yes | `2026-06-23T14:05:30.123Z` | ISO-8601, ms, `Z` |
| 3 | `timestamp_local` | host | yes | `2026-06-23 09:05:30.123` | host TZ, human |
| 4 | `sample_id` | host | yes | `12345` | logger monotonic counter |
| 5 | `session_id` | dev | yes **[propose→sibling-AQ]** | `3f9a1c` | per-boot; reboot = new id |
| 6 | `device_id` | dev | yes | `plants_esp32_a4cf12` | friendly + MAC suffix |
| 7 | `firmware_version` | dev | yes | `0.5.0` | |
| 8 | `logger_version` | host | yes | `plants_logger_0_1` | |
| 9 | `millis_ms` | dev | yes | `30000` | device monotonic ms since boot; 64-bit via `esp_timer` — no 49.7-day wrap (B4/B5) |
| 10 | `sensor_model` | dev | yes | `UMLIFE_v2_TLC555` | probe family |
| 11 | `sensor_id` | dev | yes | `s3` | physical sensor id |
| 12 | `sensor_position` | dev | yes | `origplant` | placement; all four co-located now |
| 13 | `channel` | dev | yes | `soil_moisture` | the measured quantity |
| 14 | `raw_value` | dev | yes | `1493` | ADC counts (trimmed mean) |
| 15 | `value` | dev | yes | *(null)* | interpreted value — **null** until a calibrated VWC exists; never an uncalibrated % (#38). **`raw_value` + band are authoritative.** |
| 16 | `unit` | dev | yes | *(null)* | unit of `value` (null while `value` is null) |
| 17 | `quality_flag` | dev | yes | `OK` | shared enum, §4 |
| 18 | `temp_context_c` | host/dev | yes | *(null)* | future env layer (C4) |
| 19 | `rh_context_pct` | host/dev | yes | *(null)* | future env layer (C4) |
| 20 | `pressure_context_hpa` | host/dev | yes | *(null)* | future env layer (C4) |
| 21 | `event_id` | dev/host | yes | *(null)* | links to event table, §5 (D1) |
| 22 | `payload` | dev | plants-ext | `level=OK;role=disp;spread=50;gpio=36` | `;`-sep `k=v`, §6 |
| 23 | `notes` | host | yes | *(null)* | optional human annotation |

The **shared core** (cols 1–21, 23) is byte-identical in shape between plants and the sibling air-quality project, so one
loader reads both. `payload` (22) is the type-specific escape hatch: opaque to the shared loader,
infinitely extensible without widening the header. Plants puts its soil-only fields there
(`level`, `role`, `spread`, `gpio`); the sibling air-quality project puts its gas-only fields there.

---

## 3. `record_type` namespace registry

Format `project.stream`. Namespaced so a merged file is unambiguous.

| record_type | project | meaning | backlog |
| --- | --- | --- | --- |
| `plants.soil` | plants | soil-moisture reading | C1 (live) |
| `plants.env` | plants | onboard ambient (temp/RH/light/CO2…) | C4 |
| `plants.pump` | plants | pump/actuator event | D1 |
| `plants.tank` | plants | reservoir level | D2 |
| `plants.weather` | plants | host-pulled outdoor weather | C3 |
| `plants.net` | plants | WiFi/connectivity | D4 |
| `plants.health` | plants | fast liveness tick | A3 |
| `aq.gas` | the sibling air-quality project | gas channel (CO2/VOC/…) | **[propose→sibling-AQ]** |
| `aq.env` | the sibling air-quality project | AQ ambient context | **[propose→sibling-AQ]** |

The **CO2 ↔ watering** correlation you want is: co-deploy the sibling air-quality project on the same window ledge, then
join `plants.soil`/`plants.pump` against `aq.gas` rows **on `timestamp_utc`**. The shared time axis +
namespaced `record_type` are the only mandatory pieces that makes that join trivial.

---

## 4. `quality_flag` enum (shared, from the sibling air-quality project)

Adopt the sibling air-quality project's enum verbatim — richer than plants' old binary `ok|WARN` and it upgrades plants'
own diagnostics:

`OK · WARMING · BASELINE_LEARNING · SUSPECT · SATURATED · ESTIMATED · NO_SIGNAL · ERROR`

**Plants soil mapping:**

| condition | flag | source |
| --- | --- | --- |
| healthy reading, spread within bound | `OK` | normal |
| sample spread > `spread_warn_raw` (noisy/contact) | `SUSPECT` | `health_warn` |
| floating/disconnected probe (incoherent, ~4095 spread) | `NO_SIGNAL` | classifier health |
| ADC railed (raw pegged at 0 or 4095) | `SATURATED` | raw clamp check |
| *(reserved, unused by soil)* | `WARMING`, `BASELINE_LEARNING`, `ESTIMATED`, `ERROR` | — |

---

## 5. Event overlay (from the sibling air-quality project)

Adopt the sibling air-quality project's `event_id` + separate event-metadata table. A plants watering or fault becomes a
joinable event, unifying it with the sibling air-quality project's gas exposures and giving D1's pump log its event shape.
Raw rows carry `event_id` (null when idle); one event-table row per event with: `event_id`,
`event_label`, `event_family`, `known_source`, `start/stop/recovery_timestamp_utc`, `operator`,
`notes`, `metadata_version`. (Deferred until pump logging, D1 — schema reserved now so no migration.)

---

## 6. `payload` convention

`;`-separated `key=value`, **no commas** (so it sits in one unquoted CSV field). `;` separates pairs
and the first `=` splits key/value, so values *may* contain spaces (e.g. `level=well watered`). Plants
`plants.soil` keys: `level` (band name, e.g. `OK`/`well watered`), `role` (`disp`|`diag`),
`spread` (raw spread of kept samples), `gpio`. Example: `level=well watered;role=disp;spread=48;gpio=36`.

---

## 7. File format & rotation

- **Delimiter** comma; **null** empty field; **RFC-4180** quoting (only `notes` is likely to need it).
- **Header block** at the top of every file (and re-emitted at each rotation segment so each file is
  independently self-describing): `#`-prefixed provenance lines — `schema_version`, contract version,
  firmware version + **git commit hash + build time**, `device_id` + MAC + chip/ADC config, run label,
  per-sensor map, column legend — then the CSV **column-name header row**, then data rows.
- **Naming** `plants_<device_id>_<YYYYMMDD>_<HHMMSS>.csv` (boot/segment start in the name).
- **Rotation** daily and/or by size (default: new file each calendar day, UTC); optionally gzip closed
  segments. Caps a corruption/disk-full to one segment (B5).
- **Analysis tier** raw CSV is the immutable capture; a parquet/DuckDB load tier comes later for
  analysis (shared with the sibling air-quality project's plan). One loader, both projects.
- **Sample** a committed example is at [`sample_log.csv`](sample_log.csv) (3 rotation segments + data) —
  design parsers/dashboards against it without the hardware.

---

## 8. Device serial line vs. file row (the B2 split)

The MCU emits a **compact CSV line** of its `origin=dev` columns, prefixed by `record_type` so it's
greppable, e.g.:

```text
plants.soil,3f9a1c,plants_esp32_a4cf12,0.5.0,30000,UMLIFE_v2_TLC555,s3,origplant,soil_moisture,1493,,,OK,level=well watered;role=disp;spread=48;gpio=36
```

Provenance/metadata still emit as `#`-prefixed lines at boot. The **host logger**:

1. parses the device line, prepends `timestamp_utc,timestamp_local,sample_id,logger_version`,
   reorders to the canonical §2 order, writes the full CSV row to the rotating file;
2. renders a **pretty aligned console** subset for live eyeballing;
3. writes the `#` header block once per file segment.

**Integrity (B6):** each burst is preceded by a sacrificial newline (absorbs the post-idle UART
glitch), and each device line carries a trailing NMEA-style XOR checksum `*HH` over the row body.
The host validates it and drops a byte-corrupted line deterministically (`[crc N]`) rather than
letting a mangled reading enter the data — important when the data feeds calibration. The checksum
is a transport suffix only, **not** a CSV column, so the file stays `schema_version=1`.

**Trade-off to confirm:** with the device emitting CSV, a *raw* `pio monitor` (no host logger) shows
comma lines instead of today's pretty columns. Mitigation: the host logger restores the pretty
console, and the boot `#` header stays human-readable. Alternative is to keep the device emitting
pretty columns and have the host parse them positionally — more fragile against the known
prefix-corruption. **Recommendation: device emits CSV.**

---

## 9. Open decisions (confirm before firmware Phase 2)

1. **Device line format:** CSV (recommended, §8) vs. keep pretty human columns.
2. **`device_id` scheme:** `plants_esp32_<last3 MAC bytes hex>` (recommended) vs. a fixed friendly id.
3. **Firmware version:** bump to **v0.5.0** for the reshape (recommended — distinct named feature) vs.
   fold into the still-unflashed v0.4.0.
4. **Host logger location / log dir:** `tools/logger/plants_logger.py` writing to repo-root `logs/`
   (recommended) vs. keep under `firmware/logs/`.
5. **`channel` vocabulary:** `soil_moisture` (recommended) — fixes the shared term for the join.

---

## 10. What plants proposes the sibling air-quality project adopt (for the join)

- Add a namespaced **`record_type`** column (`aq.gas`, `aq.env`).
- Add **`session_id`** (it needs it for long runs anyway, its B5-equivalent).
- Settle the open `DEC-004` items the same way: **null = empty field**, comma delimiter, the §7
  `#`-header block, `schema_version` in-header.
- Everything else already matches (timestamp, identity, `{raw_value,value,unit}`, `quality_flag`,
  event table, `*_context_*`).
