#!/usr/bin/env python3
"""Recompute the P01-P11 bench-day arc from committed raw samples (#380).

#419 promoted the raw monitor-log windows + ``arc_derivation_windows.csv`` into the
repo. This recomputes the one-read-per-plant arc **from samples** via the ratified
aggregation rule (issue #380), instead of trusting the hand-derived table — then
reconciles the sample recompute against the committed ``plant_arc_table.csv``. The
recompute is canonical; divergences are *classified* (preferential-flow vs window
/method), never silently reconciled away.

Ratified rule (Data owns the collapse; Sage owns probe validity):

* **included probes** = rows with ``probe_included_by_sage == true``. Excluded probes
  (stuck / air-reference / no-contact) never enter the read.
* **per-phase value** = median across included probes of *each probe's median within
  the phase window* (median-of-medians) — integer raw ADC. Each probe counts once,
  robust to a single noisy channel and to uneven per-probe sample counts.
* **wettest = sustained**: the wettest cross-probe sweep-median over ``peak_window``,
  **not** the deepest instantaneous spike. The instantaneous min is kept separately
  as ``wettest_instant`` (e.g. P09's 1327 spike vs its sustained level).
* **spread** = max-min across included-probe medians at ``pull_window`` (the microzone
  whisker).
* **band** = ``band_for_raw`` from the calibration ladder, never the emitted ``level=``
  payload tag (it flip-flops during transients — P09 evidence). Raw is truth.
* **null phase window** -> empty read (honest gap); reason rides ``derivation_status``.

Phases whose samples were never committed (P01's dry/wet come from sidecar summaries,
not sample rows) are carried from the committed table and flagged ``summary``; only
sample-derived phases are reconciled against the committed numbers.

Presentation-agnostic — emits the arc table; Design owns the viz. The store is
*derived*: written under gitignored ``reports/``, rebuilt from committed data, never
hand-edited.

    python tools/analytics/bench_arc.py            # recompute + reconcile + summary
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics as st
from datetime import datetime
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DATA = (
    _REPO / "docs" / "experiments" / "data" / "20260629_greenhouse_bench_arc_recovery"
)
_WINDOWS = _DATA / "windows"
_REPORTS = _REPO / "reports"

from tools.analytics.parse_v1 import band_for_raw  # noqa: E402

# (derivation phase column, derivation source column, output phase key).
_PHASES = (
    ("baseline_window", "baseline_source", "start"),
    ("peak_window", "peak_source", "wettest"),
    ("pull_window", "pull_source", "ending"),
)


def _parse_local(s: str | None) -> datetime | None:
    """Parse a ``YYYY-MM-DD HH:MM:SS[.fff]`` local stamp; None if unparseable."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_span(s: str | None) -> tuple[datetime, datetime] | None:
    """Parse a ``<start> to <end>`` window; None if absent/unparseable."""
    if not s or " to " not in s:
        return None
    lo, hi = s.split(" to ", 1)
    a, b = _parse_local(lo), _parse_local(hi)
    return (a, b) if a and b else None


def load_derivation() -> list[dict[str, str]]:
    """Per-plant phase-window rows from ``arc_derivation_windows.csv``."""
    with (_DATA / "arc_derivation_windows.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_window_rows(source_key: str) -> list[dict[str, str]]:
    """All sample rows for a window source (globs P01's ``*_partNN`` chunks)."""
    files = sorted(_WINDOWS.glob(f"{source_key}*.csv"))
    rows: list[dict[str, str]] = []
    for fp in files:
        with fp.open(encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    return rows


def _included_in_span(
    rows: list[dict[str, str]], span: tuple[datetime, datetime]
) -> dict[str, list[int]]:
    """Map probe -> raw samples, for included probes within ``span`` (inclusive)."""
    lo, hi = span
    by_probe: dict[str, list[int]] = {}
    for r in rows:
        if r.get("probe_included_by_sage", "").strip().lower() != "true":
            continue
        ts = _parse_local(r.get("timestamp_local"))
        if ts is None or ts < lo or ts > hi:
            continue
        raw = r.get("raw_value", "").strip()
        if not raw:
            continue
        by_probe.setdefault(r.get("sensor_id", "?"), []).append(int(raw))
    return by_probe


def _median_of_medians(by_probe: dict[str, list[int]]) -> int | None:
    """Median across probes of each probe's median (the ratified per-phase value)."""
    per = [st.median(v) for v in by_probe.values() if v]
    return round(st.median(per)) if per else None


def _wettest_sustained(
    rows: list[dict[str, str]], span: tuple[datetime, datetime], bucket_s: int = 6
) -> tuple[int | None, int | None]:
    """(sustained, instant) wettest over ``span``.

    Probes log a few sub-seconds apart, so a sweep isn't one timestamp — bin into
    ``bucket_s``-second windows (~one 5 s cadence + margin). *sustained* = wettest
    (min) **cross-probe median** across buckets — a whole-pot level, never a single
    spike. *instant* = the single wettest included raw sample.
    """
    lo, hi = span
    buckets: dict[int, dict[str, list[int]]] = {}
    instant: int | None = None
    for r in rows:
        if r.get("probe_included_by_sage", "").strip().lower() != "true":
            continue
        ts = _parse_local(r.get("timestamp_local"))
        if ts is None or ts < lo or ts > hi:
            continue
        raw = r.get("raw_value", "").strip()
        if not raw:
            continue
        val = int(raw)
        b = int(ts.timestamp() // bucket_s)
        buckets.setdefault(b, {}).setdefault(r.get("sensor_id", "?"), []).append(val)
        instant = val if instant is None else min(instant, val)
    if not buckets:
        return None, None
    bucket_medians = [
        st.median([st.median(v) for v in probes.values()])
        for probes in buckets.values()
    ]
    return round(min(bucket_medians)), instant


def recompute_arc() -> list[dict]:
    """Recompute every plant's arc from samples per the ratified rule."""
    out: list[dict] = []
    committed = load_committed_arc_table()
    for d in load_derivation():
        pid = d["plant_id"]
        comm = committed.get(pid, {})
        rec: dict = {
            "plant_id": pid,
            "plant_label": d.get("plant_label", ""),
            "derivation_status": d.get("derivation_status", ""),
        }
        for win_col, src_col, key in _PHASES:
            span = _parse_span(d.get(win_col))
            src = (d.get(src_col) or "").strip()
            if span and src:
                rows = load_window_rows(src)
                if key == "wettest":
                    val, instant = _wettest_sustained(rows, span)
                    rec["wettest_instant"] = instant
                    by_probe = _included_in_span(rows, span)
                else:
                    by_probe = _included_in_span(rows, span)
                    val = _median_of_medians(by_probe)
                rec[key] = val
                rec[f"{key}_source"] = "samples"
                rec[f"{key}_probes"] = ";".join(sorted(by_probe))
                rec[f"{key}_band"] = band_for_raw(val) if val is not None else None
                if key == "ending":
                    meds = [st.median(v) for v in by_probe.values() if v]
                    if len(meds) > 1:
                        rec["ending_spread"] = round(max(meds) - min(meds))
                        rec["ending_lo"] = round(min(meds))  # wettest probe at pull
                        rec["ending_hi"] = round(max(meds))  # driest probe at pull
                    else:
                        rec["ending_spread"] = None
            else:
                # No committed sample rows for this phase — carry the summary value.
                cv = comm.get(key)
                rec[key] = cv
                rec[f"{key}_source"] = "summary" if cv is not None else "gap"
                rec[f"{key}_band"] = band_for_raw(cv) if cv is not None else None
        out.append(rec)
    return out


def load_committed_arc_table() -> dict[str, dict]:
    """Committed ``plant_arc_table.csv`` keyed by plant_id (ints where numeric)."""
    table: dict[str, dict] = {}
    with (_DATA / "plant_arc_table.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            table[r["plant_id"]] = {
                "start": _int_or_none(r.get("start_raw")),
                "wettest": _int_or_none(r.get("wettest_raw")),
                "ending": _int_or_none(r.get("ending_raw")),
                "ending_spread": _int_or_none(r.get("ending_spread_raw")),
            }
    return table


def _int_or_none(s: str | None) -> int | None:
    s = (s or "").strip()
    return int(s) if s else None


def reconcile(tol: int = 2) -> list[dict]:
    """Reconcile the **sample** recompute against the curated ``plant_arc_table.csv``.

    The recompute is the rule-consistent canonical arc; the committed table was
    hand-curated. Where a sample-derived phase differs by > ``tol``, classify it:

    * ``preferential-flow/probe-set`` (|Δ| > 300) — the curated value picked the
      single responding probe; the rule uses the honest cross-probe median (most
      of the pot stayed dry — read it alongside the spread whisker).
    * ``window/method`` — a smaller pick-point / window-boundary difference.

    A divergence here is a *finding*, not a failure — same rule for every plant.
    """
    committed = load_committed_arc_table()
    out: list[dict] = []
    for rec in recompute_arc():
        comm = committed.get(rec["plant_id"], {})
        for key in ("start", "wettest", "ending"):
            if rec.get(f"{key}_source") != "samples":
                continue
            r, c = rec.get(key), comm.get(key)
            if r is None or c is None or abs(r - c) <= tol:
                continue
            out.append(
                {
                    "plant_id": rec["plant_id"],
                    "phase": key,
                    "recompute": r,
                    "curated": c,
                    "delta": r - c,
                    "class": "preferential-flow/probe-set"
                    if abs(r - c) > 300
                    else "window/method",
                }
            )
    return out


def _fmt_cell(rec: dict, key: str) -> str:
    v = rec.get(key)
    return f"{v} {rec.get(f'{key}_band') or ''}".strip() if v is not None else "-"


def _fmt_src(rec: dict) -> str:
    sym = {"samples": "S", "summary": "u", "gap": "."}
    keys = ("start", "wettest", "ending")
    return "".join(sym.get(rec.get(f"{k}_source"), "?") for k in keys)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Recompute the 2026-06-29 bench arc.")
    ap.add_argument("--write", action="store_true", help="write reports/ JSON")
    args = ap.parse_args(argv)

    arc = recompute_arc()
    print(f"{'plant':5}{'start':>14}{'wettest':>16}{'ending':>14}{'spread':>8}  src")
    for r in arc:
        sp = r.get("ending_spread")
        print(
            f"{r['plant_id']:5}{_fmt_cell(r, 'start'):>14}{_fmt_cell(r, 'wettest'):>16}"
            f"{_fmt_cell(r, 'ending'):>14}{(str(sp) if sp else ''):>8}  {_fmt_src(r)}"
        )

    diffs = reconcile()
    if diffs:
        print("\nRECONCILIATION vs curated plant_arc_table (recompute is canonical):")
        for d in diffs:
            print(
                f"  {d['plant_id']} {d['phase']}: recompute={d['recompute']} "
                f"curated={d['curated']} (d={d['delta']:+d}) [{d['class']}]"
            )
    else:
        print("\nreconciliation OK - all sample-derived phases reproduce the table")

    if args.write:
        _REPORTS.mkdir(exist_ok=True)
        (_REPORTS / "bench_arc_recomputed.json").write_text(
            json.dumps(arc, indent=2), encoding="utf-8"
        )
        print(f"wrote {_REPORTS / 'bench_arc_recomputed.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
