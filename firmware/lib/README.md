# lib

Project-private libraries live here, each in its own subfolder (for example
`lib/MoistureSensor/` containing `MoistureSensor.h` and `MoistureSensor.cpp`).

PlatformIO compiles and links anything in this folder automatically. External or
published libraries are declared in `platformio.ini` under `lib_deps` instead.

## Status map (ADR-0038 §7)

The import graph cannot tell live code from abandoned code: none of `fw_verify`, `ota_gate`, or
`pump_pulse` is consumed by production `main.cpp`, and only one of those is dead weight. So each
lib declares a status here, and **absence of a row means production**.

| lib | status | why |
| --- | --- | --- |
| `cal_resolver` · `commands` · `device_uid` · `env_sensors` · `irrigation` · `moisture_classifier` · `run_meta` · `serial_cmd` · `telemetry` · `wifi_net` | production | included by `src/main.cpp` |
| `fw_verify` | **pending** | #302 S1 — the ed25519 verify primitive; consumed by `ota_gate` and the pull path |
| `ota_gate` | **pending** | #302 S2 — verify-before-swap; wired when the pull path lands |
| `monocypher` | vendored | third-party, byte-identical to upstream 4.0.3; see its own `README.md` |
| `dose_control` | **pending** | #413 (Epic #410·B) — the ABSORBED vs RAN_THROUGH discrimination the pass-through pulse-soak needs. Built under #414 (closed); #413 is the open consumer that wires it |
| `pump_pulse` | **legacy** | superseded by the irrigation supervisor's operator forced-dose path (`irrigation.h` `forced[]`/`forced_ms[]`, ADR-0016). `!water` routes through `g_irrig` as a forced dose, not through this module. Kept, not deleted, pending the maintainer's word — see the note below |

**`pending` is the category that matters.** Without it, the signing primitive and the OTA gate look
exactly like abandoned code to any dependency analysis, and a future audit deletes the security work.

A non-production status must name its reason and its issue — "legacy" alone restates the problem.

### 📌 Firmware's ruling on `pump_pulse` — and one question it raises

The two split, which is why they could not be ruled together:

- **`dose_control` is `pending`, not legacy.** Nothing superseded it. It is the pass-through
  discrimination (ABSORBED vs RAN_THROUGH) that #413's remediation strategy is specified around —
  built ahead of its consumer, which is exactly the shape §7 introduced `pending` to protect.
- **`pump_pulse` is `legacy`.** Verified rather than assumed: `main.cpp` states that manual
  `!water` is *"a forced dose into g_irrig"*, and `irrigation.h` carries `forced[]` / `forced_ms[]`
  marked *"operator forced-dose pending (ADR-0016)"*. The operator pulse was genuinely
  re-expressed through the supervisor. Architecture's hypothesis was right.

**The question that follows is not a labelling question.** `pump_pulse` is a second, independently
compiled pump driver. ADR-0016 makes the irrigation supervisor the **single actuation authority**,
and the reason is that it structurally enforces two hard invariants a standalone pulse module does
not have. So this module is not inert dead code in the way a superseded parser would be — it is a
latent second path to a pump, sitting in the tree while the first pump has not yet been wired.

**Firmware's recommendation: retire it (delete), not merely label it** — before any relay is wired
(#215/#191), not after. Deletion loses nothing recoverable: the module's real content is its
bounded-pulse *test* coverage, and the supervisor's forced-dose path needs equivalent tests of its
own regardless.

Held rather than done, for two reasons: deleting a module is the maintainer's call, and the
retirement convention is **replace → both live one release → approved deletion**. The replacement
has shipped, so the clock has started; this is the record that it did.
