# plants

Capacitive soil-moisture sensing plus small-pump automatic watering — a beginner-friendly
embedded project built around a UMLIFE 4-sensor / 4-pump / relay / tubing kit. The goal is a
small multi-plant auto-waterer that reads soil moisture, decides when to water, and runs the
pumps through a relay, with room to grow toward logging and remote monitoring.

**Status — 2026-06-20:** Sensor QA complete. All four capacitive sensors pass the known-defect
checks and are cleared for use as-is. Microcontroller selection in progress. Build not yet started.

## Hardware

| Part | Qty | Notes |
| --- | --- | --- |
| Capacitive soil moisture sensor | 4 | Board `HW-390`, silk "Capacitive Soil Moisture Sensor V2.0.0". 3.3-5.5 V in, **0-3.0 V analog out**, 3-pin PH2.0. QA passed - see [`SENSOR_QA.md`](SENSOR_QA.md). |
| Mini submersible DC water pump | 4 | DC 2.5-6 V (rated ~3 / 4.5 V), ~0.18 A, ~100 L/h, submersible. **DC only - never mains.** |
| 4-channel relay module | 1 | 5 V module. Active-high vs active-low and 3.3 V-drive compatibility **to be bench-verified.** |
| PVC vinyl tubing | ~4 m | ID ~5.54 mm / OD ~8.20 mm. |
| Microcontroller | - | **TBD** (ESP32 leaning - 3.3 V ADC matches the 0-3.0 V sensor output; WiFi enables monitoring). |

(Kit provenance is recorded in the local `parts` inventory: UMLIFE watering kit.)

## Documentation

| Doc | What it is |
| --- | --- |
| [`SENSOR_QA.md`](SENSOR_QA.md) | Bench QA of the four capacitive sensors against the three known board defects: method, readings, verdict. |
| [`docs/RESEARCH_capacitive_soil_moisture_sensors.md`](docs/RESEARCH_capacitive_soil_moisture_sensors.md) | Foundational research: how these sensors work, every known defect + workaround, diagnosis, buying guidance, and an annotated source index (incl. code-example links). |
| [`docs/evidence/`](docs/evidence/) | Macro board photos used as QA evidence. |

## Roadmap

- [x] Research the sensor class and its known defects
- [x] Inspect + meter all four sensors (QA passed - use as-is)
- [ ] Lock the microcontroller
- [ ] Waterproof + calibrate the sensors
- [ ] Bench-verify the relay module (polarity, 3.3 V drive)
- [ ] Wire one sensor + one pump (single-channel bring-up)
- [ ] Scale to 4 channels + watering logic
- [ ] (Stretch) logging / remote monitoring

## Conventions

Private project repo. Text files use LF line endings (see `.gitattributes` / `.editorconfig`).
Secrets (e.g. WiFi credentials) must stay out of version control - see `.gitignore`.
