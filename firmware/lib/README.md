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
| `pump_pulse` · `dose_control` | **📌 needs Firmware's ruling** | compiled and unit-tested, not consumed by `main.cpp`. ADR-0016 says manual pulse was re-expressed through the irrigation supervisor — if so these are `legacy`, but that is Firmware's call to state, not architecture's to assume |

**`pending` is the category that matters.** Without it, the signing primitive and the OTA gate look
exactly like abandoned code to any dependency analysis, and a future audit deletes the security work.

A non-production status must name its reason and its issue — "legacy" alone restates the problem.
