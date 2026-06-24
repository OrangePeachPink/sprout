# Analytics

Host-side data tooling for the plants telemetry: parsing, analysis, and dashboards. This directory
reads the captured logs; it does **not** produce them — the firmware emits the device line and
`tools/logger/` writes the canonical CSV. Data flows one way: `firmware` → `logger` → `logs/` → here.

Backlog lane (see [`../../BACKLOG.md`](../../BACKLOG.md) section E):

| Item | What | Status |
| --- | --- | --- |
| E6 | Schema-v1 log parser (`parse_v1.py`) | done — this file |
| E7 | 4-channel dashboard + analytics (Sprout-styled) | next |
| E5 | Local parquet / DuckDB analysis tier | deferred until query/ML volume justifies it |

## `parse_v1.py` — schema-v1 reader (E6)

A stdlib-only reader for the `schema_version=1` long/tidy CSV (contract:
[`../../docs/TELEMETRY_SCHEMA.md`](../../docs/TELEMETRY_SCHEMA.md)). It replaces the retired
single-channel scratch parser, which cannot read the new format at all. It handles:

- the per-segment `#` provenance header blocks (re-emitted at every rotation) and the
  `record_type,...` column-name row that follows each;
- the long/tidy layout — one row per sensor per ~30 s sweep, four sensors (`s1..s4`) interleaved;
- `payload` (`level=…;role=…;spread=…;gpio=…`) exploded into fields;
- gzip-compressed archive segments (`*.csv.gz`) from the B8 LFS archive;
- future schema bumps — columns are read **by name** off each segment's header row, so an added or
  reordered column does not break the reader.

### CLI

```text
python tools/analytics/parse_v1.py docs/sample_log.csv   # the committed fixture
python tools/analytics/parse_v1.py logs/                 # every *.csv[.gz] in a dir
python tools/analytics/parse_v1.py                       # newest repo log, auto-found
```

Prints a summary: reading/segment/sweep counts, time span, per-sensor raw min/last/max + band,
`quality_flag` tally, and the latest segment's cal bounds + channel map.

### API

```python
from tools.analytics.parse_v1 import parse_files, band_for_raw

data = parse_files(["logs/"])      # LogData: .readings, .segments, .sources
data.sweeps()                      # group the 4 sensor rows per (session, tick)
data.to_dataframe()                # tidy pandas frame (optional; lazy import)
print(data.summary())

r = data.readings[-1]
r.raw_value, r.band, r.quality_flag, r.spread, r.gpio   # the trustworthy signals
```

`band_for_raw(raw, bounds)` is a naive threshold helper for drawing the band ladder; it ignores the
firmware deadband/hysteresis, so prefer the per-row `Reading.band` (the device-emitted `level`) for
ground truth.

## The `value` column is the legacy moist% — do not analyse on it (B2 / C2)

Every row carries `value`/`unit` (e.g. `value=83, unit=pct`). That is the legacy linear map
`(3400 − raw) / (3400 − 900)` — it *looks* authoritative but is **not** VWC and must not drive
analysis. The reader carries it through unchanged (raw is immutable; nothing is hidden) but surfaces
`raw_value` + `band` as the truth, and names it `value_legacy_pct` in the DataFrame to discourage
misuse. **Analyse on `raw_value` + `band`, never on `value`.**

Producer-side, this is the firmware agent's call (the device emits `value`): the recommendation is to
drop the misleading percentage — emit the band index, leave it null until a real calibration exists,
or keep it only if explicitly documented as the legacy index. Flagged for that lane; not changed here.
