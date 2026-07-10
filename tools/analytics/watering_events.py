#!/usr/bin/env python3
"""Event-annotated DuckDB view over the 2026-07-06/07 watering dose->response captures
(#835, child of #834; the #380 pattern applied to a watering session).

The evidence packet (``docs/experiments/2026-07-07-watering-dose-response/``) is rich
raw + a written report, but not *queryable*. Each per-plant capture is one probe's soil
response to one measured dose, headed with the dose metadata:

    # plant=p02 Pothos (XXL) sensor=s2 ip=192.168.68.87 dose_ml=237.0
    ts_utc,device_seq,raw,band
    2026-07-07T02:05:00+00:00,24263,2954,dry
    ...

A ``-d2`` / ``-d3`` suffix is that plant's second / third dose window. This flattens the
captures into a DuckDB store so the session can be *queried* — the substrate the #822
cycle-range and #25 predictor work reads:

* ``watering_readings`` — one row per (plant, dose, sample): ``ts_utc``, ``raw``, the
  as-logged ``band``, and the dose it belongs to. Joinable with the raw soil corpus on
  ``ts_utc`` + ``device`` (same wall-clock the fleet log stamps).
* ``watering_doses`` — one row per (plant, dose): the annotation — measured ``dose_ml``
  / ``dose_cups``, the probe, the capture window, sample count, and a ``suspect`` flag.
* ``watering_annotated`` — the view: each reading carried alongside its dose annotation,
  so "p03's raw trajectory + the 1.25-cup dose that produced it" is one query.

**Honest-data (ADR-0004):** raw + the as-logged band are the truth; no invented
normalized value. Dose volumes are operator annotations from the capture headers, never
derived from the signal. The **p02 dose-3 window is flagged ``suspect``** (a probe-head
water-contamination fault the maintainer caught — raw swung 661->2840 untouched; see the
packet README) — the rows are kept verbatim (they ARE the evidence of the fault), never
dropped. The store is *derived*: written under gitignored ``reports/``, rebuilt from the
committed captures, never hand-edited.

    python tools/analytics/watering_events.py             # (re)build + a summary
    python tools/analytics/watering_events.py --query "SELECT * FROM watering_doses"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_CAPTURES = _REPO / "docs" / "experiments" / "2026-07-07-watering-dose-response"
_STORE = _REPO / "reports" / "watering_events.duckdb"

# US legal cup in mL — the measure the doses were poured with (a 2-cup kitchen cup).
_ML_PER_CUP = 236.588

# key=value header parse: a value runs until the next ` key=` or EOL, so a spaced
# value ("plant=p02 Pothos (XXL)") is captured whole. Same idea as parse_v1._KV_RE.
_HEADER_KV = re.compile(r"(\w+)=(.*?)(?=\s+\w+=|$)")

# Rows the maintainer flagged unreliable (packet README, 2026-07-08): the p02/s2 probe
# faulted in its dose-3 window (water-contaminated head; raw physically impossible).
# Kept verbatim as evidence, marked suspect so no query trusts them as a response.
_SUSPECT_DOSES = frozenset({("p02", 3)})


def _dose_n(name: str) -> int:
    """Dose number from the filename: base capture = 1, ``-d2`` = 2, ``-d3`` = 3."""
    m = re.search(r"-d(\d+)\.csv$", name)
    return int(m.group(1)) if m else 1


def _cups(ml: float | None) -> float | None:
    return round(ml / _ML_PER_CUP, 2) if ml is not None else None


def capture_files(captures_dir: str | Path | None = None) -> list[Path]:
    """The per-plant dose captures (``pNN-*.csv``), sorted. Excludes the cross-plant
    point-in-time snapshots (``22h-`` / ``24h-`` / ``48h-``), which are a different,
    one-row-per-plant shape — this view is the per-dose response trajectories."""
    root = Path(captures_dir) if captures_dir else _CAPTURES
    return sorted(p for p in root.glob("p*.csv") if re.match(r"p\d", p.name))


def parse_capture(path: str | Path) -> dict:
    """One capture -> ``{plant_id, plant, sensor, ip, dose_ml, dose_n, rows}``. The
    ``#`` header carries the dose annotation; rows are ``(ts_utc, device_seq, raw,
    band)`` with the band as-logged (truth), never re-derived here."""
    path = Path(path)
    header: dict[str, str] = {}
    rows: list[dict] = []
    cols: list[str] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                header.update(
                    {k: v.strip() for k, v in _HEADER_KV.findall(line.lstrip("#"))}
                )
                continue
            fields = next(csv.reader([line]))
            if not cols:
                cols = fields  # the ts_utc,device_seq,raw,band column row
                continue
            rows.append(dict(zip(cols, fields, strict=False)))
    plant_val = header.get("plant", "")
    pid, _, pname = plant_val.partition(" ")
    # the -d2/-d3 capture headers embed the dose marker in the plant name
    # ("Pothos (XXL) d2"); dose_n already carries it, so keep the plant label
    # consistent across a plant's doses.
    pname = re.sub(r"\s+d\d+$", "", pname).strip()
    dose_ml = None
    try:
        dose_ml = float(header["dose_ml"]) if header.get("dose_ml") else None
    except ValueError:
        dose_ml = None
    return {
        "plant_id": pid or None,
        "plant": pname or None,
        "sensor": header.get("sensor"),
        "ip": header.get("ip"),
        "dose_ml": dose_ml,
        "dose_n": _dose_n(path.name),
        "rows": rows,
    }


def _int(s: object) -> int | None:
    try:
        return int(str(s).strip())
    except (TypeError, ValueError):
        return None


def reading_rows(captures: list[dict]) -> list[dict]:
    """One row per (plant, dose, sample). Raw + as-logged band are carried verbatim;
    each row inherits its dose's ``suspect`` flag so a fault can't hide in a join."""
    out: list[dict] = []
    for cap in captures:
        suspect = (cap["plant_id"], cap["dose_n"]) in _SUSPECT_DOSES
        for r in cap["rows"]:
            out.append(
                {
                    "plant_id": cap["plant_id"],
                    "plant": cap["plant"],
                    "probe": cap["sensor"],
                    "dose_n": cap["dose_n"],
                    "ts_utc": r.get("ts_utc"),
                    "device_seq": _int(r.get("device_seq")),
                    "raw": _int(r.get("raw")),
                    "band": r.get("band"),  # as-logged; truth, never re-derived
                    "band_basis": "as-logged",
                    "suspect": suspect,
                }
            )
    return out


def dose_rows(captures: list[dict]) -> list[dict]:
    """One row per (plant, dose): the measured-dose annotation + capture window."""
    out: list[dict] = []
    for cap in captures:
        ts = [r.get("ts_utc") for r in cap["rows"] if r.get("ts_utc")]
        suspect = (cap["plant_id"], cap["dose_n"]) in _SUSPECT_DOSES
        out.append(
            {
                "plant_id": cap["plant_id"],
                "plant": cap["plant"],
                "probe": cap["sensor"],
                "dose_n": cap["dose_n"],
                "dose_ml": cap["dose_ml"],
                "dose_cups": _cups(cap["dose_ml"]),
                "window_start_utc": min(ts) if ts else None,
                "window_end_utc": max(ts) if ts else None,
                "n_samples": len(cap["rows"]),
                "suspect": suspect,
                "suspect_reason": "probe water-contamination fault (README, 2026-07-08)"
                if suspect
                else None,
            }
        )
    return out


def _dump_rows(rows: list[dict], path: Path) -> str:
    path.write_text(json.dumps(rows), encoding="utf-8")
    return str(path)


def build_store(
    captures_dir: str | Path | None = None, out_path: str | Path | None = None
) -> dict:
    """(Re)build the derived DuckDB store from the captures; returns counts."""
    import duckdb

    out = Path(out_path) if out_path else _STORE
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()  # derived: always rebuilt fresh, never edited in place
    captures = [parse_capture(p) for p in capture_files(captures_dir)]
    readings = reading_rows(captures)
    doses = dose_rows(captures)

    # read_json_auto is portable across DuckDB versions (a list[dict]->df path is
    # version-sensitive); the transient json sidecars are cleaned up after.
    rd_json = _dump_rows(readings, out.parent / "_watering_readings.json")
    ds_json = _dump_rows(doses, out.parent / "_watering_doses.json")
    con = duckdb.connect(str(out))
    con.execute(
        "CREATE TABLE watering_readings AS SELECT * FROM read_json_auto(?)", [rd_json]
    )
    con.execute(
        "CREATE TABLE watering_doses AS SELECT * FROM read_json_auto(?)", [ds_json]
    )
    # each reading carried next to its dose annotation (join on plant + dose), so a
    # trajectory query never loses the dose that produced it.
    con.execute(
        """
        CREATE VIEW watering_annotated AS
        SELECT r.plant_id, r.plant, r.probe, r.dose_n, r.ts_utc, r.device_seq,
               r.raw, r.band, r.band_basis, r.suspect,
               d.dose_ml, d.dose_cups, d.window_start_utc, d.window_end_utc,
               d.n_samples, d.suspect_reason
        FROM watering_readings r
        LEFT JOIN watering_doses d
          ON d.plant_id = r.plant_id AND d.dose_n = r.dose_n
        """
    )
    n_plants = con.execute(
        "SELECT count(DISTINCT plant_id) FROM watering_readings"
    ).fetchone()[0]
    con.close()
    for tmp in (rd_json, ds_json):
        Path(tmp).unlink(missing_ok=True)
    return {
        "plants": n_plants,
        "doses": len(doses),
        "readings": len(readings),
        "suspect_doses": sum(1 for d in doses if d["suspect"]),
    }


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
    ap = argparse.ArgumentParser(
        description="Event-annotated watering dose->response view (#835)."
    )
    ap.add_argument("--query", help="run a read-only SQL query and print rows")
    args = ap.parse_args(argv)
    if args.query:
        for row in query(args.query):
            print(row)
        return 0
    s = build_store()
    print(
        f"built {_STORE}: {s['plants']} plants, {s['doses']} doses "
        f"({s['suspect_doses']} suspect), {s['readings']} probe-readings"
    )
    print(
        "honest-data: raw + as-logged band are truth (ADR-0004); doses are measured "
        "annotations; the p02 dose-3 fault window is kept verbatim, flagged suspect."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
