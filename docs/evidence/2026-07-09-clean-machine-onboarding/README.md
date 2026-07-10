# Clean-machine onboarding — Sprout on a fresh Windows 11 box (2026-07-09)

Point-in-time evidence, **not current instructions.** Captured on **valley-of-steel**
(a bare Windows 11 install) while standing Sprout up from scratch and reflashing the
deployed fleet in place. That box has no push path to this repo, so the raw log was
shuttled in by hand and is preserved verbatim in
[`sprout-setup-log.md`](sprout-setup-log.md) (lint-disabled — it's a captured artifact,
not repo prose).

## What it validated

- **The quick-start runs on a genuinely clean Windows box** — dashboard live at
  `http://127.0.0.1:8765` with nothing plugged in — but a fresh user hits **five gaps**
  the README/justfile don't yet cover (see the table).
- **The deployed fleet was reflashed to v4 and OTA-proven from this same box** — both
  boards (`y9d41p` classic, `8gtt1h` official C5) now emit the v4 bundle; see the #739
  rollout comment.

## Gaps found and where they're tracked

| Finding | Status |
| --- | --- |
| CP210x driver not auto-installed on fresh Win11 (classic won't enumerate a COM port) | #889 (`for:dx`) |
| First `pio run` fails at the pioarduino penv bootstrap; a retry succeeds | #890 (`for:dx`) |
| Stale `platformio.ini` C5 "do-not-flash" comment (contradicts `board_capability.h`) | PR #891 (fixed) |
| Blank first-run screen / no in-dashboard device onboarding | #875 (Voice UI epic) |
| Five quick-start gaps (`&&` on PS 5.1, no inline `uv`/`just`, `just` needs `sh`) | log §Findings — for DX |

## Provenance

- Machine: **valley-of-steel** (fresh Windows 11, admin account)
- Session: firmware bench thread `98a32080`, 2026-07-09
- Delivered via the maintainer's dev box (valley-of-steel has no repo push path)
- The log's "RESUME HERE" / "BLOCKERS" sections are **historical** — every blocker is
  resolved (both boards flashed, dashboard live). Kept verbatim as a record, not a to-do.

— Firmware 🔧
