#!/usr/bin/env python3
"""Per-plant dose->response arc over the 2026-07-06/07 watering session (#836, child of
#834; the #379/#423 honest-arc form applied to a watering session).

Status: pending — consumers land with the pump era (#477, autonomous watering).
Dose->response arcs are pump-era analytics; the pumps are on the bench, not yet
wired (#1388).

Each dosed plant gets a column on the shared 7-band calibration ladder, and its
immediate dose->response as a **baseline -> wettest -> settle** arc read from the
plant's base-dose capture (one probe, so this is the *actual* trajectory, not a
cross-probe median):

* **baseline** — the first raw of the capture (the pre-uptake, driest point);
* **wettest** — the lowest raw the probe reached (the strongest response);
* **settle** — the last raw of the capture window.

Honest by construction (ADR-0004): raw + calibrated band are the truth — **no invented
normalized %**; a **gap stays a gap** (a plant with no base capture gets no column); and
a **suspect** window (the maintainer-caught p02 dose-3 probe-contamination fault) is
never drawn as a real response — its column is greyed and labelled, the raw kept in the
evidence packet, never here as a finding.

Reuses the ONE band ladder from :mod:`bench_arc_view` (shared, not a second ladder —
the honest-cross-board-band question is #832; this coordinates with it). The dose
volume is the operator annotation from each capture header. Output is *derived* — under
gitignored ``reports/``, regenerated from the committed captures. Design owns the final
brand tokens; this is the honest functional render.

    python tools/analytics/watering_arc.py       # write reports/watering_arc.html
"""

from __future__ import annotations

import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_CAPTURES = _REPO / "docs" / "experiments" / "2026-07-07-watering-dose-response"
_REPORTS = _REPO / "reports"
# The shared band ladder + geometry (#832: one ladder, never a second definition).
from tools.analytics.bench_arc_view import (  # noqa: E402
    _BANDS,
    _PLOT_H,
    _Y_TOP,
    _col_x,
    _marker,
    _y_for,
)

# #909: share the capture parser + its dose helpers with watering_events — one parse of
# the dose-capture header/rows, not a second inline copy (both views read one source).
from tools.analytics.watering_events import (  # noqa: E402
    _ML_PER_CUP,
    _SUSPECT_DOSES,
    _dose_n,
    _int,
    parse_capture,
)


def build_arcs(captures_dir: str | Path | None = None) -> list[dict]:
    """One arc per dosed plant from its **base** dose capture (dose 1), in file order.
    A capture with no numeric raw is skipped (an honest gap, no column)."""
    root = Path(captures_dir) if captures_dir else _CAPTURES
    arcs: list[dict] = []
    for p in sorted(root.glob("p*.csv")):
        if not re.match(r"p\d", p.name) or _dose_n(p.name) != 1:
            continue  # base dose only; snapshots (22h-/24h-) don't match p\d
        cap = parse_capture(p)  # #909: the shared header+rows parser
        raws = [v for v in (_int(r.get("raw")) for r in cap["rows"]) if v is not None]
        if not raws:
            continue  # honest gap: nothing to plot
        dose_ml = cap["dose_ml"]
        arcs.append(
            {
                "plant_id": cap["plant_id"] or p.stem,
                "plant": cap["plant"],
                "probe": cap["sensor"],
                "dose_cups": round(dose_ml / _ML_PER_CUP, 2)
                if dose_ml is not None
                else None,
                "baseline": raws[0],
                "wettest": min(raws),
                "settle": raws[-1],
                "n": len(raws),
                "suspect": (cap["plant_id"], cap["dose_n"]) in _SUSPECT_DOSES,
            }
        )
    return arcs


def _dose_label(cups: float | None) -> str:
    if cups is None:
        return ""
    return f"{cups:g}c"


def render_svg(arcs: list[dict]) -> str:
    """The per-plant dose->response arc SVG (string) on the shared band ladder."""
    n = max(1, len(arcs))
    row_h = _PLOT_H / len(_BANDS)
    parts = [
        '<svg viewBox="0 0 720 628" width="100%" role="img" '
        'style="color:var(--text-primary)" '
        'aria-label="Per-plant watering dose-to-response arcs on the band ladder">',
        '<text x="104" y="34" font-size="14" font-weight="500" fill="currentColor">'
        "Watering dose &#8594; response &#183; 2026-07-06 &#183; baseline &#8594; "
        "wettest &#8594; settle</text>",
        '<text x="104" y="54" font-size="11.5" fill="currentColor" opacity="0.6">'
        "raw ADC &#183; higher = drier &#183; one probe per plant &#183; measured "
        "cup dose below</text>",
        '<text x="700" y="34" text-anchor="end" font-size="11" fill="currentColor" '
        'opacity="0.55">wetter &#8595;</text>',
    ]
    for i, b in enumerate(_BANDS):
        ry = _Y_TOP + i * row_h
        parts.append(
            f'<rect x="104" y="{ry:.1f}" width="604" height="{row_h - 2:.1f}" rx="5" '
            f'fill="{b[6]}" fill-opacity="0.14"/>'
            f'<rect x="104" y="{ry:.1f}" width="5" height="{row_h - 2:.1f}" rx="2" '
            f'fill="{b[6]}"/>'
            f'<text x="16" y="{ry + row_h / 2 - 1:.1f}" font-size="12" '
            f'font-weight="500" fill="currentColor">{b[0]}</text>'
            f'<text x="16" y="{ry + row_h / 2 + 13:.1f}" font-size="10.5" '
            f'fill="currentColor" opacity="0.55">{b[1]}</text>'
        )
    for i, a in enumerate(arcs):
        x = _col_x(i, n)
        parts.append(
            f'<line x1="{x:.1f}" y1="{_Y_TOP:.1f}" x2="{x:.1f}" '
            f'y2="{_Y_TOP + _PLOT_H:.1f}" stroke="currentColor" stroke-opacity="0.07"/>'
        )
        base_y = _Y_TOP + _PLOT_H + 22
        if a.get("suspect"):
            # a fault window is never drawn as a real response — greyed + labelled.
            parts.append(
                f'<rect x="{x - 16:.1f}" y="{_Y_TOP:.1f}" width="32" '
                f'height="{_PLOT_H:.1f}" fill="currentColor" fill-opacity="0.05"/>'
                f'<text x="{x:.1f}" y="{_Y_TOP + _PLOT_H / 2:.1f}" '
                f'text-anchor="middle" font-size="10.5" fill="currentColor" '
                f'opacity="0.5" '
                f'transform="rotate(-90 {x:.1f} {_Y_TOP + _PLOT_H / 2:.1f})">'
                "suspect &#183; see README</text>"
                f'<text x="{x:.1f}" y="{base_y:.1f}" text-anchor="middle" '
                f'font-size="12" font-weight="500" fill="currentColor" opacity="0.8">'
                f"{a['plant_id']}</text>"
            )
            continue
        pts = [
            ("start", float(a["baseline"])),
            ("wettest", float(a["wettest"])),
            ("ending", float(a["settle"])),
        ]
        d = "M" + " L".join(f"{x:.1f} {_y_for(r):.1f}" for _, r in pts)
        parts.append(
            f'<path d="{d}" fill="none" stroke="currentColor" '
            f'stroke-opacity="0.3" stroke-width="1.5"/>'
        )
        for kind, r in pts:
            parts.append(_marker(kind, x, _y_for(r), r, False))
        label = a["plant_id"] + (
            f" &#183; {_dose_label(a['dose_cups'])}" if a.get("dose_cups") else ""
        )
        parts.append(
            f'<text x="{x:.1f}" y="{base_y:.1f}" text-anchor="middle" font-size="11.5" '
            f'font-weight="500" fill="currentColor" opacity="0.8">{label}</text>'
        )
    ly = _Y_TOP + _PLOT_H + 50
    parts.append(
        f'<circle cx="116" cy="{ly - 4:.1f}" r="4.4" fill="none" stroke="currentColor" '
        f'stroke-width="1.5"/><text x="127" y="{ly:.1f}" font-size="11" '
        f'fill="currentColor" opacity="0.72">baseline</text>'
        f'<path d="M210 {ly - 9:.1f} L221 {ly - 9:.1f} L215.5 {ly + 2:.1f} Z" '
        f'fill="#36a85a"/><text x="228" y="{ly:.1f}" font-size="11" '
        f'fill="currentColor" opacity="0.72">wettest reached</text>'
        f'<circle cx="366" cy="{ly - 3:.1f}" r="5" fill="#888"/>'
        f'<text x="377" y="{ly:.1f}" font-size="11" fill="currentColor" '
        f'opacity="0.72">settle</text>'
        f'<text x="116" y="{ly + 18:.1f}" font-size="11" fill="currentColor" '
        f'opacity="0.55">raw + band = truth &#183; no invented % &#183; suspect '
        f"windows greyed, not drawn as a response (honest gap)</text>"
    )
    parts.append("</svg>")
    return "".join(parts)


def render_html(arcs: list[dict]) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Sprout watering dose to response arc — 2026-07-06</title>"
        "<style>body{margin:0;background:#f3f6ef;font-family:system-ui,sans-serif}"
        ":root{--text-primary:#1c2a1c;--surface-2:#fff}"
        ".wrap{max-width:760px;margin:24px auto;padding:8px}</style></head>"
        f"<body><div class='wrap'>{render_svg(arcs)}</div></body></html>"
    )


def main() -> int:
    arcs = build_arcs()
    _REPORTS.mkdir(exist_ok=True)
    out = _REPORTS / "watering_arc.html"
    out.write_text(render_html(arcs), encoding="utf-8")
    print(f"wrote {out} ({len(arcs)} plants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
