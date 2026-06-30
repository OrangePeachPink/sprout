#!/usr/bin/env python3
"""Event-annotated bench-data view over the P01-P11 greenhouse survey (#380).

The 2026-06-29 bench suite (#379/#383) is rich narrative + structured sidecars but
not *queryable*. This flattens the Sage survey segments (docs/experiments/
20260629_sage_*.json) into a DuckDB store so the session's findings can be queried,
not just read — the analysis substrate ADR-0022's confidence layer consumes.

Two tables + one annotated view:

* ``bench_readings`` — one row per (plant, phase, probe): the per-probe **raw ADC**
  for each summarised phase (``last_raw``, ``pre/post_water_raw``, …) and the **band
  derived from it** (via the provisional, un-ratified bounds — labelled as such; no
  band on deltas), plus the water-balance + evidence-quality caveat for that segment.
* ``bench_events`` — one row per (plant, event): the operator annotation
  (watering / probe / tray / contact / observation), classified + timestamped.
* ``bench_annotated`` — the view: each reading with its plant's events aggregated,
  so "P03 s2 raw/band + everything that happened to P03" is one query.

**Honest-data (carried verbatim from the evidence's own `global_caveats`):** raw
ADC + band are truth; the band here is **derived from raw, provisional/uncalibrated**;
events are **annotations, never interpolation**. The store is *derived* — written
under gitignored ``reports/``, rebuilt from the JSON sidecars, never hand-edited.

    python tools/analytics/bench_events.py            # (re)build + a summary
    python tools/analytics/bench_events.py --query "SELECT * FROM bench_annotated"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DOCS_EXP = _REPO / "docs" / "experiments"
_STORE = _REPO / "reports" / "bench_events.duckdb"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from parse_v1 import DEFAULT_CAL_BOUNDS  # noqa: E402

# firmware band ladder, dry -> wet (7 bands from the 6 descending cal boundaries).
_BANDS_DRY_TO_WET = (
    "air-dry",
    "DRY",
    "needs water",
    "OK",
    "well watered",
    "overwatered",
    "submerged",
)
_PROBES = ("s1", "s2", "s3", "s4")

# event-type classification by keyword (first match wins; order = specificity).
# Water-*action* words only for watering ("soak"/"fill" alone are tray-ambiguous —
# "filled the cachepot tray, paused for soak" is a tray event, not a watering one).
_EVENT_KEYWORDS = (
    ("watering", ("water", "resoak", "dose", "cup", "applied")),
    ("tray", ("tray", "cachepot", "standing water", "runoff", "saucer")),
    ("contact", ("contact", "placement", "insert", "geometry", "lift")),
    ("probe", ("probe", "pull", "remove", "rootball")),
)


def band_for_raw(
    raw: object, bounds: tuple[int, ...] = DEFAULT_CAL_BOUNDS
) -> str | None:
    """Band for a raw ADC value (higher raw = drier). Derived, provisional — the
    bounds are the un-ratified shared classifier, not per-channel calibration."""
    try:
        r = int(raw)
    except (TypeError, ValueError):
        return None
    for i, b in enumerate(bounds):  # descending: b0 driest .. b5 wettest
        if r >= b:
            return _BANDS_DRY_TO_WET[i]
    return _BANDS_DRY_TO_WET[len(bounds)]  # below every boundary = wettest


def classify_event(text: str) -> str:
    """Coarse event type from the annotation text (watering / tray / contact /
    probe / observation). Annotations only — never derived from the signal."""
    low = (text or "").lower()
    for etype, words in _EVENT_KEYWORDS:
        if any(w in low for w in words):
            return etype
    return "observation"


def _survey_files(docs_dir: str | Path | None) -> list[Path]:
    root = Path(docs_dir) if docs_dir else _DOCS_EXP
    return sorted(root.glob("20260629_sage_*.json"))


def load_segments(docs_dir: str | Path | None = None) -> list[dict]:
    """Every plant segment from the Sage survey sidecars, tagged with its source."""
    out: list[dict] = []
    for f in _survey_files(docs_dir):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for seg in doc.get("plant_segments", []) or []:
            if isinstance(seg, dict) and seg.get("plant_id"):
                out.append({**seg, "_source": f.name})
    return out


def _is_probe_dict(val: object) -> bool:
    return isinstance(val, dict) and any(p in val for p in _PROBES)


def reading_rows(segments: list[dict]) -> list[dict]:
    """One row per (plant, phase, probe). Each segment summarises raw per-probe under
    phase-named keys (`last_raw`, `water_start_to_runoff_last_raw`, `post_water_raw`,
    …); we keep the phase so cross-plant queries stay honest about *when* the raw was
    read. Band is derived (provisional) for absolute raws, never for deltas. Plants
    with no per-probe raw summary (narrative-only) contribute events but no readings."""
    rows: list[dict] = []
    for seg in segments:
        summ = seg.get("selected_log_summary") or {}
        wb = seg.get("water_balance") or {}
        eq = seg.get("evidence_quality")
        eq = eq if isinstance(eq, str) else ""
        contact = "contact" in eq.lower() or "placement" in eq.lower()
        for key, val in summ.items():
            if "raw" not in key.lower() or not _is_probe_dict(val):
                continue
            is_delta = "delta" in key.lower()  # a change, not an absolute level
            for probe in _PROBES:
                raw = val.get(probe)
                if raw is None:
                    continue
                rows.append(
                    {
                        "plant_id": seg.get("plant_id"),
                        "plant": seg.get("plant"),
                        "phase": key,
                        "probe": probe,
                        "raw": raw,
                        "band": None if is_delta else band_for_raw(raw),
                        "band_basis": "derived-provisional",  # un-ratified bounds
                        "is_delta": is_delta,
                        "window_local": summ.get("window_local"),
                        "applied_cups": wb.get("applied_cups"),
                        "runoff_observed": wb.get("runoff_observed"),
                        "evidence_quality": eq,
                        "contact_caveat": contact,
                        "source": seg.get("_source"),
                    }
                )
    return rows


def event_rows(segments: list[dict]) -> list[dict]:
    """One row per (plant, event): the classified, timestamped operator annotation."""
    rows: list[dict] = []
    for seg in segments:
        for ev in seg.get("events") or []:
            text = ev.get("event", "") if isinstance(ev, dict) else str(ev)
            rows.append(
                {
                    "plant_id": seg.get("plant_id"),
                    "time_local": ev.get("time_local")
                    if isinstance(ev, dict)
                    else None,
                    "event_type": classify_event(text),
                    "event_text": text,
                    "source": seg.get("_source"),
                }
            )
    return rows


def build_store(
    docs_dir: str | Path | None = None, out_path: str | Path | None = None
) -> dict:
    """(Re)build the derived DuckDB store from the survey sidecars; returns counts."""
    import duckdb

    out = Path(out_path) if out_path else _STORE
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # derived: always rebuilt fresh, never edited in place
    segments = load_segments(docs_dir)
    readings = reading_rows(segments)
    events = event_rows(segments)

    # Load via read_json_auto (portable across DuckDB versions; a list[dict] -> df
    # path is version-sensitive). The temp json sidecars are cleaned up after.
    rd_json = _dump_rows(readings, out.parent / "_bench_readings.json")
    ev_json = _dump_rows(events, out.parent / "_bench_events.json")
    con = duckdb.connect(str(out))
    con.execute(
        "CREATE TABLE bench_readings AS SELECT * FROM read_json_auto(?)", [rd_json]
    )
    con.execute(
        "CREATE TABLE bench_events AS SELECT * FROM read_json_auto(?)", [ev_json]
    )
    con.execute(
        """
        CREATE VIEW bench_annotated AS
        SELECT r.*,
               (SELECT count(*) FROM bench_events e WHERE e.plant_id = r.plant_id)
                   AS event_count,
               (SELECT string_agg(e.event_type || ': ' || e.event_text, ' | ')
                  FROM bench_events e WHERE e.plant_id = r.plant_id) AS events
        FROM bench_readings r
        """
    )
    n_plants = con.execute(
        "SELECT count(DISTINCT plant_id) FROM bench_readings"
    ).fetchone()[0]
    con.close()
    for tmp in (rd_json, ev_json):  # the json load-sidecars are transient
        Path(tmp).unlink(missing_ok=True)
    return {"plants": n_plants, "readings": len(readings), "events": len(events)}


def _dump_rows(rows: list[dict], path: Path) -> str:
    path.write_text(json.dumps(rows), encoding="utf-8")
    return str(path)


def query(sql: str, out_path: str | Path | None = None):
    """Read-only query against the store; returns a list of dict rows."""
    import duckdb

    out = Path(out_path) if out_path else _STORE
    con = duckdb.connect(str(out), read_only=True)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Event-annotated bench-data view (#380).")
    ap.add_argument("--query", help="run a read-only SQL query and print rows")
    args = ap.parse_args(argv)
    if args.query:
        for row in query(args.query):
            print(row)
        return 0
    summary = build_store()
    print(
        f"built {_STORE}: {summary['plants']} plants, "
        f"{summary['readings']} probe-readings, {summary['events']} events"
    )
    print(
        "honest-data: raw ADC + band are truth (band derived/provisional); "
        "events are annotations, not interpolation."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
