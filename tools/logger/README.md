# plants host logger

Host-side serial capture for the plants controller (firmware **v0.5.0+**). Replaces
`pio device monitor --filter log2file`: it owns the serial port, stamps each row with
host **UTC + local** time and a monotonic `sample_id`, writes a **rotating, self-describing
CSV** under `<repo>/logs/` per the shared schema ([../../docs/TELEMETRY_SCHEMA.md](../../docs/TELEMETRY_SCHEMA.md)),
and prints a terse live console. Auto-reconnects on disconnect; decodes losslessly.

## Requires

- Python 3.x
- `pyserial` — `pip install pyserial`

## Run

```text
python plants_logger.py --port COM5            # Windows
python plants_logger.py --port /dev/ttyUSB0    # Linux / macOS
python plants_logger.py                         # auto-detect the USB-serial port
```

Baud defaults to **19200** (matches the firmware `SERIAL_BAUD`). Output lands in
`<repo>/logs/` as `<device_id>_<YYYYMMDD>_<HHMMSS>.csv` (e.g. `plants_esp32_a4cf12_20260623_140530.csv`), a new file each UTC day,
each re-emitting the device's `#` provenance header so it's independently readable.
Stop with **Ctrl-C**.

## Notes

- Opening the port toggles DTR/RTS and **resets most ESP32 boards** — expect a fresh
  `session_id` and a boot header when you start the logger. Start it at a cycle boundary,
  not mid-capture.
- Lines that can't be re-synced to a known `record_type` are counted and shown as `[drop N]`
  on the console (not written). Corruption to date is prefix-only and ~0%; a per-line CRC
  (backlog B6) is the next step if that ever changes.
- The console is the *human* view; the CSV file is the *dense analysis* view — they
  intentionally differ (the B2 split).
