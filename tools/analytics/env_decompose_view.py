#!/usr/bin/env python3
"""Functional render of the H1/H2 drying-rate decomposition (#199, PRD-0002 R5).

Status: pending — consumers land in #199, with `env_decompose` (#1388).

Turns :func:`env_decompose.decompose` output into two honest scatter panels so an
*accelerating* curve (**H1**: drying rate rises as the soil dries) and a *sun-driven*
curve (**H2**: drying rate tracks radiation) can be looked at side by side:

* **H1** — drying rate vs ``mean_raw`` (dryness; higher raw = drier).
* **H2** — drying rate vs ``mean_radiation`` (only windows with weather coverage).

The headline is the **confound banner** (the honest core): on the 48 h baseline the two
drivers move together (06-25 is both sunnier *and* drier), so a faster rate is explained
by *both* — the banner says so and the view never implies a separation the window set
can't support. ``separable`` False → CONFOUNDED; True → decorrelated; None → no weather
(H1 only).

Presentation-agnostic: the **functional** Data render (raw scatter + the verdict);
Design owns the branded viz. Returns an SVG string; no parsing, no file I/O.
"""

from __future__ import annotations

_W, _H = 720, 430
# semantic verdict colors (work in both light/dark over a transparent host).
_CONFOUND = {
    False: ("#d9534f", "CONFOUNDED — H1 and H2 can't be told apart here"),
    True: ("#3b8a3b", "decorrelated — H1 vs H2 are distinguishable"),
    None: ("#8a8a8a", "no weather coverage — H1 only; H2 needs the weather layer"),
}
_H1_COLOR = "#2a78d6"  # dryness axis
_H2_COLOR = "#e0a53d"  # radiation axis


def _rng(vals: list[float]) -> tuple[float, float]:
    lo, hi = min(vals), max(vals)
    if lo == hi:  # a flat axis: pad so points don't collapse onto the edge
        lo, hi = lo - 1.0, hi + 1.0
    return lo, hi


def _panel(
    pts: list[tuple[float, float]],
    *,
    x0: float,
    y0: float,
    w: float,
    h: float,
    title: str,
    xlabel: str,
    ylabel: str,
    color: str,
    empty_note: str,
) -> str:
    pad_l, pad_b, pad_t = 6, 22, 26
    px0, py0 = x0 + pad_l, y0 + pad_t
    pw, ph = w - pad_l - 6, h - pad_t - pad_b
    parts = [
        f'<text x="{x0 + w / 2:.0f}" y="{y0 + 14:.0f}" text-anchor="middle" '
        f'font-size="12.5" font-weight="500" fill="currentColor">{title}</text>',
        # plot frame (recessive)
        f'<rect x="{px0:.1f}" y="{py0:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
        f'fill="none" stroke="currentColor" stroke-opacity="0.18"/>',
        f'<text x="{x0 + w / 2:.0f}" y="{y0 + h - 4:.0f}" text-anchor="middle" '
        f'font-size="10.5" fill="currentColor" opacity="0.6">{xlabel}</text>',
        f'<text x="{x0 + 10:.0f}" y="{py0 + ph / 2:.0f}" font-size="10.5" '
        f'fill="currentColor" opacity="0.6" transform="rotate(-90 {x0 + 10:.0f} '
        f'{py0 + ph / 2:.0f})" text-anchor="middle">{ylabel}</text>',
    ]
    if not pts:
        parts.append(
            f'<text x="{x0 + w / 2:.0f}" y="{py0 + ph / 2:.0f}" text-anchor="middle" '
            f'font-size="11" fill="currentColor" opacity="0.5">{empty_note}</text>'
        )
        return "".join(parts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    xlo, xhi = _rng(xs)
    ylo, yhi = _rng(ys)
    for x, y in pts:
        cx = px0 + (x - xlo) / (xhi - xlo) * pw
        cy = py0 + ph - (y - ylo) / (yhi - ylo) * ph  # y up
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{color}" '
            f'fill-opacity="0.75"/>'
        )
    # axis-range ticks (min/max) so the scatter is quantitative, not decorative
    parts.append(
        f'<text x="{px0:.0f}" y="{py0 + ph + 11:.0f}" font-size="9.5" '
        f'fill="currentColor" opacity="0.5">{round(xlo)}</text>'
        f'<text x="{px0 + pw:.0f}" y="{py0 + ph + 11:.0f}" text-anchor="end" '
        f'font-size="9.5" fill="currentColor" opacity="0.5">{round(xhi)}</text>'
    )
    return "".join(parts)


def render_svg(result: dict) -> str:
    """Build the decomposition SVG (string) from ``decompose()`` output."""
    windows = result.get("windows") or []
    confound = result.get("confound") or {}
    sep = confound.get("separable")
    color, verdict = _CONFOUND.get(sep, _CONFOUND[None])
    r = confound.get("radiation_dryness_r")
    note = confound.get("note") or verdict

    h1 = [
        (w["mean_raw"], w["drying_rate"])
        for w in windows
        if w.get("mean_raw") is not None and w.get("drying_rate") is not None
    ]
    h2 = [
        (w["mean_radiation"], w["drying_rate"])
        for w in windows
        if w.get("mean_radiation") is not None and w.get("drying_rate") is not None
    ]

    r_txt = f" · radiation↔dryness r={r}" if r is not None else ""
    parts = [
        f'<svg viewBox="0 0 {_W} {_H}" width="100%" role="img" '
        f'style="color:var(--text-primary)" '
        f'aria-label="H1/H2 drying-rate decomposition with the confound verdict">',
        '<text x="14" y="24" font-size="14" font-weight="500" fill="currentColor">'
        "Drying-rate decomposition · H1 (dryness) vs H2 (sun)</text>",
        # confound banner
        f'<rect x="14" y="34" width="{_W - 28}" height="30" rx="6" fill="{color}" '
        f'fill-opacity="0.14"/>'
        f'<rect x="14" y="34" width="5" height="30" rx="2" fill="{color}"/>'
        f'<text x="28" y="53" font-size="11.5" fill="currentColor">'
        f"{verdict}{r_txt}</text>",
        f'<text x="14" y="82" font-size="10.5" fill="currentColor" opacity="0.62">'
        f"{note}</text>",
    ]
    parts.append(
        _panel(
            h1,
            x0=14,
            y0=92,
            w=(_W - 28) / 2 - 6,
            h=_H - 92 - 8,
            title="H1 · accelerating (rate vs dryness)",
            xlabel="mean raw ADC  (higher = drier)",
            ylabel="drying rate (counts/h)",
            color=_H1_COLOR,
            empty_note="no windows",
        )
    )
    parts.append(
        _panel(
            h2,
            x0=14 + (_W - 28) / 2 + 6,
            y0=92,
            w=(_W - 28) / 2 - 6,
            h=_H - 92 - 8,
            title="H2 · sun-driven (rate vs radiation)",
            xlabel="mean radiation",
            ylabel="drying rate (counts/h)",
            color=_H2_COLOR,
            empty_note="no weather coverage",
        )
    )
    parts.append("</svg>")
    return "".join(parts)
