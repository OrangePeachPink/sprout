#!/usr/bin/env python3
"""Calibration workbench - propose band boundaries from captured experiments and export
a candidate config (#192, epic #153). Sits on the #155 analysis store.

Status: legacy - kept pending a revisit in ~2 releases (#192, ruled on #1388). The
calibration labs may be superseded by the #963 owner-cal record, but that is not
settled, and removing a workbench before its replacement is proven is how you lose
the ability to re-derive a boundary.

The seven moisture bands are separated by six raw-ADC boundaries (firmware:
``cal bounds(dry>wet)``). Given experiments that sampled known states, this proposes
refined boundaries from the *observed* per-band raw centres (the midpoint between
adjacent bands' medians), and exports a candidate config for the Data<->Firmware A2
handshake. It PROPOSES from evidence; firmware ratifies - the output is never
authoritative on its own (the #99/A2 direction; the dashboard ladder is "placeholders
pending A2").

    python tools/analytics/calibration.py            # propose + print
    python tools/analytics/calibration.py --export   # write the candidate config

Needs experiments spanning several states (e.g. the common-cup wet/dry/air-dry
characterization) - one band can't define a boundary.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_OUT = _REPO / "reports" / "calibration_candidate.json"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import analysis_store  # noqa: E402

_BANDS_SQL = """
    SELECT band,
        count(*) AS n,
        count(DISTINCT experiment_id) AS experiments,
        median(raw_value) AS raw_median,
        min(raw_value) AS raw_min,
        max(raw_value) AS raw_max
    FROM readings
    WHERE band IS NOT NULL AND band <> ''
    GROUP BY band
    ORDER BY raw_median
"""


def propose_boundaries(store_path: str | Path | None = None) -> dict:
    """Per-band centres + a proposed boundary (midpoint) between each adjacent pair.

    Bands are ordered by observed raw_median (low raw = wetter), so it works with
    whatever bands the captures actually contain - no reliance on band naming."""
    df = analysis_store.query(_BANDS_SQL, store_path)
    bands = [
        {
            "band": str(r["band"]),
            "n": int(r["n"]),
            "experiments": int(r["experiments"]),
            "raw_median": float(r["raw_median"]),
            "raw_min": int(r["raw_min"]),
            "raw_max": int(r["raw_max"]),
        }
        for _, r in df.iterrows()
    ]
    boundaries = [
        {
            "between": [a["band"], b["band"]],
            "raw": round((a["raw_median"] + b["raw_median"]) / 2),
        }
        for a, b in zip(bands, bands[1:])
    ]
    return {"bands": bands, "boundaries": boundaries}


def export_config(proposal: dict, out_path: str | Path | None = None) -> Path:
    """Write the candidate calibration config - boundaries in the firmware's dry>wet
    order, with the per-band evidence + a not-authoritative provenance note."""
    out = Path(out_path) if out_path else _OUT
    thresholds = sorted((b["raw"] for b in proposal["boundaries"]), reverse=True)
    config = {
        "schema": "plants.calibration.candidate.v1",
        "note": (
            "PROPOSED from captured experiments; firmware ratifies (the A2 handshake). "
            "Not authoritative on its own."
        ),
        "cal_bounds_dry_to_wet": thresholds,
        "boundaries": proposal["boundaries"],
        "per_band": proposal["bands"],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Propose calibration boundaries (#192).")
    ap.add_argument("--export", action="store_true", help="write the candidate config")
    ap.add_argument("--store", help="DuckDB store (default reports/plants.duckdb)")
    args = ap.parse_args(argv)
    proposal = propose_boundaries(args.store)
    bands = proposal["bands"]
    if not bands:
        print("no banded readings in the store - build it first (analysis_store.py).")
        return 0
    print(f"{len(bands)} band(s) observed, ordered wet -> dry:")
    for b in bands:
        print(
            f"  {b['band']:<14} median={b['raw_median']:.0f}  "
            f"range={b['raw_min']}-{b['raw_max']} n={b['n']} exp={b['experiments']}"
        )
    print("proposed boundaries (midpoints):")
    for bd in proposal["boundaries"]:
        print(f"  {bd['between'][0]} | {bd['between'][1]}  ->  {bd['raw']}")
    if len(bands) < 2:
        print("(need >= 2 bands to propose a boundary - capture more states)")
    if args.export:
        out = export_config(proposal)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
