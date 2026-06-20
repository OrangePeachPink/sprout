# plants

Capacitive soil-moisture sensing plus small-pump automatic watering — a beginner-friendly
embedded project built around a UMLIFE 4-sensor / 4-pump / relay / tubing kit. The goal is a
small multi-plant auto-waterer that reads soil moisture, decides when to water, and runs the
pumps through a relay, with room to grow toward logging and remote monitoring.

**Status — 2026-06-20:** Sensor QA complete. All four capacitive sensors pass the known-defect
checks and are cleared for use as-is. Microcontroller selected: **ESP32** (classic, SoC marked `ESP-32D`). Relay board identified (`CW-022`, opto-isolated, active-LOW). Build bring-up next.

## Hardware

| Part | Qty | Notes |
| --- | --- | --- |
| Capacitive soil moisture sensor | 4 | Board `HW-390`, silk "Capacitive Soil Moisture Sensor V2.0.0". 3.3-5.5 V in, **0-3.0 V analog out**, 3-pin PH2.0. QA passed - see [`SENSOR_QA.md`](SENSOR_QA.md). |
| Mini submersible DC water pump | 4 | DC 2.5-6 V (rated ~3 / 4.5 V), ~0.18 A, ~100 L/h, submersible. **DC only - never mains.** |
| 4-channel relay module | 1 | 5 V module. Active-high vs active-low and 3.3 V-drive compatibility **to be bench-verified.** |
| PVC vinyl tubing | ~4 m | ID ~5.54 mm / OD ~8.20 mm. |
| Microcontroller | 1 | **ESP32** (classic dual-core; SoC marked `ESP-32D`, ESP32-D0WD class) from the SunFounder ESP32 kit. 3.3 V ADC matches the 0-3.0 V sensor output; 4 sensors on ADC1 (avoid ADC2 = WiFi); WiFi/BT for monitoring. |

(Kit provenance is recorded in the local `parts` inventory: UMLIFE watering kit. The SunFounder ESP32 kit also bundled a 5th capacitive sensor - an `NE555`-based `v1.2` variant - which is **not used** for this project; see `SENSOR_QA.md`.)

## Documentation

| Doc | What it is |
| --- | --- |
| [`SENSOR_QA.md`](SENSOR_QA.md) | Bench QA of the four capacitive sensors against the three known board defects: method, readings, verdict. |
| [`docs/RESEARCH_capacitive_soil_moisture_sensors.md`](docs/RESEARCH_capacitive_soil_moisture_sensors.md) | Foundational research: how these sensors work, every known defect + workaround, diagnosis, buying guidance, and an annotated source index (incl. code-example links). |
| [`docs/WIRING.md`](docs/WIRING.md) | Power + wiring architecture: single-supply baseline, connection map, candidate pin map, protection parts, and escalation path. |
| [`docs/evidence/`](docs/evidence/) | Macro board photos used as QA evidence. |

## Firmware (PlatformIO)

Firmware lives in [`firmware/`](firmware/) as a PlatformIO project (ESP32, Arduino framework).
Open the `firmware/` folder in VS Code with the PlatformIO IDE extension, or use the CLI from that
folder:

- Build: `pio run`
- Upload: `pio run -t upload`
- Monitor: `pio device monitor` (115200 baud)

Board env is `esp32dev` (classic ESP32). Pin assignments and tunables live in
`firmware/include/config.h`. The build cache and resolved libraries (`firmware/.pio/`) are git-ignored.

## Roadmap

- [x] Research the sensor class and its known defects
- [x] Inspect + meter all four sensors (QA passed - use as-is)
- [x] Lock the microcontroller - **ESP32** (classic, `ESP-32D`)
- [ ] Waterproof + calibrate the sensors
- [ ] Bench-verify the relay module (polarity, 3.3 V drive)
- [ ] Wire one sensor + one pump (single-channel bring-up)
- [ ] Scale to 4 channels + watering logic
- [ ] (Stretch) logging / remote monitoring

## Conventions

Private project repo. Text files use LF line endings (see `.gitattributes` / `.editorconfig`).
Secrets (e.g. WiFi credentials) must stay out of version control - see `.gitignore`.
