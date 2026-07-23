#!/usr/bin/env python3
"""Experiment detail - the Lab Notebook's single-capture review view (#157).

Opens one capture into review: the manifest facts + per-probe stats (median / range /
slope / band, reusing ``build_context``) + an inline-SVG raw trajectory. Served by
serve.py at ``/lab/<experiment_id>``. Read-only - it never touches the capture.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from tools.analytics.card_context import (
    build_context,
)
from tools.analytics.design_assets import (
    FONTS_CSS,
    TOKENS_CSS,
)
from tools.analytics.experiments_catalog import _fmt_dur, _fmt_when
from tools.analytics.lab_notes import load_notes
from tools.analytics.parse_v1 import parse_files

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_TEMPLATE = _HERE / "lab_detail_template.html"

_EXPERIMENTS = _REPO / "experiments"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from the URL


_INTERVENTION_RE = re.compile(r"@t?\+?(\d+)\s*s?\b\s*[:\-]?\s*(.*)", re.IGNORECASE)


def _parse_interventions(text: str | None) -> list[dict]:
    """Operator interventions from the method notes, no schema change (#325).

    Convention the operator types in the notes, e.g. ``@t+180s shade removed``
    (also ``@180 ...`` / ``@t+180 ...``). Each becomes a vertical marker on the
    chart at that elapsed second. The notes editor (#158) already persists method
    text; a richer entry UI can land with #327."""
    out: list[dict] = []
    for line in (text or "").splitlines():
        m = _INTERVENTION_RE.search(line)
        if not m:
            continue
        label = m.group(2).strip() or "intervention"
        out.append({"t_s": int(m.group(1)), "label": label})
    return out


def _elapsed_label(seconds: float) -> str:
    return f"{seconds:.0f}s" if seconds < 120 else f"{seconds / 60:.1f}m"


def _svg(datasets: list[dict], interventions: list[dict] | None = None) -> str:
    """Per-probe raw trajectory as a measuring instrument (#325): raw-ADC y-axis with
    min/max, elapsed-time x-axis, and operator-intervention markers. Higher raw =
    drier = up. Honest-data law: this is raw ADC + band color, never a moisture %."""
    pts_all = [p for d in datasets for p in d.get("points", [])]
    if not pts_all:
        return (
            '<p class="empty">No trajectory yet — this probe hasn\'t '
            "reported any points.</p>"
        )
    xs = [p["x"] for p in pts_all]
    ys = [p["y"] for p in pts_all]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    xr = (xmax - xmin) or 1.0
    yr = (ymax - ymin) or 1.0
    # padding leaves room for axis labels: left for raw values, bottom for elapsed
    w, h = 760, 250
    padl, padr, padt, padb = 52, 14, 14, 28

    def sx(x: float) -> float:
        return padl + (x - xmin) / xr * (w - padl - padr)

    def sy(y: float) -> float:
        return h - padb - (y - ymin) / yr * (h - padt - padb)

    el = html.escape
    parts: list[str] = []
    # axis frame
    parts.append(
        f'<line x1="{padl}" y1="{padt}" x2="{padl}" y2="{h - padb}" '
        'class="axis"/>'
        f'<line x1="{padl}" y1="{h - padb}" x2="{w - padr}" y2="{h - padb}" '
        'class="axis"/>'
    )
    # y-axis: raw min / mid / max (raw ADC scale)
    ymid = (ymin + ymax) / 2
    for val in (ymax, ymid, ymin):
        yp = sy(val)
        parts.append(
            f'<line x1="{padl - 4}" y1="{yp:.1f}" x2="{w - padr}" y2="{yp:.1f}" '
            'class="grid"/>'
            f'<text x="{padl - 7}" y="{yp + 3:.1f}" class="ylab">{val:.0f}</text>'
        )
    parts.append(f'<text x="10" y="{padt + 4}" class="axttl">raw ADC</text>')
    # x-axis: elapsed time (start .. end), shown in s or m
    for frac in (0.0, 0.5, 1.0):
        x = xmin + frac * xr
        xp = sx(x)
        secs = (x - xmin) * 3600.0
        parts.append(
            f'<text x="{xp:.1f}" y="{h - padb + 16:.1f}" class="xlab" '
            f'text-anchor="middle">{el(_elapsed_label(secs))}</text>'
        )
    # data polylines (one per probe; color carries the channel, not a value)
    for d in datasets:
        pts = " ".join(
            f"{sx(p['x']):.1f},{sy(p['y']):.1f}" for p in d.get("points", [])
        )
        if pts:
            color = el(str(d.get("color", "#888")))
            parts.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
                f'points="{pts}"/>'
            )
    # operator-intervention markers (vertical dashed line + label at the elapsed time)
    for iv in interventions or []:
        x_h = xmin + (iv["t_s"] / 3600.0)
        if not (xmin <= x_h <= xmax):
            continue  # outside the captured window -> don't draw a misleading line
        xp = sx(x_h)
        parts.append(
            f'<line x1="{xp:.1f}" y1="{padt}" x2="{xp:.1f}" y2="{h - padb}" '
            'class="ivmark"/>'
            f'<text x="{xp + 3:.1f}" y="{padt + 10:.1f}" class="ivlab">'
            f"{el(iv['label'])}</text>"
        )
    return (
        f'<svg viewBox="0 0 {w} {h}" class="etrace" role="img" '
        f'aria-label="raw ADC trajectory per probe with elapsed-time axis">'
        f"{''.join(parts)}</svg>"
        '<p class="chartcap">raw ADC counts · higher = drier · color = probe · '
        "band by color, <b>not</b> a calibrated moisture %</p>"
    )


def _stat_card(s: dict) -> str:
    esc = html.escape
    sl = s.get("slope_per_hr")
    slope = f"{sl:+.2f}/h" if isinstance(sl, (int, float)) else "—"
    band = f"{esc(str(s.get('band_fw', '—')))} · {esc(str(s.get('band_ui', '')))}"
    rng = f"{esc(str(s.get('raw_min', '—')))}-{esc(str(s.get('raw_max', '—')))}"
    rows = [
        ("band", band),
        ("current", esc(str(s.get("raw_last", "—")))),
        ("min/max", rng),
        ("median", esc(str(s.get("raw_median", "—")))),
        ("mean", esc(str(s.get("raw_mean", "—")))),
        ("slope", esc(slope)),
        ("samples", esc(str(s.get("n", "—")))),
    ]
    body = "".join(
        f'<span class="k">{k}</span><span class="num">{v}</span>' for k, v in rows
    )
    return (
        f'<article class="scard" style="--accent:{esc(str(s.get("color", "#888")))}">'
        f'<div class="sid">{esc(str(s.get("id", "?")))} '
        f'<span class="gpio">GPIO {esc(str(s.get("gpio", "?")))}</span></div>'
        f'<div class="smeta">{body}</div></article>'
    )


def render_detail(
    experiment_id: str, experiments_dir: str | Path | None = None
) -> str | None:
    """The /lab/<id> page, or None if the experiment doesn't exist (-> 404)."""
    if not _ID_RE.match(experiment_id) or ".." in experiment_id:
        return None
    root = Path(experiments_dir) if experiments_dir else _EXPERIMENTS
    exp = root / experiment_id
    manifest = exp / "manifest.json"
    if not exp.is_dir() or not manifest.exists():
        return None
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    notes = load_notes(experiment_id)  # the living log, from the tracked sidecar (#158)
    interventions = _parse_interventions(notes.get("method"))  # #325 chart markers

    csv = exp / (m.get("file") or f"{experiment_id}.csv")
    sensors: list[dict] = []
    prov: dict = {}  # #324: server/app + contract/calibration, from build_context
    svg = '<p class="empty">No capture file found for this experiment yet.</p>'
    if csv.exists():
        try:
            ctx = build_context(parse_files([str(csv)]))
            sensors = ctx.get("sensors") or []
            prov = ctx.get("provenance") or {}
            svg = _svg(ctx.get("trajectory", {}).get("datasets", []), interventions)
        except Exception:  # a corrupt capture must not 500 the page
            svg = (
                '<p class="empty">This capture couldn\'t be read — it may '
                "be corrupted or incomplete.</p>"
            )

    t = m.get("transport") or {}
    fw = m.get("firmware") or {}  # #329: firmware version + git rev, shown separately
    srv = prov.get("server") or {}  # #324: app provenance (git SHA, staleness)
    contract = prov.get("contract") or {}
    _app_sha = srv.get("app_git_sha")
    _app = (f"{_app_sha}{' +dirty' if srv.get('dirty') else ''}") if _app_sha else "—"
    _stale = "stale (predates checkout)" if srv.get("stale") else "current"
    facts = [
        # capture identity (#324: screenshot-friendly provenance)
        ("capture", experiment_id),
        ("file", str(m.get("file") or "—")),
        ("subject", str(m.get("subject") or "—")),
        ("schema", str(m.get("schema_version", "—"))),
        ("capture ver", str(m.get("capture_version") or "—")),
        ("started", _fmt_when(m.get("started_utc"))),
        ("duration", _fmt_dur(m.get("duration_s"))),
        ("rate", f"{m.get('sample_rate_s', '—')}s"),
        ("sweeps", str(t.get("sweeps", "—"))),
        ("rows", str(t.get("rows", "—"))),
        ("dropped", str(t.get("dropped", "—"))),
        ("crc", str(t.get("crc_fail", "—"))),
        ("stopped", str(m.get("stopped_by", "—"))),
        # firmware provenance: explicit "unavailable" when the device didn't report it
        ("firmware", str(fw.get("version") or "unavailable")),
        ("git", str(fw.get("git") or "unavailable")),
        # app + honest-data contract state (#324)
        ("app git", _app),
        ("server", _stale),
        ("value/unit", str(contract.get("label") or "raw counts + band only")),
        ("calibration", str(prov.get("calibration") or "uncalibrated")),
    ]
    facts_html = "".join(
        f'<span class="fk">{html.escape(k)}</span>'
        f'<span class="fv">{html.escape(str(v))}</span>'
        for k, v in facts
    )
    cards = "".join(_stat_card(s) for s in sensors) or (
        '<p class="empty">No probe stats to show for this capture yet.</p>'
    )
    title = html.escape(str(m.get("title") or m.get("subject") or experiment_id))

    ver = notes.get("version") or 0
    saved = (
        f"saved {html.escape(str(notes.get('saved_at')))} · v{ver}"
        if ver
        else "not saved yet"
    )

    template = _TEMPLATE.read_text(encoding="utf-8")
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    return (
        template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)
        .replace("<!--__TITLE__-->", title)
        .replace("<!--__EID__-->", html.escape(experiment_id))
        .replace("<!--__FACTS__-->", facts_html)
        .replace("<!--__SVG__-->", svg)
        .replace("<!--__CARDS__-->", cards)
        .replace("<!--__SAVED__-->", saved)
        .replace("<!--__HYP__-->", html.escape(str(notes.get("hypothesis", ""))))
        .replace("<!--__MET__-->", html.escape(str(notes.get("method", ""))))
        .replace("<!--__FIN__-->", html.escape(str(notes.get("findings", ""))))
        .replace("<!--__CON__-->", html.escape(str(notes.get("conclusion", ""))))
    )
