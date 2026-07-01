"""H1/H2 drying-rate decomposition — the Data half of PRD-0002 R5 (#199).

Splits a probe's drying behaviour into the two candidate drivers so they can be
*plotted* against each other (Design owns the viz, R5):

* **H1 — accelerating**: drying rate rises as the soil dries (rate vs raw level).
* **H2 — sun-driven**: drying rate tracks measured radiation (rate vs radiation).

The honest core (ADR-0006 §7, the "named gap"): on the 48 h baseline the two days
are **confounded** — 06-25 is both sunnier *and* drier, so H1 and H2 *both* predict
"faster," and the data **cannot separate them**. This module computes that confound
explicitly (the radiation↔dryness correlation across windows) and reports whether
the window set can separate the hypotheses at all — so no plot ever implies a
separation the evidence can't support. It earns a weather-conditioned predictor
only once a window set decorrelates the two.

Inputs are presentation-agnostic (hours-since-start + raw ADC, the #370 join
convention); no parsing, no rendering. Drying rate is the slope of **raw ADC**
(higher raw = drier), never a %.
"""

from __future__ import annotations

import math


def _slope_per_hour(pairs: list[tuple[float, float]]) -> float | None:
    """Least-squares slope of raw vs hours (counts/hour); None if < 2 points.

    Positive = drying (raw climbing). Mirrors dashboard._slope_per_hour."""
    n = len(pairs)
    if n < 2:
        return None
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    var = sum((p[0] - mx) ** 2 for p in pairs)
    if var == 0:
        return None
    cov = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    return cov / var


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson r between two equal-length series; None if undefined (n<2 or flat)."""
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    return sxy / math.sqrt(sxx * syy)


def _mean_in_window(series: list[dict], key: str, lo: float, hi: float) -> float | None:
    """Mean of ``series[*][key]`` for points with x in [lo, hi); None if empty."""
    vals = [
        p[key]
        for p in series
        if p.get(key) is not None and lo <= p.get("x", float("nan")) < hi
    ]
    return sum(vals) / len(vals) if vals else None


def drying_windows(
    points: list[tuple[float, float]], window_h: float = 3.0
) -> list[dict]:
    """Per-window drying rate + mean dryness from (hours_since_start, raw) points.

    Each window: {t_lo, t_hi, t_center, drying_rate (counts/h), mean_raw, n}. A
    window with < 2 points (no slope) is skipped — surfaced as a gap, not faked."""
    if not points:
        return []
    pts = sorted(points)
    t0, t1 = pts[0][0], pts[-1][0]
    out: list[dict] = []
    lo = t0
    while lo < t1:
        hi = lo + window_h
        win = [(t, r) for (t, r) in pts if lo <= t < hi]
        rate = _slope_per_hour(win)
        if rate is not None:
            out.append(
                {
                    "t_lo": round(lo, 3),
                    "t_hi": round(hi, 3),
                    "t_center": round((lo + hi) / 2, 3),
                    "drying_rate": round(rate, 3),
                    "mean_raw": round(sum(r for _, r in win) / len(win), 1),
                    "n": len(win),
                }
            )
        lo = hi
    return out


def decompose(
    points: list[tuple[float, float]],
    weather_hourly: list[dict] | None = None,
    window_h: float = 3.0,
) -> dict:
    """The R5 decomposition + the honest confound check.

    Returns ``{"windows": [...], "confound": {...}}``. Each window carries
    ``drying_rate`` paired with both candidate drivers — ``mean_raw`` (H1, dryness)
    and ``mean_radiation`` / ``mean_cloud`` (H2, sun) — when weather is available.

    ``confound`` reports the radiation↔dryness correlation across windows and a
    ``separable`` verdict: if the two drivers move together (|r| high), a faster
    drying rate is explained by *both*, so H1 and H2 **cannot be told apart** in
    this window set. ``separable`` is None when there isn't enough weather coverage
    to even ask."""
    weather = weather_hourly or []
    windows = drying_windows(points, window_h)
    for w in windows:
        w["mean_radiation"] = _mean_in_window(
            weather, "radiation", w["t_lo"], w["t_hi"]
        )
        w["mean_cloud"] = _mean_in_window(weather, "cloud_cover", w["t_lo"], w["t_hi"])

    paired = [
        (w["mean_raw"], w["mean_radiation"])
        for w in windows
        if w.get("mean_radiation") is not None
    ]
    r = (
        _pearson([a for a, _ in paired], [b for _, b in paired])
        if len(paired) >= 2
        else None
    )
    if r is None:
        separable: bool | None = None
        note = (
            "not enough overlapping weather to test separability — "
            "drying-vs-dryness (H1) is shown; H2 needs the weather layer."
        )
    elif abs(r) >= 0.7:
        separable = False
        note = (
            f"H1 and H2 are CONFOUNDED here (radiation↔dryness r={r:.2f}): a faster "
            "drying rate is explained by both drier soil and more sun — this window "
            "set cannot separate them. Decorrelate them (e.g. a sunny-but-wet day) "
            "before claiming a sun-driven effect."
        )
    else:
        separable = True
        note = (
            f"radiation and dryness are decorrelated here (r={r:.2f}) — drying-rate "
            "vs each can distinguish H1 (accelerating) from H2 (sun-driven)."
        )
    return {
        "windows": windows,
        "confound": {
            "radiation_dryness_r": round(r, 3) if r is not None else None,
            "separable": separable,
            "n_paired_windows": len(paired),
            "note": note,
        },
    }
