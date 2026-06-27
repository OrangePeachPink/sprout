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
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_EXPERIMENTS = _REPO / "experiments"
_TEMPLATE = _HERE / "lab_detail_template.html"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from the URL

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from dashboard import FONTS_CSS, TOKENS_CSS, build_context  # noqa: E402
from experiments_catalog import _fmt_dur, _fmt_when  # noqa: E402
from lab_notes import load_notes  # noqa: E402  (Lab notes #158)
from parse_v1 import parse_files  # noqa: E402


def _svg(datasets: list[dict]) -> str:
    """A per-probe raw trajectory as one inline SVG (higher raw = drier = up)."""
    pts_all = [p for d in datasets for p in d.get("points", [])]
    if not pts_all:
        return '<p class="empty">no trajectory</p>'
    xs = [p["x"] for p in pts_all]
    ys = [p["y"] for p in pts_all]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    xr = (xmax - xmin) or 1.0
    yr = (ymax - ymin) or 1.0
    w, h, pad = 720, 220, 10

    def sx(x: float) -> float:
        return pad + (x - xmin) / xr * (w - 2 * pad)

    def sy(y: float) -> float:
        return h - pad - (y - ymin) / yr * (h - 2 * pad)

    lines = []
    for d in datasets:
        pts = " ".join(
            f"{sx(p['x']):.1f},{sy(p['y']):.1f}" for p in d.get("points", [])
        )
        if pts:
            color = html.escape(str(d.get("color", "#888")))
            lines.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.5" '
                f'points="{pts}"/>'
            )
    return (
        f'<svg viewBox="0 0 {w} {h}" class="etrace" preserveAspectRatio="none" '
        f'role="img" aria-label="raw trajectory per probe">{"".join(lines)}</svg>'
    )


def _stat_card(s: dict) -> str:
    esc = html.escape
    sl = s.get("slope_per_hr")
    slope = f"{sl:+.2f}/h" if isinstance(sl, (int, float)) else "—"
    band = f"{esc(str(s.get('band_fw', '—')))} · {esc(str(s.get('band_ui', '')))}"
    rng = f"{esc(str(s.get('raw_min', '—')))}-{esc(str(s.get('raw_max', '—')))}"
    rows = [
        ("band", band),
        ("median", esc(str(s.get("raw_median", "—")))),
        ("range", rng),
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

    csv = exp / (m.get("file") or f"{experiment_id}.csv")
    sensors: list[dict] = []
    svg = '<p class="empty">capture file missing</p>'
    if csv.exists():
        try:
            ctx = build_context(parse_files([str(csv)]))
            sensors = ctx.get("sensors") or []
            svg = _svg(ctx.get("trajectory", {}).get("datasets", []))
        except Exception:  # a corrupt capture must not 500 the page
            svg = '<p class="empty">could not parse the capture</p>'

    t = m.get("transport") or {}
    facts = [
        ("started", _fmt_when(m.get("started_utc"))),
        ("duration", _fmt_dur(m.get("duration_s"))),
        ("rate", f"{m.get('sample_rate_s', '—')}s"),
        ("sweeps", str(t.get("sweeps", "—"))),
        ("rows", str(t.get("rows", "—"))),
        ("dropped", str(t.get("dropped", "—"))),
        ("crc", str(t.get("crc_fail", "—"))),
        ("stopped", str(m.get("stopped_by", "—"))),
    ]
    facts_html = "".join(
        f'<span class="fk">{html.escape(k)}</span>'
        f'<span class="fv">{html.escape(str(v))}</span>'
        for k, v in facts
    )
    cards = "".join(_stat_card(s) for s in sensors) or (
        '<p class="empty">no probe stats</p>'
    )
    title = html.escape(str(m.get("title") or m.get("subject") or experiment_id))

    notes = load_notes(experiment_id)  # the living log, from the tracked sidecar (#158)
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
