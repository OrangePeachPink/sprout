# Untethered WiFi evidence run sheet

**One execution-ordered sheet for the remaining Wave-1 WiFi captures** — the S3 is already on
the network (evidence: [`docs/evidence/2026-07-03-esp32-s3-bringup-wifi/`](../evidence/2026-07-03-esp32-s3-bringup-wifi/README.md),
PR #568); this sheet finishes its captures and takes both C5 boards through their first WiFi
session. Companion to the [S3/C5 bring-up run sheet](s3-c5-bringup-run-sheet.md), whose
identity/flash portion (§1–§2) is complete for all three boards.

Refs #443 · epic #267 · #276 · #21 · #277 · #486 — precedent: #275/#278 closed via #568.

## Privacy rules (before anything leaves the bench)

Everything below lands raw in **your local bench packet (outside the repo)** first. Only
curated, redacted evidence enters the repo — Workflow packages it (same pattern as #568).

- **Never in repo evidence:** home SSID, WiFi password, MAC addresses (including the EUI-64
  `..ff:fe..` form), USB instance IDs/serial strings, host/machine names, router admin pages,
  DHCP client lists (they show *other* devices).
- **Setup-AP name:** the suffix is MAC-derived — write it as `Sprout-Setup-XXXX` in repo docs.
- **Private LAN IPs (`192.168.x.x` etc.) are OK** in repo evidence — RFC1918 addresses
  identify subnet numbering, not you or your network. The router page you *read* the IP from
  is not OK to capture.
- **Prefer text captures over screenshots** — `curl` output is verbatim, grep-able, and has
  nothing to crop. If you do screenshot (dashboard card, phone portal), crop to the app/page
  content and strip EXIF before packaging.
- If DX's identifier-guard tooling (#558) has landed, run it over the curated set; otherwise
  Workflow hand-greps per the standing checklist during packaging.

## §0 Pre-session (5 minutes, at the desk)

- [ ] `git pull` on main — pick up anything the night shift landed.
- [ ] **Read the latest comments on #443** — Firmware's overnight task was C5 pin-map
      candidates + flash gotchas (including any 4 MB-flash note for the yellow clone). What
      they posted may adjust §2's order; it does not block it.
- [ ] Check #558 — if the guard tool merged, note the command for packaging time.
- [ ] Have the local bench packet folder open for raw captures.

## §1 S3 captures (first — the board is already online)

The S3 rejoins on power-up with stored credentials; no portal step needed unless you run the
§1.6 encore.

- [ ] **1. Find the S3's LAN IP.** The firmware does not print it on serial (the `# net:` line
      is state+creds only — the IP appears only in the `GET /` body, which needs the IP;
      follow-on filed for Firmware). Two paths:
  - Router's connected-clients list — *read* the IP off it; capture nothing from that page.
  - Or from the PC: `arp -a` and look for a new device on your subnet (Espressif OUI).
- [ ] **2. Capture `GET /`:** `curl http://<ip>/` → save verbatim text. Expected shape (from
      `handleRoot`): `Sprout <device_id>` / `fw= git= board=` / `wifi=connected ip=` /
      `uptime_ms=` then one `ch<N>: level= raw= quality=` line per channel.
- [ ] **3. Capture `GET /telemetry`:** `curl http://<ip>/telemetry` → save verbatim. Verify
      the payload is schema-shaped (k=v pairs, `schema_version`, `time_source=device_synced`
      riding the rows).
      **Honesty caveat:** no sensors are wired and the S3 pin map is provisional — the *values*
      are floating-pin noise; the *shape*, band, and quality flag are the evidence.
- [ ] **4. Resilience poke (#21):** with the serial monitor attached
      (`pio device monitor -p COM13 -b 19200`), press RST. Capture the boot banner reprinting
      and the board rejoining on its own — `# net: state=connected creds=set` with **no portal
      appearing**. That sequence is the evidence.
- [ ] **5. Dashboard over WiFi (#277 + #486):** copy `config/devices.example.json` →
      `config/devices.local.json` (gitignored) if you haven't; in the S3 entry set
      `"base_url": "http://<ip>"`. Launch Sprout the normal way (your launcher — no terminal).
      Capture the S3's card rendering untethered data (screenshot, cropped to the app).
- [ ] **6. Optional portal encore** (#275 is already closed — only if you want the clean
      repeat): send `!wifi` bare on serial → ack `# ack wifi cleared` → `Sprout-Setup-XXXX`
      rises again → rejoin from the phone → credentials → connected. Capture the serial
      sequence if you run it.

## §2 C5 first WiFi (per variant — official first unless #443 says otherwise)

**Flash decision, stated honestly:** `platformio.ini`'s do-not-flash-C5 guard protects
*wiring* sessions — a wrong pin map matters when sensors/relays are physically attached.
Nothing is wired in this session, which is exactly how the S3 session ran on equally
provisional pins (#568). Flashing for WiFi-only evidence is consistent with that precedent;
the guard stays in force for any session that wires hardware. Read Firmware's overnight #443
comment before starting in case it changes this picture.

Per board — official C5 on **COM11** (CP210x bridge), yellow C5 on **COM10** (CH340 bridge);
native-USB ports (COM12 / COM9) are the fallback path:

- [ ] **1. Flash:** `pio run -d firmware -e esp32c5 -t upload --upload-port <COMx>`.
      **Yellow clone is 4 MB** (official is 8 MB): if the upload fails on flash size or
      partition table, stop and comment the exact error on #443 — do not improvise build
      flags at the bench.
- [ ] **2. Monitor:** `pio device monitor -p <COMx> -b 19200`. Capture verbatim:
  - boot banner — the first-ever C5 `# board:` line (`esp32-c5  wifi=yes  channels=…`)
  - `# net: state=idle creds=unset`
  - portal AP appearing (record as `Sprout-Setup-XXXX`)
- [ ] **3. Onboard from the phone:** join the setup AP → enter home WiFi credentials in the
      portal → portal reports success and the setup SSID disappears. Watch serial for
      `# portal: down`, then `# net: state=connected creds=set`, then
      `# time: source=device_synced` once NTP answers.
- [ ] **4. Captures:** same as §1 — find the IP, `curl` both `GET /` and `GET /telemetry`,
      save verbatim.
- [ ] **5. Reset behavior:** RST → banner reprints + auto-rejoin without portal (feeds the
      bring-up sheet's §3 checklist and #21).
- [ ] **6. Yellow only — thermal note:** record how warm the board runs during the session
      (flagged for observation in the bench packet).

## §3 Handoff to packaging

- [ ] All raw captures (serial text, curl output, photos/screenshots) go into the local
      packet, never straight into the repo.
- [ ] Ping Workflow with the packet location — curation, redaction, EXIF strip, evidence
      README, and the PR follow the #568 pattern (`docs/evidence/<session-date>-esp32-c5-…/`).

## §4 Not this session (do not mix — per your own packet's rule)

- **#476 sensor QA** (fresh capacitive batches + resistive trial) — its own sitting.
- **Continuity metering** — boards unpowered, separate block, per the bring-up sheet §1.
- **Classic re-qualification** — bring-up sheet §5, only if #283 lands.
- **#271 web-flasher** — not built yet; nothing to bench.
- **Any relay/pump wiring** — nothing actuates in a WiFi-evidence session.

## What each capture advances

| Capture | Issue | Effect |
| --- | --- | --- |
| §1.2 + §1.3 (`/` + `/telemetry` verbatim) | #276 | Both endpoint ACs demonstrated. **Decision at gate time:** accept the unwired-noise reading as the "live reading + band" demo (shape + band + quality flag are real), or hold #276 open until one real sensor sits on bench-verified pins. Your call when certifying. |
| §1.4 (RST → auto-rejoin) | #21 | The resilience evidence #21's scaffold portion needs; the fuller #21 scope (auth, control endpoints) stays open. |
| §1.5 (dashboard card) | #277, #486 | #277's "dashboard shows untethered-device data, no serial logger" AC — observed e2e. #486 gets its first real multi-source observation for Design. |
| §2 (both C5 sessions) | #443 | C5 WiFi bring-up evidence; pin-map bench-verify still pending Firmware's candidates. |
| §2.5 (reset behavior) | #443 | Fills the bring-up sheet §4 reset row for the C5s. |

— Workflow ⚙️
