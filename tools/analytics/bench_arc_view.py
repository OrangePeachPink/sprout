#!/usr/bin/env python3
"""Render the 2026-06-29 bench-day arc as a standalone honest SVG view (#423).

The one-time fixed summary Veronica asked for: per-plant columns on the 7-band
calibration ladder, each plant's **start -> wettest -> pull** arc as **one read
across valid probes** (the ratified rule in :mod:`bench_arc`). Honest by construction:

* the **sustained** wettest (cross-probe median) is the solid marker; the deepest a
  *single* probe reached rides a faint ``wettest_instant`` ghost diamond below it —
  so a preferential-flow pot reads as "median stayed dry, one zone dove," never a
  false "well watered";
* a **spread whisker** at pull shows how far the probes disagreed (microzone truth);
* **gaps stay gaps** — a phase with no committed samples gets no marker.

Data feeds the table + this honest functional render; Design owns final brand tokens.
The output is *derived* — written under gitignored ``reports/``, regenerated from the
committed evidence, never hand-edited. Live tracking + full-range coverage are
out of scope (#423).

    python tools/analytics/bench_arc_view.py        # write reports/bench_arc.html
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPORTS = _HERE.parents[1] / "reports"
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from bench_arc import recompute_arc  # noqa: E402

# 7-band ladder, dry -> wet, with the calibration-ladder raw ranges + colours.
# (name, sub, raw-lo, raw-hi, clamp-lo, clamp-hi, hex)
_BANDS = (
    ("Parched", "air-dry", 3050, 3401, 3050, 3400, "#e0533d"),
    ("Dry", "dry", 2140, 3050, 2140, 3050, "#e98b3a"),
    ("Drying", "needs water", 1830, 2140, 1830, 2140, "#f2b830"),
    ("Ideal", "ok", 1520, 1830, 1520, 1830, "#8cc63f"),
    ("Moist", "well watered", 1150, 1520, 1150, 1520, "#36a85a"),
    ("Wet", "overwatered", 1050, 1150, 1050, 1150, "#2bb6c4"),
    ("Saturated", "submerged", 899, 1050, 900, 1050, "#1d7c8a"),
)
_Y_TOP, _PLOT_H, _PL, _PR = 82.0, 418.0, 104.0, 708.0
_ROW_H = _PLOT_H / 7


def _band_index(raw: float) -> int:
    for i, b in enumerate(_BANDS):
        if b[2] <= raw < b[3]:
            return i
    return 0 if raw >= 3400 else 6


def _colour(raw: float) -> str:
    return _BANDS[_band_index(raw)][6]


def _y_for(raw: float) -> float:
    """Map a raw ADC value to its y within its (equal-height) band row."""
    i = _band_index(raw)
    _, _, _, _, clo, chi, _ = _BANDS[i]
    rr = max(clo, min(chi, raw))
    return _Y_TOP + i * _ROW_H + (chi - rr) / (chi - clo) * _ROW_H


def _col_x(i: int, n: int) -> float:
    return _PL + (_PR - _PL) / n * (i + 0.5)


def _marker(kind: str, x: float, y: float, raw: float, summary: bool) -> str:
    op = "0.6" if summary else "0.85"
    dash = ' stroke-dasharray="2.5 2.5"' if summary else ""
    if kind == "start":
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.6" fill="none" '
            f'stroke="currentColor" stroke-width="1.5" opacity="{op}"{dash}/>'
        )
    if kind == "wettest":
        c = _colour(raw)
        return (
            f'<path d="M{x - 5.5:.1f} {y - 5:.1f} L{x + 5.5:.1f} {y - 5:.1f} '
            f'L{x:.1f} {y + 6:.1f} Z" fill="{c}" opacity="{op}"{dash}/>'
        )
    c = _colour(raw)
    return (
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{c}" '
        f'stroke="var(--surface-2,#fff)" stroke-width="1.3"/>'
    )


def render_svg(arc: list[dict]) -> str:
    """Build the bench-arc SVG (string) from recomputed arc rows."""
    n = len(arc)
    parts = [
        '<svg viewBox="0 0 720 628" width="100%" role="img" '
        'style="color:var(--text-primary)" '
        'aria-label="Per-plant bench arcs on the calibration ladder">',
        '<text x="104" y="34" font-size="14" font-weight="500" fill="currentColor">'
        "Bench day arcs &#183; P01&#8211;P11 &#183; 2026-06-29 &#183; recomputed "
        "from samples</text>",
        '<text x="104" y="54" font-size="11.5" fill="currentColor" opacity="0.6">'
        "raw ADC &#183; higher = drier &#183; one read = median of valid probes "
        "&#183; sustained, not spike</text>",
        '<text x="700" y="34" text-anchor="end" font-size="11" fill="currentColor" '
        'opacity="0.55">wetter &#8595;</text>',
    ]
    for i, b in enumerate(_BANDS):
        ry = _Y_TOP + i * _ROW_H
        parts.append(
            f'<rect x="104" y="{ry:.1f}" width="604" height="{_ROW_H - 2:.1f}" rx="5" '
            f'fill="{b[6]}" fill-opacity="0.14"/>'
            f'<rect x="104" y="{ry:.1f}" width="5" height="{_ROW_H - 2:.1f}" rx="2" '
            f'fill="{b[6]}"/>'
            f'<text x="16" y="{ry + _ROW_H / 2 - 1:.1f}" font-size="12" '
            f'font-weight="500" fill="currentColor">{b[0]}</text>'
            f'<text x="16" y="{ry + _ROW_H / 2 + 13:.1f}" font-size="10.5" '
            f'fill="currentColor" opacity="0.55">{b[1]}</text>'
        )
    for i, p in enumerate(arc):
        x = _col_x(i, n)
        parts.append(
            f'<line x1="{x:.1f}" y1="{_Y_TOP:.1f}" x2="{x:.1f}" '
            f'y2="{_Y_TOP + _PLOT_H:.1f}" stroke="currentColor" stroke-opacity="0.07"/>'
        )
        lo, hi = p.get("ending_lo"), p.get("ending_hi")
        if lo is not None and hi is not None and (hi - lo) >= 300:
            y1, y2 = _y_for(lo), _y_for(hi)
            parts.append(
                f'<line x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}" '
                f'stroke="currentColor" stroke-opacity="0.2" stroke-width="1.4"/>'
                f'<line x1="{x - 3:.1f}" y1="{y1:.1f}" x2="{x + 3:.1f}" y2="{y1:.1f}" '
                f'stroke="currentColor" stroke-opacity="0.2"/>'
                f'<line x1="{x - 3:.1f}" y1="{y2:.1f}" x2="{x + 3:.1f}" y2="{y2:.1f}" '
                f'stroke="currentColor" stroke-opacity="0.2"/>'
            )
        pts = []
        for kind, src_key in (
            ("start", "start"),
            ("wettest", "wettest"),
            ("ending", "ending"),
        ):
            if p.get(kind) is not None:
                summary = p.get(f"{src_key}_source") == "summary"
                pts.append((kind, float(p[kind]), summary))
        if len(pts) > 1:
            d = "M" + " L".join(f"{x:.1f} {_y_for(r):.1f}" for _, r, _ in pts)
            parts.append(
                f'<path d="{d}" fill="none" stroke="currentColor" '
                f'stroke-opacity="0.3" stroke-width="1.5"/>'
            )
        inst, wet = p.get("wettest_instant"), p.get("wettest")
        if inst is not None and wet is not None and (wet - inst) > 60:
            yi, yw, ci = _y_for(inst), _y_for(wet), _colour(inst)
            parts.append(
                f'<line x1="{x:.1f}" y1="{yw:.1f}" x2="{x:.1f}" y2="{yi:.1f}" '
                f'stroke="{ci}" stroke-opacity="0.45" stroke-dasharray="2 2"/>'
                f'<path d="M{x:.1f} {yi - 4:.1f} L{x + 4:.1f} {yi:.1f} '
                f'L{x:.1f} {yi + 4:.1f} L{x - 4:.1f} {yi:.1f} Z" fill="none" '
                f'stroke="{ci}" stroke-width="1.3" opacity="0.7"/>'
            )
        for kind, r, summary in pts:
            parts.append(_marker(kind, x, _y_for(r), r, summary))
        parts.append(
            f'<text x="{x:.1f}" y="{_Y_TOP + _PLOT_H + 22:.1f}" text-anchor="middle" '
            f'font-size="12" font-weight="500" fill="currentColor" opacity="0.8">'
            f"{p['plant_id']}</text>"
        )
    ly = _Y_TOP + _PLOT_H + 50
    parts.append(
        f'<circle cx="116" cy="{ly - 4:.1f}" r="4.4" fill="none" stroke="currentColor" '
        f'stroke-width="1.5"/><text x="127" y="{ly:.1f}" font-size="11" '
        f'fill="currentColor" opacity="0.72">start</text>'
        f'<path d="M180 {ly - 9:.1f} L191 {ly - 9:.1f} L185.5 {ly + 2:.1f} Z" '
        f'fill="#36a85a"/><text x="198" y="{ly:.1f}" font-size="11" '
        f'fill="currentColor" opacity="0.72">wettest (sustained)</text>'
        f'<path d="M330 {ly - 8:.1f} L335 {ly - 3:.1f} L330 {ly + 2:.1f} '
        f'L325 {ly - 3:.1f} Z" fill="none" stroke="#36a85a" stroke-width="1.3"/>'
        f'<text x="341" y="{ly:.1f}" font-size="11" fill="currentColor" '
        f'opacity="0.72">a single zone reached</text>'
        f'<circle cx="500" cy="{ly - 3:.1f}" r="5" fill="#888"/>'
        f'<text x="511" y="{ly:.1f}" font-size="11" fill="currentColor" '
        f'opacity="0.72">at pull</text>'
        f'<line x1="566" y1="{ly - 11:.1f}" x2="566" y2="{ly + 1:.1f}" '
        f'stroke="currentColor" stroke-opacity="0.4" stroke-width="1.4"/>'
        f'<text x="575" y="{ly:.1f}" font-size="11" fill="currentColor" '
        f'opacity="0.72">probe spread</text>'
        f'<text x="116" y="{ly + 18:.1f}" font-size="11" fill="currentColor" '
        f'opacity="0.55">dashed = sidecar-summary (P01) &#183; no marker = phase not '
        f"captured (honest gap)</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def render_html(arc: list[dict]) -> str:
    """Wrap the SVG in a minimal standalone HTML page."""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Sprout bench-day arc — 2026-06-29</title>"
        "<style>body{margin:0;background:#f3f6ef;font-family:system-ui,sans-serif}"
        ":root{--text-primary:#1c2a1c;--surface-2:#fff}"
        ".wrap{max-width:760px;margin:24px auto;padding:8px}</style></head>"
        f"<body><div class='wrap'>{render_svg(arc)}</div></body></html>"
    )


def main() -> int:
    arc = recompute_arc()
    _REPORTS.mkdir(exist_ok=True)
    out = _REPORTS / "bench_arc.html"
    out.write_text(render_html(arc), encoding="utf-8")
    print(f"wrote {out} ({len(arc)} plants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
