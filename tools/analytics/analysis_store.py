#!/usr/bin/env python3
"""Analysis store - the Lab Notebook's derived, rebuildable DuckDB tier (#155).

Ingests the experiment captures into a columnar DuckDB store with two tables:

  - ``readings``            one row per probe-sample, plus derived calendar fields
                            (month / hour / season / is_daylight - absorbs #17).
  - ``experiment_features`` one row per (experiment, probe) with engineered features
                            (n / median / min / max / spread / slope-per-hour - #24).

The store is DERIVED: written under gitignored ``reports/``, rebuilt from the raw
captures, never the source of truth (#27). Absorbs #27 / #24 / #17.

    python tools/analytics/analysis_store.py            # (re)build + a summary
    python tools/analytics/analysis_store.py --query "SELECT * FROM experiment_features"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_EXPERIMENTS = _REPO / "experiments"
_STORE = _REPO / "reports" / "plants.duckdb"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from parse_v1 import parse_files  # noqa: E402

_COLS = [
    "experiment_id",
    "subject",
    "sensor_id",
    "timestamp_utc",
    "timestamp_local",
    "raw_value",
    "value",
    "band",
    "quality_flag",
]


def _readings_rows(experiments_dir: str | Path) -> list[dict]:
    """Flatten every capture into (experiment, probe, sample) rows for the store."""
    root = Path(experiments_dir)
    rows: list[dict] = []
    if not root.exists():
        return rows
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = d / "manifest.json"
        if not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        csv = d / (m.get("file") or f"{d.name}.csv")
        if not csv.exists():
            continue
        eid = m.get("experiment_id", d.name)
        subject = m.get("title") or m.get("subject") or eid
        try:
            data = parse_files([str(csv)])
        except Exception:  # a corrupt capture must not abort the whole rebuild
            continue
        for r in data.readings:
            rows.append(
                {
                    "experiment_id": eid,
                    "subject": subject,
                    "sensor_id": r.sensor_id,
                    "timestamp_utc": r.timestamp_utc,
                    "timestamp_local": r.timestamp_local,
                    "raw_value": r.raw_value,
                    "value": r.value,
                    "band": r.band,
                    "quality_flag": r.quality_flag,
                }
            )
    return rows


def build_store(
    experiments_dir: str | Path | None = None, out_path: str | Path | None = None
) -> dict:
    """(Re)build the DuckDB store fresh from raw captures; returns a count summary."""
    import duckdb
    import pandas as pd

    root = experiments_dir or _EXPERIMENTS
    out = Path(out_path) if out_path else _STORE
    rows = _readings_rows(root)

    df = pd.DataFrame(rows, columns=_COLS)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df["timestamp_local"] = pd.to_datetime(df["timestamp_local"])  # naive, rig-local

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # rebuild fresh - the store is derived, never edited in place
    con = duckdb.connect(str(out))
    try:
        con.register("raw", df)
        # readings + the calendar/temporal layer (#17) materialized on read
        con.execute("""
            CREATE TABLE readings AS SELECT *,
                month(timestamp_local)::INT AS month,
                hour(timestamp_local)::INT AS hour,
                CASE
                    WHEN month(timestamp_local) IN (12, 1, 2) THEN 'winter'
                    WHEN month(timestamp_local) IN (3, 4, 5)  THEN 'spring'
                    WHEN month(timestamp_local) IN (6, 7, 8)  THEN 'summer'
                    ELSE 'autumn'
                END AS season,
                (hour(timestamp_local) BETWEEN 6 AND 18) AS is_daylight
            FROM raw
        """)
        # one engineered row per (experiment, probe) - the #24 feature substrate
        con.execute("""
            CREATE TABLE experiment_features AS SELECT
                experiment_id,
                any_value(subject) AS subject,
                sensor_id,
                count(*) AS n,
                median(raw_value) AS raw_median,
                min(raw_value) AS raw_min,
                max(raw_value) AS raw_max,
                max(raw_value) - min(raw_value) AS raw_spread,
                regr_slope(raw_value, epoch(timestamp_local)) * 3600
                    AS raw_slope_per_hr,
                any_value(band) AS band,
                sum(CASE WHEN quality_flag <> 'OK' THEN 1 ELSE 0 END) AS quality_flags
            FROM readings
            GROUP BY experiment_id, sensor_id
            ORDER BY experiment_id, sensor_id
        """)
        summary = {
            "experiments": con.execute(
                "SELECT count(DISTINCT experiment_id) FROM readings"
            ).fetchone()[0],
            "readings": con.execute("SELECT count(*) FROM readings").fetchone()[0],
            "feature_rows": con.execute(
                "SELECT count(*) FROM experiment_features"
            ).fetchone()[0],
            "path": str(out),
        }
    finally:
        con.close()
    return summary


def query(sql: str, out_path: str | Path | None = None):
    """Run a read-only SQL query against the store; returns a DataFrame."""
    import duckdb

    out = Path(out_path) if out_path else _STORE
    con = duckdb.connect(str(out), read_only=True)
    try:
        return con.execute(sql).fetchdf()
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build/query the analysis store (#155).")
    ap.add_argument("--query", help="run a SQL query against the store (read-only)")
    ap.add_argument("--dir", help="experiments dir (default: repo experiments/)")
    args = ap.parse_args(argv)
    if args.query:
        print(query(args.query).to_string(index=False))
        return 0
    s = build_store(args.dir)
    print(
        f"built {s['path']}: {s['experiments']} experiment(s), "
        f"{s['readings']} readings, {s['feature_rows']} feature rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
