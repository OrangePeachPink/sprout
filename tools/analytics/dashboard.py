"""4-channel soil-moisture dashboard generator (backlog E7).

Reads schema-v1 logs via ``parse_v1`` (E6) and renders a single self-contained
HTML dashboard styled with the Sprout design system (``docs/design/``). It
injects a JSON context + the inlined Sprout tokens into
``dashboard_template.html``.

Reading rules baked in (#1039 canon):

* **raw + band = the reading.** The legacy moist% ``value`` column is never
  plotted (B2/C2).
* **bands are the ratified seven-in-soil ladder.** Endpoints from the
  common-cup anchors; interior boundaries measured + ratified per board class
  (#995 -> #1218/#1220, ADR-0035). Per-channel cal remains the #170 tail.
* **no fabricated light cycle.** Day/night shading (#198) uses the real,
  computed solar geometry (``env_solar``, #365/#366) - never a guessed
  schedule. Absent entirely with no rig location configured (R9).

Usage::

    python tools/analytics/dashboard.py                 # all logs/ -> reports/
    python tools/analytics/dashboard.py logs/ -o out.html
    python tools/analytics/dashboard.py docs/sample_log.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.parse_v1 import (  # noqa: E402  (needs _HERE on sys.path first)
    LogData,
)
from tools.analytics.source_adapter import (  # noqa: E402  (the source-adapter seam, #277)
    TetheredAdapter,
)

_REPO = _HERE.parents[1]


# #1336 (ADR-0038 §5.1): these live in the layer-0 `design_assets` leaf now. Four
# modules used to import THIS ~2,000-line module to obtain them; three wanted nothing
# else. Re-exported here so dashboard's own readers are unaffected — the leaf is the
# definition, this is a name.
# Brand fonts are base64-embedded (latin subsets, SIL OFL) so the dashboard renders
# in-brand fully offline - no Google-Fonts CDN. Vendored beside Chart.js;
# regenerate via tools/analytics/embed_fonts.py.
# #1336 (ADR-0038 §5.3): the card-payload cluster lives in the layer-3
# `card_context` module now — the 1,700-line composition step that decides what
# the surfaces are told, moved out of this delivery module whole. Re-exported here
# so the 36 test files and 138 call sites that pin this path are unaffected;
# card_context is the definition, these are names.
from tools.analytics.card_context import (  # noqa: E402,F401  (layer-3 composition)
    BAND_UI,
    FORECAST_BOUND_MIN_READINGS,
    FORECAST_INPUT_H,
    GAP_THRESHOLD_S,
    MOOD_BY_BAND,
    RETIRE_AFTER_H,
    SESSIONS_SHOWN,
    STALE_AFTER_S,
    TRAJ_GAP_BOUNDARY_H,
    _channel_idx,
    _fw_masthead,
    _locator,
    _night_bands,
    _recent_run_start,
    _rssi_band,
    _ver_tuple,
    _versions_block,
    _weather_hourly_join,
    build_context,
    build_env_context,
)
from tools.analytics.design_assets import (  # noqa: E402  (layer-0 leaf)
    FONTS_CSS,
    TOKENS_CSS,
)

TEMPLATE = _HERE / "dashboard_template.html"
# #875: the Home surface (the Sprout Voice UI's landing page). A pure shell —
# tokens/fonts injected here, data hydrated client-side from /cards.json — so
# serving it never runs the analytics pipeline (the #1018 fast-shell rule).
HOME_TEMPLATE = _HERE / "home_template.html"
TRIAL_TEMPLATE = _HERE / "trial_template.html"  # #1148 the evaluation surfaces
DEFAULT_OUT = _REPO / "reports" / "plants_dashboard.html"
# Vendored Chart.js -> inlined for a self-contained, offline dashboard. Falls
# back to CDN only if the vendored copy is missing.
VENDOR_CHARTJS = _HERE / "vendor" / "chart.umd.min.js"
CDN_CHARTJS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"
# #1336 (ADR-0038 §5.1): the data paths live in the layer-0 `host_paths` leaf now —
# serve.py imported THIS module for exactly these two constants. Re-exported here so
# dashboard's own readers are unaffected; the leaf is the definition, this is a name.
from tools.analytics.host_paths import (  # noqa: E402  (layer-0 leaf)
    ARCHIVE_DIR,
    LOGS_DIR,
)

# Time-range windows (E8). None = all history.
RANGE_HOURS: dict[str, float | None] = {
    "1h": 1.0,
    "3h": 3.0,
    "12h": 12.0,
    "24h": 24.0,
    "48h": 48.0,  # #821: between 1 day and 7 days — same windowing as every chip
    "7d": 24.0 * 7,
    # #1191: the sawtooth-finder window (maintainer ask). Watering cycles run 8-10+
    # days, so 7d often just misses the last-watering edge and 30d is the slow build
    # (#1134). A maintainer-ruled bridge on parity-then-retire Classic (ADR-0033) until
    # the rollup tier lands. Fast now the fit windows are segment-bound (#1157/#1162).
    "14d": 24.0 * 14,
    "30d": 24.0 * 30,
    "all": None,
}


# --------------------------------------------------------------------------- #
# inputs, windowing, downsampling (E8)
# --------------------------------------------------------------------------- #
def gather_inputs() -> list[str]:
    """Live logs/ + the B8 gz archive, de-duped by segment stem (live wins)."""
    files: dict[str, Path] = {}
    if ARCHIVE_DIR.is_dir():
        for p in ARCHIVE_DIR.glob("*.csv.gz"):
            files[p.name[:-7]] = p  # strip ".csv.gz"
    if LOGS_DIR.is_dir():
        for p in LOGS_DIR.glob("*.csv"):
            files[p.name[:-4]] = p  # ".csv" live copy overrides the archived .gz
    return [str(p) for _, p in sorted(files.items())]  # stem sort = chronological


def filter_since(data: LogData, hours: float | None) -> LogData:
    """Return a LogData windowed to the last `hours` of data (None = unchanged)."""
    if hours is None:
        return data
    times = [r.timestamp_utc for r in data.readings if r.timestamp_utc]
    if not times:
        return data
    cutoff = max(times) - timedelta(hours=hours)
    kept = [r for r in data.readings if r.timestamp_utc and r.timestamp_utc >= cutoff]
    return LogData(readings=kept, segments=data.segments, sources=data.sources)


def filter_channels(
    data: LogData, channels: list[str] | None, canonical=None
) -> LogData:
    """Keep only readings for the given sensor ids (None / empty = all) (E10).
    ``canonical`` (#602): an optional device_id -> canonical-id mapping (the
    registry's ``canonical_for``) so device-scoped tokens keep matching a
    board's whole history across renames; None = identity (v1 behavior).

    #583 (the FENCE rule): a token may be a plain sensor id (``s1`` - matches
    that channel on every device, the single-device case unchanged) or a
    device-scoped ``s1@<device_id>`` composite, matching exactly one device's
    channel - two devices' ``s1`` are different plants and must be
    independently toggleable."""
    if not channels:
        return data
    plain = {c for c in channels if "@" not in c}
    scoped = {tuple(c.split("@", 1)) for c in channels if "@" in c}
    # #602: scoped tokens carry the CANONICAL id (the card key), so a row from a
    # prior identity must match through the same coalesce the grouping uses.
    canon = canonical or (lambda d: d)
    kept = [
        r
        for r in data.readings
        if r.sensor_id in plain or (r.sensor_id, canon(r.device_id)) in scoped
    ]
    return LogData(readings=kept, segments=data.segments, sources=data.sources)


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def render_home() -> str:
    """#875: the Home shell — the same token/font injection as the Workbench shell,
    no context blob (the page hydrates itself from ``/cards.json``). Kept beside
    ``render()`` so the two surfaces can never drift on how brand CSS arrives."""
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    template = HOME_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)


def render_trial() -> str:
    """#1148: the evaluation-surface shell (the /trial route). Same token/font
    injection as Home and the Workbench — no context blob; the page hydrates from
    ``/data.json`` + ``/cards.json``. The three candidates live here, off the Home,
    until her keep/prune verdicts land."""
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    template = TRIAL_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)


def render(ctx: dict) -> str:
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    template = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(ctx, separators=(",", ":"), ensure_ascii=False)
    if VENDOR_CHARTJS.exists():
        lib = VENDOR_CHARTJS.read_text(encoding="utf-8").replace(
            "</script>", "<\\/script>"
        )
        chart_tag = f"<script>\n{lib}\n</script>"
    else:
        chart_tag = f'<script src="{CDN_CHARTJS}"></script>'
    html = template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)
    html = html.replace('"__DASH_JSON__"', blob)
    html = html.replace("<!--__CHARTJS__-->", chart_tag)
    return html


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the 4-channel dashboard.")
    ap.add_argument(
        "inputs",
        nargs="*",
        help="log files / dirs / globs (default: repo logs/)",
    )
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="output HTML path")
    args = ap.parse_args(argv)

    inputs = args.inputs or gather_inputs()
    # #277: reads through the source-adapter seam - TetheredAdapter today, a future
    # device-served adapter (#276) later, with no change to this call site. Inputs
    # are resolved up front (not left to the adapter's own discovery) so the error
    # message below still names exactly which files were checked.
    data = TetheredAdapter().load(inputs)
    if not data.readings:
        print("no readings parsed from:", inputs, file=sys.stderr)
        return 1

    ctx = build_context(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(ctx), encoding="utf-8", newline="\n")

    s = ctx["sensors"]
    print(f"wrote {out}")
    print(
        f"  {ctx['integrity']['total']} readings | "
        f"{ctx['integrity']['sweeps']} sweeps | "
        f"{len(s)} sensors | gap={ctx['integrity']['count_gap']} rows | "
        f"cadence~{ctx['integrity']['cadence_actual_s']}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
