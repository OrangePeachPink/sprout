# Telemetry schema & cross-project logging contract

**Status:** v1 draft (2026-06-23). This is the canonical row/file contract for `plants` logging,
and the **cross-project contract** that makes `plants` and the sibling air-quality project data joinable (backlog
**C2**). It consolidates the B1 self-describing-header spec and the C2 reconciliation checklist.

**Who leads:** plants has live captured data and a working device logger; the sibling air-quality project's schema
(the sibling project's data plan) is **approved but unimplemented** (Phase P5) with open decisions
(`DEC-004`: no `record_type`, no `session_id`, undefined null/delimiter/header). So this contract
**adopts the sibling air-quality project's field names where they exist** and **proposes** the additions it still lacks.
Items marked **[propose→sibling-AQ]** are things the sibling air-quality project should adopt for the join to work.

**Schema version:** `schema_version=1` is the **live, implemented** contract below (§§1-10) — what
`parse_v1` reads and the device/logger emit today; nothing in this document's status changes that.
**§11 is a v2 model, ratified 2026-07-01** (device-owned time, dedupe key, sensor provenance — the
untethered/multi-device prerequisite for [ADR-0018](adr/0018-dual-mode-transport-and-durability.md), #300),
**not yet implemented or enforced** — that's separate follow-on build work. Bump on any breaking column
change; the version is written in every file's header block so one loader can read mixed-version history.

**`schema_version=3`** shipped the stable minted `device_id` + payload `name=` (ADR-0027, §2).
**`schema_version=4` is LIVE** (the #739 bundle — the single wire revision after v3): `config_id=`
provenance (#576), `rssi=`/`uptime_s=`/`heap=` diagnostics (#669), and the `SENSOR_FAULT`
`quality_flag` value + `fault=` reason (#670). **v4 is a strict superset of v3** — every addition
rides `payload` or the `#` header; **ZERO new `CANONICAL_COLUMNS`** (the companion air-quality
shared core stays byte-identical). Reader rule: **`>=4` ⇒ full v4 vocabulary**, layered on
**`>=3` ⇒ `device_id` is the stable minted id**; `parse_v1` branches once at `>=4`, never
stitching a v3 row into v4 vocab. Details in §13.

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
| 6 | `device_id` | dev | yes | `k7m2rt` | **stable minted id** (ADR-0027) — a **6-char Crockford base32** nonce (lowercase `0-9 a-z` minus `i l o u`) from the first-boot NVS UUID; never MAC-derived (ADR-0020); the friendly *name* moves to the registry (#592) and rides payload `name=` on every row (pre-mint degrade + legibility). *Set at **`schema_version=3`**: `<3` logs carry the pretty `!name` here (v1 monitor, v2 experiment-capture); `>=3` ⇒ this is the stable id.* |
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
| 18 | `temp_context_c` | host | yes | *(null)* | interior ambient, §12 (ADR-0023 v2) |
| 19 | `rh_context_pct` | host | yes | *(null)* | interior ambient, §12 (ADR-0023 v2) |
| 20 | `pressure_context_hpa` | host | yes | *(null)* | §12 — pressure exception (ADR-0023 §3) |
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

### 3.1 Sampling pauses during a dose (by design)

`plants.soil` rows are emitted **only while the controller is in `SYS_SAMPLING`** (pumps off). During a dose
(`SYS_WATERING`) the supervisor — the single sample + actuation authority
([ADR-0016](adr/0016-actuation-wiring-seam.md) §1, §4) — pauses ADC soil reads, so **no `plants.soil` rows
are produced for the duration of the dose**. This is a hard invariant ("no sampling while pumping") —
**not data loss and not a logging interruption**.

Serial output itself is not gated — only ADC reads are — so `plants.pump` events still emit during the dose
and **bracket** the gap. That makes a by-design watering gap distinguishable from a real one:

- **By-design (watering):** the `plants.soil` gap is **bracketed by `plants.pump` on/off events** and is
  bounded by the supervisor's hard max-on ceiling (short).
- **Real interruption (logger down, restart, unplug):** the gap has **no bracketing `plants.pump` events**.

Analysis never stitches across either gap — raw stays immutable ([ADR-0006](adr/0006-data-architecture.md)) —
and gap-surfacing should treat a pump-bracketed gap as **expected**, not an interruption. *(The dashboard
cross-references `plants.pump` to suppress these once pump logging is live — D1; until then a long-enough
dose may surface as an interruption, which is honest, not wrong.)*

---

## 4. `quality_flag` enum (shared, from the sibling air-quality project)

Adopt the sibling air-quality project's enum verbatim — richer than plants' old binary `ok|WARN` and it upgrades plants'
own diagnostics:

`OK · WARMING · BASELINE_LEARNING · SUSPECT · SATURATED · ESTIMATED · NO_SIGNAL · SENSOR_FAULT · ERROR`

**`SENSOR_FAULT` is a `schema_version=4` addition** (#670, ratified in the #739 v4 bundle) —
one coarse, honest value meaning *"this reading is not trustworthy as moisture."* **[propose→sibling-AQ]**
the shared enum gains this one value; existing values are unchanged (additive, the #652
"quality_flag-is-a-wire-value" precedent). The **specific** reason rides `payload` `fault=` (§6) so the
shared enum stays small: `fault=stuck_wet` (short / water-contamination) or `fault=dead_adc`
(disconnected / ADC floating to ~0).

**Plants soil mapping:**

| condition | flag | source |
| --- | --- | --- |
| raw **strictly below** the board physical wet rail (impossibly wet: short / contamination / dead ADC) | `SENSOR_FAULT` | **v4 #670** — firmware self-declares from the per-board `wet_rail_raw` (ADR-0019; classic 900); reason in payload `fault=` |
| healthy reading, spread within bound | `OK` | normal |
| sample spread > `spread_warn_raw` (noisy/contact) | `SUSPECT` | `health_warn` |
| floating/disconnected probe (incoherent, ~4095 spread) | `NO_SIGNAL` | classifier health |
| ADC railed **high** (raw pegged at ~4095, dry rail) | `SATURATED` | raw clamp check |
| *(reserved, unused by soil)* | `WARMING`, `BASELINE_LEARNING`, `ESTIMATED`, `ERROR` | — |

> **v4 fix (#670):** the pre-v4 rule flagged a **low** rail (`raw <= 5`) as `SATURATED`, which masked a
> dead board (the live `s3-1` reading `0/7/4/1`) as four drowning plants. Under v4 a sub-wet-rail raw is
> `SENSOR_FAULT`, never `SATURATED`. **Raw is preserved (ADR-0006)** — the fault annotates the trust flag;
> the real raw stays on the wire and in the log. `SATURATED` now means the **dry** (high) rail only.

**Plants env mapping (`plants.env`, ratified by Data for #373/#374):**

Onboard ambient context from the optional `esp32dev_env` build (SHT45 temp/RH + AS7263
NIR). **Raw context, NOT plant-truth** — the sensors sit on the breadboard near the
ESP32, so `sensor_position` carries that placement on every row. One row per
(sensor, channel), tidy/long like soil — never a packed multi-value row.

| sensor | `sensor_model` | `channel` | `raw_value` | `value` | `unit` | notes |
| --- | --- | --- | --- | --- | --- | --- |
| SHT45 | `SHT45` | `ambient_temp` | raw ticks (opt) | °C | `degC` | **calibrated** — value/unit populated |
| SHT45 | `SHT45` | `ambient_rh` | raw ticks (opt) | %RH | `pctRH` | factory-calibrated sensor |
| AS7263 | `AS7263` | `nir_610`…`nir_860` | channel count | *(empty)* | *(empty)* | **raw counts** — uncalibrated, one row per band |

- **The soil raw-only law (firmware emits `,,` for soil `value`/`unit`) is soil-specific
  and does NOT extend to `plants.env`.** SHT45 is a factory-calibrated sensor, so its
  `value`/`unit` ARE the trustworthy reading (≠ the uncalibrated capacitive soil ADC).
  AS7263 stays raw-only (`raw_value` count; `value`/`unit` empty): we detect the
  *relative* skylight transit / beam-vs-shaded state, not absolute irradiance. The
  host raw-only contract check filters on `plants.soil`, so calibrated env rows never
  trip it.
- **`sensor_position`** (canonical column, not buried in payload) carries placement:
  `breadboard_near_esp32`. The spectral row's payload adds the aim qualifier.
- **`payload`** — AS7263: `gain`, `itime_ms`, `aim` (e.g. `gain=16;itime_ms=50;aim=skylight_beam;not_canopy`).
  SHT45: optional `mount=breadboard_near_esp32` mirror; placement is authoritative in `sensor_position`.
- **`quality_flag`** uses the shared enum: SHT45 → `OK` / `SUSPECT` (CRC-8 fail) /
  `NO_SIGNAL` (bus timeout); AS7263 → `NO_SIGNAL` (bus/timeout) / `SATURATED` (a band
  rails). A CRC/bus failure surfaces as a flagged row, **never a silent gap**.
- **Six tidy rows over one packed row** (the #13 tidy-format call): matches the soil
  one-row-per-channel model, so analytics treat each NIR band as a uniform series
  (joinable on `timestamp_utc` like any channel) with no payload-unpacking in `parse_v1`.

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
Host-appended keys (additive, never touching device keys): `host_monotonic_ms` (#9), the §11 v2 keys
(`device_seq`, `time_source`, `device_timestamp_utc`), and the §12 context tags (`context_source`,
`pressure_context_source`).

**`schema_version=4` device keys (the #739 v4 bundle — all payload, ZERO new canonical columns):**

| key | on | meaning |
| --- | --- | --- |
| `config_id=<8hex>` | every row (soil + env) | #576 / ADR-0025 — firmware-computed fingerprint of the active config snapshot (ADC/sampling/cal/cadence). Same id ⇒ rows are directly comparable; a change is a comparability boundary + the no-auto-adjust alarm. Header-authoritative (`# config_id=` line); **`parse_v1` reads it, never re-derives.** |
| `fault=stuck_wet｜dead_adc` | soil, only when `quality_flag=SENSOR_FAULT` | #670 — the specific fault reason (see §4). |
| `rssi=<dBm>` | soil, **connected-only** | #669 — WiFi signal strength (a negative int). **Honest-absent** (ADR-0028): a serial/tethered or unassociated row **omits the key entirely** — never a fake `0`. Only the dBm value; **never SSID/BSSID/MAC** (privacy fence). |
| `uptime_s=<s>` | every soil row | #669 — seconds since boot (board diagnostic; transport-independent). |
| `heap=<bytes>` | every soil row | #669 — free heap bytes (board diagnostic). |

---

## 7. File format & rotation

- **Delimiter** comma; **null** empty field; **RFC-4180** quoting (only `notes` is likely to need it).
- **Header block** at the top of every file (and re-emitted at each rotation segment so each file is
  independently self-describing): `#`-prefixed provenance lines — `schema_version`, contract version,
  firmware version + **git commit hash + build time**, `device_id` + chip/ADC config, run label,
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
plants.soil,3f9a1c,Sprout ESP32,0.5.0,30000,UMLIFE_v2_TLC555,s3,origplant,soil_moisture,1493,,,OK,level=well watered;role=disp;spread=48;gpio=36
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
2. **`device_id` scheme:** RESOLVED (#188 / #205) — a **pretty default** (`Sprout ESP32`, from the
   chip model) or an optional **user-set name** (`!name`, NVS-persisted, CSV-sanitized). No MAC, and no
   MAC-derived suffix.
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

---

## 11. Schema v2 (RATIFIED model — not yet implemented) — device-owned time, dedupe, sensor provenance

**Status: ratified by the maintainer 2026-07-01, alongside ADR-0018's acceptance.** This section defines — it
does not yet implement — the v2 contract [ADR-0018](adr/0018-dual-mode-transport-and-durability.md) cites
as its schema prerequisite (#300, from Trellis's #285 review). **Nothing here changes today's live
behavior**: `parse_v1` keeps reading v1 rows exactly as it does now; the device and host logger keep
emitting v1 unchanged. v2 is additive-only (new optional columns) so a v1 row is a valid v2 row with
those columns empty — no breaking change, no migration required for existing logs. Implementing /
enforcing v2 in `parse_v1.py` and the firmware/logger emitters is separate future work, gated on
ratification.

**Identity bump (ADR-0027, Accepted 2026-07-04):** separately from v2's additive columns, ADR-0027 repurposes
`device_id` (§6) from a mutable friendly name to a **short stable minted id** (the friendly name moves to the
registry, #592). Because that changes an existing column's *meaning* (not additive), it is set at
**`schema_version=3`** — **not** 2,
which is already live-emitted by the experiment-capture isolated writer (`experiment_capture.py`, `device_id`=name).
The reader rule is therefore unambiguous: **`schema_version >= 3` ⇒ `device_id` is the stable minted id**; `<3` (v1
monitor, v2 experiment-capture) ⇒ it is a friendly name. §11's additive device-owned-time columns ride the same v3
monitor emission. A one-time map re-keys the three legacy bench identities (ADR-0027 §9). Format is a 6-char
Crockford base32 nonce (§6); the friendly name rides payload `name=` on every row as the pre-mint degrade
identifier. The companion air-quality project, which has
no schema built yet, adopts the post-bump semantics from its first implementation —
stable-id-in-the-id-column from day one, no legacy epoch on that side (ADR-0027 rider 1).
This strengthens §11.2's dedupe key, whose lead
term `device_id` becomes genuinely stable. Firmware mint+emit is #601; the UUID-keyed registry is Data's slice.

**Why now:** §1's "time is host-authoritative" and this file's `session_id`-only identity model
assume one tethered device. The untethered/multi-device path ([PRD-0005](prd/0005-untethered-sprout.md))
breaks both assumptions — see epic #267 and epic #448: an untethered device may have no host
stamping `timestamp_utc` as lines arrive, and store-and-forward (buffer while offline, replay on
reconnect) can re-send rows a host has already ingested. v2 defines the columns that make both cases
honest instead of silently wrong.

### 11.1 Device-owned time, column-level

Today `timestamp_utc` is host-stamped on arrival (§1) — fine for a tethered USB device where UI latency
is negligible, wrong for a device buffering readings for minutes/hours before it can reach the host.

| column | origin | shared | example | notes |
| --- | --- | --- | --- | --- |
| `device_timestamp_utc` | dev | proposed | `2026-07-01T14:05:30.000Z` \| *(null)* | the device's own UTC stamp (SNTP/RTC), if it has one; **null when unsynced** — never a guessed value |
| `ingest_timestamp_utc` | host | proposed | `2026-07-01T14:07:12.500Z` | when the host actually received/ingested the row — always populated, tethered or not |
| `time_source` | dev | proposed (ties to ADR-0018) | `host` \| `device_synced` \| `device_uptime` | which clock the row's authoritative time comes from |

**The unsynced-row rule:** when `time_source=device_uptime` (no SNTP/RTC lock), `device_timestamp_utc`
is **`NULL`** — the device honestly doesn't know UTC, so the schema doesn't pretend it does.
`millis_ms`/an on-device monotonic sequence is still exact *relative* timing. Downstream consequences,
stated so join/forecast/gap-detection code has one place to look:

- **Join on time:** use `ingest_timestamp_utc` for cross-source joins (e.g. weather, the sibling
  air-quality project) when `device_timestamp_utc` is null — it's always present, even if it carries
  store-and-forward latency (see §11.2's `device_seq` for the row's true emission order regardless).
- **Forecast / rate-of-change:** an unsynced device's rows are still validly *ordered* (by `device_seq`)
  even though their wall-clock spacing is only approximate (ingest-time, not emission-time) until
  reconnect. Treat the inter-row `Δt` as approximate, not exact, for an unsynced run.
- **Gap detection:** a gap bounded by a `time_source` change (unsynced → synced, or a store-and-forward
  flush) is a **reporting-latency gap**, not a data gap — distinguish it the same way §3.1 distinguishes
  a pump-bracketed gap from a real interruption: by what brackets it, not by silently smoothing it over.
- **Tethered devices are unaffected:** `time_source=host` for a USB-tethered device is exactly today's
  v1 behavior (§1) — `device_timestamp_utc` stays null (no device clock involved), `ingest_timestamp_utc`
  fills the role `timestamp_utc` fills today.

### 11.2 Row idempotency / dedupe key

Store-and-forward means the **same physical reading** can arrive twice (buffered, then replayed after a
reconnect that raced the original send). v1 has no de-dupe key — `sample_id` (§2 col 4) is a **host**
monotonic counter assigned on ingest, so a replayed row gets a *new* `sample_id` and silently
duplicates.

| column | origin | shared | example | notes |
| --- | --- | --- | --- | --- |
| `device_seq` | dev | proposed | `40217` | device-monotonic counter, **survives reconnect** (persists across a buffered/replayed send; resets only on device reboot, same as `session_id`) |

**Dedupe key:** `(device_id, session_id, device_seq, record_type, sensor_id)` — the tuple that
identifies *this exact reading* independent of how many times its bytes crossed the wire. A store, not
just a stream: ingest checks this key before appending, so a replay is dropped, not duplicated.
Preserves append-only raw-is-truth (below) — dedupe happens at the ingest boundary, never by rewriting
already-stored rows.

### 11.3 Sensor provenance (ties to ADR-0019, #295)

A probe's `sensor_type` or calibration profile can change over a device's lifetime (a swapped probe, a
recalibration). Old logs must stay unambiguous about which profile produced them, so a later
calibration change never silently reinterprets historical raw data.

| column | origin | shared | example | notes |
| --- | --- | --- | --- | --- |
| `sensor_type` | dev | proposed (ADR-0019) | `capacitive_v2` | the capability-descriptor sensor type (ADR-0019 §2), not just `sensor_model`'s part number |
| `cal_profile_version` | dev/host | proposed | `3` | which calibration profile produced `value` from `raw_value` — increments on a re-cal, never edited in place |
| `cal_source` | dev/host | proposed | `header` \| `default` | ties to #295's cal-bounds-in-header work — where the bounds that produced this row's band came from |

### 11.4 Raw-is-truth preserved (ADR-0006)

v2 changes **what's recorded alongside a row**, not the raw-is-truth model itself:

- The v2 store is still **append-only raw ingest** — `raw_value` is never rewritten, dedupe drops a
  *replay* (identical reading, same dedupe key) rather than merging or overwriting anything.
- Derived views (bands, forecasts, bench-arc summaries) remain **rebuildable** from the raw v2 store,
  exactly as ADR-0006 requires for v1.
- An unsynced row's honest `NULL` `device_timestamp_utc` (§11.1) is itself raw-is-truth: the schema
  records what the device actually knew, not an inferred backfill.

### 11.5 Acceptance mapping (#300)

- [x] Time columns + the unsynced-row rule defined — §11.1
- [x] Dedupe key (incl. `device_seq`) defined — §11.2
- [x] Sensor provenance fields defined — §11.3
- [x] Raw-is-truth preserved in the v2 store model — §11.4
- [ ] ADR-0018 references this section as its schema prerequisite — for Trellis/maintainer once §11
      is ratified (this PR proposes; it does not self-ratify)

### 11.6 Explicitly out of scope for this proposal

- **Implementing v2 in `parse_v1.py`** (reading the new columns) and in the device/logger emitters —
  separate follow-on slice(s), gated on ratification, so a schema change never lands ahead of the code
  that's supposed to honor it.
- **Backfilling existing v1 logs** with v2 columns — not needed; v1 logs stay valid v1 (§11 is
  additive-only), read as-is.
- **The multi-device registry / dashboard** (#485, #486) — those consume `device_id`/`sensor_id` that
  already exist in v1; §11 doesn't change their contract.

---

## 12. Interior-ambient context fill (IMPLEMENTED — #562, ADR-0023 v2 ratified 2026-07-02)

The long-reserved context columns (18–20) are filled **host-side at log-write time** by the logger's
`ContextFiller` (`tools/logger/context_fill.py`), from the `plants.env` rows streaming through the same
session. Firmware is unaffected. The columns hold values; the **provenance tags ride `payload` k=v**
(`context_source`, `pressure_context_source`) — never new positional columns, so the shared core
(cols 1–21, 23) stays byte-identical with the sibling AQ project.

### 12.1 Two families, fenced (ADR-0023 v2)

Interior ambient (`temp_context_c`, `rh_context_pct`) fills **only** from the two proximity classes:

| Class | Meaning | `context_source` values today |
|---|---|---|
| `plant_local` | in the plant's own microclimate | `sht45_onrig` |
| `room` | smart-home ambient for the room (seam; integrations are #563) | `zigbee_room`, `thread_room`, `matter_room`, `ecobee`, `ha_ambient` |

- **The `plant_local` boundary** (the placement rule, per maintainer 2026-07-02): if the sensor shares
  the plant's shelf/rig — moving the plant would mean moving the sensor — it is plant-local; if it
  measures the room the plant happens to be in, it is room-class. The current rig's SHT45 at
  `breadboard_near_esp32` is plant-local.
- Exactly **one** source fills a row's interior columns (plant-local beats room; freshest within the
  class; never a blend). Nothing fresh → columns stay honestly empty.
- **A weather feed never fills interior temp/RH** — enforced structurally (the filler refuses an
  exterior class in its interior source map) and pinned by test.
- **ESP32 die temp never fills any context column** — excluded by identity *before* the source map is
  consulted (so even a misconfigured map can't admit it); pinned by test.
- A context value never travels without its tag; the tag resolves deterministically to its class via
  `parse_v1.context_class()`.

### 12.2 The pressure exception (ADR-0023 §3)

`pressure_context_hpa` **may** fill from the exterior family (indoor pressure tracks outdoor), tagged
with its own per-quantity `pressure_context_source` (e.g. `weather_openmeteo`) — per-quantity because
mixed-source rows are the common case (the SHT45 has no pressure). **Live wiring (#567):** the value
comes from Open-Meteo's *forecast* endpoint (`current=surface_pressure`) via a rolling
current-conditions cache (`reports/weather/pressure_current.json`, gitignored — deliberately not the
archive layer's immutable dated evidence). The dashboard's env path refreshes it opportunistically
(hourly cadence); both fill spines — the serial logger's `ContextFiller` and the untethered
`DeviceAdapter` — only ever **read** the cache, so no log loop or request poll can block on a socket.
Staleness bound: a value older than 3 h never fills (synoptic pressure moves ~<1 hPa/h, so the
indoor≈outdoor claim stays honest to a few hPa); offline, the cache ages out and fills stop —
columns stay honestly empty (R9). The archive ingestion (#367) also fetches `surface_pressure` now
for analysis-time joins; older cached windows simply lack the field (never refetched).

---

## 13. Schema v4 (LIVE — #739, one bundled wire revision)

The data-contract rule (#739): a wire change ships **together, in one revision** — one `schema_version`
bump, one `parse_v1` extension, one `TELEMETRY_SCHEMA.md` rev, one fleet reflash. v4 is that bundle.
**Trellis-ratified** against ADR-0006/0018/0021/0025/0027 and the companion shared-core binding; the
load-bearing check holds — **v4 adds zero `CANONICAL_COLUMNS` positional columns**, so the byte-identical
shared core with the companion air-quality project is preserved. Everything below rides `payload` k=v or a
`#` header line.

### 13.1 `config_id` — config provenance (#576, ADR-0025)

A **stable FNV-1a-32 fingerprint (8 lowercase hex)** of the active config snapshot — ADC resolution/atten,
`SAMPLES_PER_READ`/`SAMPLES_TRIM`/`ADC_DISCARD`, deadband, confirm windows, spread bound, sample cadence,
sensor pins, the **live** per-channel cal bounds, and (env build only) the I²C clock + AS7263 gain/itime.

- **Firmware-computed** — several inputs (trim, discard, I²C addrs) are firmware constants the host never
  sees, so only the board can honestly hash them. `parse_v1` **reads** the emitted id; it never re-derives
  (it may optionally re-hash the visible `# cfg:` fields as a *diagnostic*, never as the source of truth).
- **Two surfaces:** header-authoritative `# config_id=<hex>` line + a per-row `payload` `config_id=<hex>`
  ref on every soil **and** env row (a lone row stays self-interpreting — the #155 flatten, a pasted bug
  report, a store-and-forward replay all keep it). Same-`config_id` ⇒ directly comparable; a change ⇒ a
  machine-detectable comparability boundary + the no-auto-adjust alarm (ADR-0025). Subsumes the schema-v2
  `cal_profile_version` (#300) — a re-cal rolls `config_id` automatically.
- **v1 scope:** computed once at boot after cal load; a *runtime* cal/cadence retune does not yet re-roll it
  (a follow-on) — set-once-held is the doctrine, so the boot fingerprint is honest.

### 13.2 `rssi` / `uptime_s` / `heap` — board diagnostics (#669)

- `rssi=<dBm>` (negative int) — WiFi signal strength, **connected-only + honest-absent** (ADR-0028): an
  unassociated or serial/tethered row **omits** the key, never a fake `0`. **Only the dBm number** — never
  SSID/BSSID/MAC (privacy fence). Answers placement/drift/interference from the log.
- `uptime_s`, `heap` — seconds since boot and free heap, on **every** soil row (transport-independent).
- **Cadence:** every row (the implementers' call, #669 mandates none) — cheap vs. the 30 s soil cadence.

### 13.3 `SENSOR_FAULT` + `fault=` — physically-impossible readings (#670)

A capacitive probe **cannot** read below its physical wet rail; a sub-rail raw is a fault, not moisture.
See §4 for the enum value + the mapping table. Firmware self-declares from the **per-board `wet_rail_raw`**
(ADR-0019 descriptor; classic 900, below the #248 saturated anchors; unverified boards carry the classic
placeholder until #443). The coarse `SENSOR_FAULT` token rides `quality_flag`; the specific reason
(`stuck_wet` | `dead_adc`) rides `payload` `fault=`. **Raw is preserved (ADR-0006).** Firmware's wire flag =
the physical-impossibility call; the host-side derived *remediation* gate (what to do about it) is separate,
lives at the parse boundary, and tunes without a reflash (the #652 two-thresholds-two-homes split).
