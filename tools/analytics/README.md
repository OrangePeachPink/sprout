# Analytics

Host-side data tooling for the plants telemetry: parsing, analysis, and dashboards. This directory
reads the captured logs; it does **not** produce them — the firmware emits the device line and
`tools/logger/` writes the canonical CSV. Data flows one way: `firmware` → `logger` → `logs/` → here.

Backlog lane (see [`../../BACKLOG.md`](../../BACKLOG.md) section E):

| Item | What | Status |
| --- | --- | --- |
| E6 | Schema-v1 log parser (`parse_v1.py`) | done |
| E7 | 4-channel dashboard, static self-contained (`dashboard.py` + template) | done |
| E1 | Live-serving dashboard + Refresh / Auto (`serve.py`) | done — monitoring slice |
| E3 | Forecast engine + single-plant detail view (`forecast.py`) | done |
| E8 | Full-history join (logs + B8 archive), time-range views, recency (`serve.py` + dashboard) | done |
| E9 | Logging-gap visibility — line breaks + shaded span, quality-strip marks, integrity list | done |
| E10 | Per-channel on/off toggles + sub-day zoom ranges (1h/3h/12h) | done |
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

## `dashboard.py` — 4-channel dashboard (E7)

Renders a **single self-contained HTML dashboard** from the v1 logs, styled with the Sprout design
system (`../../docs/design/`). Chart.js is vendored (`vendor/chart.umd.min.js`) and inlined, so the
output opens offline with no network — one file you can double-click.

```text
python tools/analytics/dashboard.py                  # all logs/ -> reports/plants_dashboard.html
python tools/analytics/dashboard.py logs/ -o out.html
python tools/analytics/dashboard.py docs/sample_log.csv
```

Output lands in `reports/` (gitignored — derived and rebuildable from the logs, never tracked).

Panels: per-channel summary cards (raw + band pill + mood), the Sprout calibration range-ladder with
each probe's live position, the overlaid raw trajectory (7-band shading behind it), cross-channel
spread (the C1 pin/placement variance), per-channel distribution, a `quality_flag` heat-strip, and a
data-integrity grid that surfaces dropped/partial sweeps and session boundaries instead of hiding them.
Logging **interruptions** (a board reset, a logger restart) are surfaced three ways (E9): a break +
shaded span on the trajectory and spread charts, a hatched mark on the `quality_flag` strip, and an
explicit gap list (start + duration) in the integrity grid — a sample-to-sample delta over
`GAP_THRESHOLD_S` (120 s) counts as a gap.

Honesty rules, enforced in the generator:

- the legacy moist% `value` is never plotted — raw + band only (B2/C2);
- the 7-band boundaries are labelled **proposed**, not validated (A2);
- day/night shading is omitted — it needs the real light schedule, which is not in the data; overall
  drying slope is shown instead.

`vendor/chart.umd.min.js` is Chart.js v4.4.3 (MIT), vendored so the dashboard is offline and
self-contained. Delete it and the generator falls back to a CDN `<script>` tag.

### Single-plant view (E3)

Click any channel card to drill into a focused single-plant view (powered by `forecast.py`): the
current raw + band with a **headroom gauge** (distance to the next band and to the thirsty threshold),
a trajectory chart with a **least-squares trend line**, **forecast cards** (time-to-next-band,
time-to-thirsty, diurnal / next-day), a per-window **drying-rate table** (1h/6h/24h/all with se + R²),
a band-history ribbon, and per-window stats. Every forecast is **gated** — it shows *"no estimate yet"*
with the reason until drying is statistically real, instead of inventing an ETA. Back to the overview
with **← all channels**. The standalone CLI (`python tools/analytics/forecast.py [-s s3]`) prints the
same analysis to the terminal.

### Live mode (`serve.py`)

The static file is a point-in-time snapshot. For a view that tracks the logger as it appends, serve
it instead:

```text
python tools/analytics/serve.py            # serve repo logs/ at http://127.0.0.1:8765
python tools/analytics/serve.py logs/ -p 8000
```

`serve.py` serves the dashboard at `/` plus a `/data.json` endpoint that re-parses the logs fresh on
each request. The page's **↻ Refresh** button (and the **auto** toggle, ~30 s) pull `/data.json` and
re-render in place — no full reload, scroll and theme preserved. Opened as a bare file it detects
`file://` and stays a static snapshot (Refresh shows a "run serve.py" hint). It is read-only — it
never writes the logs. This is the live-monitoring slice of backlog **E1**.

### History & time ranges (E8)

`serve.py` reads the live `logs/*.csv` **and** the B8 gzip archive
(`.data-worktree/data/archive/*.csv.gz`), de-duped by segment (the live `.csv` wins), so history
survives once closed segments are pruned from `logs/`. A **time-range selector** — 1 h / 3 h / 12 h /
24 h / 7 d / 30 d / all, default 24 h — windows the view: served, it re-fetches `/data.json?range=…`
so the stat / rate / forecast panels recompute for the span; opened as a file it zooms the chart
client-side. Long ranges
are downsampled to ~2 k points per series so 30 days stays responsive — the panels always consume the
full windowed data, only the plotted points thin. The header shows a **"last reading N min ago"**
recency cue (amber if the capture stalls), and a B5 reset reads as a labelled session gap rather than
missing data.

**Per-channel on/off (E10).** The header chips toggle each probe individually as a comparison lens
(e.g. "everything without s2," the high-offset outlier). Served, it re-fetches `?channels=…` so the
cross-channel **spread recomputes** over the selected probes (s1/s3/s4 vs all four), the distribution
re-fits, and the stats follow; as a static file it hides the lines + bars (its spread stays 4-channel).
Colours are stable per sensor id so they don't shuffle when a channel is excluded.

## Experiment Lab Notebook (`/lab`, epic #153)

The **read/review** side of Experiment Capture — see, analyse, and keep a living log of your
experiments. Captures land in gitignored `experiments/<id>/` (a CSV + `manifest.json`); these tools
turn them into a reviewable record. Served by `serve.py`; the store + calibration also run from the CLI.

### Catalog + detail (`experiments_catalog.py`, `lab_detail.py`)

```text
http://127.0.0.1:8765/lab                     # catalog — every capture: title / date / duration / samples
http://127.0.0.1:8765/lab/<experiment_id>     # one capture: per-probe stats + an inline-SVG trajectory
http://127.0.0.1:8765/lab/experiments.json    # the catalog as JSON
```

Read-only — the catalog reads each `manifest.json` (no CSV re-parse to list); the detail view reuses
`build_context` for the per-probe stats. A running capture also charts itself live in the dashboard's
capture panel (`/capture/status` carries the live `trace`).

### Analysis store (`analysis_store.py`) — the DuckDB tier

A derived, **rebuildable** columnar store (`reports/plants.duckdb`, gitignored) over the captures:
`readings` (every probe-sample + a calendar layer — month / hour / season / is_daylight) and
`experiment_features` (one engineered row per experiment × probe — n / median / min-max / spread /
slope-per-hour / band / quality).

```text
python tools/analytics/analysis_store.py                                # (re)build + a summary
python tools/analytics/analysis_store.py --query "SELECT * FROM experiment_features"
```

Derived + gitignored + rebuilt fresh from raw each run — **never the source of truth**.

### Calibration workbench (`calibration.py`)

Proposes refined band boundaries from captured experiments and exports a candidate config for the
Data↔Firmware **A2 handshake** (the dashboard ladder is "placeholders pending A2"):

```text
python tools/analytics/calibration.py            # propose + print per-band centres + boundaries
python tools/analytics/calibration.py --export   # write reports/calibration_candidate.json
```

It **proposes from evidence; firmware ratifies** — never authoritative alone. Needs experiments
spanning several states (the common-cup wet/dry/air-dry characterization) — one band can't define a
boundary.

## The `value` column is the legacy moist% — do not analyse on it (B2 / C2)

Every row carries `value`/`unit` (e.g. `value=83, unit=pct`). That is the legacy linear map
`(3400 − raw) / (3400 − 900)` — it *looks* authoritative but is **not** VWC and must not drive
analysis. The reader carries it through unchanged (raw is immutable; nothing is hidden) but surfaces
`raw_value` + `band` as the truth, and names it `value_legacy_pct` in the DataFrame to discourage
misuse. **Analyse on `raw_value` + `band`, never on `value`.**

Producer-side, this is the firmware agent's call (the device emits `value`): the recommendation is to
drop the misleading percentage — emit the band index, leave it null until a real calibration exists,
or keep it only if explicitly documented as the legacy index. Flagged for that lane; not changed here.
